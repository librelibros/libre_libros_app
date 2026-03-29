from __future__ import annotations

from dataclasses import dataclass

from slugify import slugify
from sqlalchemy.orm import Session

from app.models import Book, GlobalRole, MembershipRole, Organization, OrganizationMembership, User, Visibility


@dataclass(frozen=True)
class BranchContext:
    branch_name: str
    organization_slug: str | None = None
    course_slug: str | None = None
    is_personal: bool = False


def user_identity_slug(user: User) -> str:
    return slugify(user.full_name or user.email.split("@")[0]) or "editor"


def user_branch_name(user: User) -> str:
    return f"users/{user_identity_slug(user)}"


def course_branch_slug(course_name: str | None) -> str:
    return slugify(course_name or "general") or "general"


def approved_branch_name(organization_slug: str, course_name: str) -> str:
    return f"orgs/{slugify(organization_slug)}/{course_branch_slug(course_name)}"


def organization_branch_name(organization_slug: str) -> str:
    return f"orgs/{organization_slug}"


def user_workspace_branch_name(user: User, organization_slug: str | None, course_name: str) -> str:
    organization_segment = slugify(organization_slug or "base") or "base"
    return f"users/{user_identity_slug(user)}/{organization_segment}/{course_branch_slug(course_name)}"


def parse_branch_context(branch_name: str) -> BranchContext:
    parts = [part for part in branch_name.split("/") if part]
    if not parts:
        return BranchContext(branch_name=branch_name)
    if parts[0] == "orgs" and len(parts) >= 3:
        return BranchContext(
            branch_name=branch_name,
            organization_slug=parts[1],
            course_slug=parts[2],
        )
    if parts[0] == "orgs" and len(parts) == 2:
        return BranchContext(
            branch_name=branch_name,
            organization_slug=parts[1],
        )
    if parts[0] == "users" and len(parts) >= 4:
        return BranchContext(
            branch_name=branch_name,
            organization_slug=None if parts[2] == "base" else parts[2],
            course_slug=parts[3],
            is_personal=True,
        )
    if parts[0] == "users" and len(parts) >= 2:
        return BranchContext(
            branch_name=branch_name,
            is_personal=True,
        )
    return BranchContext(branch_name=branch_name)


def user_memberships(db: Session, user_id: int) -> list[OrganizationMembership]:
    return (
        db.query(OrganizationMembership)
        .filter(OrganizationMembership.user_id == user_id)
        .all()
    )


def organization_for_slug(db: Session, organization_slug: str | None) -> Organization | None:
    if not organization_slug:
        return None
    return db.query(Organization).filter(Organization.slug == organization_slug).first()


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


def can_manage_organization_version(db: Session, user: User, organization_slug: str | None) -> bool:
    if not organization_slug:
        return user.global_role == GlobalRole.admin
    if user.global_role == GlobalRole.admin:
        return True
    organization = organization_for_slug(db, organization_slug)
    if not organization:
        return False
    membership = membership_for_org(db, user.id, organization.id)
    return bool(membership and membership.role == MembershipRole.organization_admin)


def is_user_workspace_branch(user: User, branch_name: str) -> bool:
    prefix = f"users/{user_identity_slug(user)}"
    return branch_name == prefix or branch_name.startswith(f"{prefix}/")


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
    personal_branch = user_workspace_branch_name(user, None, book.course)
    legacy_personal_branch = user_branch_name(user)
    if user.global_role == GlobalRole.admin:
        branches.extend([personal_branch, legacy_personal_branch])
        if book.organization:
            branches.append(approved_branch_name(book.organization.slug, book.course))
            branches.append(organization_branch_name(book.organization.slug))
        branches.append(book.base_branch)
        return list(dict.fromkeys(branches))

    if book.owner_user_id == user.id:
        branches.extend([personal_branch, legacy_personal_branch])

    membership = membership_for_org(db, user.id, book.organization_id)
    if membership and book.organization:
        branches.append(approved_branch_name(book.organization.slug, book.course))
        branches.append(organization_branch_name(book.organization.slug))
        if membership.role == MembershipRole.organization_admin:
            branches.extend([personal_branch, legacy_personal_branch])

    if book.visibility == Visibility.public:
        branches.extend([personal_branch, legacy_personal_branch])

    return list(dict.fromkeys(branches))


def can_edit_book_on_branch(db: Session, user: User, book: Book, branch_name: str) -> bool:
    if user.global_role == GlobalRole.admin:
        return True
    if not can_view_book(user, book):
        return False
    if is_user_workspace_branch(user, branch_name):
        return True
    context = parse_branch_context(branch_name)
    if context.organization_slug:
        return can_manage_organization_version(db, user, context.organization_slug)
    if book.organization and branch_name == organization_branch_name(book.organization.slug):
        return can_manage_organization_version(db, user, book.organization.slug)
    return False
