from __future__ import annotations

import logging
import mimetypes
from io import BytesIO
from pathlib import Path
from urllib.parse import quote, urlencode

from PIL import Image, UnidentifiedImageError
from sqlalchemy.exc import IntegrityError

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from slugify import slugify
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user, require_user
from app.models import Book, BookComment, GlobalRole, Organization, RepositorySource, ReviewKind, ReviewRequest, ReviewStatus, User, Visibility
from app.services.book_content import worksheet_snippet
from app.services.books import default_book_paths, export_markdown_to_pdf, sanitize_filename
from app.services.markdown_utils import PAGEBREAK_MARKER, build_book_document, markdown_preview
from app.services.permissions import (
    approved_branch_name,
    available_branches_for_book,
    can_edit_book_on_branch,
    can_create_book_in_repository,
    can_manage_organization_version,
    can_view_book,
    course_branch_slug,
    organization_for_slug,
    parse_branch_context,
    user_branch_name,
    user_workspace_branch_name,
)
from app.services.repository.factory import repository_client_for
from app.services.repository.base import RepositoryFileWrite, validate_repository_path
from app.templates import templates

router = APIRouter(prefix="/books", tags=["books"])
settings = get_settings()
WORKSPACE_SHARED = "shared"
WORKSPACE_PERSONAL = "personal"


_logger = logging.getLogger("libre_libros.books")


def _message_from_request(request: Request) -> str | None:
    return request.query_params.get("message")


def _error_from_request(request: Request) -> str | None:
    return request.query_params.get("error")


def _redirect_with_message(path: str, message: str, **params: str) -> RedirectResponse:
    query = urlencode({**params, "message": message})
    return RedirectResponse(f"{path}?{query}" if query else path, status_code=303)


def _redirect_with_error(path: str, error: str, **params: str) -> RedirectResponse:
    query = urlencode({**params, "error": error})
    return RedirectResponse(f"{path}?{query}" if query else path, status_code=303)


def _friendly_github_error(exc: httpx.HTTPStatusError, *, action: str) -> str:
    """Translate a GitHub API HTTP error into a teacher-friendly Spanish message."""
    code = exc.response.status_code
    detail: str = ""
    try:
        payload = exc.response.json()
        detail = payload.get("message") or ""
        if isinstance(payload.get("errors"), list) and payload["errors"]:
            first = payload["errors"][0]
            if isinstance(first, dict) and first.get("message"):
                detail = first["message"]
    except Exception:
        detail = (exc.response.text or "")[:200]

    detail_lower = detail.lower()
    if "no commits between" in detail_lower:
        return (
            "No hay cambios que proponer: tu versión y la versión publicada son idénticas. "
            "Edita el libro primero y guarda al menos un cambio antes de enviar la propuesta."
        )
    if "a pull request already exists" in detail_lower or "already exists" in detail_lower:
        return "Ya existe una propuesta de cambio abierta desde esta versión. Revísala antes de crear otra."
    if code == 401 or code == 403:
        return (
            "No tenemos permiso para hacer esa operación en GitHub. "
            "Avisa a la persona que administra Libre Libros para revisar el token de acceso."
        )
    if code == 404:
        return "GitHub no encuentra una de las ramas. Probablemente aún no se ha guardado tu versión en el repositorio."

    return f"GitHub ha rechazado la operación al {action}: {detail or 'sin detalle'}."


def _preferred_personal_branch(repo, user: User, organization_slug: str | None, course_name: str) -> str:
    preferred_branch = user_workspace_branch_name(user, organization_slug, course_name)
    # Only stable-ID prefixes can be selected for editing. Legacy name-based
    # branches remain explicitly readable but require an ownership map to migrate.
    legacy_branch = user_branch_name(user)
    try:
        existing_branches = set(repo.list_branches())
    except Exception:
        return preferred_branch

    if preferred_branch in existing_branches:
        return preferred_branch

    preferred_parts = [part for part in preferred_branch.split("/") if part]
    conflicting_prefixes = [
        "/".join(preferred_parts[:index])
        for index in range(2, len(preferred_parts))
        if "/".join(preferred_parts[:index]) in existing_branches
    ]
    if conflicting_prefixes:
        return conflicting_prefixes[-1]

    if legacy_branch in existing_branches:
        return legacy_branch

    return preferred_branch


def _asset_snippet(filename: str) -> str:
    media_type = mimetypes.guess_type(filename)[0] or ""
    rel_path = f"assets/{filename}"
    if media_type.startswith("image/"):
        return f"![{filename}]({rel_path})"
    if media_type == "audio/mpeg":
        return f'<audio controls src="{rel_path}"></audio>'
    return f"[{filename}]({rel_path})"


def _asset_entries(book: Book, branch_name: str) -> list[dict[str, str]]:
    repo = repository_client_for(book.repository_source)
    files = repo.list_files(book.assets_path, branch_name)
    entries: list[dict[str, str]] = []
    for rel_path in sorted(files):
        filename = rel_path.split("/")[-1]
        if filename.startswith("."):
            continue
        media_type = mimetypes.guess_type(filename)[0] or ""
        entries.append(
            {
                "filename": filename,
                "rel_path": rel_path,
                "public_url": f"/books/{book.id}/assets/{filename}?branch={branch_name}",
                "snippet": _asset_snippet(filename),
                "media_type": media_type,
            }
        )
    return entries


def _book_directory(book: Book) -> str:
    return Path(book.content_path).parent.as_posix()


def _worksheets_directory(book: Book) -> str:
    return f"{_book_directory(book)}/worksheets"


def _worksheet_rel_path(book: Book, worksheet_slug: str) -> str:
    return f"{_worksheets_directory(book)}/{worksheet_slug}.md"


