"""Hermes --no-agent healthcheck. No credentials, browser or LLM required."""
import json
import signal
import sys
import urllib.error
import urllib.request

URL = "https://libre-libros-app.onrender.com/healthz"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def deadline(signum, frame):
    raise TimeoutError("healthcheck deadline")


def main():
    # Linux Hermes: absolute bound also covers slow streaming and DNS delays.
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(100)
    try:
        request = urllib.request.Request(
            URL, headers={"User-Agent": "LibreLibros-Healthcheck/1.0", "Accept": "application/json"}
        )
        with urllib.request.build_opener(NoRedirect).open(request, timeout=90) as response:
            body = response.read(4097)
            if response.status != 200 or len(body) > 4096:
                raise ValueError("unexpected response")
            if json.loads(body).get("status") != "ok":
                raise ValueError("unexpected health status")
        # Empty stdout: Hermes remains silent. Its job state records success.
        return 0
    except Exception as exc:
        # Do not log remote bodies, headers or exception messages.
        print(f"Libre Libros: healthcheck fallido ({type(exc).__name__}); sin reinicio automático.", file=sys.stderr)
        return 1
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    sys.exit(main())
