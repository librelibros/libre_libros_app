import secrets
from urllib.parse import urlsplit

import bcrypt
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import get_settings
from passlib.context import CryptContext
from passlib.exc import UnknownHashError

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return pwd_context.verify(plain_password, password_hash)
    except UnknownHashError:
        if password_hash.startswith("$2"):
            return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
        return False


def password_needs_rehash(password_hash: str | None) -> bool:
    if not password_hash:
        return True
    return pwd_context.identify(password_hash) != "pbkdf2_sha256"


def csrf_token(request: Request) -> str:
    if not request.session.get("csrf_token"):
        request.session["csrf_token"] = secrets.token_urlsafe(32)
    return request.session["csrf_token"]


def start_session(request: Request, user) -> None:
    request.session.clear()
    request.session.update(user_id=user.id, session_version=user.session_version)
    csrf_token(request)


def _origin(value: str) -> tuple[str, str, int | None]:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Invalid origin")
    return parsed.scheme, parsed.hostname.lower(), parsed.port or (443 if parsed.scheme == "https" else 80)


async def verify_csrf(request: Request) -> None:
    settings = get_settings()
    if not settings.csrf_enabled or request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    if settings.csrf_check_origin:
        source = request.headers.get("origin") or request.headers.get("referer")
        if source:
            # Opaque origins are not trusted, including in local demos.
            try:
                allowed = {_origin(settings.public_base_url or str(request.base_url))}
                allowed.update(_origin(value) for value in settings.csrf_allowed_origins)
                if _origin(source) not in allowed:
                    raise ValueError("Untrusted origin")
            except ValueError:
                raise HTTPException(403, "Origen no permitido.")
        elif settings.csrf_require_origin:
            raise HTTPException(403, "Falta el origen de la petición.")
    submitted = request.headers.get("x-csrf-token")
    if not submitted:
        if request.headers.get("content-type", "").startswith(("application/x-www-form-urlencoded", "multipart/form-data")):
            submitted = (await request.form()).get("csrf_token")
    expected = request.session.get("csrf_token")
    if not isinstance(submitted, str) or not isinstance(expected, str) or not secrets.compare_digest(submitted.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(403, "Verificación CSRF fallida. Recarga la página.")


class CsrfMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Read the body only when a form token is needed. BaseHTTPMiddleware
        # replays the cached body to FastAPI, including multipart file uploads.
        if get_settings().csrf_enabled:
            if request.method not in {"GET", "HEAD", "OPTIONS"} and not request.headers.get("x-csrf-token"):
                await request.body()
            try:
                await verify_csrf(request)
            except HTTPException as exc:
                return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
            csrf_token(request)
        response = await call_next(request)
        if request.url.path.startswith(("/invite", "/admin/invitations", "/login", "/register")):
            response.headers["Cache-Control"] = "no-store"
            # Login/register contain no URL secrets. Preserve same-origin form
            # origins; Chromium can send Origin:null on POST under no-referrer.
            # Invitation URLs retain no-referrer to protect their bearer token.
            response.headers["Referrer-Policy"] = (
                "no-referrer" if (
                    request.url.path.startswith("/invite/")
                    and request.url.path != "/invite/accept"
                ) else "same-origin"
            )
        return response
