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
        "# Lengua Demo\n\nParrafo de prueba para importacion.\n",
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
