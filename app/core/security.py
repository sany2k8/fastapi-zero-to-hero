"""Password hashing (Argon2) and JWT creation/verification."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import Settings
from app.core.exceptions import UnauthorizedError

_password_hash = PasswordHash.recommended()  # Argon2id

ACCESS_TOKEN = "access"
REFRESH_TOKEN = "refresh"


def hash_password(plain: str) -> str:
    return _password_hash.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _password_hash.verify(plain, hashed)


def _create_token(
    subject: str, token_type: str, expires_delta: timedelta, settings: Settings
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: uuid.UUID, settings: Settings) -> str:
    return _create_token(
        str(user_id),
        ACCESS_TOKEN,
        timedelta(minutes=settings.access_token_expire_minutes),
        settings,
    )


def create_refresh_token(user_id: uuid.UUID, settings: Settings) -> str:
    return _create_token(
        str(user_id),
        REFRESH_TOKEN,
        timedelta(days=settings.refresh_token_expire_days),
        settings,
    )


def decode_token(token: str, settings: Settings, expected_type: str) -> dict[str, Any]:
    """Decode and validate a JWT, enforcing the expected token type."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Invalid token") from exc

    if payload.get("type") != expected_type:
        raise UnauthorizedError(f"Expected a {expected_type} token")
    return payload
