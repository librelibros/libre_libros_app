import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.models import GlobalRole, User
from app.routers import admin, auth, books, dashboard
from app.security import hash_password, password_needs_rehash, verify_password
from app.services.bootstrap import sync_example_repository
from app.services.runtime_migrations import ensure_runtime_schema
from app.templates import templates

settings = get_settings()


def default_external_auth_provider() -> str:
    if settings.github_oauth_enabled:
        return "github"
    if settings.gitlab_enabled:
        return "gitlab"
    if settings.google_client_id and settings.google_client_secret:
        return "google"
    if settings.generic_oidc_enabled:
        return "oidc"
    return "local"


def create_default_admin() -> None:
    if not settings.init_admin_email:
        return
    db: Session = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == settings.init_admin_email.lower().strip()).first()
        if existing:
            changed = False
            if existing.full_name != settings.init_admin_name:
                existing.full_name = settings.init_admin_name
                changed = True
            if existing.global_role != GlobalRole.admin:
                existing.global_role = GlobalRole.admin
                changed = True
            desired_provider = default_external_auth_provider() if settings.external_auth_only else "local"
            if existing.auth_provider != desired_provider:
                existing.auth_provider = desired_provider
                changed = True
            if not settings.external_auth_only and settings.init_admin_password:
                if password_needs_rehash(existing.password_hash) or not verify_password(
                    settings.init_admin_password,
                    existing.password_hash,
                ):
                    existing.password_hash = hash_password(settings.init_admin_password)
                    changed = True
            elif settings.external_auth_only and existing.password_hash is not None:
                existing.password_hash = None
                changed = True
            if changed:
                db.commit()
            return
        admin_user = User(
            full_name=settings.init_admin_name,
            email=settings.init_admin_email.lower().strip(),
            password_hash=hash_password(settings.init_admin_password) if settings.init_admin_password and not settings.external_auth_only else None,
            global_role=GlobalRole.admin,
            auth_provider=default_external_auth_provider() if settings.external_auth_only else "local",
        )
        db.add(admin_user)
        db.commit()
    finally:
        db.close()


def sync_bootstrap_content() -> None:
    db: Session = SessionLocal()
    try:
        sync_example_repository(db)
    finally:
        db.close()


_logger = logging.getLogger("libre_libros.startup")


@asynccontextmanager
async def lifespan(_: FastAPI):
    Path("data").mkdir(exist_ok=True)
    settings.repos_root.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema()
    create_default_admin()
    if settings.bootstrap_repository_provider and settings.bootstrap_repository_name:
        _logger.info(
            "bootstrap: syncing %s/%s from %s (branch=%s)",
            settings.bootstrap_repository_namespace,
            settings.bootstrap_repository_name_remote,
            settings.bootstrap_repository_provider,
            settings.bootstrap_repository_default_branch,
        )
    else:
        _logger.warning(
            "bootstrap: skipped — LIBRE_LIBROS_BOOTSTRAP_REPOSITORY_PROVIDER or _NAME not set",
        )
    try:
        sync_bootstrap_content()
        _logger.info("bootstrap: sync_example_repository finished")
    except Exception:
        _logger.exception("bootstrap: sync_example_repository failed")
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, session_cookie=settings.session_cookie_name)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


templates.env.globals["app_name"] = settings.app_name
templates.env.globals["contact_email"] = settings.contact_email

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(books.router)
app.include_router(admin.router)


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    return {"status": "ok"}
