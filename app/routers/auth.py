from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import GlobalRole, User
from app.security import hash_password, password_needs_rehash, start_session, verify_password
from app.services.invitations import normalize_email
from app.templates import templates

router = APIRouter(tags=["auth"])
oauth = OAuth()
settings = get_settings()


def _init_oauth() -> None:
    if settings.google_client_id and settings.google_client_secret:
        oauth.register(
            name="google",
            server_metadata_url=settings.google_server_metadata_url,
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            client_kwargs={"scope": "openid email profile"},
        )
    if (
        settings.generic_oidc_enabled
        and settings.generic_oidc_server_metadata_url
        and settings.generic_oidc_client_id
        and settings.generic_oidc_client_secret
    ):
        oauth.register(
            name="oidc",
            server_metadata_url=settings.generic_oidc_server_metadata_url,
            client_id=settings.generic_oidc_client_id,
            client_secret=settings.generic_oidc_client_secret,
            client_kwargs={"scope": "openid email profile"},
        )
    if settings.github_oauth_enabled and settings.github_oauth_client_id and settings.github_oauth_client_secret:
        oauth.register(
            name="github",
            client_id=settings.github_oauth_client_id,
            client_secret=settings.github_oauth_client_secret,
            authorize_url="https://github.com/login/oauth/authorize",
            access_token_url="https://github.com/login/oauth/access_token",
            api_base_url="https://api.github.com/",
            client_kwargs={"scope": "read:user user:email"},
        )
    if settings.gitlab_enabled and settings.gitlab_url and settings.gitlab_client_id and settings.gitlab_client_secret:
        gitlab_public_url = settings.gitlab_url.rstrip("/")
        gitlab_internal_url = (settings.gitlab_internal_url or settings.gitlab_url).rstrip("/")
        oauth.register(
            name="gitlab",
            client_id=settings.gitlab_client_id,
            client_secret=settings.gitlab_client_secret,
            authorize_url=f"{gitlab_public_url}/oauth/authorize",
            access_token_url=f"{gitlab_internal_url}/oauth/token",
            api_base_url=f"{gitlab_internal_url}/api/v4/",
            client_kwargs={"scope": "read_user api"},
        )


_init_oauth()


_EXTERNAL_PROVIDER_PRIORITY = ("github", "gitlab", "google", "oidc")


def _first_external_start_url() -> str | None:
    for provider in _EXTERNAL_PROVIDER_PRIORITY:
        if provider in oauth._registry:
            return f"/auth/{provider}/start"
    return None


@router.get("/login")
def login_page(request: Request, user=Depends(get_current_user)):
    if user:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        name="auth/login.html",
        request=request,
        context={
            "oidc_enabled": "oidc" in oauth._registry,
            "google_enabled": "google" in oauth._registry,
            "github_enabled": "github" in oauth._registry,
            "gitlab_enabled": "gitlab" in oauth._registry,
            "external_auth_only": settings.external_auth_only,
            "github_name": settings.github_oauth_name,
            "gitlab_name": settings.gitlab_name,
        },
    )


@router.post("/login")
def login(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(...),
    password: str = Form(...),
):
    if settings.external_auth_only:
        return RedirectResponse("/login", status_code=303)
    user = db.query(User).filter(User.email == email.lower().strip()).first()
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            name="auth/login.html",
            request=request,
            context={
                "error": "Credenciales no válidas.",
                "oidc_enabled": "oidc" in oauth._registry,
                "google_enabled": "google" in oauth._registry,
                "github_enabled": "github" in oauth._registry,
                "gitlab_enabled": "gitlab" in oauth._registry,
                "external_auth_only": settings.external_auth_only,
                "github_name": settings.github_oauth_name,
                "gitlab_name": settings.gitlab_name,
            },
            status_code=400,
        )
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        db.commit()
    start_session(request, user)
    return RedirectResponse("/", status_code=303)


@router.get("/register")
def register_page(request: Request):
    if settings.invitation_only:
        raise HTTPException(403, "El alta requiere una invitación. Abre el enlace recibido.")
    external = _first_external_start_url()
    if external:
        return RedirectResponse(external, status_code=303)
    if settings.external_auth_only:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(name="auth/register.html", request=request, context={})


