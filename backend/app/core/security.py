# app/core/security.py
# Password hashing + JWT token helpers used by the login/register routes.

from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from jose import jwt, JWTError

from app.core.config import settings

# bcrypt is the standard choice for password hashing — slow on purpose,
# which makes brute-forcing stolen hashes impractical.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(data: dict, expires_minutes: int | None = None) -> str:
    """
    Builds a signed JWT. `data` typically looks like {"sub": email}.
    The frontend stores this token and sends it back as:
        Authorization: Bearer <token>
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
