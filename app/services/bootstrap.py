from __future__ import annotations

from slugify import slugify
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Book, RepositoryProvider, RepositorySource, Visibility
from app.services.repository.factory import repository_client_for


def _book_summary(markdown_content: str) -> str | None:
    for raw_line in markdown_content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#") or line.startswith("![") or line.startswith("- "):
            continue
        return line[:280]
    return None


def _upsert_repository_source(
    db: Session,
    *,
    source_slug: str,
    name: str,
    provider: RepositoryProvider,
    default_branch: str,
    is_public: bool,
    local_path: str | None = None,
    provider_url: str | None = None,
    repository_namespace: str | None = None,
    repository_name: str | None = None,
    service_username: str | None = None,
    service_token: str | None = None,
) -> RepositorySource:
    repo_source = db.query(RepositorySource).filter(RepositorySource.slug == source_slug).first()
    if not repo_source:
        repo_source = RepositorySource(
            name=name,
            slug=source_slug,
            provider=provider,
            default_branch=default_branch,
            is_public=is_public,
        )
        db.add(repo_source)
        db.flush()

    repo_source.name = name
    repo_source.provider = provider
    repo_source.default_branch = default_branch
    repo_source.is_public = is_public
    repo_source.local_path = local_path
    repo_source.provider_url = provider_url
    repo_source.repository_namespace = repository_namespace
    repo_source.repository_name = repository_name
    repo_source.service_username = service_username
    repo_source.service_token = service_token
    return repo_source


def _sync_catalog_from_source(db: Session, repo_source: RepositorySource) -> None:
    repo = repository_client_for(repo_source)
    book_paths = sorted(path for path in repo.list_files("books", repo_source.default_branch) if path.endswith("/book.md"))
    discovered_paths = set(book_paths)

    for rel_path in book_paths:
        markdown_content = repo.read_text(rel_path, repo_source.default_branch)
        if not markdown_content:
            continue

        parts = rel_path.split("/")
        if len(parts) < 5:
            continue

        slug = parts[-2]
        subject = parts[-3].replace("-", " ").title()
        course = parts[-4].replace("-", " ").title()
        title = slug.replace("-", " ").title()
        assets_path = "/".join(parts[:-1] + ["assets"])

        existing_book = (
            db.query(Book)
            .filter(
                Book.repository_source_id == repo_source.id,
                Book.content_path == rel_path,
            )
            .first()
        )
        summary = _book_summary(markdown_content)

        if existing_book:
            existing_book.title = title
            existing_book.slug = slugify(title)
            existing_book.course = course
            existing_book.subject = subject
            existing_book.summary = summary
            existing_book.assets_path = assets_path
            existing_book.base_branch = repo_source.default_branch
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
                base_branch=repo_source.default_branch,
                content_path=rel_path,
                assets_path=assets_path,
            )
        )

    stale_books = db.query(Book).filter(Book.repository_source_id == repo_source.id).all()
    for book in stale_books:
        if book.content_path not in discovered_paths:
            db.delete(book)


def _delete_repository_source(db: Session, repo_source: RepositorySource) -> None:
    for book in db.query(Book).filter(Book.repository_source_id == repo_source.id).all():
        db.delete(book)
    db.flush()
    db.delete(repo_source)


def _cleanup_legacy_bootstrap_sources(
    db: Session,
    *,
    active_slug: str,
    active_provider: RepositoryProvider,
) -> None:
    # When the debug stack switches from the legacy local example repository
    # to a remote provider bootstrap, keep a single source of truth.
    if active_provider == RepositoryProvider.local:
        return

    legacy_sources = (
        db.query(RepositorySource)
        .filter(
            RepositorySource.slug == "repositorio-de-ejemplo",
            RepositorySource.provider == RepositoryProvider.local,
        )
        .all()
    )
    for legacy_source in legacy_sources:
        if legacy_source.slug != active_slug:
            _delete_repository_source(db, legacy_source)


def sync_example_repository(db: Session) -> None:
    settings = get_settings()
    repo_source: RepositorySource | None = None

    if settings.bootstrap_repository_provider and settings.bootstrap_repository_name:
        provider = RepositoryProvider(settings.bootstrap_repository_provider)
        source_slug = settings.bootstrap_repository_slug or slugify(settings.bootstrap_repository_name)
        _cleanup_legacy_bootstrap_sources(
            db,
            active_slug=source_slug,
            active_provider=provider,
        )
        repo_source = _upsert_repository_source(
            db,
            source_slug=source_slug,
            name=settings.bootstrap_repository_name,
            provider=provider,
            default_branch=settings.bootstrap_repository_default_branch,
            is_public=settings.bootstrap_repository_public,
            provider_url=settings.bootstrap_repository_url,
            repository_namespace=settings.bootstrap_repository_namespace,
            repository_name=settings.bootstrap_repository_name_remote,
            service_username=settings.bootstrap_repository_username,
            service_token=settings.bootstrap_repository_token,
        )
    elif settings.example_repo_path:
        repo_source = _upsert_repository_source(
            db,
            source_slug="repositorio-de-ejemplo",
            name="Repositorio de ejemplo",
            provider=RepositoryProvider.local,
            default_branch="main",
            is_public=True,
            local_path=str(settings.example_repo_path),
        )

    if not repo_source:
        db.commit()
        return

    _sync_catalog_from_source(db, repo_source)
    db.commit()
