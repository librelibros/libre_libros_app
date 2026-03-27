from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from contextlib import suppress
from datetime import date
from pathlib import Path
from typing import TextIO

import httpx


PROJECT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_DIR.parent
TEST_PLAN_DIR = PROJECT_DIR / "test_plan"


def build_output_dir(suffix: str) -> Path:
    output_dir = TEST_PLAN_DIR / f"{date.today().isoformat()}-{suffix}"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def prepare_example_repo(output_dir: Path) -> Path:
    source_repo = REPO_ROOT / "data" / "repo"
    copied_repo = output_dir / "example-repo"
    shutil.copytree(source_repo, copied_repo)
    return copied_repo


def build_env(
    output_dir: Path,
    *,
    example_repo_path: Path,
    db_filename: str,
    admin_email: str,
    admin_password: str,
    admin_name: str,
    secret_key: str,
) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "LIBRE_LIBROS_DATABASE_URL": f"sqlite:///{output_dir / db_filename}",
            "LIBRE_LIBROS_REPOS_ROOT": str(output_dir / "repos"),
            "LIBRE_LIBROS_EXAMPLE_REPO_PATH": str(example_repo_path),
            "LIBRE_LIBROS_INIT_ADMIN_EMAIL": admin_email,
            "LIBRE_LIBROS_INIT_ADMIN_PASSWORD": admin_password,
            "LIBRE_LIBROS_INIT_ADMIN_NAME": admin_name,
            "LIBRE_LIBROS_SECRET_KEY": secret_key,
        }
    )
    return env


def wait_for_server(base_url: str, timeout_seconds: int = 30) -> None:
    deadline = time.time() + timeout_seconds
    last_error = "sin respuesta"
    while time.time() < deadline:
        try:
            response = httpx.get(f"{base_url}/login", timeout=2.0)
            if response.status_code == 200:
                return
            last_error = f"/login devolvio {response.status_code}"
        except httpx.HTTPError as exc:
            last_error = str(exc)
        time.sleep(0.5)
    raise RuntimeError(f"La app no estuvo disponible en {base_url}: {last_error}")


def launch_server(
    *,
    base_url: str,
    output_dir: Path,
    env: dict[str, str],
    server_log_name: str = "server.log",
    workers: int = 1,
) -> tuple[subprocess.Popen[str], TextIO]:
    server_log = output_dir / server_log_name
    log_handle = server_log.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            base_url.rsplit(":", 1)[-1],
            "--workers",
            str(workers),
        ],
        cwd=str(PROJECT_DIR),
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_for_server(base_url)
    except Exception:
        with suppress(Exception):
            process.terminate()
        with suppress(Exception):
            process.wait(timeout=5)
        raise
    return process, log_handle
