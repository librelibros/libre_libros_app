import os
import subprocess
import sys
from base64 import b64decode
from pathlib import Path

import bcrypt
from fastapi.testclient import TestClient


TEST_PNG = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z0xQAAAAASUVORK5CYII="
)
BROKEN_RASTER_PNG = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "repo"
    / "books"
    / "primaria"
    / "lengua"
    / "lengua-primaria"
    / "assets"
    / "column-demo-image.png"
).read_bytes()


def build_client(tmp_path: Path):
    os.environ["LIBRE_LIBROS_DATABASE_URL"] = f"sqlite:///{tmp_path / 'test.db'}"
    os.environ["LIBRE_LIBROS_REPOS_ROOT"] = str(tmp_path / "repos")
    example_repo = tmp_path / "repo"
    book_dir = example_repo / "books" / "primaria" / "lengua" / "lengua-demo"
    (book_dir / "assets").mkdir(parents=True, exist_ok=True)
    (book_dir / "worksheets").mkdir(parents=True, exist_ok=True)
    (book_dir / "book.md").write_text(
        "# Lengua Demo\n\n## Introduccion\n\n![Portada](assets/cover.svg)\n\n[[columns:2]]\n### Idea clave\n\nTexto en la primera columna.\n[[col]]\n### Practica guiada\n\n[[worksheet:ficha-comprension|Ir a ficha de comprension]]\n[[/columns]]\n\n![Actividad](assets/aula.png)\n\nParrafo de prueba para importacion.\n\n<!-- pagebreak -->\n\n## Actividades\n\n- Lectura guiada\n- Escritura breve\n",
        encoding="utf-8",
    )
    (book_dir / "worksheets" / "ficha-comprension.md").write_text(
        "# Ficha Comprension\n\n## Consigna\n\nLee el texto y responde.\n",
        encoding="utf-8",
    )
    (book_dir / "assets" / "cover.svg").write_text(
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><rect width='16' height='16' fill='#2457c5'/></svg>",
        encoding="utf-8",
    )
    (book_dir / "assets" / "aula.png").write_bytes(BROKEN_RASTER_PNG)
    (book_dir / "assets" / ".gitkeep").write_text("", encoding="utf-8")
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
    assert 'doc-columns doc-columns-2' in response.text
    assert '/books/1/worksheets/ficha-comprension?branch=main' in response.text
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
            "content": "# Demo\n\n## Tema 1\n\n[[columns:3]]\n### Uno\n\nA\n[[col]]\n### Dos\n\n[[worksheet:ficha-comprension|Ficha]]\n[[col]]\n### Tres\n\nC\n[[/columns]]\n\n![Portada](assets/cover.svg){: .doc-image .doc-align-right .doc-w-50}\n\n<!-- pagebreak -->\n\n## Tema 2",
            "book_id": "1",
            "branch_name": "main",
        },
    )
    assert response.status_code == 200
    assert "doc-columns-3" in response.text
    assert "/books/1/worksheets/ficha-comprension?branch=main" in response.text
    assert "/books/1/assets/cover.svg?branch=main" in response.text
    assert "doc-align-right" in response.text
    assert "Pagina 2" in response.text
    assert "Tema 1" in response.text


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
    assert "Biblioteca del material" in response.text
    assert "cover.svg" in response.text
    assert "Guardar cambios del material" in response.text
    assert "Suelta archivos aquí o en la hoja de edición" in response.text
    assert "Se guardarán con este material" in response.text
    assert "Version activa" in response.text
    assert "Edición directa" not in response.text
    assert "Insertar en el documento" in response.text
    assert "2 columnas" in response.text
    assert "Lectura" in response.text
    assert "Recursos" in response.text
    assert "Resumen del guardado" in response.text
    assert "Ctrl/Cmd+S" in response.text
    assert ".gitkeep" not in response.text


def test_can_create_and_edit_a_worksheet(tmp_path: Path):
    client = build_client(tmp_path)
    with client:
        login_response = client.post(
            "/login",
            data={"email": "admin@test.local", "password": "admin12345"},
            follow_redirects=True,
        )
        assert login_response.status_code == 200

        create_response = client.post(
            "/books/1/worksheets/new",
            data={"branch_name": "main", "title": "Ficha Refuerzo"},
            follow_redirects=True,
        )
        assert create_response.status_code == 200
        assert "Ficha Ficha Refuerzo creada correctamente." in create_response.text
        assert "Editar ficha Ficha Refuerzo" in create_response.text

        save_response = client.post(
            "/books/1/worksheets/ficha-refuerzo/edit",
            data={
                "branch_name": "main",
                "content": "# Ficha Refuerzo\n\n[[columns:2]]\n### Reto\n\nCompleta el ejercicio.\n[[col]]\n### Enlace\n\n[[worksheet:ficha-comprension|Ficha base]]\n[[/columns]]\n",
                "commit_message": "",
            },
            follow_redirects=True,
        )
        assert save_response.status_code == 200
        assert "Ficha guardada en la rama main." in save_response.text
        assert "doc-columns-2" in save_response.text
        assert "/books/1/worksheets/ficha-comprension?branch=main" in save_response.text

        worksheet_response = client.get("/books/1/worksheets/ficha-refuerzo?branch=main")
        assert worksheet_response.status_code == 200
        assert "Ficha Refuerzo" in worksheet_response.text


