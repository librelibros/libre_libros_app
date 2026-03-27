from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from slugify import slugify
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user, require_user
from app.models import Book, BookComment, GlobalRole, Organization, RepositorySource, ReviewKind, ReviewRequest, ReviewStatus, User, Visibility
from app.services.books import default_book_paths, export_markdown_to_pdf, sanitize_filename
from app.services.markdown_utils import markdown_preview
from app.services.permissions import available_branches_for_book, can_edit_book_on_branch, can_view_book
from app.services.repository.factory import repository_client_for
from app.templates import templates

router = APIRouter(prefix="/books", tags=["books"])
settings = get_settings()


@router.get("")
def list_books(
    request: Request,
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
    return templates.TemplateResponse(
        name="books/list.html",
        request=request,
        context={"user": user, "books": visible_books},
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
        repository_sources = [
            source for source in repository_sources if source.organization_id is None or source.organization_id in {org.id for org in organizations}
        ]
    return templates.TemplateResponse(
        name="books/form.html",
        request=request,
        context={
            "user": user,
            "organizations": organizations,
            "repository_sources": repository_sources,
            "visibilities": list(Visibility),
            "book": None,
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
    if organization_id:
        organization = db.get(Organization, organization_id)
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")
        is_org_member = any(m.organization_id == organization_id for m in user.memberships)
        if user.global_role != GlobalRole.admin and not is_org_member:
            raise HTTPException(status_code=403, detail="Organization access required")
        if repo_source.organization_id and repo_source.organization_id != organization_id:
            raise HTTPException(status_code=400, detail="Repository source does not belong to the selected organization")
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
    db.add(book)
    db.commit()

    repo = repository_client_for(repo_source)
    initial_content = f"# {book.title}\n\n## Objetivo\n\nDescribe aquí el objetivo del libro.\n\n## Contenido\n\nEmpieza a redactar.\n"
    repo.write_text(
        rel_path=book.content_path,
        branch_name=book.base_branch,
        content=initial_content,
        commit_message=f"Create base book {book.title}",
        author_name=user.full_name,
        author_email=user.email,
    )
    return RedirectResponse(f"/books/{book.id}", status_code=303)


@router.get("/{book_id}")
def book_detail(
    book_id: int,
    request: Request,
    branch: str | None = None,
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
    available_branches = [book.base_branch]
    if user:
        available_branches.extend(available_branches_for_book(db, user, book))
    selected_branch = branch or available_branches[0]
    repo.ensure_branch(selected_branch, book.base_branch)
    content = repo.read_text(book.content_path, selected_branch)

    return templates.TemplateResponse(
        name="books/detail.html",
        request=request,
        context={
            "user": user,
            "book": book,
            "selected_branch": selected_branch,
            "available_branches": list(dict.fromkeys(available_branches)),
            "content": content,
            "rendered_content": markdown_preview(content),
        },
    )


@router.get("/{book_id}/edit")
def edit_book_page(
    book_id: int,
    request: Request,
    branch: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    book = db.query(Book).options(joinedload(Book.organization), joinedload(Book.repository_source)).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    branches = available_branches_for_book(db, user, book)
    if not branches:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No editable branches available")
    selected_branch = branch or branches[0]
    if not can_edit_book_on_branch(db, user, book, selected_branch):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden branch")

    repo = repository_client_for(book.repository_source)
    repo.ensure_branch(selected_branch, book.base_branch)
    content = repo.read_text(book.content_path, selected_branch) or repo.read_text(book.content_path, book.base_branch)
    return templates.TemplateResponse(
        name="books/editor.html",
        request=request,
        context={
            "user": user,
            "book": book,
            "branches": branches,
            "selected_branch": selected_branch,
            "content": content,
        },
    )


@router.post("/{book_id}/edit")
def save_book(
    book_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    branch_name: str = Form(...),
    content: str = Form(...),
    commit_message: str = Form("Update book"),
):
    book = db.query(Book).options(joinedload(Book.organization), joinedload(Book.repository_source)).filter(Book.id == book_id).first()
    if not book or not can_edit_book_on_branch(db, user, book, branch_name):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Edit not allowed")
    repo = repository_client_for(book.repository_source)
    repo.write_text(
        rel_path=book.content_path,
        branch_name=branch_name,
        content=content,
        commit_message=commit_message,
        author_name=user.full_name,
        author_email=user.email,
    )
    return RedirectResponse(f"/books/{book.id}?branch={branch_name}", status_code=303)


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
    return RedirectResponse(f"/books/{book.id}?branch={branch_name}", status_code=303)


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
    issue = repo.create_issue(title=title, body=body)
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
    return RedirectResponse(f"/books/{book.id}", status_code=303)


@router.post("/{book_id}/pull-requests")
def create_pull_request(
    book_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    head_branch: str = Form(...),
    title: str = Form(...),
    body: str = Form(""),
):
    book = db.query(Book).options(joinedload(Book.repository_source)).filter(Book.id == book_id).first()
    if not book or not can_edit_book_on_branch(db, user, book, head_branch):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PR not allowed")
    if head_branch == book.base_branch:
        raise HTTPException(status_code=400, detail="Head branch must differ from base branch")

    repo = repository_client_for(book.repository_source)
    pr = repo.create_pull_request(title=title, body=body, head_branch=head_branch, base_branch=book.base_branch)
    record = ReviewRequest(
        book_id=book.id,
        repo_source_id=book.repository_source_id,
        kind=ReviewKind.pull_request,
        title=title,
        body=body,
        base_branch=book.base_branch,
        head_branch=head_branch,
        status=ReviewStatus.open,
        external_number=pr.get("number"),
        external_url=pr.get("html_url") or pr.get("url"),
    )
    db.add(record)
    db.commit()
    return RedirectResponse(f"/books/{book.id}?branch={head_branch}", status_code=303)


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

    data = await asset.read()
    content_type = asset.content_type or ""
    if content_type.startswith("image/"):
        if len(data) > settings.max_image_bytes:
            raise HTTPException(status_code=400, detail="Image exceeds size limit")
    elif content_type == "audio/mpeg":
        if len(data) > settings.max_audio_bytes:
            raise HTTPException(status_code=400, detail="Audio exceeds size limit")
    else:
        raise HTTPException(status_code=400, detail="Only images and short mp3 files are allowed")

    repo = repository_client_for(book.repository_source)
    filename = sanitize_filename(asset.filename or "asset")
    rel_path = f"{book.assets_path}/{filename}"
    repo.write_binary(
        rel_path=rel_path,
        branch_name=branch_name,
        content=data,
        commit_message=f"Upload asset {filename}",
        author_name=user.full_name,
        author_email=user.email,
    )
    return RedirectResponse(f"/books/{book.id}/edit?branch={branch_name}", status_code=303)


@router.post("/preview", response_class=HTMLResponse)
def preview_markdown(content: str = Form(...)):
    return markdown_preview(content)


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
    pdf_bytes = export_markdown_to_pdf(book, content)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{book.slug}.pdf"'},
    )
