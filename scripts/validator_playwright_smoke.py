from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TextIO

import httpx

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import Page, expect, sync_playwright
except ImportError as exc:  # pragma: no cover - runtime guard for missing optional dep
    raise SystemExit(
        "Playwright no esta instalado. Ejecuta `python3 -m pip install -r requirements-validator.txt` "
        "y luego `python3 -m playwright install chromium`."
    ) from exc


PROJECT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_DIR.parent
TEST_PLAN_DIR = PROJECT_DIR / "test_plan"
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_ADMIN_EMAIL = "admin@validator.local"
DEFAULT_ADMIN_PASSWORD = "admin12345"


@dataclass
class Observation:
    step: str
    result: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ejecuta un smoke E2E con Playwright y guarda evidencia en test_plan.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="URL base de la app cuando se usa --reuse-server.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directorio de salida para la evidencia. Por defecto usa test_plan/<fecha>-validator-playwright.",
    )
    parser.add_argument(
        "--reuse-server",
        action="store_true",
        help="Reutiliza una instancia ya arrancada en --base-url en vez de lanzar uvicorn.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Lanza Chromium con interfaz visible.",
    )
    return parser.parse_args()


def build_output_dir(provided: Path | None) -> Path:
    if provided:
        output_dir = provided
    else:
        output_dir = TEST_PLAN_DIR / f"{date.today().isoformat()}-validator-playwright"

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def build_env(output_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    example_repo = REPO_ROOT / "data" / "repo"
    env.update(
        {
            "LIBRE_LIBROS_DATABASE_URL": f"sqlite:///{output_dir / 'validator.db'}",
            "LIBRE_LIBROS_REPOS_ROOT": str(output_dir / "repos"),
            "LIBRE_LIBROS_EXAMPLE_REPO_PATH": str(example_repo),
            "LIBRE_LIBROS_INIT_ADMIN_EMAIL": DEFAULT_ADMIN_EMAIL,
            "LIBRE_LIBROS_INIT_ADMIN_PASSWORD": DEFAULT_ADMIN_PASSWORD,
            "LIBRE_LIBROS_INIT_ADMIN_NAME": "Validator Admin",
            "LIBRE_LIBROS_SECRET_KEY": "validator-secret-key",
        }
    )
    return env


def wait_for_server(base_url: str, timeout_seconds: int = 30) -> None:
    deadline = time.time() + timeout_seconds
    errors: list[str] = []

    while time.time() < deadline:
        try:
            response = httpx.get(f"{base_url}/login", timeout=2.0)
            if response.status_code == 200:
                return
            errors.append(f"/login devolvio {response.status_code}")
        except httpx.HTTPError as exc:
            errors.append(str(exc))
        time.sleep(0.5)

    last_error = errors[-1] if errors else "sin respuesta"
    raise RuntimeError(f"La app no estuvo disponible en {base_url} tras esperar {timeout_seconds}s: {last_error}")


def launch_server(base_url: str, output_dir: Path) -> tuple[subprocess.Popen[str], Path, TextIO]:
    server_log = output_dir / "server.log"
    env = build_env(output_dir)
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
    return process, server_log, log_handle


def screenshot(page: Page, output_dir: Path, name: str) -> None:
    page.screenshot(path=str(output_dir / f"{name}.png"), full_page=True)


def run_browser_flow(base_url: str, output_dir: Path, headed: bool) -> list[Observation]:
    observations: list[Observation] = []
    browser_errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        page.on("console", lambda msg: browser_errors.append(f"[console:{msg.type}] {msg.text}") if msg.type == "error" else None)
        page.on("pageerror", lambda exc: browser_errors.append(f"[pageerror] {exc}"))

        page.goto(f"{base_url}/login", wait_until="networkidle")
        expect(page.get_by_role("heading", name="Acceder a Libre Libros")).to_be_visible()
        screenshot(page, output_dir, "01-login")
        observations.append(
            Observation(
                step="Abrir login",
                result="La pantalla de acceso carga con formulario local y estilos aplicados.",
            )
        )

        page.get_by_label("Correo").fill(DEFAULT_ADMIN_EMAIL)
        page.get_by_label("Contraseña").fill(DEFAULT_ADMIN_PASSWORD)
        page.get_by_role("button", name="Entrar").click()
        page.wait_for_url(f"{base_url}/")
        expect(page.get_by_role("heading", name="Libros por curso y materia")).to_be_visible()
        screenshot(page, output_dir, "02-dashboard")
        observations.append(
            Observation(
                step="Iniciar sesion",
                result="El admin entra correctamente y ve el panel con el catalogo inicial importado.",
            )
        )

        page.goto(f"{base_url}/books", wait_until="networkidle")
        expect(page.get_by_role("heading", name="Libros disponibles")).to_be_visible()
        screenshot(page, output_dir, "03-books-list")
        cards = page.locator("a.card.book-card")
        card_count = cards.count()
        observations.append(
            Observation(
                step="Abrir listado",
                result=f"El catalogo muestra {card_count} libros visibles antes de filtrar.",
            )
        )

        page.get_by_label("Curso").select_option("Primaria")
        page.get_by_label("Materia").select_option("Lengua")
        page.get_by_role("button", name="Filtrar").click()
        expect(page.get_by_role("heading", name="Libros disponibles")).to_be_visible()
        filtered_cards = page.locator("a.card.book-card")
        expect(filtered_cards.first).to_be_visible()
        screenshot(page, output_dir, "04-books-filtered")
        observations.append(
            Observation(
                step="Aplicar filtros",
                result=f"El filtro Primaria/Lengua devuelve {filtered_cards.count()} resultados y mantiene la pagina estable.",
            )
        )

        first_book = filtered_cards.first
        book_title = first_book.locator("h3").inner_text()
        first_book.click()
        page.wait_for_load_state("networkidle")
        current_book_url = page.url.split("?")[0]
        expect(page.locator(".document-index")).to_be_visible()
        expect(page.locator("[data-book-page].is-active article.markdown-body")).to_be_visible()
        expect(page.locator("img").first).to_be_visible()
        screenshot(page, output_dir, "05-book-detail")
        observations.append(
            Observation(
                step="Abrir detalle",
                result=f"El detalle de '{book_title}' renderiza Markdown, indice lateral, paginacion e imagenes visibles.",
            )
        )

        page.get_by_label("Comentario").fill("Comentario de smoke validator desde Playwright.")
        page.get_by_role("button", name="Añadir comentario").click()
        page.wait_for_load_state("networkidle")
        expect(page.get_by_text("Comentario de smoke validator desde Playwright.")).to_be_visible()
        screenshot(page, output_dir, "06-book-comment")
        observations.append(
            Observation(
                step="Enviar comentario",
                result="El comentario se guarda y aparece en la seccion de detalle pedagogico.",
            )
        )

        export_response = page.context.request.get(f"{current_book_url}/export/pdf?branch=main")
        if not export_response.ok:
            raise PlaywrightError(f"Exportacion PDF fallo con estado {export_response.status}")
        pdf_path = output_dir / "book-export.pdf"
        pdf_path.write_bytes(export_response.body())
        observations.append(
            Observation(
                step="Exportar PDF",
                result=f"La exportacion responde {export_response.status} y se guarda en {pdf_path.name}.",
            )
        )

        page.get_by_role("link", name="Editar").click()
        page.wait_for_load_state("networkidle")
        expect(page.get_by_text("Usa <!-- pagebreak --> para forzar un cambio de pagina.")).to_be_visible()
        expect(page.locator("[data-editor-preview] .document-index")).to_be_visible()
        expect(page.locator("[data-editor-preview] img").first).to_be_visible()
        screenshot(page, output_dir, "07-book-editor")
        observations.append(
            Observation(
                step="Abrir editor",
                result="El editor muestra la vista previa estructurada con indice, paginacion e imagenes del libro.",
            )
        )

        page.goto(f"{base_url}/admin", wait_until="networkidle")
        expect(page.get_by_role("heading", name="Alta simple")).to_be_visible()
        expect(page.get_by_role("heading", name="Git local o GitHub")).to_be_visible()
        screenshot(page, output_dir, "08-admin")
        observations.append(
            Observation(
                step="Abrir administracion",
                result="La pantalla admin carga formularios de usuarios, organizaciones y repositorios.",
            )
        )

        page.get_by_role("link", name="Cerrar sesión").click()
        page.wait_for_url(f"{base_url}/login")
        expect(page.get_by_role("heading", name="Acceder a Libre Libros")).to_be_visible()
        screenshot(page, output_dir, "09-logout")
        observations.append(
            Observation(
                step="Cerrar sesion",
                result="La sesion finaliza y la app vuelve al formulario de acceso.",
            )
        )

        browser.close()

    if browser_errors:
        browser_log = output_dir / "browser-errors.log"
        browser_log.write_text("\n".join(browser_errors) + "\n", encoding="utf-8")
        observations.append(
            Observation(
                step="Revision de consola",
                result=f"Se registraron {len(browser_errors)} errores de navegador en {browser_log.name}.",
            )
        )
    else:
        observations.append(
            Observation(
                step="Revision de consola",
                result="No se detectaron errores de consola ni excepciones de pagina durante el smoke.",
            )
        )

    return observations


def write_run_log(output_dir: Path, base_url: str, observations: list[Observation], reused_server: bool) -> None:
    run_log = output_dir / "run-log.md"
    lines = [
        "# Validator Playwright Smoke",
        "",
        f"- Fecha: {date.today().isoformat()}",
        f"- Base URL: `{base_url}`",
        f"- Servidor reutilizado: `{'si' if reused_server else 'no'}`",
        f"- Usuario de prueba: `{DEFAULT_ADMIN_EMAIL}`",
        "",
        "## Pasos y resultados",
        "",
    ]
    for index, item in enumerate(observations, start=1):
        lines.append(f"{index}. **{item.step}**: {item.result}")
    evidence = [
        "",
        "## Evidencia generada",
        "",
        "- `01-login.png`",
        "- `02-dashboard.png`",
        "- `03-books-list.png`",
        "- `04-books-filtered.png`",
        "- `05-book-detail.png`",
        "- `06-book-comment.png`",
        "- `07-book-editor.png`",
        "- `08-admin.png`",
        "- `09-logout.png`",
        "- `book-export.pdf`",
    ]
    if (output_dir / "browser-errors.log").exists():
        evidence.append("- `browser-errors.log`")
    if not reused_server:
        evidence.append("- `server.log`")
    lines.extend(evidence)
    run_log.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(output_dir: Path, observations: list[Observation], reused_server: bool) -> None:
    browser_log = output_dir / "browser-errors.log"
    verdict = "APPROVED" if not browser_log.exists() else "CHANGES_REQUESTED"
    report = output_dir / "validation-report.md"
    lines = [
        "# Validation Report",
        "",
        f"- Date: {date.today().isoformat()}",
        f"- Verdict: {verdict}",
        f"- Server reused: {'yes' if reused_server else 'no'}",
        "",
        "## Covered user histories",
        "",
    ]
    for index, item in enumerate(observations, start=1):
        lines.append(f"{index}. **{item.step}**: {item.result}")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- Run log: `{(output_dir / 'run-log.md').name}`",
            "- Screenshots: `01-login.png` to `09-logout.png`",
            "- PDF export: `book-export.pdf`",
        ]
    )
    if browser_log.exists():
        lines.append("- Browser errors: `browser-errors.log`")
    if not reused_server:
        lines.append("- Server log: `server.log`")
    if verdict == "APPROVED":
        lines.extend(
            [
                "",
                "## Summary",
                "",
                "All smoke scenarios passed and no browser-side errors were detected.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "## Summary",
                "",
                "The smoke scenarios completed but browser-side errors were detected. Review `browser-errors.log` and iterate before approval.",
            ]
        )
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(args: argparse.Namespace) -> int:
    output_dir = build_output_dir(args.output_dir)
    server_process: subprocess.Popen[str] | None = None
    log_handle: TextIO | None = None

    try:
        if args.reuse_server:
            wait_for_server(args.base_url)
        else:
            server_process, _, log_handle = launch_server(args.base_url, output_dir)

        observations = run_browser_flow(args.base_url, output_dir, args.headed)
        write_run_log(output_dir, args.base_url, observations, args.reuse_server)
        write_report(output_dir, observations, args.reuse_server)
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
    args = parse_args()
    raise SystemExit(main(args))