def _extract_document_title(content: str, fallback: str) -> str:
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if line.startswith("# "):
            return line[2:].strip() or fallback
    return fallback


def _extract_document_summary(content: str) -> str | None:
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#") or line.startswith("![") or line.startswith("- ") or line.startswith("[["):
            continue
        return line[:220]
    return None


def _worksheet_entries(book: Book, branch_name: str) -> list[dict[str, str]]:
    repo = repository_client_for(book.repository_source)
    entries: list[dict[str, str]] = []
    for rel_path in sorted(repo.list_files(_worksheets_directory(book), branch_name)):
        if not rel_path.endswith(".md"):
            continue
        slug = Path(rel_path).stem
        content = repo.read_text(rel_path, branch_name)
        title = _extract_document_title(content, slug.replace("-", " ").title())
        entries.append(
            {
                "slug": slug,
                "title": title,
                "summary": _extract_document_summary(content),
                "detail_url": f"/books/{book.id}/worksheets/{slug}?branch={branch_name}",
                "edit_url": f"/books/{book.id}/worksheets/{slug}/edit?branch={branch_name}",
                "snippet": worksheet_snippet(slug, title),
            }
        )
    return entries


def _worksheet_content_template(title: str) -> str:
    return (
        f"# {title}\n\n"
        "## Objetivo\n\n"
        "Completa la ficha con una actividad breve y clara.\n\n"
        "## Actividad\n\n"
        "- Lee la consigna.\n"
        "- Responde con tu grupo.\n"
        "- Revisa el resultado final.\n"
    )


def _default_worksheet_commit_message(worksheet_title: str, branch_name: str, uploaded_filenames: list[str] | None = None) -> str:
    uploaded_filenames = uploaded_filenames or []
    if uploaded_filenames:
        if len(uploaded_filenames) == 1:
            return f"Update worksheet {worksheet_title} and add {uploaded_filenames[0]} on {branch_name}"
        return f"Update worksheet {worksheet_title} and add {len(uploaded_filenames)} assets on {branch_name}"
    return f"Update worksheet {worksheet_title} on {branch_name}"


async def _prepare_asset_writes(
    files: list[UploadFile] | None,
    book: Book,
) -> tuple[list[RepositoryFileWrite], list[str]]:
    writes: list[RepositoryFileWrite] = []
    uploaded_filenames: list[str] = []

    for asset in files or []:
        if not asset.filename:
            continue
        data = await asset.read(max(settings.max_image_bytes, settings.max_audio_bytes) + 1)
        if not data:
            continue
        data, extension = _validate_asset_upload(data, asset.content_type or "")
        filename = (slugify(Path(asset.filename).stem) or "recurso") + extension
        writes.append(
            RepositoryFileWrite(
                rel_path=f"{book.assets_path}/{filename}",
                content=data,
            )
        )
        uploaded_filenames.append(filename)

    return writes, uploaded_filenames


def _raster_png(data: bytes) -> bytes:
    """Decode allowlisted raster formats and discard metadata/embedded content."""
    with Image.open(BytesIO(data)) as image:
        if image.format not in {"PNG", "JPEG", "GIF", "WEBP"} or image.width * image.height > 16_000_000:
            raise ValueError("Formato o dimensiones no admitidos")
        image.verify()
    with Image.open(BytesIO(data)) as image:
        image.load()
        normalized = image.convert("RGBA")
        output = BytesIO()
        normalized.save(output, format="PNG")
        return output.getvalue()


