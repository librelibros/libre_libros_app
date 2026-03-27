from __future__ import annotations

import re
from markdown import markdown
from slugify import slugify


COLUMN_START_PATTERN = re.compile(r"^\s*\[\[columns:(?P<count>[23])\]\]\s*$", re.IGNORECASE)
COLUMN_SEPARATOR_PATTERN = re.compile(r"^\s*\[\[col\]\]\s*$", re.IGNORECASE)
COLUMN_END_PATTERN = re.compile(r"^\s*\[\[/columns\]\]\s*$", re.IGNORECASE)
WORKSHEET_TOKEN_PATTERN = re.compile(
    r"\[\[worksheet:(?P<slug>[A-Za-z0-9\-_]+)(?:\|(?P<label>[^\]]+))?\]\]",
    re.IGNORECASE,
)


def render_rich_markdown_html(content: str, worksheet_url_builder=None) -> str:
    fragments: list[str] = []
    buffer: list[str] = []
    lines = content.splitlines()
    index = 0

    def flush_buffer() -> None:
        if not buffer:
            return
        markdown_chunk = "\n".join(buffer).strip()
        buffer.clear()
        if markdown_chunk:
            fragments.append(_render_markdown_chunk(markdown_chunk, worksheet_url_builder))

    while index < len(lines):
        start_match = COLUMN_START_PATTERN.match(lines[index].strip())
        if not start_match:
            buffer.append(lines[index])
            index += 1
            continue

        flush_buffer()
        column_count = int(start_match.group("count"))
        parsed_columns, next_index = _parse_column_block(lines, index + 1)
        if parsed_columns is None:
            buffer.append(lines[index])
            index += 1
            continue

        fragments.append(_render_columns_html(parsed_columns, column_count, worksheet_url_builder))
        index = next_index

    flush_buffer()
    return "\n".join(fragment for fragment in fragments if fragment.strip())


def flatten_rich_markdown_for_pdf(content: str) -> str:
    lines = content.splitlines()
    flattened: list[str] = []
    index = 0

    while index < len(lines):
        start_match = COLUMN_START_PATTERN.match(lines[index].strip())
        if not start_match:
            flattened.append(_replace_worksheet_tokens_with_text(lines[index]))
            index += 1
            continue

        parsed_columns, next_index = _parse_column_block(lines, index + 1)
        if parsed_columns is None:
            flattened.append(_replace_worksheet_tokens_with_text(lines[index]))
            index += 1
            continue

        for column_index, column_content in enumerate(parsed_columns, start=1):
            section = column_content.strip()
            if not section:
                continue
            flattened.append(f"### Columna {column_index}")
            flattened.append("")
            flattened.extend(_replace_worksheet_tokens_with_text(line) for line in section.splitlines())
            flattened.append("")
        index = next_index

    return "\n".join(flattened)


def worksheet_snippet(slug: str, label: str | None = None) -> str:
    worksheet_slug = slugify(slug)
    worksheet_label = (label or slug.replace("-", " ").strip() or worksheet_slug).strip()
    return f"[[worksheet:{worksheet_slug}|{worksheet_label}]]"


def columns_snippet(column_count: int) -> str:
    safe_count = 3 if column_count == 3 else 2
    blocks = [
        f"### Columna {index}\n\nEscribe aqui el contenido de la columna {index}."
        for index in range(1, safe_count + 1)
    ]
    return f"[[columns:{safe_count}]]\n" + "\n[[col]]\n".join(blocks) + "\n[[/columns]]"


def _render_markdown_chunk(chunk: str, worksheet_url_builder=None) -> str:
    prepared_chunk = _replace_worksheet_tokens_with_links(chunk, worksheet_url_builder)
    return markdown(
        prepared_chunk,
        extensions=["extra", "tables", "fenced_code", "toc", "attr_list"],
    )


def _render_columns_html(columns: list[str], column_count: int, worksheet_url_builder=None) -> str:
    rendered_columns: list[str] = []
    for column in columns:
        inner_markdown = column.strip()
        if not inner_markdown:
            inner_markdown = "_Columna vacia_"
        rendered_columns.append(
            "\n".join(
                [
                    '<div class="doc-column">',
                    _render_markdown_chunk(inner_markdown, worksheet_url_builder),
                    "</div>",
                ]
            )
        )
    return "\n".join(
        [
            f'<div class="doc-columns doc-columns-{column_count}">',
            *rendered_columns,
            "</div>",
        ]
    )


def _parse_column_block(lines: list[str], start_index: int) -> tuple[list[str], int] | tuple[None, None]:
    columns: list[str] = []
    current: list[str] = []
    index = start_index

    while index < len(lines):
        raw_line = lines[index]
        stripped = raw_line.strip()
        if COLUMN_SEPARATOR_PATTERN.match(stripped):
            columns.append("\n".join(current).strip())
            current = []
            index += 1
            continue
        if COLUMN_END_PATTERN.match(stripped):
            columns.append("\n".join(current).strip())
            return columns, index + 1
        current.append(raw_line)
        index += 1

    return None, None


def _replace_worksheet_tokens_with_links(content: str, worksheet_url_builder=None) -> str:
    def replace(match: re.Match[str]) -> str:
        slug = slugify(match.group("slug"))
        label = (match.group("label") or match.group("slug").replace("-", " ")).strip()
        href = worksheet_url_builder(slug) if worksheet_url_builder else f"#worksheet-{slug}"
        return f'[{label}]({href}){{: .worksheet-link}}'

    return WORKSHEET_TOKEN_PATTERN.sub(replace, content)


def _replace_worksheet_tokens_with_text(content: str) -> str:
    def replace(match: re.Match[str]) -> str:
        label = (match.group("label") or match.group("slug").replace("-", " ")).strip()
        return f"Ficha: {label}"

    return WORKSHEET_TOKEN_PATTERN.sub(replace, content)
