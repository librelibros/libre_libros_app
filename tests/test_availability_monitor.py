"""No network, subprocesses, Hermes or application startup."""
import json
import urllib.error
from unittest.mock import Mock

import pytest

from scripts import libre_libros_healthcheck as monitor


@pytest.fixture(autouse=True)
def forbid_real_opener(monkeypatch):
    monkeypatch.setattr(monitor.urllib.request, "build_opener", Mock(side_effect=AssertionError("Network forbidden")))


class Response:
    def __init__(self, body=b'{"status":"ok","db":"ok"}', status=200):
        self.body = body
        self.status = status
        self.read_sizes = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, size):
        self.read_sizes.append(size)
        return self.body[:size]


class Opener:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request.full_url, timeout))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def run(path, second=None):
    return monitor.main(opener=Opener(Response(), second if second is not None else Response()), state_path=path)


def test_success_both_endpoints_bounded_and_persisted(tmp_path, capsys):
    path = tmp_path / "state.json"
    responses = [Response(), Response()]
    opener = Opener(*responses)
    assert monitor.main(opener=opener, state_path=path) == 0
    assert [url for url, _ in opener.calls] == [monitor.BASE_URL + endpoint for endpoint in monitor.ENDPOINTS]
    assert all(0 < timeout <= monitor.ENDPOINT_TIMEOUT for _, timeout in opener.calls)
    assert all(response.read_sizes == [monitor.MAX_BODY + 1] for response in responses)
    state = json.loads(path.read_text())
    assert state["endpoints"] == {"/healthz": "ok", "/healthz/db": "ok"}
    assert state["consecutive_failures"] == 0 and state["alerted"] is False
    assert state["checked_at"].endswith("+00:00")
    assert capsys.readouterr() == ("", "")
    assert [entry for entry in tmp_path.iterdir() if entry.is_file()] == [path]
    assert not list(tmp_path.glob(".healthcheck-*"))
    assert path.stat().st_size < monitor.MAX_STATE


@pytest.mark.parametrize("response,expected", [
    (Response(b'{"status":"ok","db":"error","detail":"PRIVATE"}'), "unhealthy"),
    (Response(b'{"status":"ok"}'), "unhealthy"),
    (Response(b'{"status":"error","db":"ok"}'), "unhealthy"),
    (Response(b'{"status":true,"db":[]}'), "unhealthy"),
    (Response(b'[]'), "invalid_json"),
    (Response(b'null'), "invalid_json"),
    (Response(b'123'), "invalid_json"),
    (Response(b'"PRIVATE"'), "invalid_json"),
    (Response(b'{PRIVATE'), "invalid_json"),
    (Response(b'\xff'), "invalid_json"),
    (Response(b'x' * (monitor.MAX_BODY + 1)), "body_too_large"),
    (Response(b'PRIVATE', 503), "http_error"),
    (TimeoutError("PRIVATE"), "timeout"),
    (urllib.error.URLError(TimeoutError("PRIVATE")), "timeout"),
    (urllib.error.URLError("PRIVATE"), "network_error"),
])
def test_failures_safe_output_no_retries(tmp_path, capsys, response, expected):
    path = tmp_path / "state.json"
    opener = Opener(Response(), response)
    assert monitor.main(opener=opener, state_path=path) == 1
    assert len(opener.calls) == 2
    state = json.loads(path.read_text())
    assert state["endpoints"]["/healthz/db"] == expected
    assert state["consecutive_failures"] == 1
    out, err = capsys.readouterr()
    assert out == "" and err == "Libre Libros: comprobación de disponibilidad fallida.\n"
    assert "PRIVATE" not in path.read_text()


def test_third_failure_only_and_recovery_only_when_alerted(tmp_path, capsys):
    path = tmp_path / "state.json"
    for count in range(1, 6):
        assert run(path, Response(b'{"status":"ok","db":"fail"}')) == 1
        out, err = capsys.readouterr()
        assert bool(out) == (count == 3)
        if out:
            assert "ALERTA" in out
        assert err
        state = json.loads(path.read_text())
        assert state["consecutive_failures"] == count
        assert state["alerted"] == (count >= 3)
    assert run(path) == 0
    out, err = capsys.readouterr()
    assert "RECUPERADO" in out and not err
    assert json.loads(path.read_text())["transition"] == "recovered"
    assert run(path) == 0
    assert capsys.readouterr() == ("", "")
    assert run(path, TimeoutError()) == 1
    capsys.readouterr()
    assert run(path) == 0
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("content", [b'PRIVATE', b'[]', b'null', b'{}', b'x' * 4097,
    b'{"version":1,"consecutive_failures":true,"alerted":false}'])
