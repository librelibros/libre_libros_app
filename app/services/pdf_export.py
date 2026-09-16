"""Bounded, offline Markdown -> ReportLab PDF. No app/config/database imports."""
from __future__ import annotations

import re
import unicodedata
import warnings
from collections.abc import Callable
from dataclasses import dataclass, field
from html import escape
from html.parser import HTMLParser
from io import BytesIO
from urllib.parse import urlsplit

from markdown import markdown
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable, Image, LongTable, PageBreak, Paragraph, SimpleDocTemplate,
    Spacer, TableStyle,
)
from reportlab.platypus.doctemplate import LayoutError

MAX_CONTENT_BYTES = 1_000_000
MAX_IMAGE_BYTES = 10_000_000
MAX_IMAGE_PIXELS = 16_000_000
MAX_IMAGE_TOTAL_BYTES = 40_000_000
MAX_IMAGE_TOTAL_PIXELS = 32_000_000
MAX_IMAGES = 64
MAX_NODES = 30_000
MAX_DEPTH = 64
MAX_TABLE_CELLS = 10_000
MAX_PAGES = 250
PAGE_WIDTH, PAGE_HEIGHT = A4
CONTENT_WIDTH = PAGE_WIDTH - 96
CONTENT_HEIGHT = PAGE_HEIGHT - 112


class PDFExportError(ValueError):
    """A documented input/layout limit; callers should return a recoverable error."""


@dataclass
class _Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[_Node | str] = field(default_factory=list)


class _Parser(HTMLParser):
    """Parse inert HTML; never pass user tags/attributes to ReportLab's parser."""

    VOID = {"img", "br", "hr", "source", "input", "meta", "link", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("root")
        self.stack = [self.root]
        self.count = 0

    def handle_starttag(self, tag, attrs):
        self.count += 1
        if self.count > MAX_NODES or len(self.stack) >= MAX_DEPTH:
            raise PDFExportError("Documento demasiado complejo para exportar a PDF.")
        node = _Node(tag, {key: value or "" for key, value in attrs})
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)

    def handle_comment(self, data):
        if data.strip().lower() == "pagebreak":
            self.stack[-1].children.append(_Node("pagebreak"))


def _text(node: _Node | str) -> str:
    if isinstance(node, str):
        return node
    if node.tag in {"script", "style", "iframe", "object", "svg"}:
        return ""
    return "".join(_text(child) for child in node.children)


def _prepare(content: str) -> str:
    """Interpret custom standalone markers, but not literal fenced/indented code."""
    output = []
    fence = None
    for line in content.splitlines():
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if marker:
            run = marker[1]
            if fence is None:
                fence = run
            elif run[0] == fence[0] and len(run) >= len(fence) and not marker[2].strip():
                fence = None
            output.append(line)
            continue
        if fence or line.startswith(("    ", "\t")):
            output.append(line)
            continue
        token = line.strip().lower()
        if re.fullmatch(r"\[\[columns:[23]\]\]", token):
            output.append("\n**Aviso PDF: columnas aplanadas en orden de lectura; no se conserva la maquetación lateral.**\n")
        elif token == "[[col]]":
            output.append("\n**Columna siguiente**\n")
        elif token == "[[/columns]]":
            output.append("\n")
        elif token == "[[pagebreak]]" or re.fullmatch(r"<!--\s*pagebreak\s*-->", token):
            output.append("\n<!-- pagebreak -->\n")
        else:
            line = re.sub(
                r"\[\[worksheet:([A-Za-z0-9_-]+)(?:\|([^\]]+))?\]\]",
                lambda match: "Ficha (no incluida): " + (match[2] or match[1]),
                line, flags=re.IGNORECASE,
            )
            output.append(line)
    return "\n".join(output)


def _font_text(value: str) -> str:
    # Standard PDF fonts cover Spanish/WinAnsi, not arbitrary Unicode. Preserve
    # unsupported code points visibly rather than silently emitting black squares.
    result = []
    for character in unicodedata.normalize("NFC", value):
        if ord(character) < 32 and character not in "\n\t\r":
            continue
        try:
            character.encode("cp1252")
            result.append(character)
        except UnicodeEncodeError:
            result.append(f"[U+{ord(character):04X}]")
    return "".join(result)


