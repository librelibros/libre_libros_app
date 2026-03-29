import bcrypt
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
