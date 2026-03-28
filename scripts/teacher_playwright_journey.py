from __future__ import annotations

import argparse
import base64
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

from journey_support import build_env, build_output_dir, launch_server, prepare_example_repo

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
        page.get_by_label("Espacio de trabajo").select_option("users/ana-profe")
        page.get_by_role("button", name="Recursos").click()
        page.locator("[data-insert-worksheet]").first.click()
        page.get_by_role("button", name="Edición").click()
        page.get_by_role("button", name="2 columnas").click()
        drop_file(page, "[data-editor-surface]", upload_file, "image/png")
        expect(page.locator("[data-inline-assets] img")).to_be_visible()
        screenshot(page, output_dir, "05-editor-assets", full_page=False)
        observations.append(
            Observation(
                "Preparar recurso",
                "La profesora inserta una ficha, añade un bloque de dos columnas y arrastra una imagen al mismo lienzo de edición.",
            )
        )

        page.get_by_role("button", name="Lectura").click()
        expect(page.locator("[data-rich-preview] .document-page").first).to_be_visible()
        page.get_by_role("button", name="Guardar").click()
        expect(page.get_by_role("heading", name="Guardar cambios del material")).to_be_visible()
        page.get_by_label("Resumen del guardado").fill("Adaptacion docente del proyecto lector")
        screenshot(page, output_dir, "06-editor-content", full_page=False)
        page.get_by_role("button", name="Guardar cambios").click()
        page.wait_for_load_state("networkidle")
        expect(page.get_by_text("Cambios guardados en la rama users/ana-profe.")).to_be_visible()
        expect(page.get_by_text("Recursos anadidos: foto-de-clase.png.")).to_be_visible()
        screenshot(page, output_dir, "07-detail-updated")
        observations.append(
            Observation(
                "Modificar y guardar",
                "La profesora revisa la lectura final y guarda los cambios desde un modal de lenguaje docente en su espacio personal.",
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
    output_dir = build_output_dir("teacher-journey")
    server_process = None
    log_handle = None

    try:
        example_repo_path = prepare_example_repo(output_dir)
        server_process, log_handle = launch_server(
            base_url=args.base_url,
            output_dir=output_dir,
            env=build_env(
                output_dir,
                example_repo_path=example_repo_path,
                db_filename="teacher.db",
                admin_email="admin@teacher.local",
                admin_password="admin12345",
                admin_name="Teacher Admin",
                secret_key="teacher-journey-secret",
            ),
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
