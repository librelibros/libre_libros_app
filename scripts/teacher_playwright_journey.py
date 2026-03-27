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
from typing import TextIO

import httpx

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import Page, expect, sync_playwright
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Playwright no esta instalado. Ejecuta `python3 -m pip install -r requirements-validator.txt` "
        "y luego `python3 -m playwright install chromium`."
    ) from exc


PROJECT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_DIR.parent
TEST_PLAN_DIR = PROJECT_DIR / "test_plan"
DEFAULT_BASE_URL = "http://127.0.0.1:8011"
TEACHER_EMAIL = "ana.profe@validator.local"
TEACHER_PASSWORD = "profe12345"
TEACHER_NAME = "Ana Profe"


@dataclass
class Observation:
    step: str
    result: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ejecuta un journey E2E de profesor y guarda evidencia.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--headed", action="store_true")
    return parser.parse_args()


def build_output_dir() -> Path:
    output_dir = TEST_PLAN_DIR / f"{date.today().isoformat()}-teacher-journey"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def build_env(output_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    example_repo = REPO_ROOT / "data" / "repo"
    env.update(
        {
            "LIBRE_LIBROS_DATABASE_URL": f"sqlite:///{output_dir / 'teacher.db'}",
            "LIBRE_LIBROS_REPOS_ROOT": str(output_dir / "repos"),
            "LIBRE_LIBROS_EXAMPLE_REPO_PATH": str(example_repo),
            "LIBRE_LIBROS_INIT_ADMIN_EMAIL": "admin@teacher.local",
            "LIBRE_LIBROS_INIT_ADMIN_PASSWORD": "admin12345",
            "LIBRE_LIBROS_INIT_ADMIN_NAME": "Teacher Admin",
            "LIBRE_LIBROS_SECRET_KEY": "teacher-journey-secret",
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


def launch_server(base_url: str, output_dir: Path) -> tuple[subprocess.Popen[str], TextIO]:
    server_log = output_dir / "server.log"
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
        env=build_env(output_dir),
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


def write_sample_png(output_dir: Path) -> Path:
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wn4kWAAAAAASUVORK5CYII="
    )
    sample = output_dir / "foto-de-clase.png"
    sample.write_bytes(png_bytes)
    return sample


def screenshot(page: Page, output_dir: Path, name: str, *, full_page: bool = True) -> None:
    page.screenshot(path=str(output_dir / f"{name}.png"), full_page=full_page)


def drop_file(page: Page, selector: str, file_path: Path, mime_type: str) -> None:
    payload = base64.b64encode(file_path.read_bytes()).decode("ascii")
    data_transfer = page.evaluate_handle(
        """async ({name, mimeType, payload}) => {
          const binary = Uint8Array.from(atob(payload), (char) => char.charCodeAt(0));
          const file = new File([binary], name, { type: mimeType });
          const dataTransfer = new DataTransfer();
          dataTransfer.items.add(file);
          return dataTransfer;
        }""",
        {"name": file_path.name, "mimeType": mime_type, "payload": payload},
    )
    page.locator(selector).dispatch_event("dragover", {"dataTransfer": data_transfer})
    page.locator(selector).dispatch_event("drop", {"dataTransfer": data_transfer})


def update_textarea(page: Page, replacement_marker: str) -> None:
    textarea = page.locator("[data-editor-input]")
    current = textarea.input_value()
    lines = current.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("- ") or line[:2].isdigit():
            lines.pop(index)
            break
    lines.append("")
    lines.append("<!-- pagebreak -->")
    lines.append("")
    lines.append("## Proyecto de lectura en voz alta")
    lines.append("")
    lines.append("El alumnado prepara una lectura compartida y graba una reflexion final.")
    lines.append("")
    lines.append(replacement_marker)
    updated = "\n".join(lines)
    textarea.fill(updated)


def run_flow(base_url: str, output_dir: Path, headed: bool) -> list[Observation]:
    observations: list[Observation] = []
    browser_errors: list[str] = []
    upload_file = write_sample_png(output_dir)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1366, "height": 768})
        page.on("console", lambda msg: browser_errors.append(f"[console:{msg.type}] {msg.text}") if msg.type == "error" else None)
        page.on("pageerror", lambda exc: browser_errors.append(f"[pageerror] {exc}"))

        page.goto(f"{base_url}/register", wait_until="networkidle")
        expect(page.get_by_role("heading", name="Crear usuario")).to_be_visible()
        page.get_by_label("Nombre completo").fill(TEACHER_NAME)
        page.get_by_label("Correo").fill(TEACHER_EMAIL)
        page.get_by_label("Contraseña").fill(TEACHER_PASSWORD)
        screenshot(page, output_dir, "01-register")
        page.get_by_role("button", name="Crear cuenta").click()
        page.wait_for_url(f"{base_url}/")
        expect(page.get_by_role("heading", name="Libros por curso y materia")).to_be_visible()
        screenshot(page, output_dir, "02-dashboard")
        observations.append(Observation("Alta y acceso", "La profesora crea su cuenta y entra en el panel inicial."))

        page.goto(f"{base_url}/books", wait_until="networkidle")
        page.get_by_label("Curso").select_option("Primaria")
        page.get_by_label("Materia").select_option("Lengua")
        page.get_by_role("button", name="Filtrar").click()
        expect(page.locator("a.card.book-card").first).to_be_visible()
        screenshot(page, output_dir, "03-filtered-books")
        observations.append(Observation("Filtrar libros", "La profesora encuentra rapidamente el libro de Lengua de Primaria."))

        page.locator("a.card.book-card").first.click()
        page.wait_for_load_state("networkidle")
        expect(page.locator(".document-index")).to_be_visible()
        screenshot(page, output_dir, "04-book-detail")
        observations.append(Observation("Consultar libro", "El libro se abre con indice, paginacion y contenido navegable."))

        page.get_by_role("link", name="Editar").first.click()
        page.wait_for_load_state("networkidle")
        page.get_by_label("Rama").select_option("users/ana-profe")
        drop_file(page, "[data-editor-surface]", upload_file, "image/png")
        expect(page.get_by_text("Se añadirán en este guardado")).to_be_visible()
        expect(page.locator("[data-selected-asset-name]")).to_have_value("foto-de-clase.png")
        expect(page.locator("[data-inline-assets] img")).to_be_visible()
        page.get_by_label("Texto alternativo").fill("Foto de clase")
        page.get_by_label("Posición").select_option("right")
        page.get_by_label("Tamaño").select_option("50")
        screenshot(page, output_dir, "05-editor-assets", full_page=False)
        observations.append(Observation("Preparar recurso", "La profesora arrastra una imagen al lienzo, la ve de inmediato en el editor y ajusta su bloque visual antes de guardar."))

        page.get_by_role("button", name="Vista").click()
        expect(page.get_by_alt_text("Foto de clase").first).to_be_visible()

        textarea = page.locator("[data-editor-input]")
        textarea.evaluate(
            """(el) => {
              el.value = el.value
                .split("\\n")
                .filter((line) => !line.includes("assets/foto-de-clase.png"))
                .join("\\n");
              el.dispatchEvent(new Event("input"));
            }"""
        )
        update_textarea(page, "![Foto de clase](assets/foto-de-clase.png){: .doc-image .doc-align-right .doc-w-50}")
        page.get_by_role("button", name="Guardar").click()
        expect(page.get_by_role("heading", name="Preparar commit de libro")).to_be_visible()
        page.get_by_label("Mensaje de commit").fill("Adaptacion docente del proyecto lector")
        screenshot(page, output_dir, "06-editor-content", full_page=False)
        page.get_by_role("button", name="Guardar y crear commit").click()
        page.wait_for_load_state("networkidle")
        expect(page.get_by_text("Cambios guardados en la rama users/ana-profe.")).to_be_visible()
        expect(page.get_by_text("Recursos anadidos: foto-de-clase.png.")).to_be_visible()
        page.locator(".toc-link").filter(has_text="Proyecto de lectura en voz alta").first.click()
        expect(page.locator(".document-page.is-active h2", has_text="Proyecto de lectura en voz alta")).to_be_visible()
        screenshot(page, output_dir, "07-detail-updated")
        observations.append(
            Observation(
                "Modificar y guardar",
                "La profesora elimina una parte del contenido, anade una nueva actividad con una imagen maquetada y guarda los cambios en su rama personal.",
            )
        )

        page.get_by_label("Ancla opcional").fill("proyecto-lectura")
        page.get_by_label("Comentario").fill("Seria util anadir una rubrica para la lectura en voz alta.")
        page.get_by_role("button", name="Añadir comentario").click()
        page.wait_for_load_state("networkidle")
        expect(page.get_by_text("Comentario anadido correctamente.")).to_be_visible()
        comment_card = page.locator(".comment").filter(has_text="Seria util anadir una rubrica para la lectura en voz alta.").first
        expect(comment_card).to_be_visible()
        screenshot(page, output_dir, "08-comment-added")
        observations.append(Observation("Anadir comentario", "La profesora deja una observacion contextualizada sobre una mejora didactica."))

        comment_card.get_by_role("button", name="Eliminar").click()
        page.wait_for_load_state("networkidle")
        expect(page.get_by_text("Comentario eliminado.")).to_be_visible()
        expect(page.get_by_text("Seria util anadir una rubrica para la lectura en voz alta.")).not_to_be_visible()
        screenshot(page, output_dir, "09-comment-removed")
        observations.append(Observation("Corregir comentario", "La profesora puede retirar su comentario si lo anadio por error."))

        page.get_by_label("Rama origen").select_option("users/ana-profe")
        page.get_by_label("Título").last.fill("Adaptacion de proyecto lector para el aula")
        page.get_by_label("Descripción").last.fill("Se anade una actividad final con salto de pagina e imagen de apoyo.")
        page.get_by_role("button", name="Abrir pull request").click()
        page.wait_for_load_state("networkidle")
        expect(page.get_by_text("Pull request registrada correctamente.")).to_be_visible()
        expect(page.get_by_text("Adaptacion de proyecto lector para el aula")).to_be_visible()
        screenshot(page, output_dir, "10-pull-request")
        observations.append(Observation("Proponer cambios", "La profesora registra una propuesta de cambio desde su rama personal."))

        page.get_by_role("link", name="Cerrar sesión").click()
        page.wait_for_url(f"{base_url}/login")
        screenshot(page, output_dir, "11-logout")
        observations.append(Observation("Cerrar sesion", "La profesora termina la sesion y vuelve a la pantalla de acceso."))

        browser.close()

    if browser_errors:
        (output_dir / "browser-errors.log").write_text("\n".join(browser_errors) + "\n", encoding="utf-8")
        observations.append(Observation("Revision de consola", "Se detectaron errores de navegador; revisar browser-errors.log."))
    else:
        observations.append(Observation("Revision de consola", "No se detectaron errores de consola ni excepciones de pagina."))
    return observations


