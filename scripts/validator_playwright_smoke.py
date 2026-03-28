from __future__ import annotations

import argparse
import base64
import os
import shutil
import subprocess
import sys
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, TextIO

import httpx
from journey_support import snapshot_example_repo

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
USER_STORIES_PATH = PROJECT_DIR / "user_stories.md"
DEFAULT_BASE_URL = "http://127.0.0.1:8010"
DEFAULT_ADMIN_EMAIL = "admin@validator.local"
DEFAULT_ADMIN_PASSWORD = "admin12345"
DEFAULT_STEP_DELAY_MS = 3000

CLICK_HIGHLIGHT_SCRIPT = """
(() => {
  if (window.__libreLibrosClickHighlightInstalled) return;
  window.__libreLibrosClickHighlightInstalled = true;

  const ensureStyle = () => {
    if (document.querySelector("style[data-codex-click-highlight]")) return;
    const host = document.head || document.documentElement || document.body;
    if (!host) return;

    const style = document.createElement("style");
    style.setAttribute("data-codex-click-highlight", "true");
    style.textContent = `
      .codex-click-highlight {
        position: fixed;
        width: 22px;
        height: 22px;
        margin-left: -11px;
        margin-top: -11px;
        border-radius: 999px;
        border: 3px solid rgba(36, 87, 197, 0.92);
        background: rgba(36, 87, 197, 0.18);
        box-shadow: 0 0 0 10px rgba(36, 87, 197, 0.12);
        pointer-events: none;
        z-index: 2147483647;
        opacity: 0;
        transform: scale(0.55);
        transition: opacity 180ms ease, transform 220ms ease;
      }
      .codex-click-highlight.is-visible {
        opacity: 1;
        transform: scale(1);
      }
    `;
    host.appendChild(style);
  };

  ensureStyle();
  document.addEventListener("DOMContentLoaded", ensureStyle, { once: true });

  document.addEventListener(
    "pointerdown",
    (event) => {
      ensureStyle();
      const ring = document.createElement("div");
      ring.className = "codex-click-highlight";
      ring.style.left = `${event.clientX}px`;
      ring.style.top = `${event.clientY}px`;
      const host = document.body || document.documentElement;
      if (!host) return;
      host.appendChild(ring);
      requestAnimationFrame(() => ring.classList.add("is-visible"));
      setTimeout(() => {
        ring.classList.remove("is-visible");
        setTimeout(() => ring.remove(), 320);
      }, 1350);
    },
    true,
  );
})();
"""


@dataclass(frozen=True)
class UserStory:
    story_id: str
    slug: str
    title: str
    goal: str
    expected_result: str


@dataclass
class Observation:
    story: UserStory
    result: str
    screenshot_name: str
    video_name: str
    pdf_name: str | None = None


CATALOG_COMMENT_STORY = UserStory(
    story_id="catalogo_filtrar_y_comentar",
    slug="catalogo-filtrar-y-comentar",
    title="Catalogo, filtro y comentario",
    goal="Revisar el catalogo, localizar un libro y dejar una observacion pedagogica.",
    expected_result="El libro filtrado se abre correctamente y el comentario queda visible en la pagina de detalle.",
)

EDIT_COLUMNS_PDF_STORY = UserStory(
    story_id="editar_varias_columnas_y_generar_pdf",
    slug="editar-varias-columnas-y-generar-pdf",
    title="Editar varias columnas y generar PDF",
    goal="Editar un libro con dos columnas, texto e imagen y exportarlo a PDF.",
    expected_result="El libro guarda un bloque de dos columnas con texto e imagen y el PDF se genera correctamente.",
)

