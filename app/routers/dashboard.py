from collections import defaultdict

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Book, MembershipRole, OrganizationMembership, ReviewRequest, ReviewStatus, User, Visibility
from app.services.permissions import can_view_book
from app.services.review_sync import refresh_open_reviews
from app.templates import templates

router = APIRouter(tags=["dashboard"])


@router.get("/")
def home(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login", status_code=303)

    books = (
        db.query(Book)
        .options(joinedload(Book.organization), joinedload(Book.repository_source))
        .order_by(Book.course, Book.subject, Book.title)
        .all()
    )
    visible_books = [book for book in books if can_view_book(user, book)]
    grouped = defaultdict(lambda: defaultdict(list))
    for book in visible_books:
        grouped[book.course][book.subject].append(book)

    # Refrescamos las propuestas abiertas contra GitHub antes de listar para
    # que la home muestre el estado real (mergeada → "Aceptada", commits/comentarios
    # nuevos). El servicio cachea por SYNC_TTL para no martillear la API.
    if refresh_open_reviews(db) > 0:
        db.commit()

    recent_reviews = (
        db.query(ReviewRequest)
        .options(joinedload(ReviewRequest.book))
        .order_by(ReviewRequest.created_at.desc())
        .limit(10)
        .all()
    )
    open_reviews_count = sum(1 for r in recent_reviews if r.status in (ReviewStatus.open, ReviewStatus.draft))
    manageable_org_ids = {
        membership.organization_id
        for membership in db.query(OrganizationMembership)
        .filter(OrganizationMembership.user_id == user.id)
        .all()
        if membership.role == MembershipRole.organization_admin
    }
    manageable_organizations = [book.organization for book in visible_books if book.organization_id in manageable_org_ids]
    manageable_organizations = list(
        {organization.id: organization for organization in manageable_organizations if organization is not None}.values()
    )

    return templates.TemplateResponse(
        name="dashboard/index.html",
        request=request,
        context={
            "user": user,
            "grouped_books": dict(grouped),
            "books_count": len(visible_books),
            "public_books_count": len([book for book in visible_books if book.visibility == Visibility.public]),
            "recent_reviews": recent_reviews,
            "open_reviews_count": open_reviews_count,
            "manageable_organizations": manageable_organizations,
        },
    )
