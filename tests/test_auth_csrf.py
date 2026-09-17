import re

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LIBRE_LIBROS_INVITATION_ONLY", "true")
    monkeypatch.setenv("LIBRE_LIBROS_CSRF_ENABLED", "true")
    from app import main
    monkeypatch.setattr(main, "sync_bootstrap_content", lambda: None)
    with TestClient(main.app, follow_redirects=False) as client:
        yield client


def csrf(client, path="/login"):
    response = client.get(path)
    assert response.status_code == 200, response.text
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
    assert match, response.text
    return match.group(1)


def login(client):
    token = csrf(client)
    response = client.post("/login", data={"email": "admin@test.local", "password": "admin12345", "csrf_token": token})
    assert response.status_code == 303, response.text
    return csrf(client, "/admin/invitations")


def test_login_csrf_missing_foreign_and_valid(client):
    credentials = {"email": "admin@test.local", "password": "admin12345"}
    assert client.post("/login", data=credentials).status_code == 403
    token = csrf(client)
    assert client.post("/login", data={**credentials, "csrf_token": "wrong"}).status_code == 403
    assert client.post("/login", data={**credentials, "csrf_token": token},
                       headers={"Origin": "https://foreign.example"}).status_code == 403
    result = client.post("/login", data={**credentials, "csrf_token": token},
                         headers={"Origin": "http://testserver"})
    assert result.status_code == 303
    cookie = result.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert csrf(client, "/admin/invitations") != token


def test_logout_post_only_and_header_token(client):
    token = login(client)
    assert client.get("/logout").status_code == 405
    assert client.post("/logout").status_code == 403
    assert client.post("/logout", headers={"X-CSRF-Token": token}).status_code == 303
    assert client.get("/admin/invitations").status_code != 200


def test_inactive_and_revoked_session_rejected(client):
    from app.database import SessionLocal
    from app.models import User
    login(client)
    with SessionLocal() as db:
        user = db.query(User).one()
        user.session_version += 1
        db.commit()
    assert client.get("/admin/invitations").status_code != 200
    login(client)
    with SessionLocal() as db:
        user = db.query(User).one()
        user.is_active = False
        db.commit()
    assert client.get("/admin/invitations").status_code != 200
    token = csrf(client)
    assert client.post("/login", data={"email": "admin@test.local", "password": "admin12345", "csrf_token": token}).status_code == 400


def test_closed_registration_and_oauth_no_autolinking(client):
    from app.database import SessionLocal
    from app.models import User
    from app.routers.auth import _upsert_oidc_user, _github_email
    from fastapi import HTTPException
    token = csrf(client)
    assert client.get("/register").status_code == 403
    assert client.post("/register", data={"full_name": "Nuevo", "email": "new@example.test", "password": "password", "csrf_token": token}).status_code == 403
    with SessionLocal() as db:
        for email, verified in [("new@example.test", True), ("admin@test.local", True), ("admin@test.local", False)]:
            with pytest.raises(HTTPException):
                _upsert_oidc_user(db, email, "Nuevo", "oidc:test", "subject", verified)
        assert db.query(User).count() == 1
    assert _github_email({"email": "unverified@example.test"}, []) is None


def test_secure_cookie_and_external_only_gate(client):
    from app.config import get_settings
    from app.security import CsrfMiddleware
    from starlette.middleware.sessions import SessionMiddleware
    from fastapi import FastAPI
    app = FastAPI()
    app.add_middleware(CsrfMiddleware)
    app.add_middleware(SessionMiddleware, secret_key="fixture-secret", https_only=True, same_site="lax")
    @app.get("/")
    def home():
        return {"ok": True}
    with TestClient(app, base_url="https://testserver") as secure_client:
        cookie = secure_client.get("/").headers["set-cookie"].lower()
        assert "secure" in cookie and "httponly" in cookie and "samesite=lax" in cookie
    token = login(client)
    get_settings().external_auth_only = True
    assert client.post("/admin/invitations", data={"email": "new@example.test", "organization_id": 1,
                                                  "csrf_token": token}).status_code == 400


def test_token_from_another_session_and_unicode_rejected(client):
    from app.main import app
    token = csrf(client)
    with TestClient(app, follow_redirects=False) as other:
        assert csrf(other) != token
        for submitted in (token, "ñ"):
            assert other.post("/login", data={"email": "admin@test.local", "password": "admin12345",
                                             "csrf_token": submitted}).status_code == 403


