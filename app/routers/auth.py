from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import GlobalRole, User
from app.security import hash_password, password_needs_rehash, verify_password
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
            "gitlab_enabled": "gitlab" in oauth._registry,
            "external_auth_only": settings.external_auth_only,
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
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            name="auth/login.html",
            request=request,
            context={
                "error": "Credenciales no válidas.",
                "oidc_enabled": "oidc" in oauth._registry,
                "google_enabled": "google" in oauth._registry,
                "gitlab_enabled": "gitlab" in oauth._registry,
                "external_auth_only": settings.external_auth_only,
                "gitlab_name": settings.gitlab_name,
            },
            status_code=400,
        )
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        db.commit()
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)


@router.get("/register")
def register_page(request: Request):
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
    if settings.external_auth_only:
        return RedirectResponse("/login", status_code=303)
    normalized_email = email.lower().strip()
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
    db.commit()
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.get("/logout")
def logout_get(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


def _upsert_oidc_user(db: Session, email: str, name: str, provider: str) -> User:
    normalized_email = email.lower().strip()
    user = db.query(User).filter(User.email == normalized_email).first()
    if not user:
        user = User(
            email=normalized_email,
            full_name=name or normalized_email.split("@")[0],
            auth_provider=provider,
            global_role=GlobalRole.admin if settings.init_admin_email and normalized_email == settings.init_admin_email.lower().strip() else GlobalRole.editor,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif settings.init_admin_email and normalized_email == settings.init_admin_email.lower().strip() and user.global_role != GlobalRole.admin:
        user.global_role = GlobalRole.admin
        db.commit()
    return user


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
    user = _upsert_oidc_user(db, user_info["email"], user_info.get("name", ""), "google")
    request.session["user_id"] = user.id
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
    user = _upsert_oidc_user(db, user_info["email"], user_info.get("name", ""), "oidc")
    request.session["user_id"] = user.id
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
    email = user_info.get("email") or user_info.get("public_email")
    if not email:
        return RedirectResponse("/login", status_code=303)
    user = _upsert_oidc_user(db, email, user_info.get("name", user_info.get("username", "")), "gitlab")
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)
