from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException


@pytest.fixture
def store():
    from app.database import Base, engine, SessionLocal
    from app.models import GlobalRole, Organization, User
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        admin = User(email="issuer@example.test", full_name="Admin", global_role=GlobalRole.admin)
        org = Organization(name="Colegio", slug="colegio")
        db.add_all([admin, org])
        db.commit()
        yield db, admin, org


def test_single_use_and_server_owned_fields(store):
    from app.models import OrganizationMembership, User
    from app.services.invitations import issue_invitation, accept_invitation, token_digest
    db, admin, org = store
    invitation, token = issue_invitation(db, admin, " Teacher@Example.test ", org.id)
    assert invitation.token_hash != token
    user = accept_invitation(db, token_digest(token), "Docente", "long-secret-password")
    assert user.email == "teacher@example.test"
    assert user.global_role.value == "editor"
    assert db.query(OrganizationMembership).one().organization_id == org.id
    with pytest.raises(HTTPException):
        accept_invitation(db, token_digest(token), "Otro", "long-secret-password")
    assert db.query(User).count() == 2


def test_existing_account_requires_password_and_never_resets(store):
    from app.models import User, Invitation
    from app.security import hash_password
    from app.services.invitations import issue_invitation, accept_invitation, token_digest
    db, admin, org = store
    original = hash_password("original-password")
    user = User(email="existing@example.test", full_name="Existente", password_hash=original)
    db.add(user)
    db.commit()
    invitation, token = issue_invitation(db, admin, user.email, org.id)
    with pytest.raises(HTTPException) as error:
        accept_invitation(db, token_digest(token), "Reemplazo", "different-password")
    assert error.value.status_code == 403
    assert db.get(Invitation, invitation.id).used_at is None
    accepted = accept_invitation(db, token_digest(token), "Reemplazo", "original-password")
    assert accepted.id == user.id
    assert accepted.password_hash == original
    assert accepted.full_name == "Existente"


@pytest.mark.parametrize("state", ["expired", "revoked", "used"])
def test_invalid_state_no_effects(store, state):
    from app.models import User, OrganizationMembership
    from app.services.invitations import issue_invitation, accept_invitation, token_digest
    db, admin, org = store
    invitation, token = issue_invitation(db, admin, "teacher@example.test", org.id)
    setattr(invitation, {"expired": "expires_at", "revoked": "revoked_at", "used": "used_at"}[state],
            datetime.utcnow() - timedelta(seconds=1))
    db.commit()
    with pytest.raises(HTTPException):
        accept_invitation(db, token_digest(token), "Docente", "long-secret-password")
    assert db.query(User).count() == 1
    assert db.query(OrganizationMembership).count() == 0


def test_reissue_revokes_previous_and_concurrent_acceptance(store):
    from app.database import SessionLocal
    from app.models import Invitation, OrganizationMembership
    from app.services.invitations import issue_invitation, accept_invitation, token_digest
    db, admin, org = store
    old, _ = issue_invitation(db, admin, "teacher@example.test", org.id)
    _, token = issue_invitation(db, admin, "teacher@example.test", org.id)
    db.refresh(old)
    assert old.revoked_at is not None
    db.rollback()
    def accept():
        with SessionLocal() as session:
            try:
                accept_invitation(session, token_digest(token), "Docente", "long-secret-password")
                return 200
            except HTTPException as exc:
                return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: accept(), range(2)))
    assert results.count(200) == 1
    assert set(results) <= {200, 400, 409}
    assert db.query(OrganizationMembership).count() == 1
