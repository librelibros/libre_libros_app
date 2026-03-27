import os
from pathlib import Path

from fastapi.testclient import TestClient


def build_client(tmp_path: Path):
    os.environ["LIBRE_LIBROS_DATABASE_URL"] = f"sqlite:///{tmp_path / 'test.db'}"
    os.environ["LIBRE_LIBROS_REPOS_ROOT"] = str(tmp_path / "repos")
    example_repo = tmp_path / "repo"
    book_dir = example_repo / "books" / "primaria" / "lengua" / "lengua-demo"
    (book_dir / "assets").mkdir(parents=True, exist_ok=True)
    (book_dir / "book.md").write_text(
        "# Lengua Demo\n\n## Introduccion\n\n![Portada](assets/cover.svg)\n\nParrafo de prueba para importacion.\n\n<!-- pagebreak -->\n\n## Actividades\n\n- Lectura guiada\n- Escritura breve\n",
        encoding="utf-8",
    )
    (book_dir / "assets" / "cover.svg").write_text(
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><rect width='16' height='16' fill='#2457c5'/></svg>",
        encoding="utf-8",
    )
    os.environ["LIBRE_LIBROS_EXAMPLE_REPO_PATH"] = str(example_repo)
    os.environ["LIBRE_LIBROS_INIT_ADMIN_EMAIL"] = "admin@test.local"
    os.environ["LIBRE_LIBROS_INIT_ADMIN_PASSWORD"] = "admin12345"

    from app.config import get_settings

    get_settings.cache_clear()

    from app.main import app

    return TestClient(app)


def test_redirects_to_login(tmp_path: Path):
    client = build_client(tmp_path)
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_markdown_preview_endpoint(tmp_path: Path):
    client = build_client(tmp_path)
    response = client.post("/books/preview", data={"content": "# Hola"})
    assert response.status_code == 200
    assert "<h1" in response.text


def test_bootstrap_imports_example_books(tmp_path: Path):
    client = build_client(tmp_path)
    with client:
        pass

    from app.database import SessionLocal
    from app.models import Book, RepositorySource

    db = SessionLocal()
    try:
        assert db.query(RepositorySource).count() == 1
        books = db.query(Book).all()
        assert len(books) == 1
        assert books[0].title == "Lengua Demo"
        assert books[0].visibility.value == "public"
    finally:
        db.close()


def test_books_list_supports_course_and_subject_filters(tmp_path: Path):
    client = build_client(tmp_path)

    login_response = client.post(
        "/login",
        data={"email": "admin@test.local", "password": "admin12345"},
        follow_redirects=True,
    )
    assert login_response.status_code == 200

    response = client.get("/books?course=Primaria&subject=Lengua")
    assert response.status_code == 200
    assert "Lengua Demo" in response.text
    assert "Todas las materias" in response.text

    response = client.get("/books?course=Secundaria")
    assert response.status_code == 200
    assert "Lengua Demo" not in response.text
    assert "No hay libros que coincidan con los filtros seleccionados." in response.text


def test_book_detail_rewrites_asset_urls_and_serves_assets(tmp_path: Path):
    client = build_client(tmp_path)

    login_response = client.post(
        "/login",
        data={"email": "admin@test.local", "password": "admin12345"},
        follow_redirects=True,
    )
    assert login_response.status_code == 200

    response = client.get("/books/1")
    assert response.status_code == 200
    assert '/books/1/assets/cover.svg?branch=main' in response.text
    assert "Temas del libro" in response.text
    assert "Pagina 2 de 2" in response.text or "Pagina 1 de 2" in response.text

    asset_response = client.get("/books/1/assets/cover.svg?branch=main")
    assert asset_response.status_code == 200
    assert asset_response.headers["content-type"].startswith("image/svg+xml")


def test_preview_endpoint_builds_paginated_preview_with_book_assets(tmp_path: Path):
    client = build_client(tmp_path)

    response = client.post(
        "/books/preview",
        data={
            "content": "# Demo\n\n## Tema 1\n\n![Portada](assets/cover.svg)\n\n<!-- pagebreak -->\n\n## Tema 2",
            "book_id": "1",
            "branch_name": "main",
        },
    )
    assert response.status_code == 200
    assert "Temas del libro" in response.text
    assert "/books/1/assets/cover.svg?branch=main" in response.text
    assert "Pagina 2" in response.text