def _local_asset(path: str) -> str | None:
    path = path.removeprefix("./")
    if not path.startswith("assets/") or any(char in path for char in "\\%?#:"):
        return None
    if any(ord(char) < 32 for char in path):
        return None
    if any(part in {"", ".", ".."} for part in path.split("/")):
        return None
    return path


def _safe_link(value: str) -> str | None:
    if any(ord(char) < 32 for char in value):
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme in {"https", "http"} and parsed.hostname and not parsed.username:
            return value
        if parsed.scheme == "mailto" and parsed.path and not parsed.query:
            return value
    except ValueError:
        pass
    return None


class _Renderer:
    def __init__(self, asset_loader):
        self.asset_loader = asset_loader
        self.image_count = 0
        self.image_bytes = 0
        self.image_pixels = 0
        styles = getSampleStyleSheet()
        self.body = ParagraphStyle("PDFBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=10, leading=14, spaceAfter=7, splitLongWords=1)
        self.title = ParagraphStyle("PDFTitle", parent=styles["Title"], splitLongWords=1)
        self.headings = {
            f"h{level}": ParagraphStyle(f"PDFHeading{level}", parent=self.body, fontName="Helvetica-Bold", fontSize=max(11, 20 - level * 2), leading=max(15, 24 - level * 2), spaceBefore=10, keepWithNext=False)
            for level in range(1, 7)
        }
        self.note = ParagraphStyle("PDFNote", parent=self.body, textColor=colors.HexColor("#8b2929"))
        self.cell = ParagraphStyle("PDFCell", parent=self.body, fontSize=9, leading=12, spaceAfter=0)
        self.code = ParagraphStyle("PDFCode", parent=self.body, fontName="Courier", fontSize=8, leading=11, backColor=colors.HexColor("#f3f3f3"))

    def paragraph(self, text, style=None):
        return Paragraph(text or "&#160;", style or self.body)

    def inline(self, node):
        if isinstance(node, str):
            return escape(_font_text(node))
        tag = node.tag
        if tag in {"script", "style", "iframe", "object", "svg"}:
            return "[Contenido activo omitido]"
        if tag == "img":
            return escape(_font_text("[Imagen: " + node.attrs.get("alt", "sin descripción") + "]"))
        if tag in {"audio", "video"}:
            return "[Multimedia no incluida en PDF]"
        if tag == "br":
            return "<br/>"
        content = "".join(self.inline(child) for child in node.children)
        mapping = {"strong": "b", "b": "b", "em": "i", "i": "i", "s": "strike", "del": "strike", "code": "font"}
        if tag in mapping:
            if tag == "code":
                return f'<font name="Courier">{content}</font>'
            safe_tag = mapping[tag]
            return f"<{safe_tag}>{content}</{safe_tag}>"
        if tag == "a":
            href = _safe_link(node.attrs.get("href", ""))
            if href:
                return f'<link href="{escape(href, quote=True)}" color="#184a80">{content}</link>'
        return content

    def images(self, node):
        for child in node.children:
            if isinstance(child, _Node):
                if child.tag == "img":
                    yield child
                elif child.tag not in {"script", "style", "svg", "iframe", "object"}:
                    yield from self.images(child)

    def image(self, node):
        self.image_count += 1
        if self.image_count > MAX_IMAGES:
            raise PDFExportError("Demasiadas imágenes para un único PDF (máximo 64).")
        path = _local_asset(node.attrs.get("src", ""))
        label = node.attrs.get("alt", "") or "sin descripción"

        def missing(reason):
            return self.paragraph(escape(_font_text(f"Imagen no disponible ({label}): {reason}.")), self.note)

        if not path:
            return missing("solo se permiten rutas locales assets/ sin traversal")
        if path.lower().endswith(".svg"):
            return missing("SVG no admitido; utilizar PNG o JPEG")
        if not self.asset_loader:
            return missing("no hay lector de recursos")
        try:
            data = self.asset_loader(path)
            if not data:
                return missing("archivo ausente")
            if not isinstance(data, bytes) or len(data) > MAX_IMAGE_BYTES:
                return missing("archivo demasiado grande o no válido")
            self.image_bytes += len(data)
            if self.image_bytes > MAX_IMAGE_TOTAL_BYTES:
                raise PDFExportError("Los recursos del PDF superan el límite total de 40 MB.")
            with warnings.catch_warnings():
                warnings.simplefilter("error", PILImage.DecompressionBombWarning)
                with PILImage.open(BytesIO(data)) as source:
                    if source.format not in {"PNG", "JPEG", "GIF", "WEBP"}:
                        return missing("formato raster no admitido")
                    width, height = source.size
                    if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                        return missing("dimensiones excesivas o inválidas")
                    self.image_pixels += width * height
                    if self.image_pixels > MAX_IMAGE_TOTAL_PIXELS:
                        raise PDFExportError("Los recursos del PDF superan el límite total de 32 millones de píxeles.")
                    source.verify()
                with PILImage.open(BytesIO(data)) as source:
                    source.seek(0)
                    source.load()
                    normalized = source.convert("RGB" if source.mode == "RGB" else "RGBA")
                    normalized_data = BytesIO()
                    normalized.save(normalized_data, format="PNG")
            fraction = 1.0
            classes = node.attrs.get("class", "").split()
            for size in (33, 50, 66):
                if f"doc-w-{size}" in classes:
                    fraction = size / 100
                    break
            scale = min(CONTENT_WIDTH * fraction / width, CONTENT_HEIGHT * 0.42 / height, 1)
            result = Image(BytesIO(normalized_data.getvalue()), width=width * scale, height=height * scale)
            result.hAlign = "LEFT" if "doc-align-left" in classes else "RIGHT" if "doc-align-right" in classes else "CENTER"
            return result
        except PDFExportError:
            raise
        except Exception:
            # Includes loader errors and corrupt raster data; never disclose a
            # provider exception, filesystem path or credential in the PDF.
            return missing("no se pudo leer o decodificar el archivo")

    def table(self, node):
        rows = []
        has_header = False
        combined = False
        def collect(parent):
            nonlocal has_header, combined
            for child in parent.children:
                if not isinstance(child, _Node):
                    continue
                if child.tag == "tr":
                    cells = [cell for cell in child.children if isinstance(cell, _Node) and cell.tag in {"td", "th"}]
                    if cells:
                        has_header |= not rows and any(cell.tag == "th" for cell in cells)
                        combined |= any(cell.attrs.get("colspan", "1") != "1" or cell.attrs.get("rowspan", "1") != "1" for cell in cells)
                        rows.append(cells)
                elif child.tag in {"thead", "tbody", "tfoot"}:
                    collect(child)
        collect(node)
        if not rows:
            return []
        count = max(len(row) for row in rows)
        if sum(len(row) for row in rows) > MAX_TABLE_CELLS:
            raise PDFExportError("Tabla demasiado grande (máximo 10000 celdas).")
        data = [[self.paragraph(self.inline(cell), self.cell) for cell in row] + [self.paragraph("", self.cell)] * (count - len(row)) for row in rows]
        column_width = CONTENT_WIDTH / count
        tall = count > 8 or combined
        if not tall:
            heights = [max(cell.wrap(column_width - 12, CONTENT_HEIGHT)[1] for cell in row) + 12 for row in data]
            header_height = heights[0] if has_header else 0
            tall = any(height + header_height > CONTENT_HEIGHT - 24 for height in heights)
        if tall:
            output = [self.paragraph("Aviso PDF: tabla aplanada por anchura, altura o celdas combinadas; se conservan todas las celdas en orden.", self.note)]
            for index, row in enumerate(rows, 1):
                output.append(self.paragraph(f"Fila {index}", self.headings["h4"]))
                for cell_index, cell in enumerate(row, 1):
                    output.append(self.paragraph(f"<b>Celda {cell_index}:</b> " + self.inline(cell)))
                    output.extend(self.image(image) for image in self.images(cell))
            return output
        table = LongTable(data, colWidths=[column_width] * count, repeatRows=1 if has_header else 0, hAlign="LEFT", splitByRow=1)
        commands = [
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#888888")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]
        if has_header:
            commands.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf3")))
        table.setStyle(TableStyle(commands))
        output = [table, Spacer(1, 8)]
        images = list(self.images(node))
        if images:
            output.append(self.paragraph("Aviso PDF: las imágenes de la tabla se muestran a continuación, en orden de celdas.", self.note))
            output.extend(self.image(image) for image in images)
        return output

    def blocks(self, children, depth=0):
        output = []
        for node in children:
            if isinstance(node, str):
                if node.strip():
                    output.append(self.paragraph(self.inline(node)))
                continue
            tag = node.tag
            if tag == "pagebreak":
                output.append(PageBreak())
            elif tag == "hr":
                output.extend([HRFlowable(width="100%", spaceAfter=8), Spacer(1, 4)])
            elif tag == "table":
                output.extend(self.table(node))
            elif tag == "img":
                output.append(self.image(node))
            elif tag == "pre":
                # Individual wrapped lines can split across pages, unlike a
                # KeepTogether/Preformatted block higher than the frame.
                for line in _text(node).expandtabs(4).splitlines() or [""]:
                    text = escape(_font_text(line)).replace(" ", "&#160;")
                    output.append(self.paragraph(text, self.code))
            elif tag in {"ul", "ol"}:
                try:
                    start = int(node.attrs.get("start", "1"))
                except ValueError:
                    start = 1
                for index, item in enumerate(child for child in node.children if isinstance(child, _Node) and child.tag == "li"):
                    # Tight Markdown lists contain inline nodes directly in li;
                    # keep emphasis/links within their paragraph instead of
                    # emitting a new block for each mark.
                    children = []
                    inline_children = []
                    for child in item.children:
                        if isinstance(child, _Node) and child.tag in {"p", "ul", "ol", "pre", "table", "blockquote"}:
                            if inline_children:
                                children.append(_Node("p", children=inline_children))
                                inline_children = []
                            children.append(child)
                        else:
                            inline_children.append(child)
                    if inline_children:
                        children.append(_Node("p", children=inline_children))
                    parts = self.blocks(children, depth + 1)
                    prefix = f"{start + index}. " if tag == "ol" else "• "
                    style = ParagraphStyle(f"PDFList{depth}", parent=self.body, leftIndent=min(depth + 1, 8) * 14)
                    if parts and isinstance(parts[0], Paragraph):
                        parts[0] = self.paragraph(escape(prefix) + parts[0].text, style)
                    else:
                        parts.insert(0, self.paragraph(prefix, style))
                    output.extend(parts)
            elif tag in {"p", "h1", "h2", "h3", "h4", "h5", "h6"}:
                output.append(self.paragraph(self.inline(node), self.headings.get(tag, self.body)))
                output.extend(self.image(image) for image in self.images(node))
            elif tag in {"script", "style", "iframe", "object", "svg", "audio", "video"}:
                output.append(self.paragraph(self.inline(node), self.note))
            elif tag in {"root", "div", "section", "article", "blockquote", "li"}:
                output.extend(self.blocks(node.children, depth))
            else:
                output.append(self.paragraph(self.inline(node)))
        return output


def render_pdf(
    title: str,
    content: str,
    asset_loader: Callable[[str], bytes] | None = None,
) -> bytes:
    """Return A4 PDF bytes from Markdown and optional authorized local assets.

    Only the callback accesses asset bytes. It must enforce book/revision access
    and confinement; this module never fetches URLs or opens filesystem paths.
    Unsupported layouts produce visible notes. Size/complexity limits raise
    PDFExportError for the caller to map to a recoverable response.
    """
    if len(content.encode("utf-8")) > MAX_CONTENT_BYTES or len(title) > 2000:
        raise PDFExportError("Documento o título demasiado grande para exportar a PDF.")
    html = markdown(_prepare(content), extensions=["tables", "fenced_code", "attr_list", "sane_lists"])
    parser = _Parser()
    parser.feed(html)
    parser.close()
    renderer = _Renderer(asset_loader)
    story = [renderer.paragraph(escape(_font_text(title)), renderer.title)]
    story.extend(renderer.blocks(parser.root.children))
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=48, rightMargin=48, topMargin=56, bottomMargin=56, title=_font_text(title), author="Libre Libros")

    def page_number(canvas, doc):
        if doc.page > MAX_PAGES:
            raise PDFExportError("El documento supera el máximo de 250 páginas.")
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(PAGE_WIDTH - 48, 30, f"Página {doc.page}")
        canvas.restoreState()

    try:
        document.build(story, onFirstPage=page_number, onLaterPages=page_number)
    except LayoutError as exc:
        raise PDFExportError("No se pudo distribuir el contenido en A4; simplifica el bloque indicado antes de exportar.") from exc
    return buffer.getvalue()