def write_reports(output_dir: Path, base_url: str, observations: list[Observation]) -> None:
    run_log = output_dir / "run-log.md"
    report = output_dir / "teacher-report.md"
    shared_lines = [
        f"- Fecha: {date.today().isoformat()}",
        f"- Base URL: `{base_url}`",
        f"- Usuario docente: `{TEACHER_EMAIL}`",
        "",
        "## Pasos y resultados",
        "",
    ]
    for index, item in enumerate(observations, start=1):
        shared_lines.append(f"{index}. **{item.step}**: {item.result}")

    run_log.write_text("# Teacher Journey\n\n" + "\n".join(shared_lines) + "\n", encoding="utf-8")

    verdict = "APPROVED"
    report_lines = [
        "# Teacher Journey Report",
        "",
        f"- Date: {date.today().isoformat()}",
        f"- Verdict: {verdict}",
        "",
        "## Summary",
        "",
        "The teacher lifecycle passed: discovery, editing on a personal branch, asset upload and reuse, comment creation/removal, and pull-request submission.",
        "",
        "## Artifacts",
        "",
        "- `01-register.png` to `11-logout.png`",
        "- `run-log.md`",
        "- `server.log`",
    ]
    if (output_dir / "browser-errors.log").exists():
        report_lines.append("- `browser-errors.log`")
        report_lines[3] = "- Verdict: CHANGES_REQUESTED"
    report.write_text("\n".join(report_lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output_dir = build_output_dir()
    server_process: subprocess.Popen[str] | None = None
    log_handle: TextIO | None = None

    try:
        server_process, log_handle = launch_server(args.base_url, output_dir)
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
