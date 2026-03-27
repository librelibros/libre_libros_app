from slugify import slugify
from sqlalchemy.orm import Session

from app.models import Book, GlobalRole, MembershipRole, OrganizationMembership, User, Visibility


def user_branch_name(user: User) -> str:
    return f"users/{slugify(user.full_name or user.email.split('@')[0])}"


def organization_branch_name(organization_slug: str) -> str:
    return f"orgs/{organization_slug}"


def user_memberships(db: Session, user_id: int) -> list[OrganizationMembership]:
    return (
        db.query(OrganizationMembership)
        .filter(OrganizationMembership.user_id == user_id)
        .all()
    )


def membership_for_org(db: Session, user_id: int, organization_id: int | None) -> OrganizationMembership | None:
    if not organization_id:
        return None
    return (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id == organization_id,
        )
        .first()
    )


def can_view_book(user: User | None, book: Book) -> bool:
    if book.visibility == Visibility.public:
        return True
    if not user:
        return False
    if user.global_role == GlobalRole.admin:
        return True
    if book.owner_user_id == user.id:
        return True
    if book.organization_id:
        return any(m.organization_id == book.organization_id for m in user.memberships)
    return False


def available_branches_for_book(db: Session, user: User, book: Book) -> list[str]:
    branches: list[str] = []
    personal_branch = user_branch_name(user)
    if user.global_role == GlobalRole.admin:
        branches.append(personal_branch)
        if book.organization:
            branches.append(organization_branch_name(book.organization.slug))
        branches.append(book.base_branch)
        return list(dict.fromkeys(branches))

    if book.owner_user_id == user.id:
        branches.append(personal_branch)

    membership = membership_for_org(db, user.id, book.organization_id)
    if membership and book.organization:
        branches.append(organization_branch_name(book.organization.slug))
        if membership.role == MembershipRole.organization_admin:
            branches.append(personal_branch)

    if book.visibility == Visibility.public:
        branches.append(personal_branch)

    return list(dict.fromkeys(branches))


def can_edit_book_on_branch(db: Session, user: User, book: Book, branch_name: str) -> bool:
    allowed = available_branches_for_book(db, user, book)
    return branch_name in allowed

