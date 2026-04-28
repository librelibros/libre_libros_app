from __future__ import annotations

import argparse
import re
from contextlib import suppress
from dataclasses import dataclass
from datetime import date
from pathlib import Path

try:
    from playwright.sync_api import Page, expect, sync_playwright
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Playwright no esta instalado. Ejecuta `python3 -m pip install -r requirements-validator.txt` "
        "y luego `python3 -m playwright install chromium`."
    ) from exc

from journey_support import build_env, build_output_dir, launch_server, prepare_example_repo

DEFAULT_BASE_URL = "http://127.0.0.1:8013"


@dataclass
class Observation:
    step: str
    result: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valida el acceso y alta basados en GitHub.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--headed", action="store_true")
    return parser.parse_args()


def screenshot(page: Page, output_dir: Path, name: str) -> None:
    page.screenshot(path=str(output_dir / f"{name}.png"), full_page=True)


def run_flow(base_url: str, output_dir: Path, headed: bool) -> list[Observation]:
    observations: list[Observation] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1366, "height": 900})

        page.goto(f"{base_url}/login", wait_until="networkidle")
        expect(page.get_by_role("heading", name="Acceder a Libre Libros")).to_be_visible()
        expect(page.get_by_role("link", name="Entrar o crear cuenta con GitHub")).to_be_visible()
        expect(page.get_by_text("Libre Libros usa cuentas de GitHub")).to_be_visible()
        screenshot(page, output_dir, "01-login-github")
        observations.append(
            Observation(
                "Pantalla de acceso",
                "La pantalla de login presenta GitHub como mecanismo principal de entrada y alta.",
            )
        )

        with page.expect_navigation(url=re.compile(r"^https://github\.com/login")):
            page.get_by_role("link", name="Entrar o crear cuenta con GitHub").click()
        expect(page).to_have_url(re.compile(r"^https://github\.com/login"))
        expect(page).to_have_url(re.compile(r"client_id=validator-client-id"))
        screenshot(page, output_dir, "02-github-authorize")
        observations.append(
            Observation(
                "Redireccion de acceso",
                "El boton principal redirige al endpoint de autorizacion de GitHub.",
            )
        )

        page.goto(f"{base_url}/register", wait_until="load")
        expect(page).to_have_url(re.compile(r"^https://github\.com/login"))
        expect(page).to_have_url(re.compile(r"client_id=validator-client-id"))
        screenshot(page, output_dir, "03-register-redirect")
        observations.append(
            Observation(
                "Redireccion de alta",
                "La ruta /register ya no muestra un alta local y redirige directamente a GitHub.",
            )
        )

        browser.close()

    return observations


def write_reports(output_dir: Path, base_url: str, observations: list[Observation]) -> None:
    run_log = output_dir / "run-log.md"
    report = output_dir / "github-auth-report.md"

    run_lines = [
        "# GitHub Auth Redirect Smoke",
        "",
        f"- Fecha: {date.today().isoformat()}",
        f"- Base URL: `{base_url}`",
        "",
        "## Pasos y resultados",
        "",
    ]
    for index, observation in enumerate(observations, start=1):
        run_lines.append(f"{index}. **{observation.step}**: {observation.result}")
    run_log.write_text("\n".join(run_lines) + "\n", encoding="utf-8")

    report_lines = [
        "# GitHub Auth Redirect Report",
        "",
        f"- Date: {date.today().isoformat()}",
        "- Verdict: APPROVED",
        "",
        "## Summary",
        "",
        "The login page advertises GitHub as the primary sign-in path, and both entry and registration redirect to GitHub authorization.",
        "",
        "## Artifacts",
        "",
        "- `01-login-github.png`",
        "- `02-github-authorize.png`",
        "- `03-register-redirect.png`",
        "- `run-log.md`",
        "- `server.log`",
    ]
    report.write_text("\n".join(report_lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output_dir = build_output_dir("github-auth-smoke")
    server_process = None
    log_handle = None

    try:
        example_repo_path = prepare_example_repo(output_dir)
        env = build_env(
            output_dir,
            example_repo_path=example_repo_path,
            db_filename="github-auth.db",
            admin_email="admin@github-auth.local",
            admin_password="admin12345",
            admin_name="GitHub Auth Admin",
            secret_key="github-auth-secret",
        )
        env.update(
            {
                "LIBRE_LIBROS_EXTERNAL_AUTH_ONLY": "true",
                "LIBRE_LIBROS_GITHUB_OAUTH_ENABLED": "true",
                "LIBRE_LIBROS_GITHUB_OAUTH_CLIENT_ID": "validator-client-id",
                "LIBRE_LIBROS_GITHUB_OAUTH_CLIENT_SECRET": "validator-client-secret",
                "LIBRE_LIBROS_GITHUB_OAUTH_NAME": "GitHub",
            }
        )
        server_process, log_handle = launch_server(
            base_url=args.base_url,
            output_dir=output_dir,
            env=env,
        )
        observations = run_flow(args.base_url, output_dir, args.headed)
        write_reports(output_dir, args.base_url, observations)
    finally:
        if server_process is not None:
            with suppress(Exception):
                server_process.terminate()
            with suppress(Exception):
                server_process.wait(timeout=10)
        if log_handle is not None:
            with suppress(Exception):
                log_handle.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
