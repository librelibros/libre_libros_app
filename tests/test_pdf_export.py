"""Offline PDF unit tests. No app.main, settings, repository or owner dotenv."""
from __future__ import annotations

import importlib.util
import socket
import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image as PILImage
from reportlab.platypus import Image, LongTable, PageBreak, Paragraph

# Load this standalone service without importing the application package.
_spec = importlib.util.spec_from_file_location(
    "isolated_pdf_export", Path(__file__).parents[1] / "app/services/pdf_export.py"
)
pdf = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = pdf
_spec.loader.exec_module(pdf)


@pytest.fixture(autouse=True)
def isolated_app_environment(monkeypatch):
    """Override app-oriented conftest fixture: this service needs no settings."""
    def no_network(*args, **kwargs):
        raise AssertionError("PDF export must not access the network")
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket.socket, "connect", no_network)
    yield


def reader(data):
    pypdf = pytest.importorskip("pypdf", reason="Install pypdf in the dev venv to run PDF extraction assertions")
    return pypdf.PdfReader(BytesIO(data))


def text(data):
    return "\n".join(page.extract_text() for page in reader(data).pages)


def raster(width=20, height=30):
    output = BytesIO()
    PILImage.new("RGB", (width, height), "blue").save(output, format="PNG")
    return output.getvalue()


def parsed(content):
    parser = pdf._Parser()
    parser.feed(pdf.markdown(pdf._prepare(content), extensions=["tables", "fenced_code", "attr_list", "sane_lists"]))
    parser.close()
    return parser.root


def flowables(content, loader=None):
    return pdf._Renderer(loader).blocks(parsed(content).children)


def long_table(rows=50):
    return "| Actividad | Descripción | Valor |\n| :--- | --- | ---: |\n" + "\n".join(
        f"| Fila-{index:03d} | **Lectura** española con [enlace](https://example.invalid) y A\\|B | {index} |"
        for index in range(rows)
    )


def test_returns_complete_pdf_bytes_without_application():
    data = pdf.render_pdf("A & B <b>literal</b>", "# Unidad\n\nHola **mundo**.\n\n- Primero\n- Segundo")
    assert isinstance(data, bytes)
    assert data.startswith(b"%PDF-")
    assert data.rstrip().endswith(b"%%EOF")
    assert b"/Type /Page" in data


def test_spanish_accents_and_composed_unicode_are_extractable():
    data = pdf.render_pdf("Castellano", "áéíóú ü ñ Ñ ¿Qué? ¡Sí! € 1º\n\nCafe\u0301")
    extracted = text(data)
    for token in ("áéíóú", "ü", "ñ", "Ñ", "¿Qué?", "¡Sí!", "€", "1º", "Café"):
        assert token in extracted


def test_unknown_unicode_is_explicit_not_silently_lost():
    assert pdf._font_text("niño 🦉") == "niño [U+1F989]"


def test_title_never_interprets_reportlab_markup():
    extracted = text(pdf.render_pdf('A & B <img src="https://example.invalid/a.png"/>', "Texto"))
    assert "A & B <img" in extracted


def test_long_gfm_table_has_repeatable_header_and_no_dropped_rows():
    table = next(item for item in flowables(long_table()) if isinstance(item, LongTable))
    assert table.repeatRows == 1
    assert len(table._cellvalues) == 51
    assert len(table._cellvalues[-1]) == 3
    assert "Fila-049" in table._cellvalues[-1][0].text
    assert "A|B" in table._cellvalues[1][1].text
    assert pdf.render_pdf("Tabla larga", long_table()).startswith(b"%PDF-")


def test_long_table_pages_repeat_header_and_preserve_all_rows():
    document = reader(pdf.render_pdf("Tabla larga", long_table()))
    assert len(document.pages) >= 2
    pages = [page.extract_text() for page in document.pages]
    for page in pages:
        if "Fila-" in page:
            assert "Actividad" in page
            assert "Descripción" in page
    joined = "\n".join(pages)
    for index in range(50):
        assert joined.count(f"Fila-{index:03d}") == 1


def test_headings_lists_links_and_code_translate_to_safe_markup():
    items = flowables("#### Apartado\n\n5. cinco\n6. seis\n\n**fuerte** y *suave* y `x < y`\n\n[Web](https://example.invalid)\n\n```python\nprint('<img>')\n```")
    paragraphs = [item for item in items if isinstance(item, Paragraph)]
    markup = "\n".join(item.text for item in paragraphs)
    assert "5. cinco" in markup
    assert "6. seis" in markup
    assert "<b>fuerte</b>" in markup
    assert "<i>suave</i>" in markup
    assert 'name="Courier"' in markup
    assert "&lt;img&gt;" in markup
    assert any(item.style.name == "PDFHeading4" for item in paragraphs)
    assert 'href="https://example.invalid"' in markup


