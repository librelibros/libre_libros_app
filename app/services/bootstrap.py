from __future__ import annotations

from pathlib import Path

from slugify import slugify
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Book, RepositoryProvider, RepositorySource, Visibility


def _book_summary(markdown_path: Path) -> str | None:
    try:
        lines = markdown_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#") or line.startswith("![") or line.startswith("- "):
            continue
        return line[:280]
    return None


def sync_example_repository(db: Session) -> None:
    settings = get_settings()
    if not settings.example_repo_path:
        return

    repo_path = Path(settings.example_repo_path)
    books_root = repo_path / "books"
    if not books_root.exists():
        return

    repo_source = (
        db.query(RepositorySource)
        .filter(RepositorySource.slug == "repositorio-de-ejemplo")
        .first()
    )
    if not repo_source:
        repo_source = RepositorySource(
            name="Repositorio de ejemplo",
            slug="repositorio-de-ejemplo",
            provider=RepositoryProvider.local,
            default_branch="main",
            local_path=str(repo_path),
            is_public=True,
        )
        db.add(repo_source)
        db.flush()
    else:
        repo_source.local_path = str(repo_path)
        repo_source.provider = RepositoryProvider.local
        repo_source.default_branch = "main"
        repo_source.is_public = True

    discovered_paths: set[str] = set()
    for markdown_path in books_root.glob("*/*/*/book.md"):
        rel_path = markdown_path.relative_to(repo_path).as_posix()
        discovered_paths.add(rel_path)
        slug = markdown_path.parent.name
        subject = markdown_path.parent.parent.name.replace("-", " ").title()
        course = markdown_path.parent.parent.parent.name.title()
        title = slug.replace("-", " ").title()
        assets_path = markdown_path.parent.joinpath("assets").relative_to(repo_path).as_posix()

        existing_book = (
            db.query(Book)
            .filter(
                Book.repository_source_id == repo_source.id,
                Book.content_path == rel_path,
            )
            .first()
        )
        summary = _book_summary(markdown_path)

        if existing_book:
            existing_book.title = title
            existing_book.slug = slugify(title)
            existing_book.course = course
            existing_book.subject = subject
            existing_book.summary = summary
            existing_book.assets_path = assets_path
            existing_book.base_branch = "main"
            existing_book.visibility = Visibility.public
            existing_book.owner_user_id = None
            existing_book.organization_id = None
            continue

        db.add(
            Book(
                title=title,
                slug=slugify(title),
                course=course,
                subject=subject,
                summary=summary,
                visibility=Visibility.public,
                repository_source_id=repo_source.id,
                organization_id=None,
                owner_user_id=None,
                base_branch="main",
                content_path=rel_path,
                assets_path=assets_path,
            )
        )

    stale_books = (
        db.query(Book)
        .filter(Book.repository_source_id == repo_source.id)
        .all()
    )
    for book in stale_books:
        if book.content_path not in discovered_paths:
            db.delete(book)

    db.commit()
