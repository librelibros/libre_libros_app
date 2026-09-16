"""Hermetic defaults: no owner dotenv, remote providers, or shared app modules."""
from __future__ import annotations

import os
import socket
import sys
from ipaddress import ip_address
import tempfile
from pathlib import Path

import pytest

from scripts.journey_support import TEST_PLAN_DIR, build_env


def pytest_configure(config):
    # Configure this before pytest's tmp_path factory or test-module collection.
    temp_root = TEST_PLAN_DIR / "tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    if config.option.basetemp is None:
        config.option.basetemp = tempfile.mkdtemp(prefix="pytest-", dir=temp_root)
    elif not Path(config.option.basetemp).resolve().is_relative_to(temp_root.resolve()):
        raise pytest.UsageError("--basetemp must be inside test_plan/tmp")
    patch = pytest.MonkeyPatch()
    config.add_cleanup(patch.undo)
    patch.setenv("TMPDIR", str(temp_root))
    patch.setattr(tempfile, "tempdir", str(temp_root))
    for key in list(os.environ):
        if key.startswith(("LIBRE_LIBROS_", "SUPABASE_")):
            patch.delenv(key)
    patch.setenv("LIBRE_LIBROS_ENV_FILE", "")


def _unload_app():
    # Reloading database alone leaves stale engines/sessionmakers in routers and
    # services; reloading models alone duplicates SQLAlchemy table definitions.
    database = sys.modules.get("app.database")
    if database is not None:
        database.engine.dispose()
    config = sys.modules.get("app.config")
    if config is not None:
        config.get_settings.cache_clear()
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            del sys.modules[name]


@pytest.fixture(autouse=True)
def block_external_network(monkeypatch):
    """TestClient uses an in-process transport; only actual loopback is allowed."""
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_getaddrinfo = socket.getaddrinfo

    def check_host(host):
        if host == "localhost":
            return
        try:
            if ip_address(host).is_loopback:
                return
        except ValueError:
            pass
        raise AssertionError("External network access is disabled in tests")

    def connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            check_host(address[0])
        return original_connect(sock, address)

    def connect_ex(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            check_host(address[0])
        return original_connect_ex(sock, address)

    def getaddrinfo(host, *args, **kwargs):
        check_host(host)
        return original_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)


@pytest.fixture(autouse=True)
def isolated_app_environment(tmp_path: Path, monkeypatch):
    _unload_app()
    env = build_env(
        tmp_path,
        example_repo_path=tmp_path / "repo",
        db_filename="test.db",
        admin_email="admin@test.local",
        admin_password="admin12345",
        admin_name="Test Admin",
        secret_key="test-only-not-a-production-secret",
    )
    for key in list(os.environ):
        if key.startswith(("LIBRE_LIBROS_", "SUPABASE_")):
            monkeypatch.delenv(key)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    from app.config import Settings, get_settings

    # Also covers Settings() directly, independently of the launcher env flag.
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()
    try:
        yield
    finally:
        _unload_app()