def test_http_link_creates_pdf_annotation_without_fetching():
    document = reader(pdf.render_pdf("Enlace", "[Recurso](https://example.invalid/material?a=1&b=2)"))
    annotations = [ref.get_object() for page in document.pages for ref in page.get("/Annots", [])]
    assert any(annotation.get("/A", {}).get("/URI") == "https://example.invalid/material?a=1&b=2" for annotation in annotations)


@pytest.mark.parametrize("marker", ["<!-- pagebreak -->", "<!-- PAGEBREAK -->", "[[pagebreak]]"])
def test_explicit_pagebreaks(marker):
    assert any(isinstance(item, PageBreak) for item in flowables(f"Antes\n\n{marker}\n\nDespués"))
    document = reader(pdf.render_pdf("Saltos", f"Antes\n\n{marker}\n\nDespués"))
    assert len(document.pages) == 2
    assert "Antes" in document.pages[0].extract_text()
    assert "Después" in document.pages[1].extract_text()


def test_code_markers_remain_literal_and_long_code_splits():
    content = "```\n<!-- pagebreak -->\n[[columns:2]]\n" + "x" * 500 + "\n" + "\n".join(f"línea {i}" for i in range(100)) + "\n```"
    items = flowables(content)
    assert not any(isinstance(item, PageBreak) for item in items)
    markup = "\n".join(item.text for item in items if isinstance(item, Paragraph))
    assert "[[columns:2]]" in markup
    assert "columnas aplanadas" not in markup
    assert pdf.render_pdf("Código", content).startswith(b"%PDF-")


@pytest.mark.parametrize("ending", ["\n[[/columns]]", ""])
def test_columns_flatten_extra_and_unclosed_bodies_without_truncation(ending):
    content = "[[columns:2]]\nINICIO\n[[col]]\nMEDIO\n[[col]]\nFINAL" + ending
    items = flowables(content)
    markup = "\n".join(item.text for item in items if isinstance(item, Paragraph))
    assert "columnas aplanadas" in markup
    assert all(token in markup for token in ("INICIO", "MEDIO", "FINAL"))
    assert pdf.render_pdf("Columnas", content).startswith(b"%PDF-")


def test_long_columns_preserve_end_on_actual_pages():
    content = "[[columns:2]]\n" + "\n\n".join(f"Izquierda-{i}" for i in range(60))
    content += "\n[[col]]\n" + "\n\n".join(f"Derecha-{i}" for i in range(60)) + "\n[[/columns]]"
    extracted = text(pdf.render_pdf("Columnas", content))
    assert "columnas aplanadas" in extracted
    assert "Izquierda-59" in extracted
    assert "Derecha-59" in extracted


def test_local_raster_scaled_and_embedded():
    calls = []
    def loader(path):
        calls.append(path)
        return raster(1500, 2000)
    items = flowables("![Esquema](./assets/esquema.png){: .doc-w-50 .doc-align-left}", loader)
    image = next(item for item in items if isinstance(item, Image))
    assert image.drawWidth <= pdf.CONTENT_WIDTH / 2
    assert image.drawHeight <= pdf.CONTENT_HEIGHT * 0.42
    assert image.hAlign == "LEFT"
    data = pdf.render_pdf("Imagen", "![Esquema](assets/esquema.png)", loader)
    assert b"/Subtype /Image" in data
    assert calls == ["assets/esquema.png", "assets/esquema.png"]


@pytest.mark.parametrize("path", [
    "https://example.invalid/a.png", "file:///etc/hosts", "//example.invalid/a.png",
    "assets/../private.png", "assets/%2e%2e/private.png", "assets/a%252e.png",
    "assets/a\\b.png", "assets/a.png?x=1", "data:image/png;base64,AAAA", "assets/./a.png",
    "assets/a.svg", "assets/a.SVG",
])
def test_unsafe_paths_and_svg_never_reach_loader(path):
    def loader(_path):
        pytest.fail("Forbidden resource was requested")
    result = pdf._Renderer(loader).image(pdf._Node("img", {"src": path, "alt": "Ejemplo"}))
    assert isinstance(result, Paragraph)
    assert "Imagen no disponible" in result.text


