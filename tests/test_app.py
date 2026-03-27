import os
from base64 import b64decode
from pathlib import Path

from fastapi.testclient import TestClient


TEST_PNG = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z0xQAAAAASUVORK5CYII="
)


def build_client(tmp_path: Path):
    os.environ["LIBRE_LIBROS_DATABASE_URL"] = f"sqlite:///{tmp_path / 'test.db'}"
    os.environ["LIBRE_LIBROS_REPOS_ROOT"] = str(tmp_path / "repos")
    example_repo = tmp_path / "repo"
    book_dir = example_repo / "books" / "primaria" / "lengua" / "lengua-demo"
    (book_dir / "assets").mkdir(parents=True, exist_ok=True)
    (book_dir / "book.md").write_text(
        "# Lengua Demo\n\n## Introduccion\n\n![Portada](assets/cover.svg)\n\n![Actividad](assets/aula.png)\n\nParrafo de prueba para importacion.\n\n<!-- pagebreak -->\n\n## Actividades\n\n- Lectura guiada\n- Escritura breve\n",
        encoding="utf-8",
    )
    (book_dir / "assets" / "cover.svg").write_text(
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><rect width='16' height='16' fill='#2457c5'/></svg>",
        encoding="utf-8",
    )
    (book_dir / "assets" / "aula.png").write_bytes(TEST_PNG)
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


def test_editor_shows_asset_library_and_snippets(tmp_path: Path):
    client = build_client(tmp_path)

    login_response = client.post(
        "/login",
        data={"email": "admin@test.local", "password": "admin12345"},
        follow_redirects=True,
    )
    assert login_response.status_code == 200

    response = client.get("/books/1/edit?branch=main")
    assert response.status_code == 200
    assert "Recursos disponibles en main" in response.text
    assert "cover.svg" in response.text
    assert "![cover.svg](assets/cover.svg)" in response.text
    assert "Insertar en el editor" in response.text
    assert "Arrastra y suelta imágenes o audio" in response.text


def test_editor_save_persists_uploaded_assets_in_repository(tmp_path: Path):
    client = build_client(tmp_path)

    login_response = client.post(
        "/login",
        data={"email": "admin@test.local", "password": "admin12345"},
        follow_redirects=True,
    )
    assert login_response.status_code == 200

    response = client.post(
        "/books/1/edit",
        data={
            "branch_name": "main",
            "content": "# Lengua Demo\n\n![Nueva imagen](assets/mi-imagen.png)\n",
            "commit_message": "Update with inline asset",
        },
        files=[("assets", ("Mi imagen.PNG", TEST_PNG, "image/png"))],
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "mi-imagen.png" in response.text

    asset_response = client.get("/books/1/assets/mi-imagen.png?branch=main")
    assert asset_response.status_code == 200
    assert asset_response.content == TEST_PNG


def test_pdf_export_includes_embedded_images(tmp_path: Path):
    client = build_client(tmp_path)

    login_response = client.post(
        "/login",
        data={"email": "admin@test.local", "password": "admin12345"},
        follow_redirects=True,
    )
    assert login_response.status_code == 200

    response = client.get("/books/1/export/pdf?branch=main")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")
    assert b"/Subtype /Image" in response.content


def test_comment_can_be_deleted_by_author(tmp_path: Path):
    client = build_client(tmp_path)

    login_response = client.post(
        "/login",
        data={"email": "admin@test.local", "password": "admin12345"},
        follow_redirects=True,
    )
    assert login_response.status_code == 200

    add_response = client.post(
        "/books/1/comments",
        data={"branch_name": "main", "anchor": "introduccion", "body": "Comentario temporal"},
        follow_redirects=True,
    )
    assert add_response.status_code == 200
    assert "Comentario temporal" in add_response.text

    from app.database import SessionLocal
    from app.models import BookComment

    db = SessionLocal()
    try:
        comment = db.query(BookComment).filter(BookComment.body == "Comentario temporal").first()
        assert comment is not None
        comment_id = comment.id
    finally:
        db.close()

    delete_response = client.post(
        f"/books/1/comments/{comment_id}/delete",
        follow_redirects=True,
    )
    assert delete_response.status_code == 200
    assert "Comentario eliminado." in delete_response.text
    assert "Comentario temporal" not in delete_response.text


def test_public_book_edit_link_falls_back_to_teacher_branch(tmp_path: Path):
    client = build_client(tmp_path)

    register_response = client.post(
        "/register",
        data={"full_name": "Ana Profe", "email": "ana@test.local", "password": "profe12345"},
        follow_redirects=True,
    )
    assert register_response.status_code == 200

    response = client.get("/books/1/edit?branch=main")
    assert response.status_code == 200
    assert "Rama de trabajo" in response.text
    assert "users/ana-profe" in response.text
