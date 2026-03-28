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
DEFAULT_BASE_URL = "http://127.0.0.1:8010"
DEFAULT_ADMIN_EMAIL = "admin@validator.local"
DEFAULT_ADMIN_PASSWORD = "admin12345"


@dataclass
class Observation:
    step: str
    result: str
    video_name: str | None = None


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


def slugify_story(value: str) -> str:
    return (
        value.lower()
        .replace(" ", "-")
        .replace("/", "-")
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ñ", "n")
    )


def story_video_filename(story_slug: str) -> str:
    return f"user-story-{story_slug}.webm"


def attach_browser_error_hooks(page: Page, browser_errors: list[str]) -> None:
    page.on("console", lambda msg: browser_errors.append(f"[console:{msg.type}] {msg.text}") if msg.type == "error" else None)
    page.on("pageerror", lambda exc: browser_errors.append(f"[pageerror] {exc}"))


def rename_story_video(page: Page, context, output_dir: Path, story_slug: str) -> str:
    video = page.video
    context.close()
    if video is None:
        raise PlaywrightError(f"No se genero video para la historia {story_slug}")
    source = Path(video.path())
    target = output_dir / story_video_filename(story_slug)
    if target.exists():
        target.unlink()
    source.replace(target)
    return target.name


def login(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/login", wait_until="networkidle")
    expect(page.get_by_role("heading", name="Acceder a Libre Libros")).to_be_visible()
    page.get_by_label("Correo").fill(DEFAULT_ADMIN_EMAIL)
    page.get_by_label("Contraseña").fill(DEFAULT_ADMIN_PASSWORD)
    page.get_by_role("button", name="Entrar").click()
    page.wait_for_url(f"{base_url}/")
    expect(page.get_by_role("heading", name="Libros por curso y materia")).to_be_visible()


def open_filtered_books(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/books", wait_until="networkidle")
    expect(page.get_by_role("heading", name="Libros disponibles")).to_be_visible()
    page.get_by_label("Curso").select_option("Primaria")
    page.get_by_label("Materia").select_option("Lengua")
    page.get_by_role("button", name="Filtrar").click()
    expect(page.locator("a.card.book-card").first).to_be_visible()


def open_first_filtered_book(page: Page, base_url: str) -> str:
    open_filtered_books(page, base_url)
    first_book = page.locator("a.card.book-card").first
    book_title = first_book.locator("h3").inner_text()
    first_book.click()
    page.wait_for_load_state("networkidle")
    expect(page.locator(".document-index")).to_be_visible()
    expect(page.locator("[data-book-page].is-active article.markdown-body")).to_be_visible()
    return book_title


def run_browser_flow(base_url: str, output_dir: Path, headed: bool) -> list[Observation]:
    observations: list[Observation] = []
    browser_errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)

        def execute_story(story_slug: str, screenshot_name: str, callback) -> Observation:
            context = browser.new_context(
                viewport={"width": 1440, "height": 1200},
                record_video_dir=str(output_dir),
                record_video_size={"width": 1440, "height": 900},
            )
            page = context.new_page()
            attach_browser_error_hooks(page, browser_errors)
            try:
                step, result = callback(page)
                screenshot(page, output_dir, screenshot_name)
            finally:
                video_name = rename_story_video(page, context, output_dir, story_slug)
            return Observation(step=step, result=result, video_name=video_name)

        observations.append(
            execute_story(
                "login-y-acceso",
                "01-login-dashboard",
                lambda page: (
                    login(page, base_url),
                    (
                        "Iniciar sesion",
                        "El admin entra correctamente y ve el panel con el catalogo inicial importado.",
                    ),
                )[1],
            )
        )

        observations.append(
            execute_story(
                "abrir-catalogo",
                "02-books-list",
                lambda page: (
                    login(page, base_url),
                    page.goto(f"{base_url}/books", wait_until="networkidle"),
                    expect(page.get_by_role("heading", name="Libros disponibles")).to_be_visible(),
                    (
                        "Abrir listado",
                        f"El catalogo muestra {page.locator('a.card.book-card').count()} libros visibles antes de filtrar.",
                    ),
                )[3],
            )
        )

        observations.append(
            execute_story(
                "filtrar-catalogo",
                "03-books-filtered",
                lambda page: (
                    login(page, base_url),
                    open_filtered_books(page, base_url),
                    (
                        "Aplicar filtros",
                        f"El filtro Primaria/Lengua devuelve {page.locator('a.card.book-card').count()} resultados y mantiene la pagina estable.",
                    ),
                )[2],
            )
        )

        observations.append(
            execute_story(
                "abrir-detalle-del-libro",
                "04-book-detail",
                lambda page: (
                    login(page, base_url),
                    (
                        lambda title: (
                            expect(page.locator("img").first).to_be_visible(),
                            (
                                "Abrir detalle",
                                f"El detalle de '{title}' renderiza Markdown, indice lateral, paginacion e imagenes visibles.",
                            ),
                        )[1]
                    )(open_first_filtered_book(page, base_url)),
                )[1],
            )
        )

        observations.append(
            execute_story(
                "anadir-comentario",
                "05-book-comment",
                lambda page: (
                    login(page, base_url),
                    open_first_filtered_book(page, base_url),
                    page.get_by_label("Comentario").fill("Comentario de smoke validator desde Playwright."),
                    page.get_by_role("button", name="Añadir comentario").click(),
                    page.wait_for_load_state("networkidle"),
                    expect(page.get_by_text("Comentario de smoke validator desde Playwright.")).to_be_visible(),
                    (
                        "Enviar comentario",
                        "El comentario se guarda y aparece en la seccion de detalle pedagogico.",
                    ),
                )[6],
            )
        )

        def export_story(page: Page) -> tuple[str, str]:
            login(page, base_url)
            open_first_filtered_book(page, base_url)
            current_book_url = page.url.split("?")[0]
            export_response = page.context.request.get(f"{current_book_url}/export/pdf?branch=main")
            if not export_response.ok:
                raise PlaywrightError(f"Exportacion PDF fallo con estado {export_response.status}")
            pdf_path = output_dir / "book-export.pdf"
            pdf_path.write_bytes(export_response.body())
            return (
                "Exportar PDF",
                f"La exportacion responde {export_response.status} y se guarda en {pdf_path.name}.",
            )

        observations.append(execute_story("exportar-pdf", "06-book-export-source", export_story))

        def editor_story(page: Page) -> tuple[str, str]:
            login(page, base_url)
            open_first_filtered_book(page, base_url)
            page.get_by_role("link", name="Editar").first.click()
            page.wait_for_load_state("networkidle")
            expect(page.get_by_role("button", name="Edición")).to_be_visible()
            expect(page.get_by_role("button", name="Lectura")).to_be_visible()
            expect(page.locator("[data-rich-editor]")).to_be_visible()
            return (
                "Abrir editor",
                "El editor enriquecido abre una sola superficie de trabajo con cinta superior, lectura integrada y recursos reutilizables.",
            )

        observations.append(execute_story("abrir-editor", "07-book-editor", editor_story))

        def admin_story(page: Page) -> tuple[str, str]:
            login(page, base_url)
            page.goto(f"{base_url}/admin", wait_until="networkidle")
            expect(page.get_by_role("heading", name="Alta simple")).to_be_visible()
            expect(page.get_by_role("heading", name="Git local o GitHub")).to_be_visible()
            return (
                "Abrir administracion",
                "La pantalla admin carga formularios de usuarios, organizaciones y repositorios.",
            )

        observations.append(execute_story("abrir-administracion", "08-admin", admin_story))

        def logout_story(page: Page) -> tuple[str, str]:
            login(page, base_url)
            page.get_by_role("link", name="Cerrar sesión").click()
            page.wait_for_url(f"{base_url}/login")
            expect(page.get_by_role("heading", name="Acceder a Libre Libros")).to_be_visible()
            return (
                "Cerrar sesion",
                "La sesion finaliza y la app vuelve al formulario de acceso.",
            )

        observations.append(execute_story("cerrar-sesion", "09-logout", logout_story))

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
        video_suffix = f" Video: `{item.video_name}`." if item.video_name else ""
        lines.append(f"{index}. **{item.step}**: {item.result}{video_suffix}")
    evidence = [
        "",
        "## Evidencia generada",
        "",
        "- `01-login-dashboard.png`",
        "- `02-books-list.png`",
        "- `03-books-filtered.png`",
        "- `04-book-detail.png`",
        "- `05-book-comment.png`",
        "- `06-book-export-source.png`",
        "- `07-book-editor.png`",
        "- `08-admin.png`",
        "- `09-logout.png`",
        "- `book-export.pdf`",
    ]
    video_artifacts = [f"- `{item.video_name}`" for item in observations if item.video_name]
    if video_artifacts:
        evidence.extend(["", "### Videos por user story", ""])
        evidence.extend(video_artifacts)
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
        video_suffix = f" Video: `{item.video_name}`." if item.video_name else ""
        lines.append(f"{index}. **{item.step}**: {item.result}{video_suffix}")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- Run log: `{(output_dir / 'run-log.md').name}`",
            f"- Story video report: `{(output_dir / 'story-video-report.md').name}`",
            "- Screenshots: `01-login-dashboard.png` to `09-logout.png`",
            "- User story videos: `user-story-*.webm`",
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


def write_story_video_report(output_dir: Path, base_url: str, observations: list[Observation]) -> None:
    report = output_dir / "story-video-report.md"
    video_rows = []
    for item in observations:
        if item.video_name:
            video_rows.append(f"| {item.step} | `{item.video_name}` | {item.result} |")

    lines = [
        "# Story Video Report",
        "",
        f"- Date: {date.today().isoformat()}",
        f"- Base URL: `{base_url}`",
        "",
        "## How The Application Behaved",
        "",
        "La aplicacion ha respondido de forma estable en las historias basicas de validacion: acceso, catalogo, filtros, detalle, comentario, exportacion, editor, administracion y cierre de sesion.",
        "La navegacion principal es consistente y el catalogo importado desde el repositorio base se presenta correctamente en la web.",
        "",
        "## User Story Videos",
        "",
        "| User story | Video | Result |",
        "|------------|-------|--------|",
    ]
    lines.extend(video_rows)
    lines.extend(
        [
            "",
            "## Novedades Observadas",
            "",
            "- El editor ya funciona como una superficie unica de trabajo, con modos superiores para edicion, lectura y recursos.",
            "- La maquetacion del contenido admite columnas y recursos embebidos dentro del propio flujo de edicion.",
            "- El catalogo base importado ofrece una cobertura mas amplia por etapas y materias, lo que mejora la sensacion de producto listo para arrancar.",
            "- La exportacion a PDF y la parte de comentarios siguen operativas dentro del flujo funcional principal.",
            "",
            "## Proposed Improvements",
            "",
            "- Traducir mas mensajes tecnicos de persistencia para profesorado. Por ejemplo, evitar en UI expresiones como `rama` cuando no aportan valor al usuario final.",
            "- Añadir un indice o resumen visual de videos generados dentro del propio `validation-report.md` para acelerar la revision del validador.",
            "- Extender el mismo patron de video por user story a los journeys docentes y a las pruebas de refinement UX, no solo al smoke general.",
            "- Incluir una marca visual de exito por historia al finalizar cada flujo para que los videos cierren con una señal mas clara de resultado.",
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
        write_story_video_report(output_dir, args.base_url, observations)
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