def _validate_asset_upload(data: bytes, content_type: str) -> tuple[bytes, str]:
    if content_type == "audio/mpeg":
        if len(data) > settings.max_audio_bytes or not (data.startswith(b"ID3") or data[:2] in {b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"}):
            raise HTTPException(status_code=400, detail="Audio no válido o demasiado grande")
        return data, ".mp3"
    if len(data) > settings.max_image_bytes:
        raise HTTPException(status_code=400, detail="La imagen supera el límite de tamaño")
    try:
        return _raster_png(data), ".png"
    except (ValueError, OSError, SyntaxError, UnidentifiedImageError, Image.DecompressionBombError):
        raise HTTPException(status_code=400, detail="Sube una imagen PNG, JPEG, GIF o WebP válida; SVG no está admitido") from None


def _book_asset_path(book: Book, asset_path: str) -> str:
    # Validate before concatenation: confinement is to this book's assets,
    # not merely to the repository. Do not resolve/normalize away '..'.
    validate_repository_path(book.assets_path)
    validate_repository_path(asset_path)
    return f"{book.assets_path}/{asset_path}"


def _pdf_asset_loader(book: Book, repo, branch_name: str):
    def load(markdown_path: str) -> bytes:
        rel_path = markdown_path.removeprefix("./")
        if not rel_path.startswith("assets/"):
            return b""
        try:
            asset_path = _book_asset_path(book, rel_path.removeprefix("assets/"))
        except ValueError:
            return b""
        return repo.read_binary(asset_path, branch_name)

    return load


def _default_commit_message(book: Book, branch_name: str, uploaded_filenames: list[str] | None = None) -> str:
    uploaded_filenames = uploaded_filenames or []
    if uploaded_filenames:
        if len(uploaded_filenames) == 1:
            return f"Update {book.title} and add {uploaded_filenames[0]} on {branch_name}"
        return f"Update {book.title} and add {len(uploaded_filenames)} assets on {branch_name}"
    return f"Update {book.title} on {branch_name}"


def _distinct_course_options(db: Session, book: Book) -> list[str]:
    course_options = sorted({value for (value,) in db.query(Book.course).distinct().all() if value})
    if book.course not in course_options:
        course_options.append(book.course)
        course_options.sort()
    return course_options


def _school_options(db: Session) -> list[Organization]:
    return db.query(Organization).order_by(Organization.name).all()


def _course_name_from_slug(course_slug: str | None, available_courses: list[str], fallback: str) -> str:
    if not course_slug:
        return fallback
    for course_name in available_courses:
        if course_branch_slug(course_name) == course_slug:
            return course_name
    return fallback


def _branch_label_for_ui(branch_name: str, school_name: str | None = None, course_name: str | None = None) -> str:
    context = parse_branch_context(branch_name)
    if branch_name == "main":
        return "Material base compartido"
    if context.is_personal:
        if school_name and course_name:
            return f"Mi version docente · {school_name} · {course_name}"
        if course_name:
            return f"Mi version docente · {course_name}"
        return "Mi version docente"
    if context.organization_slug:
        if school_name and course_name:
            return f"Version aprobada · {school_name} · {course_name}"
        if school_name:
            return f"Version aprobada · {school_name}"
    return branch_name


def _review_branch_label(db: Session, branch_name: str, fallback_course: str) -> str:
    context = parse_branch_context(branch_name)
    organization = organization_for_slug(db, context.organization_slug) if context.organization_slug else None
    school_name = organization.name if organization else None
    available_courses = sorted({value for (value,) in db.query(Book.course).distinct().all() if value})
    if fallback_course not in available_courses:
        available_courses.append(fallback_course)
    course_name = _course_name_from_slug(context.course_slug, available_courses, fallback_course)
    return _branch_label_for_ui(branch_name, school_name, course_name)


def _resolve_version_context(
    db: Session,
    user: User | None,
    book: Book,
    school_slug: str | None,
    course_version: str | None,
    workspace: str | None,
    branch: str | None,
) -> dict[str, object]:
    repo = repository_client_for(book.repository_source)
    available_courses = _distinct_course_options(db, book)
    available_schools = _school_options(db)
    selected_course = course_version.strip() if course_version else book.course
    selected_school_slug = (school_slug or "").strip()
    selected_workspace = workspace if workspace in {WORKSPACE_SHARED, WORKSPACE_PERSONAL} else WORKSPACE_SHARED

    if branch:
        parsed = parse_branch_context(branch)
        if parsed.organization_slug:
            selected_school_slug = parsed.organization_slug
        if parsed.course_slug:
            selected_course = _course_name_from_slug(parsed.course_slug, available_courses, selected_course)
        selected_workspace = WORKSPACE_PERSONAL if parsed.is_personal else WORKSPACE_SHARED

    selected_school = next((org for org in available_schools if org.slug == selected_school_slug), None)
    selected_school_name = selected_school.name if selected_school else "Material base"

    if branch:
        selected_branch = branch
    elif selected_workspace == WORKSPACE_PERSONAL and user:
        selected_branch = _preferred_personal_branch(repo, user, selected_school_slug or None, selected_course)
    elif selected_school_slug:
        selected_branch = approved_branch_name(selected_school_slug, selected_course)
    else:
        selected_branch = book.base_branch

    approved_branch = approved_branch_name(selected_school_slug, selected_course) if selected_school_slug else book.base_branch
    personal_branch = (
        _preferred_personal_branch(repo, user, selected_school_slug or None, selected_course)
        if user
        else None
    )
    current_workspace_label = (
        "Mi version docente" if selected_workspace == WORKSPACE_PERSONAL else ("Version aprobada del cole" if selected_school_slug else "Material base")
    )

    edit_branch = None
    if user:
        if selected_workspace == WORKSPACE_PERSONAL and personal_branch and can_edit_book_on_branch(db, user, book, personal_branch):
            edit_branch = personal_branch
        elif selected_school_slug and can_edit_book_on_branch(db, user, book, approved_branch):
            edit_branch = approved_branch
        elif personal_branch and can_edit_book_on_branch(db, user, book, personal_branch):
            edit_branch = personal_branch
        elif can_edit_book_on_branch(db, user, book, selected_branch):
            edit_branch = selected_branch

    return {
        "available_courses": available_courses,
        "available_schools": available_schools,
        "selected_course": selected_course,
        "selected_school_slug": selected_school_slug,
        "selected_school_name": selected_school_name,
        "selected_workspace": selected_workspace,
        "selected_workspace_label": current_workspace_label,
        "selected_branch": selected_branch,
        "approved_branch": approved_branch,
        "personal_branch": personal_branch,
        "active_branch_label": _branch_label_for_ui(selected_branch, selected_school_name if selected_school_slug else None, selected_course),
        "edit_branch": edit_branch,
        "can_manage_selected_version": bool(user and selected_school_slug and can_manage_organization_version(db, user, selected_school_slug)),
        "query_params": {
            "school": selected_school_slug,
            "course_version": selected_course,
            "workspace": selected_workspace,
        },
    }


def _book_file_writes_for_branch(book: Book, repo, source_branch: str) -> list[RepositoryFileWrite]:
    writes: list[RepositoryFileWrite] = [
        RepositoryFileWrite(
            rel_path=book.content_path,
            content=repo.read_text(book.content_path, source_branch).encode("utf-8"),
        )
    ]

    for rel_path in sorted(repo.list_files(book.assets_path, source_branch)):
        asset_bytes = repo.read_binary(rel_path, source_branch)
        if asset_bytes:
            writes.append(RepositoryFileWrite(rel_path=rel_path, content=asset_bytes))

    for rel_path in sorted(repo.list_files(_worksheets_directory(book), source_branch)):
        worksheet_content = repo.read_text(rel_path, source_branch)
        if worksheet_content:
            writes.append(RepositoryFileWrite(rel_path=rel_path, content=worksheet_content.encode("utf-8")))

    return writes


def _book_related_paths(book: Book, repo, branch_name: str) -> set[str]:
    paths = {book.content_path}
    paths.update(repo.list_files(book.assets_path, branch_name))
    paths.update(repo.list_files(_worksheets_directory(book), branch_name))
    return {path for path in paths if path}


@router.get("")
def list_books(
    request: Request,
    course: str | None = None,
    subject: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    books = (
        db.query(Book)
        .options(joinedload(Book.organization), joinedload(Book.repository_source))
        .order_by(Book.course, Book.subject, Book.title)
        .all()
    )
    visible_books = [book for book in books if can_view_book(user, book)]
    available_courses = sorted({book.course for book in visible_books})
    available_subjects = sorted({book.subject for book in visible_books})

    selected_course = course.strip() if course else ""
    selected_subject = subject.strip() if subject else ""
    if selected_course:
        visible_books = [book for book in visible_books if book.course == selected_course]
    if selected_subject:
        visible_books = [book for book in visible_books if book.subject == selected_subject]

    return templates.TemplateResponse(
        name="books/list.html",
        request=request,
        context={
            "user": user,
            "books": visible_books,
            "available_courses": available_courses,
            "available_subjects": available_subjects,
            "selected_course": selected_course,
            "selected_subject": selected_subject,
            "message": _message_from_request(request),
        },
    )


@router.get("/new")
def new_book_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    organizations = [membership.organization for membership in user.memberships]
    repository_sources = db.query(RepositorySource).order_by(RepositorySource.name).all()
    if user.global_role != GlobalRole.admin:
        repository_sources = [source for source in repository_sources if can_create_book_in_repository(user, source)]
    return templates.TemplateResponse(
        name="books/form.html",
        request=request,
        context={
            "user": user,
            "organizations": organizations,
            "repository_sources": repository_sources,
            "visibilities": list(Visibility),
            "book": None,
            "message": _message_from_request(request),
        },
    )


@router.post("/new")
def create_book(
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    title: str = Form(...),
    course: str = Form(...),
    subject: str = Form(...),
    summary: str = Form(""),
    visibility: Visibility = Form(Visibility.private),
    repository_source_id: int = Form(...),
    organization_id: int | None = Form(None),
):
    slug = slugify(title)
    content_path, assets_path = default_book_paths(course, subject, slug)
    repo_source = db.get(RepositorySource, repository_source_id)
    if not repo_source:
        raise HTTPException(status_code=404, detail="Repository source not found")
    if not can_create_book_in_repository(user, repo_source):
        raise HTTPException(status_code=403, detail="No puedes crear libros en este repositorio")
    if organization_id is not None and organization_id != repo_source.organization_id:
        raise HTTPException(status_code=400, detail="El repositorio no pertenece a la organización seleccionada")
    organization_id = repo_source.organization_id
    if not slug or not slugify(course) or not slugify(subject):
        raise HTTPException(status_code=400, detail="Completa título, curso y materia")
    if db.query(Book).filter(Book.repository_source_id == repo_source.id, Book.content_path == content_path).first():
        raise HTTPException(status_code=409, detail="Ya existe un libro en esa ruta")
    if organization_id:
        organization = db.get(Organization, organization_id)
    book = Book(
        title=title.strip(),
        slug=slug,
        course=course.strip(),
        subject=subject.strip(),
        summary=summary.strip() or None,
        visibility=visibility,
        repository_source_id=repo_source.id,
        organization_id=organization_id,
        owner_user_id=None if organization_id else user.id,
        base_branch=repo_source.default_branch,
        content_path=content_path,
        assets_path=assets_path,
    )
    repo = repository_client_for(repo_source)
    if content_path in repo.list_files(_book_directory(book), book.base_branch):
        raise HTTPException(status_code=409, detail="Ya existe contenido en esa ruta del repositorio")
    initial_content = f"# {book.title}\n\n## Objetivo\n\nDescribe aquí el objetivo del libro.\n\n## Contenido\n\nEmpieza a redactar.\n"
    try:
        db.add(book)
        # The central model migration owns the UNIQUE(repo, path) constraint.
        # Flush before Git so concurrent duplicate requests fail before writes.
        db.flush()
        repo.write_text(
            rel_path=book.content_path,
            branch_name=book.base_branch,
            content=initial_content,
            commit_message=f"Create base book {book.title}",
            author_name=user.full_name,
            author_email=user.email,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ya existe un libro en esa ruta") from None
    except Exception:
        db.rollback()
        raise HTTPException(status_code=503, detail="No se pudo crear el libro. Inténtalo de nuevo") from None
    db.refresh(book)
    return _redirect_with_message(f"/books/{book.id}", "Libro creado correctamente.")


@router.get("/{book_id}")
def book_detail(
    book_id: int,
    request: Request,
    branch: str | None = None,
    school: str | None = None,
    course_version: str | None = None,
    workspace: str | None = None,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    book = (
        db.query(Book)
        .options(
            joinedload(Book.organization),
            joinedload(Book.repository_source),
            joinedload(Book.comments).joinedload(BookComment.author),
            joinedload(Book.review_requests),
        )
        .filter(Book.id == book_id)
        .first()
    )
    if not book or not can_view_book(user, book):
        raise HTTPException(status_code=404, detail="Book not found")

    repo = repository_client_for(book.repository_source)
    version_context = _resolve_version_context(db, user, book, school, course_version, workspace, branch)
    selected_branch = version_context["selected_branch"]
    version_pending = selected_branch not in repo.list_branches()
    if version_pending and branch is not None:
        raise HTTPException(status_code=404, detail="La versión solicitada no existe")
    read_branch = book.base_branch if version_pending else selected_branch
    content = repo.read_text(book.content_path, read_branch)
    edit_branch = version_context["edit_branch"]
    proposal_head_branch = version_context["personal_branch"] if user else None
    proposal_base_branch = version_context["approved_branch"] if version_context["selected_school_slug"] else book.base_branch

    return templates.TemplateResponse(
        name="books/detail.html",
        request=request,
        context={
            "user": user,
            "book": book,
            "selected_branch": selected_branch,
            "content": content,
            "document": build_book_document(content, book_id=book.id, branch_name=read_branch),
            "worksheet_entries": _worksheet_entries(book, read_branch),
            "read_branch": read_branch,
            "version_pending": version_pending,
            "edit_branch": edit_branch,
            "version_context": version_context,
            "proposal_head_branch": proposal_head_branch,
            "proposal_base_branch": proposal_base_branch,
            "can_create_proposal": bool(
                user
                and proposal_head_branch
                and proposal_head_branch != proposal_base_branch
                and can_edit_book_on_branch(db, user, book, proposal_head_branch)
            ),
            "review_entries": [
                {
                    "review": review,
                    "head_label": _review_branch_label(db, review.head_branch, book.course) if review.head_branch else None,
                    "base_label": _review_branch_label(db, review.base_branch, book.course),
                }
                for review in book.review_requests
            ],
            "comment_entries": [
                {
                    "comment": comment,
                    "branch_label": _review_branch_label(db, comment.branch_name, book.course),
                }
                for comment in book.comments
            ],
            "message": _message_from_request(request),
            "error": _error_from_request(request),
        },
    )


@router.get("/{book_id}/edit")
def edit_book_page(
    book_id: int,
    request: Request,
    branch: str | None = None,
    school: str | None = None,
    course_version: str | None = None,
    workspace: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    book = db.query(Book).options(joinedload(Book.organization), joinedload(Book.repository_source)).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    if branch and parse_branch_context(branch).is_personal and not can_edit_book_on_branch(db, user, book, branch):
        raise HTTPException(status_code=403, detail="No puedes editar esa versión personal")
    version_context = _resolve_version_context(db, user, book, school, course_version, workspace, branch)
    selected_branch = branch if branch and can_edit_book_on_branch(db, user, book, branch) else version_context["edit_branch"]
    if not selected_branch:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No editable versions available")

    repo = repository_client_for(book.repository_source)
    read_branch = selected_branch if selected_branch in repo.list_branches() else book.base_branch
    content = repo.read_text(book.content_path, read_branch)
    return templates.TemplateResponse(
        name="books/editor.html",
        request=request,
        context={
            "user": user,
            "book": book,
            "selected_branch": selected_branch,
            "content": content,
            "document_title": book.title,
            "editor_page_title": f"Editar {book.title}",
            "save_action": f"/books/{book.id}/edit",
            "cancel_href": f"/books/{book.id}?branch={selected_branch}",
            "resource_kind_label": "Libro",
            "preview_document": build_book_document(content, book_id=book.id, branch_name=read_branch),
            "pagebreak_marker": PAGEBREAK_MARKER,
            "asset_entries": _asset_entries(book, read_branch),
            "worksheet_entries": _worksheet_entries(book, read_branch),
            "version_context": version_context,
            "message": _message_from_request(request),
        },
    )


@router.post("/{book_id}/edit")
async def save_book(
    book_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    branch_name: str = Form(...),
    content: str = Form(...),
    commit_message: str | None = Form(None),
    assets: list[UploadFile] | None = File(None),
):
    book = db.query(Book).options(joinedload(Book.organization), joinedload(Book.repository_source)).filter(Book.id == book_id).first()
    if not book or not can_edit_book_on_branch(db, user, book, branch_name):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Edit not allowed")
    repo = repository_client_for(book.repository_source)
    asset_writes, uploaded_filenames = await _prepare_asset_writes(assets, book)

    # Detección de no-op: si el contenido enviado es byte-idéntico a lo que ya
    # hay en la rama y no se suben assets, no creamos commit ni propuesta.
    # Evita PRs vacías cuando el usuario abre el editor y guarda sin cambiar nada.
    new_bytes = content.encode("utf-8")
    if not asset_writes:
        try:
            current_text = repo.read_text(book.content_path, branch_name)
            if current_text and current_text.encode("utf-8") == new_bytes:
                return _redirect_with_message(
                    f"/books/{book.id}",
                    "No había cambios reales que guardar en esta versión.",
                    branch=branch_name,
                )
        except Exception:
            # Si la lectura falla seguimos con el flujo normal de escritura.
            _logger.exception("save_book: lectura previa para detección de no-op falló")

    resolved_commit_message = (commit_message or "").strip() or _default_commit_message(
        book,
        branch_name,
        uploaded_filenames,
    )
    repo.write_files(
        branch_name=branch_name,
        files=[RepositoryFileWrite(rel_path=book.content_path, content=new_bytes), *asset_writes],
        commit_message=resolved_commit_message,
        author_name=user.full_name,
        author_email=user.email,
    )
    message = f"Cambios guardados en la rama {branch_name}."
    if uploaded_filenames:
        message += f" Recursos anadidos: {', '.join(uploaded_filenames)}."
    return _redirect_with_message(
        f"/books/{book.id}",
        message,
        branch=branch_name,
    )


@router.post("/{book_id}/worksheets/new")
def create_worksheet(
    book_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    branch_name: str = Form(...),
    title: str = Form(...),
):
    book = db.query(Book).options(joinedload(Book.repository_source)).filter(Book.id == book_id).first()
    if not book or not can_edit_book_on_branch(db, user, book, branch_name):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Worksheet creation not allowed")

    worksheet_title = title.strip()
    worksheet_slug = slugify(worksheet_title)
    if not worksheet_title or not worksheet_slug:
        raise HTTPException(status_code=400, detail="Worksheet title required")

    repo = repository_client_for(book.repository_source)
    rel_path = _worksheet_rel_path(book, worksheet_slug)
    if repo.read_text(rel_path, branch_name):
        raise HTTPException(status_code=400, detail="Worksheet already exists")

    repo.write_text(
        rel_path=rel_path,
        branch_name=branch_name,
        content=_worksheet_content_template(worksheet_title),
        commit_message=f"Create worksheet {worksheet_title} on {branch_name}",
        author_name=user.full_name,
        author_email=user.email,
    )
    return _redirect_with_message(
        f"/books/{book.id}/worksheets/{worksheet_slug}/edit",
        f"Ficha {worksheet_title} creada correctamente.",
        branch=branch_name,
    )


@router.get("/{book_id}/worksheets/{worksheet_slug}")
def worksheet_detail(
    book_id: int,
    worksheet_slug: str,
    request: Request,
    branch: str | None = None,
    school: str | None = None,
    course_version: str | None = None,
    workspace: str | None = None,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    book = db.query(Book).options(joinedload(Book.repository_source)).filter(Book.id == book_id).first()
    if not book or not can_view_book(user, book):
        raise HTTPException(status_code=404, detail="Book not found")

    repo = repository_client_for(book.repository_source)
    version_context = _resolve_version_context(db, user, book, school, course_version, workspace, branch)
    selected_branch = version_context["selected_branch"]
    version_pending = selected_branch not in repo.list_branches()
    if version_pending and branch is not None:
        raise HTTPException(status_code=404, detail="La versión solicitada no existe")
    read_branch = book.base_branch if version_pending else selected_branch
    content = repo.read_text(_worksheet_rel_path(book, worksheet_slug), read_branch)
    if not content:
        raise HTTPException(status_code=404, detail="Worksheet not found")
    edit_branch = version_context["edit_branch"]
    worksheet_title = _extract_document_title(content, worksheet_slug.replace("-", " ").title())
    return templates.TemplateResponse(
        name="books/worksheet_detail.html",
        request=request,
        context={
            "user": user,
            "book": book,
            "worksheet_slug": worksheet_slug,
            "worksheet_title": worksheet_title,
            "worksheet_summary": _extract_document_summary(content),
            "selected_branch": selected_branch,
            "version_pending": version_pending,
            "document": build_book_document(content, book_id=book.id, branch_name=read_branch),
            "edit_branch": edit_branch,
            "version_context": version_context,
            "message": _message_from_request(request),
        },
    )


@router.get("/{book_id}/worksheets/{worksheet_slug}/edit")
def edit_worksheet_page(
    book_id: int,
    worksheet_slug: str,
    request: Request,
    branch: str | None = None,
    school: str | None = None,
    course_version: str | None = None,
    workspace: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    book = db.query(Book).options(joinedload(Book.repository_source)).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    if branch and parse_branch_context(branch).is_personal and not can_edit_book_on_branch(db, user, book, branch):
        raise HTTPException(status_code=403, detail="No puedes editar esa versión personal")
    version_context = _resolve_version_context(db, user, book, school, course_version, workspace, branch)
    selected_branch = branch if branch and can_edit_book_on_branch(db, user, book, branch) else version_context["edit_branch"]
    if not selected_branch:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No editable versions available")

    repo = repository_client_for(book.repository_source)
    rel_path = _worksheet_rel_path(book, worksheet_slug)
    read_branch = selected_branch if selected_branch in repo.list_branches() else book.base_branch
    content = repo.read_text(rel_path, read_branch)
    if not content:
        raise HTTPException(status_code=404, detail="Worksheet not found")
    worksheet_title = _extract_document_title(content, worksheet_slug.replace("-", " ").title())
    return templates.TemplateResponse(
        name="books/editor.html",
        request=request,
        context={
            "user": user,
            "book": book,
            "selected_branch": selected_branch,
            "content": content,
            "document_title": worksheet_title,
            "editor_page_title": f"Editar ficha {worksheet_title}",
            "save_action": f"/books/{book.id}/worksheets/{worksheet_slug}/edit",
            "cancel_href": f"/books/{book.id}/worksheets/{worksheet_slug}?branch={selected_branch}",
            "resource_kind_label": "Ficha",
            "preview_document": build_book_document(content, book_id=book.id, branch_name=read_branch),
            "pagebreak_marker": PAGEBREAK_MARKER,
            "asset_entries": _asset_entries(book, read_branch),
            "worksheet_entries": _worksheet_entries(book, read_branch),
            "version_context": version_context,
            "message": _message_from_request(request),
        },
    )


@router.post("/{book_id}/worksheets/{worksheet_slug}/edit")
async def save_worksheet(
    book_id: int,
    worksheet_slug: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    branch_name: str = Form(...),
    content: str = Form(...),
    commit_message: str | None = Form(None),
    assets: list[UploadFile] | None = File(None),
):
    book = db.query(Book).options(joinedload(Book.repository_source)).filter(Book.id == book_id).first()
    if not book or not can_edit_book_on_branch(db, user, book, branch_name):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Worksheet edit not allowed")

    repo = repository_client_for(book.repository_source)
    rel_path = _worksheet_rel_path(book, worksheet_slug)
    if not (repo.read_text(rel_path, branch_name) or repo.read_text(rel_path, book.base_branch)):
        raise HTTPException(status_code=404, detail="Worksheet not found")

    asset_writes, uploaded_filenames = await _prepare_asset_writes(assets, book)
    worksheet_title = _extract_document_title(content, worksheet_slug.replace("-", " ").title())
    resolved_commit_message = (commit_message or "").strip() or _default_worksheet_commit_message(
        worksheet_title,
        branch_name,
        uploaded_filenames,
    )
    repo.write_files(
        branch_name=branch_name,
        files=[RepositoryFileWrite(rel_path=rel_path, content=content.encode("utf-8")), *asset_writes],
        commit_message=resolved_commit_message,
        author_name=user.full_name,
        author_email=user.email,
    )
    message = f"Ficha guardada en la rama {branch_name}."
    if uploaded_filenames:
        message += f" Recursos anadidos: {', '.join(uploaded_filenames)}."
    return _redirect_with_message(
        f"/books/{book.id}/worksheets/{worksheet_slug}",
        message,
        branch=branch_name,
    )


@router.post("/{book_id}/comments")
def add_comment(
    book_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    branch_name: str = Form(...),
    anchor: str = Form(""),
    body: str = Form(...),
):
    book = db.get(Book, book_id)
    if not book or not can_view_book(user, book):
        raise HTTPException(status_code=404, detail="Book not found")
    comment = BookComment(
        book_id=book.id,
        author_id=user.id,
        branch_name=branch_name,
        anchor=anchor.strip() or None,
        body=body.strip(),
    )
    db.add(comment)
    db.commit()
    return _redirect_with_message(
        f"/books/{book.id}",
        "Comentario anadido correctamente.",
        branch=branch_name,
    )


@router.post("/{book_id}/comments/{comment_id}/delete")
def delete_comment(
    book_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    comment = db.get(BookComment, comment_id)
    if not comment or comment.book_id != book_id:
        raise HTTPException(status_code=404, detail="Comment not found")
    book = db.get(Book, book_id)
    if not book or not can_view_book(user, book):
        raise HTTPException(status_code=404, detail="Book not found")
    if user.global_role != GlobalRole.admin and comment.author_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Comment delete not allowed")
    branch_name = comment.branch_name
    db.delete(comment)
    db.commit()
    return _redirect_with_message(
        f"/books/{book.id}",
        "Comentario eliminado.",
        branch=branch_name,
    )


@router.post("/{book_id}/issues")
def create_issue(
    book_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    title: str = Form(...),
    body: str = Form(...),
):
    book = db.query(Book).options(joinedload(Book.repository_source)).filter(Book.id == book_id).first()
    if not book or not can_view_book(user, book):
        raise HTTPException(status_code=404, detail="Book not found")
    repo = repository_client_for(book.repository_source)
    try:
        issue = repo.create_issue(title=title, body=body)
    except httpx.HTTPStatusError as exc:
        _logger.warning("create_issue failed: status=%s body=%s", exc.response.status_code, exc.response.text[:300])
        return _redirect_with_error(f"/books/{book.id}", _friendly_github_error(exc, action="crear el aviso"))
    except Exception as exc:
        _logger.exception("create_issue unexpected error")
        return _redirect_with_error(f"/books/{book.id}", f"No se pudo registrar el aviso: {exc}")
    record = ReviewRequest(
        book_id=book.id,
        repo_source_id=book.repository_source_id,
        kind=ReviewKind.issue,
        title=title,
        body=body,
        base_branch=book.base_branch,
        head_branch=None,
        status=ReviewStatus.open,
        external_number=issue.get("number"),
        external_url=issue.get("html_url") or issue.get("url"),
    )
    db.add(record)
    db.commit()
    return _redirect_with_message(f"/books/{book.id}", "Aviso registrado correctamente.")


@router.post("/{book_id}/pull-requests")
def create_pull_request(
    book_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    head_branch: str = Form(...),
    base_branch: str = Form(""),
    title: str = Form(...),
    body: str = Form(""),
):
    book = db.query(Book).options(joinedload(Book.repository_source)).filter(Book.id == book_id).first()
    if not book or not can_edit_book_on_branch(db, user, book, head_branch):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PR not allowed")
    target_branch = base_branch.strip() or book.base_branch
    if head_branch == target_branch:
        return _redirect_with_error(
            f"/books/{book.id}",
            "No hay nada que proponer: estás intentando enviar la versión publicada hacia sí misma. "
            "Edita primero el libro en tu versión docente y guarda los cambios antes de enviar la propuesta.",
        )

    repo = repository_client_for(book.repository_source)
    try:
        repo.ensure_branch(target_branch, book.base_branch)
        pr = repo.create_pull_request(title=title, body=body, head_branch=head_branch, base_branch=target_branch)
    except httpx.HTTPStatusError as exc:
        _logger.warning("create_pull_request failed: status=%s body=%s", exc.response.status_code, exc.response.text[:300])
        return _redirect_with_error(f"/books/{book.id}", _friendly_github_error(exc, action="enviar la propuesta de cambio"))
    except Exception as exc:
        _logger.exception("create_pull_request unexpected error")
        return _redirect_with_error(f"/books/{book.id}", f"No se pudo enviar la propuesta de cambio: {exc}")
    record = ReviewRequest(
        book_id=book.id,
        repo_source_id=book.repository_source_id,
        kind=ReviewKind.pull_request,
        title=title,
        body=body,
        base_branch=target_branch,
        head_branch=head_branch,
        status=ReviewStatus.open,
        external_number=pr.get("number"),
        external_url=pr.get("html_url") or pr.get("url"),
    )
    db.add(record)
    db.commit()
    return _redirect_with_message(
        f"/books/{book.id}",
        "Propuesta de cambio enviada para revisión.",
        branch=head_branch,
    )


@router.post("/{book_id}/approve-version")
def approve_book_version(
    book_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    source_branch: str = Form(...),
    target_branch: str = Form(...),
):
    book = db.query(Book).options(joinedload(Book.repository_source)).filter(Book.id == book_id).first()
    if not book or not can_view_book(user, book):
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    target_context = parse_branch_context(target_branch)
    organization = organization_for_slug(db, target_context.organization_slug)
    if (target_context.is_personal or not organization or not target_context.course_slug
            or target_branch != approved_branch_name(organization.slug, target_context.course_slug)
            or not can_manage_organization_version(db, user, organization.slug)
            or (book.repository_source.organization_id and book.repository_source.organization_id != organization.id)):
        raise HTTPException(status_code=403, detail="No puedes aprobar esta versión")

    repo = repository_client_for(book.repository_source)
    if source_branch not in repo.list_branches() or not repo.read_text(book.content_path, source_branch):
        raise HTTPException(status_code=404, detail="La versión de origen no existe")
    if source_branch == target_branch:
        raise HTTPException(status_code=400, detail="Selecciona una versión de origen diferente")
    repo.ensure_branch(target_branch, book.base_branch)
    target_paths = _book_related_paths(book, repo, target_branch)
    source_paths = _book_related_paths(book, repo, source_branch)
    paths_to_delete = sorted(target_paths - source_paths)
    if paths_to_delete:
        repo.delete_files(
            branch_name=target_branch,
            rel_paths=paths_to_delete,
            commit_message=f"Remove deleted files from {book.title} for {target_branch}",
            author_name=user.full_name,
            author_email=user.email,
        )
    writes = _book_file_writes_for_branch(book, repo, source_branch)
    repo.write_files(
        branch_name=target_branch,
        files=writes,
        commit_message=f"Approve {book.title} for {target_branch}",
        author_name=user.full_name,
        author_email=user.email,
    )

    pending_review = (
        db.query(ReviewRequest)
        .filter(
            ReviewRequest.book_id == book.id,
            ReviewRequest.head_branch == source_branch,
            ReviewRequest.base_branch == target_branch,
            ReviewRequest.status == ReviewStatus.open,
        )
        .order_by(ReviewRequest.created_at.desc())
        .first()
    )
    if pending_review:
        pending_review.status = ReviewStatus.merged
    db.commit()
    return _redirect_with_message(
        f"/books/{book.id}",
        "Version aprobada para el colegio y curso seleccionados.",
        branch=target_branch,
    )


@router.post("/{book_id}/upload")
async def upload_asset(
    book_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    branch_name: str = Form(...),
    asset: UploadFile = File(...),
):
    book = db.query(Book).options(joinedload(Book.repository_source)).filter(Book.id == book_id).first()
    if not book or not can_edit_book_on_branch(db, user, book, branch_name):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Upload not allowed")

    data = await asset.read(max(settings.max_image_bytes, settings.max_audio_bytes) + 1)
    data, extension = _validate_asset_upload(data, asset.content_type or "")

    repo = repository_client_for(book.repository_source)
    filename = (slugify(Path(asset.filename or "recurso").stem) or "recurso") + extension
    rel_path = f"{book.assets_path}/{filename}"
    repo.write_binary(
        rel_path=rel_path,
        branch_name=branch_name,
        content=data,
        commit_message=_default_commit_message(book, branch_name, [filename]),
        author_name=user.full_name,
        author_email=user.email,
    )
    return _redirect_with_message(
        f"/books/{book.id}/edit",
        f"Archivo {filename} subido correctamente.",
        branch=branch_name,
    )


@router.post("/preview", response_class=HTMLResponse)
def preview_markdown(
    content: str = Form(...),
    book_id: int | None = Form(None),
    branch_name: str | None = Form(None),
):
    document = build_book_document(content, book_id=book_id, branch_name=branch_name)
    template = templates.env.get_template("books/_document.html")
    return template.render(document=document, document_id="editor-preview", compact_preview=True)


@router.get("/{book_id}/assets/{asset_path:path}")
def serve_book_asset(
    book_id: int,
    asset_path: str,
    branch: str | None = None,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    book = db.query(Book).options(joinedload(Book.repository_source)).filter(Book.id == book_id).first()
    if not book or not can_view_book(user, book):
        raise HTTPException(status_code=404, detail="Book not found")

    try:
        rel_path = _book_asset_path(book, asset_path)
    except ValueError:
        raise HTTPException(status_code=404, detail="Recurso no encontrado") from None
    repo = repository_client_for(book.repository_source)
    selected_branch = branch or book.base_branch
    asset_bytes = repo.read_binary(rel_path, selected_branch)
    if not asset_bytes:
        raise HTTPException(status_code=404, detail="Asset not found")

    headers = {"X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox; default-src 'none'"}
    try:
        if len(asset_bytes) > settings.max_image_bytes:
            raise ValueError("Recurso demasiado grande")
        image_bytes = _raster_png(asset_bytes)
    except (ValueError, OSError, SyntaxError, UnidentifiedImageError, Image.DecompressionBombError):
        # Legacy SVG/HTML and all unknown formats are downloads, never same-
        # origin documents. Do not trust their filename or declared MIME type.
        headers["Content-Disposition"] = "attachment; filename*=UTF-8''" + quote(Path(asset_path).name, safe="")
        return Response(content=asset_bytes, media_type="application/octet-stream", headers=headers)
    return Response(content=image_bytes, media_type="image/png", headers=headers)


@router.get("/{book_id}/export/pdf")
def export_pdf(
    book_id: int,
    branch: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    book = db.query(Book).options(joinedload(Book.repository_source)).filter(Book.id == book_id).first()
    if not book or not can_view_book(user, book):
        raise HTTPException(status_code=404, detail="Book not found")
    repo = repository_client_for(book.repository_source)
    selected_branch = branch or book.base_branch
    content = repo.read_text(book.content_path, selected_branch)
    from app.services.pdf_export import PDFExportError

    try:
        pdf_bytes = export_markdown_to_pdf(
            book,
            content,
            asset_loader=_pdf_asset_loader(book, repo, selected_branch),
        )
    except PDFExportError:
        raise HTTPException(status_code=400, detail="No se pudo exportar el PDF. Reduce el tamaño o simplifica el documento e inténtalo de nuevo.") from None
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{book.slug}.pdf"'},
    )
