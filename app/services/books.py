from io import BytesIO
from pathlib import Path

from markdown import markdown
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from slugify import slugify

from app.models import Book


def default_book_paths(course: str, subject: str, slug: str) -> tuple[str, str]:
    course_slug = slugify(course)
    subject_slug = slugify(subject)
    base = f"books/{course_slug}/{subject_slug}/{slug}"
    return f"{base}/book.md", f"{base}/assets"


def render_markdown_html(content: str) -> str:
    return markdown(
        content,
        extensions=["extra", "tables", "fenced_code", "toc"],
    )


def export_markdown_to_pdf(book: Book, content: str) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [Paragraph(book.title, styles["Title"]), Spacer(1, 12)]

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            story.append(Spacer(1, 8))
            continue
        if line.startswith("### "):
            story.append(Paragraph(line[4:], styles["Heading3"]))
        elif line.startswith("## "):
            story.append(Paragraph(line[3:], styles["Heading2"]))
        elif line.startswith("# "):
            story.append(Paragraph(line[2:], styles["Heading1"]))
        else:
            story.append(Paragraph(line, styles["BodyText"]))
        story.append(Spacer(1, 6))

    doc.build(story)
    return buffer.getvalue()


def sanitize_filename(filename: str) -> str:
    name = Path(filename).name
    return slugify(Path(name).stem) + Path(name).suffix.lower()

