"""Exercise Uvicorn's import and ASGI lifespan in an isolated child process."""
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("valid_key", [False, True])
def test_production_asgi_startup(tmp_path, valid_key):
    project = Path(__file__).resolve().parents[1]
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("LIBRE_LIBROS_", "SUPABASE_"))}
    env.update({
        "LIBRE_LIBROS_ENV_FILE": "",
        "LIBRE_LIBROS_ENVIRONMENT": "production",
        "LIBRE_LIBROS_DATABASE_URL": f"sqlite:///{tmp_path / 'startup.db'}",
        "LIBRE_LIBROS_REPOS_ROOT": str(tmp_path / "repos"),
    })
    if valid_key:
        env["LIBRE_LIBROS_SECRET_KEY"] = "isolated-startup-only-not-a-real-production-secret"
    code = """
import asyncio
import uvicorn
from uvicorn.lifespan.on import LifespanOn
config = uvicorn.Config('app.main:app', lifespan='on', log_level='warning')
config.load()
lifespan = LifespanOn(config)
async def check():
    await lifespan.startup()
    assert not lifespan.should_exit, 'ASGI startup failed'
    await lifespan.shutdown()
    assert not lifespan.shutdown_failed
asyncio.run(check())
print('ASGI_STARTUP_SHUTDOWN_OK')
"""
    result = subprocess.run([sys.executable, "-c", code], cwd=project, env=env,
                            capture_output=True, text=True, timeout=40)
    if valid_key:
        assert result.returncode == 0, result.stderr
        assert "ASGI_STARTUP_SHUTDOWN_OK" in result.stdout
    else:
        assert result.returncode != 0
        assert "LIBRE_LIBROS_SECRET_KEY" in result.stderr
        assert "NameError" not in result.stderr
        assert not (tmp_path / "startup.db").exists()
