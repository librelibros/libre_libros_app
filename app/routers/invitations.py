from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import require_admin
from app.models import Invitation, Organization, User
from app.security import start_session
from app.services.invitations import accept_invitation, issue_invitation, token_digest, valid_invitation
from app.templates import templates

router = APIRouter(tags=["invitations"])


@router.get("/admin/invitations")
def invitation_panel(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return templates.TemplateResponse(request=request, name="admin/invitations.html", context={
        "user": admin, "organizations": db.query(Organization).order_by(Organization.name).all(),
        "invitations": db.query(Invitation).order_by(Invitation.id.desc()).limit(100).all(),
    })


@router.post("/admin/invitations")
def create_invitation(request: Request, email: str = Form(...), organization_id: int = Form(...),
                      db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if get_settings().external_auth_only:
        raise HTTPException(400, "Las invitaciones locales requieren habilitar el acceso local.")
    invitation, token = issue_invitation(db, admin, email, organization_id)
    # El enlace se muestra una sola vez al emisor: entrega manual privada.
    return templates.TemplateResponse(request=request, name="admin/invitation_created.html", context={
        "user": admin, "invitation": invitation,
        "invitation_url": f"{(get_settings().public_base_url or str(request.base_url)).rstrip('/')}/invite/{token}",
    }, status_code=201)


@router.post("/admin/invitations/{invitation_id}/revoke")
def revoke_invitation(invitation_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    invitation = db.get(Invitation, invitation_id)
    if not invitation:
        raise HTTPException(404, "Invitación no encontrada.")
    db.execute(update(Invitation).where(Invitation.id == invitation_id, Invitation.used_at.is_(None),
                                       Invitation.revoked_at.is_(None)).values(revoked_at=datetime.utcnow()))
    db.commit()
    return RedirectResponse("/admin/invitations", status_code=303)


@router.get("/invite/{token}")
def open_invitation(token: str, request: Request, db: Session = Depends(get_db)):
    digest = token_digest(token)
    valid_invitation(db, digest)
    # No guardar el bearer original en la cookie firmada/legible. El digest
    # sólo se acepta dentro de la sesión firmada, nunca desde formularios.
    request.session["invitation_digest"] = digest
    return RedirectResponse("/invite", status_code=303)


@router.get("/invite")
def invitation_page(request: Request, db: Session = Depends(get_db)):
    invitation = valid_invitation(db, request.session.get("invitation_digest", ""))
    return templates.TemplateResponse(request=request, name="invitations/accept.html", context={
        "invitation": invitation, "external_auth_only": get_settings().external_auth_only,
    })


@router.post("/invite/accept")
def accept(request: Request, full_name: str = Form(""), password: str = Form(...), db: Session = Depends(get_db)):
    if get_settings().external_auth_only:
        raise HTTPException(403, "El acceso local está desactivado.")
    user = accept_invitation(db, request.session.get("invitation_digest", ""), full_name, password)
    start_session(request, user)
    return RedirectResponse("/", status_code=303)
