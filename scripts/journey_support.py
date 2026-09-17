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
SEED_REPO = REPO_ROOT / "libre_libros_content"


def _local_output(path: Path) -> Path:
    path = path.resolve()
    if not path.is_relative_to(TEST_PLAN_DIR.resolve()) or path == TEST_PLAN_DIR.resolve():
        raise ValueError("Validation output must be inside test_plan/")
    return path


def snapshot_example_repo(repo_path: Path) -> None:
    subprocess.run(["git", "-C", str(repo_path), "config", "user.name", "Codex Validator"], check=True)
    subprocess.run(["git", "-C", str(repo_path), "config", "user.email", "validator@local.test"], check=True)
    status = subprocess.run(
        ["git", "-C", str(repo_path), "status", "--short"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if not status:
        return
    subprocess.run(["git", "-C", str(repo_path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo_path), "commit", "-m", "Prepare validator snapshot"], check=True)


def build_output_dir(suffix: str) -> Path:
    output_dir = _local_output(TEST_PLAN_DIR / f"{date.today().isoformat()}-{suffix}")
    # Do not delete another run's artifacts.
    if output_dir.exists():
        from uuid import uuid4
        output_dir = output_dir.with_name(f"{output_dir.name}-{uuid4().hex[:8]}")
    output_dir.mkdir(parents=True, exist_ok=False)
    return output_dir


def prepare_example_repo(output_dir: Path) -> Path:
    output_dir = _local_output(output_dir)
    copied_repo = output_dir / "example-repo"
    # Copy public teaching content only, never Git remotes/config/hooks or dotenv.
    shutil.copytree(SEED_REPO / "books", copied_repo / "books", ignore=shutil.ignore_patterns(".git", ".env*"))
    subprocess.run(["git", "init", "-b", "main", str(copied_repo)], check=True)
    snapshot_example_repo(copied_repo)
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
    output_dir = _local_output(output_dir)
    example_repo_path = _local_output(example_repo_path)
    database_path = _local_output(output_dir / db_filename)
    temp_dir = output_dir / "tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    env = {
        key: value for key, value in os.environ.items()
        if not key.startswith(("LIBRE_LIBROS_", "SUPABASE_"))
    }
    env.update(
        {
            # Requires get_settings() to pass this flag as _env_file=None.
            "LIBRE_LIBROS_ENV_FILE": "",
            "LIBRE_LIBROS_DATABASE_URL": f"sqlite:///{database_path}",
            "LIBRE_LIBROS_APP_NAME": "Libre Libros Test",
            "LIBRE_LIBROS_HOST": "127.0.0.1",
            "LIBRE_LIBROS_PORT": "8000",
            "LIBRE_LIBROS_EXTERNAL_AUTH_ONLY": "false",
            "LIBRE_LIBROS_GITHUB_OAUTH_ENABLED": "false",
            "LIBRE_LIBROS_GITLAB_ENABLED": "false",
            "LIBRE_LIBROS_GENERIC_OIDC_ENABLED": "false",
            "LIBRE_LIBROS_BOOTSTRAP_REPOSITORY_PROVIDER": "local",
            "LIBRE_LIBROS_BOOTSTRAP_REPOSITORY_DEFAULT_BRANCH": "main",
            "LIBRE_LIBROS_BOOTSTRAP_REPOSITORY_PUBLIC": "true",
            "LIBRE_LIBROS_SESSION_COOKIE_NAME": "libre_libros_test_session",
            "TMPDIR": str(temp_dir),
            "TMP": str(temp_dir),
            "TEMP": str(temp_dir),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
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
    output_dir = _local_output(output_dir)
    server_log = _local_output(output_dir / server_log_name)
    if env.get("LIBRE_LIBROS_ENV_FILE") != "":
        raise ValueError("Journey server must explicitly disable dotenv")
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
        log_handle.close()
        raise
    return process, log_handle
