from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import GlobalRole, OrganizationMembership, User


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(User, user_id)


def require_user(user: User | None = Depends(get_current_user)) -> User:
    if not user:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, detail="Authentication required")
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    if user.global_role != GlobalRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user


def load_memberships(db: Session, user_id: int) -> list[OrganizationMembership]:
    return db.query(OrganizationMembership).filter(OrganizationMembership.user_id == user_id).all()


def require_org_management(org_id_getter: Callable[[Request], int]):
    def dependency(
        request: Request,
        user: User = Depends(require_user),
        db: Session = Depends(get_db),
    ) -> User:
        if user.global_role == GlobalRole.admin:
            return user
        org_id = org_id_getter(request)
        membership = (
            db.query(OrganizationMembership)
            .filter(
                OrganizationMembership.user_id == user.id,
                OrganizationMembership.organization_id == org_id,
            )
            .first()
        )
        if not membership or membership.role.value != "organization_admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admin required")
        return user

    return dependency

