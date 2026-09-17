import re
from html import escape, unescape
from urllib.parse import quote, urlencode

import bleach
from slugify import slugify

from app.services.book_content import render_rich_markdown_html
from app.services.books import PAGEBREAK_PATTERN

PAGEBREAK_MARKER = "<!-- pagebreak -->"
HEADING_PATTERN = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.*?)(?:\s+\{#(?P<anchor>[A-Za-z0-9\-_]+)\})?\s*$")

ALLOWED_TAGS = bleach.sanitizer.ALLOWED_TAGS.union(
    {"p", "pre", "hr", "h1", "h2", "h3", "h4", "h5", "h6", "span", "img", "audio", "source", "div",
     "table", "thead", "tbody", "tr", "th", "td", "s", "del"}
)
ALLOWED_ATTRIBUTES = {
    "*": ["class", "id"],
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt"],
    "audio": ["controls", "src"],
    "source": ["src", "type"],
}


def markdown_preview(content: str, worksheet_url_builder=None) -> str:
    html = render_rich_markdown_html(content, worksheet_url_builder=worksheet_url_builder)
    return bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)


def build_book_document(content: str, book_id: int | None = None, branch_name: str | None = None) -> dict:
    pages: list[dict] = []
    toc: list[dict] = []
    used_anchors: set[str] = set()
    page_chunks = _split_markdown_pages(content)

    for page_number, page_markdown in enumerate(page_chunks, start=1):
        prepared_markdown, page_toc, page_label = _prepare_page_markdown(page_markdown, page_number, used_anchors)
        html = markdown_preview(
            prepared_markdown,
            worksheet_url_builder=(
                (lambda worksheet_slug, current_book_id=book_id, current_branch=branch_name: _worksheet_url(current_book_id, worksheet_slug, current_branch))
                if book_id and branch_name
                else None
            ),
        )
        if book_id and branch_name:
            html = _rewrite_book_asset_urls(html, book_id=book_id, branch_name=branch_name)
        pages.append(
            {
                "number": page_number,
                "label": page_label,
                "html": html,
            }
        )
        toc.extend(page_toc)

    return {
        "pages": pages,
        "toc": toc,
        "total_pages": len(pages),
        "pagebreak_marker": PAGEBREAK_MARKER,
    }


def book_markdown_preview(content: str, book_id: int, branch_name: str) -> str:
    html = markdown_preview(
        content,
        worksheet_url_builder=lambda worksheet_slug: _worksheet_url(book_id, worksheet_slug, branch_name),
    )
    return _rewrite_book_asset_urls(html, book_id=book_id, branch_name=branch_name)


def _split_markdown_pages(content: str) -> list[str]:
    pages = [chunk.strip() for chunk in PAGEBREAK_PATTERN.split(content) if chunk.strip()]
    return pages or [content.strip() or "# Documento vacio"]


def _prepare_page_markdown(page_markdown: str, page_number: int, used_anchors: set[str]) -> tuple[str, list[dict], str]:
    prepared_lines: list[str] = []
    toc: list[dict] = []
    page_label = f"Pagina {page_number}"

    for raw_line in page_markdown.splitlines():
        match = HEADING_PATTERN.match(raw_line.strip())
        if not match:
            prepared_lines.append(raw_line)
            continue

        hashes = match.group("hashes")
        title = match.group("title").strip()
        anchor = match.group("anchor") or _unique_anchor(f"page-{page_number}-{slugify(title) or 'seccion'}", used_anchors)
        used_anchors.add(anchor)
        prepared_lines.append(f"{hashes} {title} {{#{anchor}}}")
        toc.append(
            {
                "title": title,
                "level": len(hashes),
                "page_number": page_number,
                "anchor": anchor,
            }
        )
        if page_label == f"Pagina {page_number}":
            page_label = title

    return "\n".join(prepared_lines), toc, page_label


def _unique_anchor(candidate: str, used_anchors: set[str]) -> str:
    anchor = candidate
    suffix = 2
    while anchor in used_anchors:
        anchor = f"{candidate}-{suffix}"
        suffix += 1
    return anchor


def _rewrite_book_asset_urls(html: str, book_id: int, branch_name: str) -> str:
    """Rewrite relative asset URLs into authenticated, branch-scoped book URLs.

    Runs on sanitized HTML only. Attribute values are parsed (unescaped once) and
    re-encoded safely, so a branch name containing quotes or markup can never
    inject attributes or tags after the sanitization step (B02).
    """
    asset_pattern = re.compile(r'(?P<attr>(?:src|href))="(?P<path>(?:\./)?assets/[^"]*)"')

    def replace(match: re.Match[str]) -> str:
        attr = match.group("attr")
        rel_path = unescape(match.group("path")).removeprefix("./")
        if not rel_path:
            return match.group(0)
        query: dict[str, str] = {}
        if branch_name:
            query["branch"] = branch_name
        suffix = f"?{urlencode(query)}" if query else ""
        url = f"/books/{int(book_id)}/{quote(rel_path)}{suffix}"
        return f'{attr}="{escape(url, quote=True)}"'

    # All rewritten attributes pass through the final sanitizer as well.
    return bleach.clean(asset_pattern.sub(replace, html), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)


def _worksheet_url(book_id: int, worksheet_slug: str, branch_name: str) -> str:
    query = {"branch": branch_name} if branch_name else {}
    suffix = f"?{urlencode(query)}" if query else ""
    return f"/books/{int(book_id)}/worksheets/{quote(worksheet_slug)}{suffix}"