@router.post("/register")
def register(
    request: Request,
    db: Session = Depends(get_db),
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    if settings.invitation_only:
        raise HTTPException(403, "El alta requiere una invitación.")
    external = _first_external_start_url()
    if external:
        return RedirectResponse(external, status_code=303)
    if settings.external_auth_only:
        return RedirectResponse("/login", status_code=303)
    normalized_email = normalize_email(email)
    existing = db.query(User).filter(User.email == normalized_email).first()
    if existing:
        return templates.TemplateResponse(
            name="auth/register.html",
            request=request,
            context={"error": "Ya existe una cuenta con ese correo."},
            status_code=400,
        )
    user = User(
        full_name=full_name.strip(),
        email=normalized_email,
        password_hash=hash_password(password),
        global_role=GlobalRole.editor,
        auth_provider="local",
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "La cuenta ya existe.") from exc
    start_session(request, user)
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


def _upsert_oidc_user(db: Session, email: str, name: str, provider: str,
                      subject: str | None = None, email_verified: bool = False) -> User:
    from app.models import ExternalIdentity

    if email_verified is not True or not subject:
        raise HTTPException(403, "El proveedor debe verificar el correo y la identidad.")
    normalized_email = normalize_email(email)
    identity = db.query(ExternalIdentity).filter_by(provider=provider, subject=subject).first()
    if identity:
        user = db.get(User, identity.user_id)
        if not user or not user.is_active:
            raise HTTPException(403, "Cuenta no disponible.")
        return user
    # Nunca vincular por email ni promover administradores desde callbacks.
    if settings.invitation_only or db.query(User).filter(User.email == normalized_email).first():
        raise HTTPException(403, "Identidad no vinculada. Contacta con administración.")
    user = User(email=normalized_email, full_name=name or normalized_email.split("@")[0],
                auth_provider=provider.split(":", 1)[0], global_role=GlobalRole.editor)
    try:
        db.add(user)
        db.flush()
        db.add(ExternalIdentity(user_id=user.id, provider=provider, subject=subject))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "La identidad ya está registrada.") from exc
    return user


def _github_email(user_info: dict, emails: list[dict]) -> str | None:
    primary_verified = [
        email["email"]
        for email in emails
        if email.get("primary") and email.get("verified") and email.get("email")
    ]
    if primary_verified:
        return primary_verified[0]
    verified = [email["email"] for email in emails if email.get("verified") and email.get("email")]
    if verified:
        return verified[0]
    return None


@router.get("/auth/github/start")
async def github_start(request: Request):
    if "github" not in oauth._registry:
        return RedirectResponse("/login", status_code=303)
    redirect_uri = request.url_for("github_callback")
    return await oauth.github.authorize_redirect(request, redirect_uri)


@router.get("/auth/github/callback", name="github_callback")
async def github_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.github.authorize_access_token(request)
    user_response = await oauth.github.get("user", token=token)
    user_info = user_response.json()
    emails_response = await oauth.github.get("user/emails", token=token)
    email = _github_email(user_info, emails_response.json())
    if not email:
        return RedirectResponse("/login", status_code=303)
    name = user_info.get("name") or user_info.get("login") or ""
    user = _upsert_oidc_user(db, email, name, "github:https://github.com",
                             str(user_info["id"]) if user_info.get("id") else None, True)
    start_session(request, user)
    return RedirectResponse("/", status_code=303)


@router.get("/auth/google/start")
async def google_start(request: Request):
    if "google" not in oauth._registry:
        return RedirectResponse("/login", status_code=303)
    redirect_uri = request.url_for("google_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/google/callback", name="google_callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get("userinfo") or await oauth.google.parse_id_token(request, token)
    user = _upsert_oidc_user(db, user_info.get("email", ""), user_info.get("name", ""),
                             "google:" + settings.google_server_metadata_url,
                             user_info.get("sub"), user_info.get("email_verified") is True)
    start_session(request, user)
    return RedirectResponse("/", status_code=303)


@router.get("/auth/oidc/start")
async def oidc_start(request: Request):
    if "oidc" not in oauth._registry:
        return RedirectResponse("/login", status_code=303)
    redirect_uri = request.url_for("oidc_callback")
    return await oauth.oidc.authorize_redirect(request, redirect_uri)


@router.get("/auth/oidc/callback", name="oidc_callback")
async def oidc_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.oidc.authorize_access_token(request)
    user_info = token.get("userinfo") or await oauth.oidc.parse_id_token(request, token)
    user = _upsert_oidc_user(db, user_info.get("email", ""), user_info.get("name", ""),
                             "oidc:" + (settings.generic_oidc_server_metadata_url or ""),
                             user_info.get("sub"), user_info.get("email_verified") is True)
    start_session(request, user)
    return RedirectResponse("/", status_code=303)


@router.get("/auth/gitlab/start")
async def gitlab_start(request: Request):
    if "gitlab" not in oauth._registry:
        return RedirectResponse("/login", status_code=303)
    redirect_uri = request.url_for("gitlab_callback")
    return await oauth.gitlab.authorize_redirect(request, redirect_uri)


@router.get("/auth/gitlab/callback", name="gitlab_callback")
async def gitlab_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.gitlab.authorize_access_token(request)
    response = await oauth.gitlab.get("user", token=token)
    user_info = response.json()
    # REST public_email is not proof of verification. Fail closed unless the
    # configured provider explicitly supplies a verified-email claim.
    email = user_info.get("email") if user_info.get("email_verified") is True else None
    if not email:
        return RedirectResponse("/login", status_code=303)
    user = _upsert_oidc_user(db, email, user_info.get("name", user_info.get("username", "")),
                             "gitlab:" + (settings.gitlab_url or "").rstrip("/"),
                             str(user_info["id"]) if user_info.get("id") else None, True)
    start_session(request, user)
    return RedirectResponse("/", status_code=303)
