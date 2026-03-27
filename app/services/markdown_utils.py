import bleach

from app.services.books import render_markdown_html

ALLOWED_TAGS = bleach.sanitizer.ALLOWED_TAGS.union(
    {"p", "pre", "hr", "h1", "h2", "h3", "h4", "h5", "h6", "span", "img", "audio", "source"}
)
ALLOWED_ATTRIBUTES = {
    "*": ["class", "id"],
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt"],
    "audio": ["controls"],
    "source": ["src", "type"],
}


def markdown_preview(content: str) -> str:
    html = render_markdown_html(content)
    return bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)

