"""Run a loopback-only demo without loading owner dotenv or remote credentials."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from scripts.journey_support import build_env, build_output_dir, prepare_example_repo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("El puerto debe estar entre 1024 y 65535")
    output = build_output_dir("local-demo")
    repo = prepare_example_repo(output)
    password = secrets.token_urlsafe(18)
    env = build_env(output, example_repo_path=repo, db_filename="demo.db",
                    admin_email="admin@example.org", admin_password=password,
                    admin_name="Coordinación del piloto", secret_key=secrets.token_hex(32))
    env.update({"LIBRE_LIBROS_INVITATION_ONLY": "true",
                "LIBRE_LIBROS_APP_NAME": "Libre Libros · Demo local",
                "LIBRE_LIBROS_PUBLIC_BASE_URL": f"http://127.0.0.1:{args.port}",
                # Local browsers emit the opaque `Origin: null` sentinel; this
                # demo-only tolerance never ships to production deployments.
                "LIBRE_LIBROS_CSRF_ALLOW_NULL_ORIGIN": "true"})
    credentials = output / "demo-access.txt"
    descriptor = os.open(credentials, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(f"SOLO DEMO LOCAL\nUsuario: admin@example.org\nContraseña: {password}\n")
    print(f"Demo: http://127.0.0.1:{args.port}\nAcceso privado: {credentials}\n"
          "Copia aislada sin remotos. Ctrl+C detiene el servidor. No subir estos datos.", flush=True)
    os.chdir(PROJECT)
    os.execve(sys.executable, [sys.executable, "-m", "uvicorn", "app.main:app",
                              "--host", "127.0.0.1", "--port", str(args.port),
                              "--no-access-log"], env)


if __name__ == "__main__":
    main()