def test_linked_oauth_identity_is_stable_not_email(client):
    from app.database import SessionLocal
    from app.models import ExternalIdentity, User
    from app.routers.auth import _upsert_oidc_user
    from fastapi import HTTPException
    with SessionLocal() as db:
        user = db.query(User).one()
        db.add(ExternalIdentity(user_id=user.id, provider="oidc:issuer", subject="stable"))
        db.commit()
        assert _upsert_oidc_user(db, "changed@example.test", "Nombre", "oidc:issuer", "stable", True).id == user.id
        for provider, subject in [("oidc:other", "stable"), ("oidc:issuer", "other")]:
            with pytest.raises(HTTPException):
                _upsert_oidc_user(db, user.email, "Nombre", provider, subject, True)
        user.is_active = False
        db.commit()
        with pytest.raises(HTTPException):
            _upsert_oidc_user(db, user.email, "Nombre", "oidc:issuer", "stable", True)


def test_local_invitation_end_to_end_and_no_get_consumption(client):
    from app.database import SessionLocal
    from app.models import Invitation, Organization, OrganizationMembership, User
    token = login(client)
    with SessionLocal() as db:
        org = Organization(name="Colegio", slug="colegio")
        db.add(org)
        db.commit()
        org_id = org.id
    data = {"email": "teacher@example.test", "organization_id": org_id}
    assert client.post("/admin/invitations", data=data).status_code == 403
    response = client.post("/admin/invitations", data={**data, "csrf_token": token})
    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "no-store"
    invitation_url = re.search(r'value="(http://testserver/invite/[^"]+)"', response.text).group(1)
    assert client.post("/logout", headers={"X-CSRF-Token": token}).status_code == 303
    response = client.get(invitation_url)
    assert response.status_code == 303 and response.headers["location"] == "/invite"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert invitation_url.rsplit("/", 1)[1] not in response.headers.get("set-cookie", "")
    token = csrf(client, "/invite")
    with SessionLocal() as db:
        assert db.query(Invitation).one().used_at is None
    data = {"full_name": "Docente", "password": "long-secret-password", "email": "attacker@example.test", "role": "admin", "organization_id": 999}
    assert client.post("/invite/accept", data=data).status_code == 403
    response = client.post("/invite/accept", data={**data, "csrf_token": token})
    assert response.status_code == 303, response.text
    with SessionLocal() as db:
        user = db.query(User).filter_by(email="teacher@example.test").one()
        assert user.global_role.value == "editor"
        assert db.query(OrganizationMembership).one().organization_id == org_id
        assert db.query(Invitation).one().used_at is not None
    assert client.get(invitation_url).status_code == 400


def test_memberships_unique_fk_and_integrity_response(client):
    from app.database import SessionLocal, engine
    from app.models import Organization, User
    from sqlalchemy import text
    token = login(client)
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
    with SessionLocal() as db:
        org = Organization(name="Colegio", slug="colegio")
        db.add(org)
        db.commit()
        data = {"organization_id": org.id, "user_id": db.query(User).one().id, "role": "editor", "csrf_token": token}
    assert client.post("/admin/memberships", data=data).status_code == 303
    assert client.post("/admin/memberships", data=data).status_code == 409
    assert client.post("/admin/memberships", data={**data, "user_id": 999}).status_code in {400, 409}


def test_origin_policy_and_multipart_header(client):
    from app.config import get_settings
    token = csrf(client)
    settings = get_settings()
    settings.csrf_require_origin = True
    data = {"email": "admin@test.local", "password": "admin12345"}
    assert client.post("/login", data={**data, "csrf_token": token}).status_code == 403
    response = client.post("/login", files={key: (None, value) for key, value in data.items()},
                           headers={"X-CSRF-Token": token, "Referer": "http://testserver/login"})
    assert response.status_code == 303


def test_null_origin_rejected_without_demo_bypass(client):
    from app.config import get_settings
    token = csrf(client)
    settings = get_settings()
    # Default: the opaque sentinel is never same-origin (sandboxed iframe).
    headers = {"X-CSRF-Token": token, "Origin": "null"}
    assert client.post("/login", data={"email": "admin@test.local", "password": "admin12345"},
                       headers=headers).status_code == 403
    # There is no demo bypass: same-origin forms remain subject to tokens.
    assert not hasattr(settings, "csrf_allow_null_origin")
    response = client.get("/login")
    assert response.headers["referrer-policy"] == "same-origin"
    # A Referer alongside Origin:null is still an attacker-replay signature.
    replay = client.post("/login", data={"email": "admin@test.local", "password": "admin12345"},
                         headers={**headers, "Referer": "http://testserver/"})
    assert replay.status_code == 403
