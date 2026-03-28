import re
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from markdown import markdown
from PIL import Image as PILImage
from PIL import ImageFile
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image as PDFImage
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer
from slugify import slugify
from svglib.svglib import svg2rlg

from app.models import Book
from app.services.book_content import flatten_rich_markdown_for_pdf

PAGEBREAK_PATTERN = re.compile(r"^\s*(?:<!--\s*pagebreak\s*-->|\[\[pagebreak\]\])\s*$", re.IGNORECASE | re.MULTILINE)
MARKDOWN_IMAGE_PATTERN = re.compile(
    r'^!\[(?P<alt>[^\]]*)\]\((?P<path>[^)\s]+)(?:\s+"[^"]*")?\)\s*(?:\{:\s*(?P<attrs>[^}]*)\})?\s*$'
)
MARKDOWN_ORDERED_ITEM_PATTERN = re.compile(r"^(?P<index>\d+)\.\s+(?P<body>.+)$")
MARKDOWN_UNORDERED_ITEM_PATTERN = re.compile(r"^[-*]\s+(?P<body>.+)$")
ImageFile.LOAD_TRUNCATED_IMAGES = True


def default_book_paths(course: str, subject: str, slug: str) -> tuple[str, str]:
    course_slug = slugify(course)
    subject_slug = slugify(subject)
    base = f"books/{course_slug}/{subject_slug}/{slug}"
    return f"{base}/book.md", f"{base}/assets"


def render_markdown_html(content: str) -> str:
    return markdown(
        content,
        extensions=["extra", "tables", "fenced_code", "toc", "attr_list"],
    )


def export_markdown_to_pdf(
    book: Book,
    content: str,
    asset_loader: Callable[[str], bytes] | None = None,
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=48, rightMargin=48, topMargin=56, bottomMargin=56)
    styles = getSampleStyleSheet()
    body_style = ParagraphStyle("BookBody", parent=styles["BodyText"], leading=16, spaceAfter=0)
    list_style = ParagraphStyle("BookList", parent=body_style, leftIndent=16, firstLineIndent=-10)
    caption_style = ParagraphStyle(
        "BookCaption",
        parent=styles["Italic"],
        fontSize=9,
        leading=11,
        alignment=1,
        textColor="#5d708b",
    )
    fallback_style = ParagraphStyle("BookFallback", parent=body_style, textColor="#9f2d37")
    story = [Paragraph(book.title, styles["Title"]), Spacer(1, 12)]
    image_max_width = doc.width
    image_max_height = doc.height * 0.42

    for raw_line in flatten_rich_markdown_for_pdf(content).splitlines():
        line = raw_line.strip()
        if PAGEBREAK_PATTERN.match(line):
            story.append(PageBreak())
            continue
        if not line:
            story.append(Spacer(1, 8))
            continue
        image_match = MARKDOWN_IMAGE_PATTERN.match(line)
        if image_match:
            story.extend(
                _build_pdf_image_block(
                    alt_text=image_match.group("alt").strip(),
                    asset_path=image_match.group("path").strip(),
                    asset_loader=asset_loader,
                    max_width=_image_width_from_attrs(image_match.group("attrs"), image_max_width),
                    max_height=image_max_height,
                    caption_style=caption_style,
                    fallback_style=fallback_style,
                )
            )
            continue
        if line.startswith("### "):
            story.append(Paragraph(escape(line[4:]), styles["Heading3"]))
        elif line.startswith("## "):
            story.append(Paragraph(escape(line[3:]), styles["Heading2"]))
        elif line.startswith("# "):
            story.append(Paragraph(escape(line[2:]), styles["Heading1"]))
        elif unordered_match := MARKDOWN_UNORDERED_ITEM_PATTERN.match(line):
            story.append(Paragraph(f"• {escape(unordered_match.group('body'))}", list_style))
        elif ordered_match := MARKDOWN_ORDERED_ITEM_PATTERN.match(line):
            story.append(Paragraph(f"{ordered_match.group('index')}. {escape(ordered_match.group('body'))}", list_style))
        else:
            story.append(Paragraph(escape(line), body_style))
        story.append(Spacer(1, 6))

    doc.build(story)
    return buffer.getvalue()


def sanitize_filename(filename: str) -> str:
    name = Path(filename).name
    return slugify(Path(name).stem) + Path(name).suffix.lower()


def _build_pdf_image_block(
    alt_text: str,
    asset_path: str,
    asset_loader: Callable[[str], bytes] | None,
    max_width: float,
    max_height: float,
    caption_style: ParagraphStyle,
    fallback_style: ParagraphStyle,
):
    if asset_loader is None:
        return [Paragraph(f"Imagen omitida en PDF: {escape(asset_path)}", fallback_style), Spacer(1, 10)]

    asset_bytes = asset_loader(asset_path)
    if not asset_bytes:
        return [Paragraph(f"Imagen no encontrada: {escape(asset_path)}", fallback_style), Spacer(1, 10)]

    try:
        image_flowable = _build_pdf_image_flowable(asset_path, asset_bytes, max_width=max_width, max_height=max_height)
    except Exception:
        return [Paragraph(f"No se pudo renderizar la imagen: {escape(asset_path)}", fallback_style), Spacer(1, 10)]

    items = [image_flowable]
    if alt_text:
        items.extend([Spacer(1, 6), Paragraph(escape(alt_text), caption_style)])
    items.append(Spacer(1, 12))
    return [KeepTogether(items)]


def _build_pdf_image_flowable(asset_path: str, asset_bytes: bytes, max_width: float, max_height: float):
    suffix = Path(asset_path).suffix.lower()
    if suffix == ".svg":
        drawing = svg2rlg(BytesIO(asset_bytes))
        if drawing is None:
            raise ValueError("SVG drawing could not be parsed")
        width, height = _scaled_dimensions(drawing.width, drawing.height, max_width, max_height)
        scale_x = width / drawing.width if drawing.width else 1
        scale_y = height / drawing.height if drawing.height else 1
        drawing.scale(scale_x, scale_y)
        drawing.width = width
        drawing.height = height
        drawing.hAlign = "CENTER"
        return drawing

    normalized_bytes = _normalize_raster_asset(asset_bytes)
    source = BytesIO(normalized_bytes)
    reader = ImageReader(source)
    original_width, original_height = reader.getSize()
    width, height = _scaled_dimensions(original_width, original_height, max_width, max_height)
    image = PDFImage(BytesIO(normalized_bytes), width=width, height=height)
    image.hAlign = "CENTER"
    return image


def _normalize_raster_asset(asset_bytes: bytes) -> bytes:
    with PILImage.open(BytesIO(asset_bytes)) as image:
        image.load()
        normalized = image.convert("RGBA") if image.mode not in {"RGB", "RGBA"} else image.copy()

    buffer = BytesIO()
    normalized.save(buffer, format="PNG")
    return buffer.getvalue()


def _scaled_dimensions(original_width: float, original_height: float, max_width: float, max_height: float) -> tuple[float, float]:
    if original_width <= 0 or original_height <= 0:
        raise ValueError("Invalid asset dimensions")
    scale = min(max_width / original_width, max_height / original_height, 1)
    return original_width * scale, original_height * scale


def _image_width_from_attrs(attrs: str | None, base_width: float) -> float:
    if not attrs:
        return base_width
    if ".doc-w-33" in attrs:
        return base_width * 0.33
    if ".doc-w-50" in attrs:
        return base_width * 0.5
    if ".doc-w-66" in attrs:
        return base_width * 0.66
    return base_width