ADMIN_LOGOUT_STORY = UserStory(
    story_id="administracion_y_cierre_de_sesion",
    slug="administracion-y-cierre-de-sesion",
    title="Administracion y cierre de sesion",
    goal="Verificar que la zona de administracion carga y que la sesion puede cerrarse correctamente.",
    expected_result="La pagina de administracion se muestra y el cierre de sesion devuelve al login.",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ejecuta un validator smoke E2E por historias completas y guarda evidencia en test_plan.",
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
    output_dir = provided or TEST_PLAN_DIR / f"{date.today().isoformat()}-validator-playwright"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def build_env(output_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    source_example_repo = REPO_ROOT / "data" / "repo"
    example_repo = output_dir / "example-repo"
    shutil.copytree(source_example_repo, example_repo)
    snapshot_example_repo(example_repo)
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


def screenshot(page: Page, output_dir: Path, name: str) -> str:
    filename = f"{name}.png"
    page.screenshot(path=str(output_dir / filename), full_page=True)
    return filename


def ffmpeg_binary() -> str:
    binary = shutil.which("ffmpeg")
    if not binary:
        raise RuntimeError("No se encontro ffmpeg en PATH. Se necesita para convertir los videos a mp4.")
    return binary


def story_video_filename(story: UserStory) -> str:
    return f"user-story-{story.slug}.mp4"


def pause_for_video(page: Page, milliseconds: int = DEFAULT_STEP_DELAY_MS) -> None:
    page.wait_for_timeout(milliseconds)


def prepare_story_page(page: Page) -> None:
    page.add_init_script(CLICK_HIGHLIGHT_SCRIPT)


def paced_click(page: Page, locator) -> None:
    locator.click()
    pause_for_video(page)


def paced_fill(page: Page, locator, value: str) -> None:
    locator.click()
    pause_for_video(page, 1000)
    locator.fill(value)
    pause_for_video(page)


def paced_select(page: Page, locator, value: str) -> None:
    locator.select_option(value)
    pause_for_video(page)


def focus_editor(page: Page, position: str) -> None:
    page.locator("[data-rich-markdown-editor]").evaluate(
        "(form, position) => form._richState?.editor?.commands?.focus(position)",
        position,
    )
    pause_for_video(page, 1000)


def replace_block_text(page: Page, locator, text: str) -> None:
    locator.click()
    locator.evaluate(
        """(element) => {
            const range = document.createRange();
            range.selectNodeContents(element);
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
            element.closest(".ProseMirror")?.focus();
        }""",
    )
    pause_for_video(page, 1000)
    page.keyboard.type(text, delay=40)
    pause_for_video(page)


def attach_browser_error_hooks(page: Page, browser_errors: list[str]) -> None:
    page.on("console", lambda msg: browser_errors.append(f"[console:{msg.type}] {msg.text}") if msg.type == "error" else None)
    page.on("pageerror", lambda exc: browser_errors.append(f"[pageerror] {exc}"))


def convert_video_to_mp4(source: Path, target: Path) -> None:
    command = [
        ffmpeg_binary(),
        "-y",
        "-i",
        str(source),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(target),
    ]
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"ffmpeg fallo al convertir {source.name} a mp4: {completed.stderr.strip()}")


def finalize_story_video(page: Page, context, output_dir: Path, story: UserStory) -> str:
    video = page.video
    context.close()
    if video is None:
        raise PlaywrightError(f"No se genero video para la historia {story.story_id}")
    webm_path = Path(video.path())
    mp4_path = output_dir / story_video_filename(story)
    if mp4_path.exists():
        mp4_path.unlink()
    convert_video_to_mp4(webm_path, mp4_path)
    if webm_path.exists():
        webm_path.unlink()
    return mp4_path.name


def login(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/login", wait_until="networkidle")
    pause_for_video(page)
    expect(page.get_by_role("heading", name="Acceder a Libre Libros")).to_be_visible()
    paced_fill(page, page.get_by_label("Correo"), DEFAULT_ADMIN_EMAIL)
    paced_fill(page, page.get_by_label("Contraseña"), DEFAULT_ADMIN_PASSWORD)
    paced_click(page, page.get_by_role("button", name="Entrar"))
    page.wait_for_url(f"{base_url}/")
    expect(page.get_by_role("heading", name="Libros por curso y materia")).to_be_visible()
    pause_for_video(page)


def logout(page: Page, base_url: str) -> None:
    paced_click(page, page.get_by_role("link", name="Cerrar sesión"))
    page.wait_for_url(f"{base_url}/login")
    expect(page.get_by_role("heading", name="Acceder a Libre Libros")).to_be_visible()
    pause_for_video(page)


def open_filtered_books(page: Page, base_url: str) -> int:
    page.goto(f"{base_url}/books", wait_until="networkidle")
    pause_for_video(page)
    expect(page.get_by_role("heading", name="Libros disponibles")).to_be_visible()
    paced_select(page, page.get_by_label("Curso"), "Primaria")
    paced_select(page, page.get_by_label("Materia"), "Lengua")
    paced_click(page, page.get_by_role("button", name="Filtrar"))
    filtered_cards = page.locator("a.card.book-card")
    expect(filtered_cards.first).to_be_visible()
    pause_for_video(page)
    return filtered_cards.count()


def open_first_filtered_book(page: Page, base_url: str) -> str:
    open_filtered_books(page, base_url)
    first_book = page.locator("a.card.book-card").first
    book_title = first_book.locator("h3").inner_text()
    paced_click(page, first_book)
    page.wait_for_load_state("networkidle")
    expect(page.locator(".document-index")).to_be_visible()
    expect(page.locator("[data-book-page].is-active article.markdown-body")).to_be_visible()
    pause_for_video(page)
    return book_title


def run_catalog_comment_story(page: Page, base_url: str) -> tuple[str, str]:
    login(page, base_url)
    result_count = open_filtered_books(page, base_url)
    book_title = open_first_filtered_book(page, base_url)
    comment_text = "Comentario de validacion punto a punto para el catalogo."
    paced_fill(page, page.get_by_label("Comentario"), comment_text)
    paced_click(page, page.get_by_role("button", name="Añadir comentario"))
    page.wait_for_load_state("networkidle")
    expect(page.get_by_text(comment_text)).to_be_visible()
    pause_for_video(page)
    return (
        CATALOG_COMMENT_STORY.title,
        f"El catalogo filtra correctamente ({result_count} resultado), se abre '{book_title}' y el comentario queda visible en detalle.",
    )


def run_edit_columns_pdf_story(page: Page, base_url: str, output_dir: Path) -> tuple[str, str, str]:
    login(page, base_url)
    book_title = open_first_filtered_book(page, base_url)
    detail_url = page.url.split("?")[0]

    paced_click(page, page.get_by_role("link", name="Editar").first)
    page.wait_for_load_state("networkidle")
    expect(page.get_by_role("button", name="Edición")).to_be_visible()
    editor_root = page.locator(".ProseMirror")
    expect(editor_root).to_be_visible()
    pause_for_video(page)

    existing_columns = editor_root.locator("[data-layout='columns']").count()
    focus_editor(page, "start")
    paced_click(page, page.get_by_role("button", name="2 columnas"))

    columns_blocks = editor_root.locator("[data-layout='columns']")
    expect(columns_blocks).to_have_count(existing_columns + 1)
    new_block = columns_blocks.first
    column_nodes = new_block.locator("[data-layout-column]")
    expect(column_nodes).to_have_count(2)
    pause_for_video(page)

    first_column_body = column_nodes.nth(0).locator("p").last
    second_column_body = column_nodes.nth(1).locator("p").last
    expect(first_column_body).to_be_visible()
    expect(second_column_body).to_be_visible()

    replace_block_text(page, first_column_body, "Texto de la primera columna para la prueba de exportacion.")
    replace_block_text(page, second_column_body, "Texto de la segunda columna con apoyo visual.")

    paced_click(page, second_column_body)
    paced_click(page, page.get_by_role("button", name="Recursos"))
    paced_click(page, page.locator("[data-insert-asset][data-asset-media-type^='image/']").first)
    expect(page.locator(".ProseMirror img[data-asset-path]").last).to_be_visible()
    pause_for_video(page)

    paced_click(page, page.get_by_role("button", name="Guardar"))
    expect(page.get_by_role("heading", name="Guardar cambios del material")).to_be_visible()
    paced_fill(page, page.get_by_label("Resumen del guardado"), "Prueba de columnas y exportacion PDF")
    paced_click(page, page.get_by_role("button", name="Guardar cambios"))
    page.wait_for_load_state("networkidle")
    pause_for_video(page)

    active_page_body = page.locator("[data-book-page].is-active article.markdown-body")
    expect(page.locator("[data-book-page].is-active .doc-columns-2").last).to_be_visible()
    expect(active_page_body).to_contain_text("Texto de la primera columna para la prueba de exportacion.")
    expect(active_page_body).to_contain_text("Texto de la segunda columna con apoyo visual.")
    expect(active_page_body.locator("img[src*='column-demo-image']").first).to_be_visible()

    export_response = page.context.request.get(f"{detail_url}/export/pdf?branch=main")
    if not export_response.ok:
        raise PlaywrightError(f"Exportacion PDF fallo con estado {export_response.status}")
    pdf_name = f"user-story-{EDIT_COLUMNS_PDF_STORY.slug}.pdf"
    pdf_path = output_dir / pdf_name
    pdf_path.write_bytes(export_response.body())

    return (
        EDIT_COLUMNS_PDF_STORY.title,
        f"'{book_title}' guarda un bloque de dos columnas con texto e imagen y exporta correctamente a {pdf_name}.",
        pdf_name,
    )


def run_admin_logout_story(page: Page, base_url: str) -> tuple[str, str]:
    login(page, base_url)
    page.goto(f"{base_url}/admin", wait_until="networkidle")
    pause_for_video(page)
    expect(page.get_by_role("heading", name="Alta simple")).to_be_visible()
    expect(page.get_by_role("heading", name="Git local o GitHub")).to_be_visible()
    pause_for_video(page)
    logout(page, base_url)
    return (
        ADMIN_LOGOUT_STORY.title,
        "La administracion carga sus secciones principales y el cierre de sesion devuelve al formulario de acceso.",
    )


def run_browser_flow(base_url: str, output_dir: Path, headed: bool) -> tuple[list[Observation], list[str]]:
    observations: list[Observation] = []
    browser_errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)

        def execute_story(
            story: UserStory,
            screenshot_stem: str,
            callback: Callable[[Page], tuple[str, str] | tuple[str, str, str]],
        ) -> None:
            context = browser.new_context(
                viewport={"width": 1440, "height": 1200},
                record_video_dir=str(output_dir),
                record_video_size={"width": 1440, "height": 900},
            )
            page = context.new_page()
            prepare_story_page(page)
            attach_browser_error_hooks(page, browser_errors)
            pdf_name: str | None = None
            try:
                callback_result = callback(page)
                if len(callback_result) == 3:
                    step_title, result, pdf_name = callback_result
                else:
                    step_title, result = callback_result
                screenshot_name = screenshot(page, output_dir, screenshot_stem)
            finally:
                video_name = finalize_story_video(page, context, output_dir, story)
            observations.append(
                Observation(
                    story=story,
                    result=result,
                    screenshot_name=screenshot_name,
                    video_name=video_name,
                    pdf_name=pdf_name,
                )
            )

        execute_story(CATALOG_COMMENT_STORY, "01-catalogo-filtrar-y-comentar", lambda page: run_catalog_comment_story(page, base_url))
        execute_story(
            EDIT_COLUMNS_PDF_STORY,
            "02-editar-varias-columnas-y-generar-pdf",
            lambda page: run_edit_columns_pdf_story(page, base_url, output_dir),
        )
        execute_story(
            ADMIN_LOGOUT_STORY,
            "03-administracion-y-cierre-de-sesion",
            lambda page: run_admin_logout_story(page, base_url),
        )
        browser.close()

    return observations, browser_errors


def write_run_log(output_dir: Path, base_url: str, observations: list[Observation], reused_server: bool) -> None:
    run_log = output_dir / "run-log.md"
    lines = [
        "# Validator Playwright Smoke",
        "",
        f"- Fecha: {date.today().isoformat()}",
        f"- Base URL: `{base_url}`",
        f"- Servidor reutilizado: `{'si' if reused_server else 'no'}`",
        f"- Usuario de prueba: `{DEFAULT_ADMIN_EMAIL}`",
        f"- Historias fuente: `{USER_STORIES_PATH.name}`",
        "",
        "## Historias ejecutadas",
        "",
    ]
    for index, item in enumerate(observations, start=1):
        lines.extend(
            [
                f"{index}. **{item.story.story_id}**",
                f"   - Objetivo: {item.story.goal}",
                f"   - Resultado esperado: {item.story.expected_result}",
                f"   - Resultado observado: {item.result}",
                f"   - Captura final: `{item.screenshot_name}`",
                f"   - Video completo: `{item.video_name}`",
            ]
        )
        if item.pdf_name:
            lines.append(f"   - PDF generado: `{item.pdf_name}`")

    lines.extend(
        [
            "",
            "## Evidencia generada",
            "",
            f"- Historias definidas: `{USER_STORIES_PATH.name}`",
        ]
    )
    for item in observations:
        lines.append(f"- `{item.screenshot_name}`")
    for item in observations:
        lines.append(f"- `{item.video_name}`")
    for item in observations:
        if item.pdf_name:
            lines.append(f"- `{item.pdf_name}`")
    if not reused_server:
        lines.append("- `server.log`")
    if (output_dir / "browser-errors.log").exists():
        lines.append("- `browser-errors.log`")
    run_log.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_validation_report(
    output_dir: Path,
    observations: list[Observation],
    reused_server: bool,
    browser_errors: list[str],
) -> None:
    report = output_dir / "validation-report.md"
    verdict = "APPROVED" if not browser_errors else "CHANGES_REQUESTED"
    lines = [
        "# Validation Report",
        "",
        f"- Date: {date.today().isoformat()}",
        f"- Verdict: {verdict}",
        f"- Server reused: {'yes' if reused_server else 'no'}",
        f"- User stories source: `{USER_STORIES_PATH.name}`",
        "",
        "## Covered user stories",
        "",
        "| Story | Video | Result |",
        "|------|-------|--------|",
    ]
    for item in observations:
        lines.append(f"| {item.story.story_id} | `{item.video_name}` | {item.result} |")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- Run log: `{(output_dir / 'run-log.md').name}`",
            f"- Story report: `{(output_dir / 'story-video-report.md').name}`",
            "- Screenshots: `01-catalogo-filtrar-y-comentar.png` to `03-administracion-y-cierre-de-sesion.png`",
            "- Full-flow videos: `user-story-*.mp4`",
        ]
    )
    pdf_artifacts = [item.pdf_name for item in observations if item.pdf_name]
    for pdf_name in pdf_artifacts:
        lines.append(f"- PDF export: `{pdf_name}`")
    if not reused_server:
        lines.append("- Server log: `server.log`")
    if browser_errors:
        lines.append("- Browser errors: `browser-errors.log`")
    lines.extend(
        [
            "",
            "## Summary",
            "",
            "The validator executed the complete stories defined in `user_stories.md`, recording one mp4 per story from login to final outcome.",
            "The browser videos include deliberate pauses between key actions and a visible click marker so the flow can be reviewed by humans.",
        ]
    )
    if browser_errors:
        lines.append("Browser-side errors were detected and should be reviewed before approval.")
    else:
        lines.append("All full-flow user stories passed and no browser-side errors were detected.")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_story_video_report(output_dir: Path, base_url: str, observations: list[Observation]) -> None:
    report = output_dir / "story-video-report.md"
    lines = [
        "# Story Video Report",
        "",
        f"- Date: {date.today().isoformat()}",
        f"- Base URL: `{base_url}`",
        f"- User stories source: `{USER_STORIES_PATH.name}`",
        "",
        "## How The Application Behaved",
        "",
        "La aplicacion ha respondido de forma estable en los flujos completos definidos para este proyecto.",
        "Las historias se han ejecutado desde el login hasta el resultado final, lo que permite revisar no solo pantallas aisladas sino el recorrido funcional entero.",
        "",
        "## User Story Execution",
        "",
        "| Story | Goal | Video | Result |",
        "|------|------|-------|--------|",
    ]
    for item in observations:
        lines.append(f"| {item.story.story_id} | {item.story.goal} | `{item.video_name}` | {item.result} |")
    lines.extend(
        [
            "",
            "## Novedades Observadas",
            "",
            "- La validacion ya no se basa en microacciones sueltas, sino en historias completas de punta a punta.",
            "- Cada historia deja un video `mp4` reutilizable para revisiones funcionales y de UX.",
            "- Los videos usan pausas entre acciones y un marcador visual de clic para que el recorrido sea legible durante la revision.",
            "- El editor sigue permitiendo estructurar contenido con varias columnas y combinar texto con imagen dentro del flujo de trabajo.",
            "- La app mantiene operativos el catalogo, los comentarios, la exportacion PDF y la zona de administracion en el mismo ciclo de validacion.",
            "",
            "## Posibles Mejoras",
            "",
            "- Extender este mismo patron de historias completas a `teacher_playwright_journey.py` y al refinamiento UX para unificar toda la evidencia visual del proyecto.",
            "- Añadir verificacion automatica del contenido del PDF exportado para comprobar no solo que se genera, sino que conserva la estructura esperada.",
            "- Relacionar cada historia con una vista resumen dentro de la aplicacion de validacion para comparar video, captura y logs sin salir de `test_plan`.",
            "- Hacer que el validador marque en el cierre de cada flujo un estado visual de exito o error para que el final del video sea mas facil de revisar.",
        ]
    )
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(args: argparse.Namespace) -> int:
    if not USER_STORIES_PATH.exists():
        raise SystemExit(f"No existe {USER_STORIES_PATH}. Crea las historias antes de ejecutar el validator smoke.")

    output_dir = build_output_dir(args.output_dir)
    server_process: subprocess.Popen[str] | None = None
    log_handle: TextIO | None = None

    try:
        if args.reuse_server:
            wait_for_server(args.base_url)
        else:
            server_process, _, log_handle = launch_server(args.base_url, output_dir)

        observations, browser_errors = run_browser_flow(args.base_url, output_dir, args.headed)
        if browser_errors:
            (output_dir / "browser-errors.log").write_text("\n".join(browser_errors) + "\n", encoding="utf-8")
        write_run_log(output_dir, args.base_url, observations, args.reuse_server)
        write_validation_report(output_dir, observations, args.reuse_server, browser_errors)
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
