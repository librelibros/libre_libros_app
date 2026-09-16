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
    from app.services.pdf_export import render_pdf

    return render_pdf(book.title, content, asset_loader=asset_loader)


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
