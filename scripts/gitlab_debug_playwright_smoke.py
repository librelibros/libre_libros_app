from __future__ import annotations

import argparse
import shutil
from contextlib import suppress
from dataclasses import dataclass
from datetime import date
from pathlib import Path

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import Page, expect, sync_playwright
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Playwright no esta instalado. Ejecuta `python3 -m pip install -r requirements-validator.txt` "
        "y luego `python3 -m playwright install chromium`."
    ) from exc


PROJECT_DIR = Path(__file__).resolve().parents[1]
TEST_PLAN_DIR = PROJECT_DIR / "test_plan"
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_ADMIN_EMAIL = "admin@example.com"
DEFAULT_ADMIN_PASSWORD = "admin12345"


@dataclass
class Observation:
    step: str
    result: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valida el flujo GitLab debug de Libre Libros.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--headed", action="store_true")
    return parser.parse_args()


def build_output_dir() -> Path:
    output_dir = TEST_PLAN_DIR / f"{date.today().isoformat()}-gitlab-debug"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def screenshot(page: Page, output_dir: Path, name: str, *, full_page: bool = True) -> str:
    filename = f"{name}.png"
    page.screenshot(path=str(output_dir / filename), full_page=full_page)
    return filename


def click_if_visible(page: Page, selectors: list[str]) -> bool:
    for selector in selectors:
        locator = page.locator(selector).first
        with suppress(PlaywrightError):
            if locator.is_visible(timeout=1000):
                locator.click()
                return True
    return False


def run_flow(base_url: str, output_dir: Path, headed: bool) -> list[Observation]:
    observations: list[Observation] = []
    browser_errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1366, "height": 900})
        page.on("console", lambda msg: browser_errors.append(f"[console:{msg.type}] {msg.text}") if msg.type == "error" else None)
        page.on("pageerror", lambda exc: browser_errors.append(f"[pageerror] {exc}"))

        page.goto(f"{base_url}/login", wait_until="networkidle")
        expect(page.get_by_role("heading", name="Acceder a Libre Libros")).to_be_visible()
        expect(page.get_by_text("El acceso local está desactivado.")).to_be_visible()
        expect(page.get_by_role("link", name="Entrar con GitLab Debug")).to_be_visible()
        screenshot(page, output_dir, "01-login")
        observations.append(Observation("Pantalla de acceso", "La app arranca con login externo y boton GitLab visible."))

        page.get_by_role("link", name="Entrar con GitLab Debug").click()
        page.wait_for_url(lambda url: "8081" in url or "/users/sign_in" in url)
        login_input = page.locator("input[name='user[login]']").first
        password_input = page.locator("input[name='user[password]']").first
        expect(login_input).to_be_visible()
        expect(password_input).to_be_visible()
        login_input.fill(DEFAULT_ADMIN_EMAIL)
        password_input.fill(DEFAULT_ADMIN_PASSWORD)
        screenshot(page, output_dir, "02-gitlab-login")
        page.locator("button[type='submit']").first.click()

        page.wait_for_load_state("networkidle")
        click_if_visible(
            page,
            [
                "button:has-text('Authorize')",
                "button:has-text('Authorize application')",
                "button:has-text('Autorizar')",
                "input[type='submit'][value='Authorize']",
            ],
        )

        page.wait_for_url(lambda url: url.startswith(base_url), timeout=60000)
        expect(page.get_by_role("heading", name="Libros por curso y materia")).to_be_visible()
        screenshot(page, output_dir, "03-dashboard")
        observations.append(Observation("OAuth GitLab", "El login en GitLab devuelve la sesion a Libre Libros correctamente."))

        page.goto(f"{base_url}/books", wait_until="networkidle")
        expect(page.get_by_text("Lengua Primaria")).to_be_visible()
        expect(page.get_by_text("Matematicas Infantil")).to_be_visible()
        screenshot(page, output_dir, "04-books")
        observations.append(Observation("Catalogo GitLab", "La app carga el catalogo base desde el repositorio GitLab bootstrap."))

        page.get_by_role("link", name="Cerrar sesión").click()
        page.wait_for_url(f"{base_url}/login")
        expect(page.get_by_role("link", name="Entrar con GitLab Debug")).to_be_visible()
        screenshot(page, output_dir, "05-logout")
        observations.append(Observation("Cierre de sesion", "La sesion OAuth se cierra y la app vuelve al login externo."))

        browser.close()

    if browser_errors:
        (output_dir / "browser-errors.log").write_text("\n".join(browser_errors) + "\n", encoding="utf-8")
    return observations


def write_reports(output_dir: Path, base_url: str, observations: list[Observation]) -> None:
    run_log = output_dir / "run-log.md"
    report = output_dir / "validation-report.md"

    run_lines = [
        "# GitLab Debug Smoke",
        "",
        f"- Fecha: {date.today().isoformat()}",
        f"- Base URL: `{base_url}`",
        f"- Usuario GitLab: `{DEFAULT_ADMIN_EMAIL}`",
        "",
        "## Pasos",
        "",
    ]
    for index, item in enumerate(observations, start=1):
        run_lines.append(f"{index}. **{item.step}**: {item.result}")
    if (output_dir / "browser-errors.log").exists():
        run_lines.extend(["", "## Incidencias", "", "- Revisar `browser-errors.log`."])
    run_log.write_text("\n".join(run_lines) + "\n", encoding="utf-8")

    verdict = "APPROVED" if not (output_dir / "browser-errors.log").exists() else "CHANGES_REQUESTED"
    report_lines = [
        "# GitLab Debug Validation",
        "",
        f"- Date: {date.today().isoformat()}",
        f"- Verdict: {verdict}",
        "",
        "## Artifacts",
        "",
        "- `01-login.png`",
        "- `02-gitlab-login.png`",
        "- `03-dashboard.png`",
        "- `04-books.png`",
        "- `05-logout.png`",
        "- `run-log.md`",
    ]
    if (output_dir / "browser-errors.log").exists():
        report_lines.append("- `browser-errors.log`")
    report.write_text("\n".join(report_lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output_dir = build_output_dir()

    observations = run_flow(args.base_url, output_dir, args.headed)
    write_reports(output_dir, args.base_url, observations)
    print(f"Evidencia guardada en {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