@pytest.mark.parametrize("data", [None, b"", b"not a png", b"\x89PNG\r\n\x1a\ntruncated", b'<svg><image href="https://example.invalid/a.png"/></svg>'])
def test_missing_and_corrupt_raster_are_visible_placeholders(data):
    output = pdf.render_pdf("Recursos", "![Foto](assets/foto.png)", lambda path: data)
    assert output.startswith(b"%PDF-")
    item = pdf._Renderer(lambda path: data).image(pdf._Node("img", {"src": "assets/foto.png"}))
    assert isinstance(item, Paragraph)
    assert "Imagen no disponible" in item.text


def test_loader_failure_does_not_abort_or_leak_exception():
    def loader(path):
        raise RuntimeError("secret-provider-detail")
    items = flowables("![Foto](assets/foto.png)", loader)
    assert any("no se pudo leer" in item.text for item in items if isinstance(item, Paragraph))
    assert not any("secret-provider-detail" in item.text for item in items if isinstance(item, Paragraph))
    assert pdf.render_pdf("Recursos", "![Foto](assets/foto.png)", loader).startswith(b"%PDF-")


def test_image_limits_use_placeholders_and_bounded_document(monkeypatch):
    monkeypatch.setattr(pdf, "MAX_IMAGE_BYTES", 5)
    result = pdf._Renderer(lambda path: b"123456").image(pdf._Node("img", {"src": "assets/a.png"}))
    assert "demasiado grande" in result.text
    monkeypatch.setattr(pdf, "MAX_IMAGES", 1)
    with pytest.raises(pdf.PDFExportError, match="Demasiadas imágenes"):
        pdf.render_pdf("Límite", "![a](assets/a.png)\n\n![b](assets/b.png)")


def test_pixel_budget_prevents_decode(monkeypatch):
    monkeypatch.setattr(pdf, "MAX_IMAGE_PIXELS", 10)
    result = pdf._Renderer(lambda path: raster()).image(pdf._Node("img", {"src": "assets/a.png"}))
    assert "dimensiones excesivas" in result.text


def test_long_cell_and_wide_tables_flatten_instead_of_layout_error():
    tall = "| Título | Otro |\n| --- | --- |\n| " + "palabra " * 1500 + "FIN-CELDA | final |"
    wide = "| " + " | ".join(f"C{i}" for i in range(9)) + " |\n| " + " | ".join(["---"] * 9) + " |\n| " + " | ".join(["valor"] * 9) + " |"
    for content in (tall, wide):
        items = flowables(content)
        assert not any(isinstance(item, LongTable) for item in items)
        assert "tabla aplanada" in items[0].text
        assert pdf.render_pdf("Tabla límite", content).startswith(b"%PDF-")
    assert "FIN-CELDA" in text(pdf.render_pdf("Tabla alta", tall))


def test_raw_active_html_and_reportlab_specific_tags_are_not_executed():
    content = '<script>SECRET_SCRIPT</script><style>SECRET_STYLE</style>\n\n<para><font name="nonexistent"><b>Texto</b></font></para>\n\n<a href="javascript:alert(1)">Seguro</a>\n\n<img src="https://example.invalid/a.png">'
    items = flowables(content)
    markup = "\n".join(item.text for item in items if isinstance(item, Paragraph))
    assert "SECRET_SCRIPT" not in markup
    assert "SECRET_STYLE" not in markup
    assert "javascript:" not in markup
    assert "nonexistent" not in markup
    assert pdf.render_pdf("Seguro", content).startswith(b"%PDF-")


def test_limits_fail_explicitly_not_partial_pdf(monkeypatch):
    monkeypatch.setattr(pdf, "MAX_CONTENT_BYTES", 10)
    with pytest.raises(pdf.PDFExportError, match="demasiado grande"):
        pdf.render_pdf("Test", "a" * 11)
    monkeypatch.setattr(pdf, "MAX_CONTENT_BYTES", 1_000_000)
    monkeypatch.setattr(pdf, "MAX_PAGES", 1)
    with pytest.raises(pdf.PDFExportError, match="250 páginas"):
        pdf.render_pdf("Test", "a\n\n[[pagebreak]]\n\nb")
    with pytest.raises(pdf.PDFExportError, match="complejo"):
        pdf.render_pdf("Test", "<div>" * 70 + "texto" + "</div>" * 70)


def test_empty_document_and_large_heading_export():
    assert pdf.render_pdf("Vacío", "").startswith(b"%PDF-")
    assert pdf.render_pdf("Encabezado", "# " + "palabra " * 1000).startswith(b"%PDF-")
