from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from slugify import slugify
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models import (
    GlobalRole,
    MembershipRole,
    Organization,
    OrganizationMembership,
    RepositoryProvider,
    RepositorySource,
    User,
)
from app.templates import templates

router = APIRouter(prefix="/admin", tags=["admin"])
settings = get_settings()


def _ensure_org_manager(db: Session, user: User, organization_id: int) -> Organization:
    organization = db.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    if user.global_role == GlobalRole.admin:
        return organization
    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id == organization_id,
        )
        .first()
    )
    if not membership or membership.role != MembershipRole.organization_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admin required")
    return organization


@router.get("")
def admin_panel(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return templates.TemplateResponse(
        name="admin/index.html",
        request=request,
        context={
            "user": admin,
            "users": db.query(User).order_by(User.full_name).all(),
            "organizations": db.query(Organization).order_by(Organization.name).all(),
            "memberships": db.query(OrganizationMembership).all(),
            "repository_sources": db.query(RepositorySource).order_by(RepositorySource.name).all(),
            "global_roles": list(GlobalRole),
            "membership_roles": list(MembershipRole),
            "repository_providers": list(RepositoryProvider),
            "example_repo_path": str(settings.example_repo_path) if settings.example_repo_path else "",
            "external_auth_only": settings.external_auth_only,
        },
    )


@router.post("/users")
def create_user(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    global_role: GlobalRole = Form(GlobalRole.editor),
):
    if settings.external_auth_only:
        raise HTTPException(status_code=400, detail="External authentication is enabled")
    from app.security import hash_password

    user = User(
        full_name=full_name.strip(),
        email=email.lower().strip(),
        password_hash=hash_password(password),
        global_role=global_role,
        auth_provider="local",
    )
    db.add(user)
    db.commit()
    return RedirectResponse("/admin", status_code=303)


@router.post("/organizations")
def create_organization(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    name: str = Form(...),
    description: str = Form(""),
):
    organization = Organization(name=name.strip(), slug=slugify(name), description=description.strip() or None)
    db.add(organization)
    db.commit()
    return RedirectResponse("/admin", status_code=303)


@router.post("/memberships")
def create_membership(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    user_id: int = Form(...),
    organization_id: int = Form(...),
    role: MembershipRole = Form(...),
):
    membership = OrganizationMembership(user_id=user_id, organization_id=organization_id, role=role)
    db.add(membership)
    db.commit()
    return RedirectResponse("/admin", status_code=303)


@router.post("/memberships/{membership_id}/delete")
def delete_membership(
    membership_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user:
        raise HTTPException(status_code=403, detail="Authentication required")
    membership = db.get(OrganizationMembership, membership_id)
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")
    _ensure_org_manager(db, user, membership.organization_id)
    db.delete(membership)
    db.commit()
    if user.global_role == GlobalRole.admin:
        return RedirectResponse("/admin", status_code=303)
    return RedirectResponse(f"/admin/organizations/{membership.organization_id}", status_code=303)


@router.post("/repositories")
def create_repository_source(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    name: str = Form(...),
    provider: RepositoryProvider = Form(...),
    default_branch: str = Form("main"),
    organization_id: int | None = Form(None),
    local_path: str = Form(""),
    provider_url: str = Form(""),
    repository_namespace: str = Form(""),
    repository_name: str = Form(""),
    service_username: str = Form(""),
    service_token: str = Form(""),
    is_public: bool = Form(False),
):
    source = RepositorySource(
        name=name.strip(),
        slug=slugify(name),
        provider=provider,
        default_branch=default_branch.strip() or "main",
        organization_id=organization_id,
        local_path=local_path.strip() or None,
        provider_url=provider_url.strip() or None,
        repository_namespace=repository_namespace.strip() or None,
        repository_name=repository_name.strip() or None,
        service_username=service_username.strip() or None,
        service_token=service_token.strip() or None,
        github_owner=repository_namespace.strip() or None,
        github_repo=repository_name.strip() or None,
        github_token=service_token.strip() or None,
        is_public=is_public,
    )
    db.add(source)
    db.commit()
    return RedirectResponse("/admin", status_code=303)


@router.get("/organizations/{organization_id}")
def organization_panel(
    organization_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user:
        raise HTTPException(status_code=403, detail="Authentication required")
    organization = _ensure_org_manager(db, user, organization_id)
    memberships = (
        db.query(OrganizationMembership)
        .filter(OrganizationMembership.organization_id == organization.id)
        .all()
    )
    return templates.TemplateResponse(
        name="admin/organization.html",
        request=request,
        context={
            "user": user,
            "organization": organization,
            "memberships": memberships,
            "users": db.query(User).order_by(User.full_name).all(),
            "membership_roles": list(MembershipRole),
        },
    )


@router.post("/organizations/{organization_id}/memberships")
def create_organization_membership(
    organization_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    user_id: int = Form(...),
    role: MembershipRole = Form(...),
):
    if not user:
        raise HTTPException(status_code=403, detail="Authentication required")
    _ensure_org_manager(db, user, organization_id)
    existing = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id == organization_id,
        )
        .first()
    )
    if not existing:
        db.add(OrganizationMembership(user_id=user_id, organization_id=organization_id, role=role))
        db.commit()
    return RedirectResponse(f"/admin/organizations/{organization_id}", status_code=303)
