"""Invitaciones locales: el token autoriza membresía, nunca recuperación de cuenta."""
import hashlib
import logging
import re
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import GlobalRole, Invitation, MembershipRole, Organization, OrganizationMembership, User
from app.security import hash_password, verify_password

logger = logging.getLogger(__name__)


def normalize_email(email: str) -> str:
    email = email.strip().lower()
    if len(email) > 255 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(400, "Correo no válido.")
    return email


def token_digest(token: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise HTTPException(400, "Invitación no válida o caducada.")
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def valid_invitation(db: Session, digest: str) -> Invitation:
    invitation = db.query(Invitation).filter(
        Invitation.token_hash == digest,
        Invitation.used_at.is_(None), Invitation.revoked_at.is_(None),
        Invitation.expires_at > datetime.utcnow(),
    ).first()
    if not invitation:
        raise HTTPException(400, "Invitación no válida o caducada.")
    return invitation


def issue_invitation(db: Session, admin: User, email: str, organization_id: int) -> tuple[Invitation, str]:
    if not admin.is_active or admin.global_role != GlobalRole.admin:
        raise HTTPException(403, "Solo administración puede invitar.")
    email = normalize_email(email)
    if not db.get(Organization, organization_id):
        raise HTTPException(400, "Organización no válida.")
    now = datetime.utcnow()
    count = db.query(func.count(Invitation.id)).filter(
        Invitation.created_by_user_id == admin.id,
        Invitation.created_at > now - timedelta(hours=1),
    ).scalar()
    if count >= get_settings().invitation_max_per_hour:
        raise HTTPException(429, "Límite de invitaciones alcanzado. Inténtalo más tarde.")
    token = secrets.token_urlsafe(32)
    try:
        db.execute(update(Invitation).where(
            Invitation.email_normalized == email,
            Invitation.organization_id == organization_id,
            Invitation.used_at.is_(None), Invitation.revoked_at.is_(None),
        ).values(revoked_at=now))
        invitation = Invitation(
            token_hash=token_digest(token), email_normalized=email,
            organization_id=organization_id, membership_role=MembershipRole.editor,
            created_by_user_id=admin.id, created_at=now,
            expires_at=now + timedelta(hours=get_settings().invitation_ttl_hours),
        )
        db.add(invitation)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Conflicto al emitir la invitación.") from exc
    logger.info("invitation issued id=%s actor=%s org=%s", invitation.id, admin.id, organization_id)
    return invitation, token


def accept_invitation(db: Session, digest: str, full_name: str, password: str) -> User:
    """UPDATE condicional y alta en una transacción; rollback incluye used_at.

    Para cuentas existentes se reautentica su contraseña, sin reemplazarla.
    Las cuentas externas deben usar un futuro flujo de enlace explícito.
    """
    try:
        invitation = valid_invitation(db, digest)
        user = db.query(User).filter(func.lower(User.email) == invitation.email_normalized).first()
        if user:
            if not user.is_active or not verify_password(password, user.password_hash):
                raise HTTPException(403, "Introduce la contraseña de tu cuenta existente para aceptar.")
        elif not full_name.strip() or len(full_name.strip()) > 255 or not 12 <= len(password) <= 128:
            raise HTTPException(400, "Indica tu nombre y una contraseña de entre 12 y 128 caracteres.")
        result = db.execute(update(Invitation).where(
            Invitation.id == invitation.id,
            Invitation.used_at.is_(None), Invitation.revoked_at.is_(None),
            Invitation.expires_at > datetime.utcnow(),
        ).values(used_at=datetime.utcnow()).execution_options(synchronize_session=False))
        if result.rowcount != 1:
            raise HTTPException(409, "La invitación ya no está disponible.")
        if not user:
            user = User(email=invitation.email_normalized, full_name=full_name.strip(),
                        password_hash=hash_password(password), global_role=GlobalRole.editor,
                        auth_provider="local")
            db.add(user)
            db.flush()
        # Una nueva invitación no cambia el rol de una membresía previa.
        existing = db.query(OrganizationMembership).filter_by(
            user_id=user.id, organization_id=invitation.organization_id,
        ).first()
        if not existing:
            db.add(OrganizationMembership(user_id=user.id, organization_id=invitation.organization_id,
                                          role=invitation.membership_role))
        db.commit()
        logger.info("invitation accepted id=%s user=%s", invitation.id, user.id)
        return user
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Conflicto al aceptar la invitación. Vuelve a intentarlo.") from exc
    except Exception:
        db.rollback()
        raise
