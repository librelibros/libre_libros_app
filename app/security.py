from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    return pwd_context.verify(plain_password, password_hash)

