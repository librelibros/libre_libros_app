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
from app.security import hash_password
from app.services.bootstrap import sync_example_repository
from app.templates import templates

settings = get_settings()


def create_default_admin() -> None:
    if not settings.init_admin_email or not settings.init_admin_password:
        return
    db: Session = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == settings.init_admin_email.lower().strip()).first()
        if existing:
            return
        admin_user = User(
            full_name=settings.init_admin_name,
            email=settings.init_admin_email.lower().strip(),
            password_hash=hash_password(settings.init_admin_password),
            global_role=GlobalRole.admin,
            auth_provider="local",
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


@asynccontextmanager
async def lifespan(_: FastAPI):
    Path("data").mkdir(exist_ok=True)
    settings.repos_root.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    create_default_admin()
    sync_bootstrap_content()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, session_cookie=settings.session_cookie_name)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


templates.env.globals["app_name"] = settings.app_name

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(books.router)
app.include_router(admin.router)
