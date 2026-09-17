"""Monitor for a Hermes --no-agent script job; no credentials or LLM needed."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
import urllib.error
import urllib.request

BASE_URL = "https://libre-libros-app.onrender.com"
ENDPOINTS = ("/healthz", "/healthz/db")
GLOBAL_TIMEOUT = 145  # Below the job's 150-second budget, including state IO.
ENDPOINT_TIMEOUT = 60
MAX_BODY = 4096
MAX_STATE = 4096
MAX_FAILURES = 1_000_000
STATE_ENV = "LIBRE_LIBROS_HEALTHCHECK_STATE_PATH"
STATES = {"ok", "http_error", "timeout", "network_error", "body_too_large", "invalid_json", "unhealthy"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class StateError(Exception):
    pass


def deadline(signum, frame):
    raise TimeoutError()


@contextmanager
def bounded(seconds):
    """Linux/main-thread wall clock bound, including DNS and slow streams."""
    handler = signal.getsignal(signal.SIGALRM)
    previous, interval = signal.getitimer(signal.ITIMER_REAL)
    started = time.monotonic()
    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, min(seconds, previous) if previous else seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, handler)
        if previous:
            signal.setitimer(signal.ITIMER_REAL, max(0.001, previous - (time.monotonic() - started)), interval)


def probe(opener, endpoint, remaining):
    if remaining <= 0:
        return "timeout"
    timeout = min(ENDPOINT_TIMEOUT, remaining)
    request = urllib.request.Request(
        BASE_URL + endpoint,
        headers={"User-Agent": "LibreLibros-Healthcheck/2.0", "Accept": "application/json"},
    )
    try:
        with bounded(timeout):
            with opener.open(request, timeout=timeout) as response:
                if response.status != 200:
                    return "http_error"
                body = response.read(MAX_BODY + 1)
                if len(body) > MAX_BODY:
                    return "body_too_large"
                try:
                    payload = json.loads(body)
                except (ValueError, UnicodeError, RecursionError):
                    return "invalid_json"
                if not isinstance(payload, dict):
                    return "invalid_json"
                if payload.get("status") != "ok":
                    return "unhealthy"
                if endpoint == "/healthz/db" and payload.get("db") != "ok":
                    return "unhealthy"
                return "ok"
    except TimeoutError:
        return "timeout"
    except urllib.error.HTTPError:
        return "http_error"  # Includes rejected redirects. Never print reason/body.
    except urllib.error.URLError as exc:
        return "timeout" if isinstance(exc.reason, TimeoutError) else "network_error"
    except Exception:
        return "network_error"


def read_state(path):
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_STATE + 1)
    except FileNotFoundError:
        return {"consecutive_failures": 0, "alerted": False}
    except OSError:
        raise StateError() from None
    try:
        if len(raw) > MAX_STATE:
            raise ValueError()
        state = json.loads(raw)
        if not isinstance(state, dict) or state.get("version") != 1:
            raise ValueError()
        count = state["consecutive_failures"]
        alerted = state["alerted"]
        if type(count) is not int or not 0 <= count <= MAX_FAILURES or type(alerted) is not bool:
            raise ValueError()
        if alerted != (count >= 3):
            raise ValueError()
        endpoints = state["endpoints"]
        if not isinstance(endpoints, dict) or set(endpoints) != set(ENDPOINTS):
            raise ValueError()
        if any(type(value) is not str or value not in STATES for value in endpoints.values()):
            raise ValueError()
        if (count == 0) != all(value == "ok" for value in endpoints.values()):
            raise ValueError()
        if state["transition"] not in (None, "alert", "recovered"):
            raise ValueError()
        if state["transition"] == "alert" and count != 3:
            raise ValueError()
        if state["transition"] == "recovered" and count != 0:
            raise ValueError()
        date = datetime.fromisoformat(state["checked_at"])
        if date.tzinfo is None:
            raise ValueError()
        return state
    except (ValueError, TypeError, KeyError, RecursionError):
        raise StateError() from None


def write_state(path, state):
    """Only one retained JSON; temporary sibling is atomically replaced/removed."""
    temporary = None
    try:
        payload = json.dumps(state, ensure_ascii=True, sort_keys=True) + "\n"
        if len(payload.encode()) > MAX_STATE:
            raise StateError()
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".healthcheck-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError:
        raise StateError() from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(*, opener=None, state_path=None):
    try:
        with bounded(GLOBAL_TIMEOUT):
            expires = time.monotonic() + GLOBAL_TIMEOUT
            path = Path(state_path) if state_path is not None else Path(
                os.environ.get(STATE_ENV, str(Path(__file__).with_suffix(".state.json")))
            )
            previous = read_state(path)
            if opener is None:
                opener = urllib.request.build_opener(NoRedirect())
            endpoints = {endpoint: probe(opener, endpoint, expires - time.monotonic()) for endpoint in ENDPOINTS}
            failed = any(value != "ok" for value in endpoints.values())
            count = min(previous["consecutive_failures"] + 1, MAX_FAILURES) if failed else 0
            transition = None
            if failed and count == 3 and not previous["alerted"]:
                transition = "alert"
            elif not failed and previous["alerted"]:
                transition = "recovered"
            state = {
                "version": 1, "checked_at": datetime.now(timezone.utc).isoformat(),
                "endpoints": endpoints, "consecutive_failures": count,
                "alerted": count >= 3, "transition": transition,
            }
            write_state(path, state)
            if failed:
                print("Libre Libros: comprobación de disponibilidad fallida.", file=sys.stderr)
            if transition == "alert":
                print("Libre Libros: ALERTA, tres comprobaciones consecutivas fallidas. Revisar disponibilidad; sin reinicio automático.")
            elif transition == "recovered":
                print("Libre Libros: RECUPERADO, ambos endpoints de salud responden correctamente.")
            return 1 if failed else 0
    except StateError:
        print("Libre Libros: estado local inválido o no accesible; revisión manual necesaria.", file=sys.stderr)
    except TimeoutError:
        print("Libre Libros: plazo global de comprobación agotado.", file=sys.stderr)
    except Exception:
        print("Libre Libros: error interno del monitor.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
