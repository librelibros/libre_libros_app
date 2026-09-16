"""B01 regressions: generated canaries only, no application startup or seed repo."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture(autouse=True)
def isolated_app_environment(tmp_path, monkeypatch):
    # Override the shared fixture: these tests own all configuration and data.
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            del sys.modules[name]
    for key in list(os.environ):
        if key.startswith(("LIBRE_LIBROS_", "SUPABASE_", "GIT_")):
            monkeypatch.delenv(key)
    monkeypatch.setenv("LIBRE_LIBROS_ENV_FILE", "")
    monkeypatch.setenv("LIBRE_LIBROS_DATABASE_URL", "sqlite://")
    monkeypatch.setenv("LIBRE_LIBROS_REPOS_ROOT", str(tmp_path / "repos"))
    monkeypatch.setenv("LIBRE_LIBROS_SECRET_KEY", "isolated-test-key-not-for-production")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    empty_config = tmp_path / "empty-git-config"
    empty_config.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty_config))
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "0")
    yield
    database = sys.modules.get("app.database")
    if database:
        database.engine.dispose()
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            del sys.modules[name]


@pytest.fixture
def repository(tmp_path):
    from app.services.repository.local_git import LocalGitRepositoryClient

    root = tmp_path / "repo"
    repo = LocalGitRepositoryClient(root)
    assets = root / "books/one/assets"
    assets.mkdir(parents=True)
    (assets / "nested").mkdir()
    (assets / "nested/ok.txt").write_bytes(b"versioned asset\n")
    (root / "books/one/book.md").write_bytes(b"BOOK-CANARY\n")
    (root / "books/two/assets").mkdir(parents=True)
    (root / "books/two/assets/other.txt").write_bytes(b"OTHER-BOOK-CANARY\n")
    canary = tmp_path / "outside-canary.txt"
    canary.write_bytes(b"OUTSIDE-CANARY\n")
    (assets / "external.txt").symlink_to(canary)
    (assets / "cross-book.txt").symlink_to("../../two/assets/other.txt")
    (assets / "external-dir").symlink_to(tmp_path, target_is_directory=True)
    repo._run("add", "books")
    repo._run("-c", "user.name=Test Service", "-c", "user.email=noreply@test.invalid", "commit", "-m", "Fixture")
    # Must never become readable via a missing file/revision fallback.
    (assets / "untracked.txt").write_bytes(b"WORKTREE-CANARY\n")
    (assets / "nested/ok.txt").write_bytes(b"DIRTY-WORKTREE-CANARY\n")
    return repo


@pytest.fixture
def asset_app(repository, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.database import Base, get_db
    from app.dependencies import get_current_user
    from app.models import Book, RepositorySource, RepositoryProvider, Visibility
    from app.routers.books import router

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        source = RepositorySource(name="Fixture", slug="fixture", provider=RepositoryProvider.local,
                                  local_path=str(repository.repo_path), default_branch="main")
        book = Book(title="Uno", slug="uno", course="Primaria", subject="Lengua", visibility=Visibility.public,
                    repository_source=source, content_path="books/one/book.md", assets_path="books/one/assets", base_branch="main")
        db.add(book)
        db.commit()
        book_id = book.id
    from starlette.middleware.sessions import SessionMiddleware
    from app.security import csrf_token
    from app.templates import templates

    app = FastAPI()
    # Router-level permission tests omit main/startup, but rendered forms still
    # need a real session and token generator (never a blank CSRF stub).
    app.add_middleware(SessionMiddleware, secret_key="isolated-router-session-key")
    monkeypatch.setitem(templates.env.globals, "csrf_token", csrf_token)
    app.state.test_sessions = sessions
    app.include_router(router)

    def get_test_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = get_test_db
    app.dependency_overrides[get_current_user] = lambda: None
    with TestClient(app) as client:
        yield client, book_id
    engine.dispose()


@pytest.mark.parametrize("branch", ['users/7/base/primaria', 'Edición "aula" & revisión', "Texto <entre comillas>"])
def test_preview_urls_preserve_branch_without_extra_attributes(branch):
    from html.parser import HTMLParser
    from urllib.parse import parse_qs, urlsplit
    from app.services.markdown_utils import build_book_document, _worksheet_url

    class Elements(HTMLParser):
        def __init__(self):
            super().__init__()
            self.elements = []

        def handle_starttag(self, tag, attrs):
            self.elements.append((tag, dict(attrs)))

    document = build_book_document('![Aula](assets/aula.png)', book_id=1, branch_name=branch)
    parser = Elements()
    parser.feed(document["pages"][0]["html"])
    image = next(attrs for tag, attrs in parser.elements if tag == "img")
    assert set(image) == {"src", "alt"}
    assert urlsplit(image["src"]).path == "/books/1/assets/aula.png"
    assert parse_qs(urlsplit(image["src"]).query) == {"branch": [branch]}
    assert parse_qs(urlsplit(_worksheet_url(1, "ficha", branch)).query) == {"branch": [branch]}


def test_preview_preserves_editor_contract():
    from app.services.markdown_utils import markdown_preview

    html = markdown_preview('<table><thead><tr><th>Título</th></tr></thead><tbody><tr><td>Texto</td></tr></tbody></table>\n\n<s>Antes</s><del>Después</del>\n\n<audio controls src="assets/aula.mp3"></audio>')
    for tag in ["table", "thead", "tbody", "tr", "th", "td", "s", "del", "audio"]:
        assert f"<{tag}" in html
    assert 'src="assets/aula.mp3"' in html


def test_pending_selector_reads_base_without_creating_refs(asset_app, repository):
    from app.dependencies import get_current_user, require_user
    from app.models import User, GlobalRole, Organization

    client, book_id = asset_app
    with client.app.state.test_sessions() as db:
        user = User(full_name="Ana Profe", email="ana@test.invalid", global_role=GlobalRole.editor)
        db.add_all([user, Organization(name="Colegio", slug="colegio")])
        db.commit()
        db.refresh(user)
        user.memberships = []
        user_id = user.id
        db.expunge(user)
    client.app.dependency_overrides[get_current_user] = lambda: user
    client.app.dependency_overrides[require_user] = lambda: user
    before = repository.list_branches()
    for query in ["workspace=personal", "school=colegio&course_version=Primaria&workspace=shared"]:
        response = client.get(f"/books/{book_id}?{query}")
        assert response.status_code == 200
        assert "aún no se ha creado" in response.text
        assert "BOOK-CANARY" in response.text
        assert f"users/id-{user_id}/" in response.text
    assert client.get(f"/books/{book_id}?branch=missing-branch").status_code == 404
    assert repository.list_branches() == before
    assert client.get(f"/books/{book_id}/edit?branch=users/ana-profe").status_code == 403
    editor = client.get(f"/books/{book_id}/edit?branch=users/id-{user_id}/base/primaria")
    assert editor.status_code == 200
    assert repository.list_branches() == before


def test_pdf_errors_are_recoverable_and_generic(asset_app, monkeypatch):
    from app.dependencies import require_user
    from app.models import User, GlobalRole
    from app.routers import books
    from app.services.pdf_export import PDFExportError

    client, book_id = asset_app
    client.app.dependency_overrides[require_user] = lambda: User(id=1, global_role=GlobalRole.admin)

    def fail(*args, **kwargs):
        raise PDFExportError("INTERNAL-DETAIL-CANARY")

    monkeypatch.setattr(books, "export_markdown_to_pdf", fail)
    response = client.get(f"/books/{book_id}/export/pdf")
    assert response.status_code == 400
    assert "simplifica" in response.text
    assert "INTERNAL-DETAIL-CANARY" not in response.text


@pytest.mark.parametrize("data,mime", [(b'<html><p>Documento</p></html>', "image/png"),
                                        (b'<svg xmlns="http://www.w3.org/2000/svg"/>', "image/svg+xml"),
                                        (b"imagen incompleta", "image/jpeg")])
def test_upload_rejects_non_raster(asset_app, data, mime):
    from app.dependencies import require_user
    from app.models import User, GlobalRole
    client, book_id = asset_app
    client.app.dependency_overrides[require_user] = lambda: User(id=1, global_role=GlobalRole.admin)
    response = client.post(f"/books/{book_id}/upload", data={"branch_name": "main"},
                           files={"asset": ("imagen.png", data, mime)})
    assert response.status_code == 400


def test_upload_normalizes_format_and_legacy_download(asset_app, repository):
    from io import BytesIO
    from PIL import Image
    from app.dependencies import require_user
    from app.models import User, GlobalRole
    client, book_id = asset_app
    client.app.dependency_overrides[require_user] = lambda: User(id=1, full_name="Servicio", email="test@test.invalid", global_role=GlobalRole.admin)
    image = BytesIO()
    Image.new("RGB", (2, 2), "white").save(image, format="JPEG")
    response = client.post(f"/books/{book_id}/upload", data={"branch_name": "main"},
                           files={"asset": ("foto.html", image.getvalue(), "image/jpeg")}, follow_redirects=False)
    assert response.status_code == 303
    stored = repository.read_binary("books/one/assets/foto.png", "main")
    assert stored.startswith(b"\x89PNG")
    response = client.get(f"/books/{book_id}/assets/foto.png")
    assert response.headers["content-type"] == "image/png"
    repository.write_text("books/one/assets/legacy.svg", "main", '<svg xmlns="http://www.w3.org/2000/svg"/>', "Fixture", "Servicio", "test@test.invalid")
    response = client.get(f"/books/{book_id}/assets/legacy.svg")
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert "sandbox" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"


def test_homonyms_and_legacy_never_share_write_permission():
    from app.models import User, Book, Visibility, GlobalRole
    from app.services.permissions import user_workspace_branch_name, can_edit_book_on_branch
    user = User(id=7, full_name="Ana Profe", email="one@test.invalid", global_role=GlobalRole.editor)
    other = User(id=8, full_name="Ana Profe", email="two@test.invalid", global_role=GlobalRole.admin)
    book = Book(visibility=Visibility.public)
    branch = user_workspace_branch_name(user, None, "Primaria")
    assert branch != user_workspace_branch_name(other, None, "Primaria")
    assert can_edit_book_on_branch(None, user, book, branch)
    assert not can_edit_book_on_branch(None, other, book, branch)
    assert not can_edit_book_on_branch(None, user, book, "users/ana-profe")
    user.full_name = "Nombre cambiado"
    assert branch == user_workspace_branch_name(user, None, "Primaria")


def test_creation_authorizes_repository_and_prevents_replacement(asset_app, repository):
    from app.dependencies import require_user
    from app.models import User, GlobalRole, RepositorySource, Organization, Book
    client, book_id = asset_app
    user = User(id=7, full_name="Docente", email="docente@test.invalid", global_role=GlobalRole.editor)
    user.memberships = []
    client.app.dependency_overrides[require_user] = lambda: user
    with client.app.state.test_sessions() as db:
        source = db.query(RepositorySource).one()
        organization = Organization(name="Ajena", slug="ajena")
        source.organization = organization
        db.commit()
        source_id = source.id
    form = {"title": "Nuevo", "course": "Primaria", "subject": "Lengua", "repository_source_id": source_id}
    before = repository._run("rev-parse", "main")
    assert client.post("/books/new", data=form).status_code == 403
    user.global_role = GlobalRole.admin
    assert client.post("/books/new", data=form, follow_redirects=False).status_code == 303
    path = "books/primaria/lengua/nuevo/book.md"
    original = repository.read_text(path, "main")
    assert original
    assert client.post("/books/new", data=form).status_code == 409
    with client.app.state.test_sessions() as db:
        db.delete(db.query(Book).filter_by(content_path=path).one())
        db.commit()
    assert client.post("/books/new", data=form).status_code == 409
    assert repository.read_text(path, "main") == original
    assert repository._run("rev-parse", "main") != before


@pytest.mark.parametrize("target", ["users/id-9/colegio/primaria", "orgs/inexistente/primaria", "orgs/colegio/primaria/extra"])
def test_approval_rejects_noncanonical_targets(asset_app, repository, target):
    from app.dependencies import require_user
    from app.models import User, GlobalRole, Organization
    client, book_id = asset_app
    with client.app.state.test_sessions() as db:
        db.add(Organization(name="Colegio", slug="colegio"))
        db.commit()
    client.app.dependency_overrides[require_user] = lambda: User(id=7, global_role=GlobalRole.admin)
    refs = repository.list_branches()
    response = client.post(f"/books/{book_id}/approve-version", data={"source_branch": "main", "target_branch": target})
    assert response.status_code == 403
    assert repository.list_branches() == refs


def test_approval_requires_book_access_and_existing_source(asset_app, repository):
    from app.dependencies import require_user
    from app.models import User, GlobalRole, Organization, Book, Visibility
    client, book_id = asset_app
    user = User(id=7, global_role=GlobalRole.editor)
    user.memberships = []
    client.app.dependency_overrides[require_user] = lambda: user
    with client.app.state.test_sessions() as db:
        db.add(Organization(name="Colegio", slug="colegio"))
        db.get(Book, book_id).visibility = Visibility.private
        db.commit()
    form = {"source_branch": "main", "target_branch": "orgs/colegio/primaria"}
    assert client.post(f"/books/{book_id}/approve-version", data=form).status_code == 404
    user.global_role = GlobalRole.admin
    form["source_branch"] = "no-existe"
    before = repository.list_branches()
    assert client.post(f"/books/{book_id}/approve-version", data=form).status_code == 404
    assert repository.list_branches() == before


def test_dashboard_filters_reviews_before_limit(asset_app, monkeypatch):
    from datetime import datetime, timedelta
    from app.dependencies import get_current_user
    from app.models import Book, User, Visibility, GlobalRole, ReviewRequest, ReviewKind, ReviewStatus
    from app.routers import dashboard
    client, book_id = asset_app
    client.app.include_router(dashboard.router)
    user = User(id=7, global_role=GlobalRole.editor)
    user.memberships = []
    client.app.dependency_overrides[get_current_user] = lambda: user
    monkeypatch.setattr(dashboard, "refresh_open_reviews", lambda db: 0)
    # App startup normally installs these presentation globals; no startup here.
    monkeypatch.setitem(dashboard.templates.env.globals, "review_kind_labels", {})
    monkeypatch.setitem(dashboard.templates.env.globals, "review_status_labels", {})
    with client.app.state.test_sessions() as db:
        public = db.get(Book, book_id)
        private = Book(title="Privado", slug="privado", course="Primaria", subject="Lengua", visibility=Visibility.private,
                       repository_source_id=public.repository_source_id, content_path="books/private/book.md", assets_path="books/private/assets")
        db.add(private)
        db.flush()
        now = datetime.now()
        for index in range(12):
            db.add(ReviewRequest(book_id=private.id, repo_source_id=public.repository_source_id, kind=ReviewKind.issue,
                                 title=f"PRIVADO-CANARY-{index}", body="", base_branch="main", status=ReviewStatus.open,
                                 created_at=now + timedelta(seconds=index)))
        db.add(ReviewRequest(book_id=public.id, repo_source_id=public.repository_source_id, kind=ReviewKind.issue,
                             title="Revisión visible", body="", base_branch="main", status=ReviewStatus.open, created_at=now))
        db.commit()
    response = client.get("/")
    assert response.status_code == 200
    assert "Revisión visible" in response.text
    assert "PRIVADO-CANARY" not in response.text


def test_local_reads_only_versioned_snapshot(repository):
    path = "books/one/assets/nested/ok.txt"
    assert repository.read_binary(path, "main") == b"versioned asset\n"
    assert repository.read_text(path, "main") == "versioned asset\n"
    assert repository.read_binary(path, "missing-branch") == b""
    assert repository.read_text(path, "missing-branch") == ""
    assert repository.read_binary("books/one/assets/untracked.txt", "main") == b""
    assert repository.list_files("books/one/assets", "main") == [path]
    assert repository.list_files("books/one/assets", "missing-branch") == []


@pytest.mark.parametrize("path", ["../outside-canary.txt", "/outside-canary.txt", "books/one/assets/../book.md",
                                  "books/one/assets/../../../outside-canary.txt", "books\\one\\book.md",
                                  "books/one/assets/\x00", ".git/config"])
def test_local_rejects_unsafe_paths(repository, path):
    assert repository.read_binary(path, "main") == b""
    assert repository.read_text(path, "missing-branch") == ""
    assert repository.list_files(path, "main") == []


@pytest.mark.parametrize("path", ["external.txt", "cross-book.txt", "external-dir/outside-canary.txt"])
def test_local_never_reads_symlinks(repository, path):
    assert repository.read_binary(f"books/one/assets/{path}", "main") == b""


def test_asset_http_valid_snapshot_and_missing_revision(asset_app):
    client, book_id = asset_app
    url = f"/books/{book_id}/assets/nested/ok.txt"
    assert client.get(url).content == b"versioned asset\n"
    assert client.get(url, params={"branch": "missing-branch"}).status_code == 404
    assert client.get(f"/books/{book_id}/assets/untracked.txt").status_code == 404


@pytest.mark.parametrize("path", ["%2e%2e/book.md", "%2e%2e/%2e%2e/two/assets/other.txt",
                                  "%2Foutside-canary.txt", "..%5Cbook.md", "%00", "external.txt",
                                  "cross-book.txt", "external-dir/outside-canary.txt"])
def test_asset_http_rejects_escapes_and_symlinks(asset_app, path):
    client, book_id = asset_app
    response = client.get(f"/books/{book_id}/assets/{path}")
    assert response.status_code == 404
    assert b"CANARY" not in response.content


@pytest.mark.parametrize("path", ["../book.md", "../../two/assets/other.txt", "/outside-canary.txt",
                                  "nested/../../book.md", "../outside-canary.txt"])
def test_asset_http_boundary_rejects_raw_paths(asset_app, path):
    # Test the handler directly too: HTTP clients normally remove raw dot
    # segments before transmission, which could mask a missing boundary check.
    from fastapi import HTTPException
    from app.database import get_db
    from app.routers.books import serve_book_asset

    client, book_id = asset_app
    db_generator = client.app.dependency_overrides[get_db]()
    db = next(db_generator)
    try:
        with pytest.raises(HTTPException) as error:
            serve_book_asset(book_id=book_id, asset_path=path, branch="main", db=db, user=None)
        assert error.value.status_code == 404
    finally:
        db_generator.close()


def test_pdf_loader_confines_before_repository_access(repository):
    from app.routers.books import _pdf_asset_loader

    book = SimpleNamespace(assets_path="books/one/assets")
    calls = []

    class SpyRepo:
        def read_binary(self, path, branch):
            calls.append(path)
            return repository.read_binary(path, branch)

    loader = _pdf_asset_loader(book, SpyRepo(), "main")
    for path in ["assets/../book.md", "assets/../../two/assets/other.txt", "assets/../../../outside-canary.txt",
                 "/outside-canary.txt", "assets//outside-canary.txt", "assets/..\\book.md", "assets/\x00"]:
        assert loader(path) == b""
    assert calls == []
    for path in ["external.txt", "cross-book.txt", "external-dir/outside-canary.txt"]:
        assert loader(f"assets/{path}") == b""
    assert loader("./assets/nested/ok.txt") == b"versioned asset\n"
    assert _pdf_asset_loader(book, repository, "missing-branch")("assets/nested/ok.txt") == b""
