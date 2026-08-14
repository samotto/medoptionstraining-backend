from datetime import datetime, timedelta, timezone
from hashlib import sha256
from hmac import compare_digest

from fastapi import Cookie, Depends, HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
settings = get_settings()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "purpose": "access", "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_email_verification_token(user_id: int, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.email_verification_minutes)
    payload = {
        "sub": str(user_id),
        "email": email,
        "purpose": "verify_email",
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_email_verification_token(token: str) -> tuple[int, str]:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("purpose") != "verify_email":
            raise JWTError("Incorrect token purpose")
        user_id = int(payload["sub"])
        email = str(payload["email"]).strip().lower()
    except (JWTError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The verification link is invalid or has expired",
        ) from exc
    return user_id, email


def _password_version(password_hash: str | None) -> str:
    return sha256((password_hash or "").encode("utf-8")).hexdigest()


def create_password_reset_token(user_id: int, email: str, password_hash: str | None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_minutes)
    payload = {
        "sub": str(user_id),
        "email": email,
        "password_version": _password_version(password_hash),
        "purpose": "reset_password",
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_password_reset_token(token: str) -> tuple[int, str, str]:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("purpose") != "reset_password":
            raise JWTError("Incorrect token purpose")
        user_id = int(payload["sub"])
        email = str(payload["email"]).strip().lower()
        password_version = str(payload["password_version"])
    except (JWTError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The password reset link is invalid or has expired",
        ) from exc
    return user_id, email, password_version


def password_reset_token_matches(password_version: str, password_hash: str | None) -> bool:
    return compare_digest(password_version, _password_version(password_hash))


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("purpose") != "access":
            raise JWTError("Incorrect token purpose")
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from exc

    subject = payload.get("sub")
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")

    return subject


def get_current_user(
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    subject = decode_access_token(access_token)
    try:
        user_id = int(subject)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token") from exc

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if user.role == "Pending":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email address has not been verified")
    return user
