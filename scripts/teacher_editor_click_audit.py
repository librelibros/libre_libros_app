from __future__ import annotations

import argparse
import base64
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
TEACHER_EMAIL = "ana.editor@validator.local"
TEACHER_PASSWORD = "profe12345"
TEACHER_NAME = "Ana Profe"


@dataclass
class ClickStat:
    step: str
    clicks: int
    note: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audita clicks del flujo de edición docente.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    return parser.parse_args()


def write_sample_png(output_dir: Path) -> Path:
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wn4kWAAAAAASUVORK5CYII="
    )
    sample = output_dir / "auditoria-editor.png"
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


def run_audit(base_url: str, output_dir: Path) -> list[ClickStat]:
    clicks = 0
    stats: list[ClickStat] = []
    sample_png = write_sample_png(output_dir)

    def click(locator, step: str, note: str) -> None:
        nonlocal clicks
        clicks += 1
        locator.click()
        stats.append(ClickStat(step=step, clicks=clicks, note=note))

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        page.goto(f"{base_url}/register", wait_until="networkidle")
        page.get_by_label("Nombre completo").fill(TEACHER_NAME)
        page.get_by_label("Correo").fill(TEACHER_EMAIL)
        page.get_by_label("Contraseña").fill(TEACHER_PASSWORD)
        click(page.get_by_role("button", name="Crear cuenta"), "Alta", "La profesora crea la cuenta.")
        page.wait_for_url(f"{base_url}/")

        page.goto(f"{base_url}/books/1/edit?branch=main", wait_until="networkidle")
        expect(page.get_by_role("button", name="Edición")).to_be_visible()
        screenshot(page, output_dir, "01-editor-open", full_page=False)

        click(page.get_by_role("button", name="Recursos"), "Abrir recursos", "Abre la biblioteca integrada desde la cabecera.")
        click(
            page.locator("[data-insert-worksheet]").first,
            "Insertar ficha",
            "Inserta una ficha enlazada sin abandonar el editor.",
        )
        expect(page.get_by_role("button", name="Edición")).to_have_attribute("aria-selected", "true")

        click(page.get_by_role("button", name="2 columnas"), "Insertar columnas", "Añade un bloque de dos columnas desde la cinta superior.")
        drop_file(page, "[data-editor-surface]", sample_png, "image/png")
        expect(page.locator('.ProseMirror img[data-asset-path="assets/auditoria-editor.png"]')).to_be_visible()
        expect(page.get_by_text("Se guardarán con este material")).to_be_visible()
        screenshot(page, output_dir, "02-editor-with-layout", full_page=False)

        click(page.get_by_role("button", name="Lectura"), "Abrir lectura", "Comprueba la vista final desde la pestaña superior.")
        expect(page.locator("[data-rich-preview] .document-page").first).to_be_visible()
        screenshot(page, output_dir, "03-reading-mode", full_page=False)

        click(page.get_by_role("button", name="Guardar"), "Abrir guardado", "Abre el resumen de guardado sin salir del editor.")
        expect(page.get_by_role("heading", name="Guardar cambios del material")).to_be_visible()
        click(page.get_by_role("button", name="Guardar cambios").last, "Confirmar guardado", "Confirma el guardado final.")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_text("Cambios guardados en la rama users/ana-profe.")).to_be_visible()
        screenshot(page, output_dir, "04-saved-detail")

        browser.close()

    return stats


def write_report(output_dir: Path, base_url: str, stats: list[ClickStat]) -> None:
    total_clicks = stats[-1].clicks if stats else 0
    lines = [
        "# Teacher Editor Click Audit",
        "",
        f"- Date: {date.today().isoformat()}",
        f"- Base URL: `{base_url}`",
        f"- Total UI clicks: `{total_clicks}`",
        "- Non-click interaction: `1` drag-and-drop de imagen",
        "",
        "## Sequence",
        "",
    ]
    previous_clicks = 0
    for item in stats:
        lines.append(f"1. **{item.step}**: +{item.clicks - previous_clicks} click(s). {item.note}")
        previous_clicks = item.clicks
    lines.extend(
        [
            "",
            "## Assessment",
            "",
            "El flujo principal para insertar ficha, maquetar en 2 columnas, añadir imagen, revisar lectura y guardar queda en 7 clicks de interfaz y un drag-and-drop.",
            "La navegación se concentra en la parte superior y ya no depende de una vista previa lateral permanente.",
        ]
    )
    (output_dir / "click-audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output_dir = build_output_dir("editor-click-audit")
    example_repo_path = prepare_example_repo(output_dir)
    server_process = None
    log_handle = None

    try:
        server_process, log_handle = launch_server(
            base_url=args.base_url,
            output_dir=output_dir,
            env=build_env(
                output_dir,
                example_repo_path=example_repo_path,
                db_filename="editor-audit.db",
                admin_email="admin@editor-audit.local",
                admin_password="admin12345",
                admin_name="Editor Audit Admin",
                secret_key="editor-click-audit",
            ),
        )
        stats = run_audit(args.base_url, output_dir)
        write_report(output_dir, args.base_url, stats)
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
