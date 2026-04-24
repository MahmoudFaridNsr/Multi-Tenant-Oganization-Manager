import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from app.settings import Settings


def hash_password(settings: Settings, password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        settings.password_hash_iterations,
        dklen=32,
    )
    salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii").rstrip("=")
    derived_b64 = base64.urlsafe_b64encode(derived).decode("ascii").rstrip("=")
    return f"pbkdf2_sha256${settings.password_hash_iterations}${salt_b64}${derived_b64}"


def verify_password(settings: Settings, password: str, password_hash: str) -> bool:
    try:
        scheme, iter_str, salt_b64, derived_b64 = password_hash.split("$", 3)
    except ValueError:
        return False

    if scheme != "pbkdf2_sha256":
        return False

    try:
        iterations = int(iter_str)
    except ValueError:
        return False

    salt = base64.urlsafe_b64decode(salt_b64 + "==")
    expected = base64.urlsafe_b64decode(derived_b64 + "==")
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
        dklen=len(expected),
    )
    return hmac.compare_digest(derived, expected)


def create_access_token(settings: Settings, subject: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {"sub": subject, "iat": int(now.timestamp()), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(settings: Settings, token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid token") from exc