def test_editor_save_persists_uploaded_assets_in_repository(tmp_path: Path):
    client = build_client(tmp_path)
    with client:
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


def test_editor_save_generates_commit_message_when_empty(tmp_path: Path):
    client = build_client(tmp_path)
    with client:
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
                "content": "# Lengua Demo\n\nTexto actualizado.\n",
                "commit_message": "   ",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "Cambios guardados en la rama main." in response.text

        commit_subject = subprocess.run(
            ["git", "log", "-1", "--pretty=%s"],
            cwd=tmp_path / "repo",
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert commit_subject == "Update Lengua Demo on main"


def test_editor_save_generates_commit_message_when_missing(tmp_path: Path):
    client = build_client(tmp_path)
    with client:
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
                "content": "# Lengua Demo\n\nTexto actualizado otra vez.\n",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "Cambios guardados en la rama main." in response.text

        commit_subject = subprocess.run(
            ["git", "log", "-1", "--pretty=%s"],
            cwd=tmp_path / "repo",
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert commit_subject == "Update Lengua Demo on main"


def test_pdf_export_includes_embedded_images(tmp_path: Path):
    client = build_client(tmp_path)
    with client:
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
    assert "users/ana-profe" in response.text


def test_local_git_repository_serializes_parallel_process_writes(tmp_path: Path):
    client = build_client(tmp_path)
    with client:
        pass

    repo_path = tmp_path / "repo"

    workers = [
        ("users/ana-profe", "Ana Profe"),
        ("users/bruno-profe", "Bruno Profe"),
        ("users/carla-profe", "Carla Profe"),
    ]

    worker_code = """
from pathlib import Path
import sys
import time
from app.services.repository.local_git import LocalGitRepositoryClient

repo_path, branch_name, label = sys.argv[1:4]
client = LocalGitRepositoryClient(Path(repo_path))
rel_path = "books/primaria/lengua/lengua-demo/book.md"

for version in range(4):
    client.write_text(
        rel_path=rel_path,
        branch_name=branch_name,
        content=f"# {label}\\n\\nVersion {version}\\n",
        commit_message=f"{label} version {version}",
        author_name=label,
        author_email=f"{label.lower()}@test.local",
    )
    time.sleep(0.01)
"""

    processes = [
        subprocess.Popen(
            [sys.executable, "-c", worker_code, str(repo_path), branch_name, label],
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for branch_name, label in workers
    ]

    for process in processes:
        stdout, stderr = process.communicate(timeout=30)
        assert process.returncode == 0, stdout + stderr

    for branch_name, label in workers:
        branch_content = subprocess.run(
            ["git", "show", f"{branch_name}:books/primaria/lengua/lengua-demo/book.md"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert label in branch_content
        assert "Version 3" in branch_content

    current_branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert current_branch == "main"


def test_login_accepts_legacy_bcrypt_hash_and_migrates_it(tmp_path: Path):
    client = build_client(tmp_path)
    with client:
        pass

    from app.database import SessionLocal
    from app.main import create_default_admin
    from app.models import User

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == "admin@test.local").first()
        assert admin is not None
        admin.password_hash = bcrypt.hashpw(b"admin12345", bcrypt.gensalt()).decode("utf-8")
        db.commit()
    finally:
        db.close()

    login_response = client.post(
        "/login",
        data={"email": "admin@test.local", "password": "admin12345"},
        follow_redirects=True,
    )
    assert login_response.status_code == 200

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == "admin@test.local").first()
        assert admin is not None
        assert admin.password_hash.startswith("$pbkdf2-sha256$")
    finally:
        db.close()

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == "admin@test.local").first()
        assert admin is not None
        admin.password_hash = "legacy-hash-without-scheme"
        db.commit()
    finally:
        db.close()

    create_default_admin()

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == "admin@test.local").first()
        assert admin is not None
        assert admin.password_hash.startswith("$pbkdf2-sha256$")
    finally:
        db.close()


def test_book_detail_uses_school_course_and_workspace_selectors(tmp_path: Path):
    client = build_client(tmp_path)
    with client:
        pass

    from app.database import SessionLocal
    from app.models import Organization

    db = SessionLocal()
    try:
        db.add(Organization(name="Colegio Selector", slug="colegio-selector", description="Centro de prueba"))
        db.commit()
    finally:
        db.close()

    login_response = client.post(
        "/login",
        data={"email": "admin@test.local", "password": "admin12345"},
        follow_redirects=True,
    )
    assert login_response.status_code == 200

    response = client.get("/books/1?school=colegio-selector&course_version=Primaria&workspace=shared")
    assert response.status_code == 200
    assert "Colegio" in response.text
    assert "Curso" in response.text
    assert "Version" in response.text
    assert "Version aprobada del cole" in response.text
    assert "Mi version docente" in response.text
    assert "Rama origen" not in response.text


def test_teacher_can_propose_and_org_admin_can_accept_school_course_version(tmp_path: Path):
    client = build_client(tmp_path)
    with client:
        pass

    from app.database import SessionLocal
    from app.models import MembershipRole, Organization, OrganizationMembership, ReviewRequest, ReviewStatus, User
    from app.security import hash_password
    from app.services.permissions import approved_branch_name, user_workspace_branch_name

    db = SessionLocal()
    try:
        school = Organization(name="Colegio Flujo", slug="colegio-flujo", description="Centro de prueba")
        teacher = User(
            full_name="Ana Profe",
            email="ana-flujo@test.local",
            password_hash=hash_password("profe12345"),
        )
        org_admin = User(
            full_name="Marta Directora",
            email="marta-flujo@test.local",
            password_hash=hash_password("admincolegio123"),
        )
        db.add_all([school, teacher, org_admin])
        db.commit()
        db.refresh(school)
        db.refresh(teacher)
        db.refresh(org_admin)
        db.add_all(
            [
                OrganizationMembership(user_id=teacher.id, organization_id=school.id, role=MembershipRole.editor),
                OrganizationMembership(user_id=org_admin.id, organization_id=school.id, role=MembershipRole.organization_admin),
            ]
        )
        db.commit()
    finally:
        db.close()

    teacher_login = client.post(
        "/login",
        data={"email": "ana-flujo@test.local", "password": "profe12345"},
        follow_redirects=True,
    )
    assert teacher_login.status_code == 200

    teacher_branch = user_workspace_branch_name(type("UserLike", (), {"full_name": "Ana Profe", "email": "ana-flujo@test.local"})(), "colegio-flujo", "Primaria")
    approved_branch = approved_branch_name("colegio-flujo", "Primaria")

    save_response = client.post(
        "/books/1/edit",
        data={
            "branch_name": teacher_branch,
            "content": "# Lengua Demo\n\n## Introduccion\n\nTexto adaptado para Colegio Flujo.\n",
            "commit_message": "Adaptacion Colegio Flujo",
        },
        follow_redirects=True,
    )
    assert save_response.status_code == 200
    assert "Texto adaptado para Colegio Flujo" in save_response.text

    pr_response = client.post(
        "/books/1/pull-requests",
        data={
            "head_branch": teacher_branch,
            "base_branch": approved_branch,
            "title": "Adaptacion para Colegio Flujo",
            "body": "Propuesta docente para la version aprobada.",
        },
        follow_redirects=True,
    )
    assert pr_response.status_code == 200
    assert "Pull request registrada correctamente." in pr_response.text

    client.get("/logout", follow_redirects=True)

    admin_login = client.post(
        "/login",
        data={"email": "marta-flujo@test.local", "password": "admincolegio123"},
        follow_redirects=True,
    )
    assert admin_login.status_code == 200

    approve_response = client.post(
        "/books/1/approve-version",
        data={"source_branch": teacher_branch, "target_branch": approved_branch},
        follow_redirects=True,
    )
    assert approve_response.status_code == 200
    assert "Version aprobada para el colegio y curso seleccionados." in approve_response.text

    branch_content = subprocess.run(
        ["git", "show", f"{approved_branch}:books/primaria/lengua/lengua-demo/book.md"],
        cwd=tmp_path / "repo",
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "Texto adaptado para Colegio Flujo." in branch_content

    db = SessionLocal()
    try:
        review = db.query(ReviewRequest).filter(ReviewRequest.head_branch == teacher_branch).first()
        assert review is not None
        assert review.status == ReviewStatus.merged
    finally:
        db.close()