def test_corrupt_state_not_silently_reset(tmp_path, capsys, content):
    path = tmp_path / "state.json"
    path.write_bytes(content)
    opener = Opener()
    assert monitor.main(opener=opener, state_path=path) == 1
    assert not opener.calls
    assert path.read_bytes() == content
    out, err = capsys.readouterr()
    assert not out and "estado local" in err and "PRIVATE" not in err


def test_environment_override_and_write_failure(tmp_path, monkeypatch, capsys):
    path = tmp_path / "configured.json"
    monkeypatch.setenv(monitor.STATE_ENV, str(path))
    assert monitor.main(opener=Opener(Response(), Response())) == 0
    assert path.exists()
    monkeypatch.setattr(monitor.os, "replace", Mock(side_effect=OSError("PRIVATE")))
    assert run(path) == 1
    out, err = capsys.readouterr()
    assert not out and "estado local" in err and "PRIVATE" not in err
    assert [entry for entry in tmp_path.iterdir() if entry.is_file()] == [path]
    assert not list(tmp_path.glob(".healthcheck-*"))


def test_redirect_rejected_without_retry(tmp_path, capsys):
    handler = monitor.NoRedirect()
    assert handler.redirect_request(None, None, 302, "PRIVATE", {}, "https://external.invalid") is None
    opener = Opener(urllib.error.HTTPError("https://private.invalid", 302, "PRIVATE", {}, None), Response())
    assert monitor.main(opener=opener, state_path=tmp_path / "state.json") == 1
    assert len(opener.calls) == 2
    assert "PRIVATE" not in str(capsys.readouterr())


def test_global_and_endpoint_wall_deadlines_installed(tmp_path, monkeypatch):
    values = []
    original = monitor.signal.setitimer
    def setitimer(which, seconds, interval=0):
        values.append(seconds)
        return original(which, seconds, interval)
    monkeypatch.setattr(monitor.signal, "setitimer", setitimer)
    assert run(tmp_path / "state.json") == 0
    assert values[0] == monitor.GLOBAL_TIMEOUT <= 150
    assert values.count(monitor.ENDPOINT_TIMEOUT) == 2
    assert monitor.signal.getitimer(monitor.signal.ITIMER_REAL)[0] == 0


def test_global_deadline_failure_is_sanitized(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(monitor, "read_state", Mock(side_effect=TimeoutError("PRIVATE")))
    opener = Opener()
    assert monitor.main(opener=opener, state_path=tmp_path / "state.json") == 1
    assert not opener.calls
    out, err = capsys.readouterr()
    assert not out and "plazo global" in err and "PRIVATE" not in err
    assert monitor.signal.getitimer(monitor.signal.ITIMER_REAL)[0] == 0


@pytest.mark.parametrize("key,value", [("alerted", True), ("consecutive_failures", -1),
    ("checked_at", "invalid"), ("endpoints", {"/healthz": "PRIVATE"}), ("transition", "unexpected")])
def test_inconsistent_saved_state_is_not_reset(tmp_path, capsys, key, value):
    path = tmp_path / "state.json"
    assert run(path) == 0
    state = json.loads(path.read_text())
    state[key] = value
    path.write_text(json.dumps(state))
    raw = path.read_bytes()
    assert run(path) == 1
    assert path.read_bytes() == raw
    out, err = capsys.readouterr()
    assert not out and "estado local" in err and "PRIVATE" not in err


def test_slow_body_timeout_does_not_skip_other_endpoint(tmp_path, capsys):
    class Slow(Response):
        def read(self, size):
            monitor.deadline(None, None)
    opener = Opener(Slow(), Response())
    assert monitor.main(opener=opener, state_path=tmp_path / "state.json") == 1
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["endpoints"] == {"/healthz": "timeout", "/healthz/db": "ok"}
    assert len(opener.calls) == 2
    assert capsys.readouterr().out == ""
