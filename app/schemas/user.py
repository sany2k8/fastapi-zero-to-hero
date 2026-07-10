import uuid
from datetime import datetime

from pydantic import EmailStr, Field, field_validator

from app.models.user import UserRole
from app.schemas.common import APIModel


def _validate_password_strength(value: str) -> str:
    if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
        raise ValueError("password must contain at least one letter and one digit")
    return value


class UserCreate(APIModel):
    email: EmailStr = Field(examples=["ada@example.com"])
    full_name: str = Field(min_length=1, max_length=100, examples=["Ada Lovelace"])
    password: str = Field(min_length=8, max_length=128, examples=["s3cure-passw0rd"])

    _check_password = field_validator("password")(_validate_password_strength)


class UserUpdate(APIModel):
    """Self-service profile update (PATCH semantics — all fields optional)."""

    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def _check_password(cls, value: str | None) -> str | None:
        return None if value is None else _validate_password_strength(value)


class AdminUserUpdate(APIModel):
    """Admin-only fields, kept separate so members can never touch them."""

    role: UserRole | None = None
    is_active: bool | None = None


class UserRead(APIModel):
    """Public representation — hashed_password is deliberately not a field here."""

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
