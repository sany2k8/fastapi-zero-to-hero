"""Registration, credential verification, and token issuance/refresh."""

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ConflictError, ForbiddenError, UnauthorizedError
from app.core.security import (
    REFRESH_TOKEN,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import TokenPair
from app.schemas.user import UserCreate

logger = structlog.get_logger(__name__)


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings):
        self.session = session
        self.settings = settings
        self.users = UserRepository(session)

    async def register(self, payload: UserCreate) -> User:
        email = payload.email.lower()
        if await self.users.get_by_email(email):
            raise ConflictError("A user with this email already exists")

        user = self.users.add(
            User(
                email=email,
                full_name=payload.full_name,
                hashed_password=hash_password(payload.password),
            )
        )
        await self.session.commit()
        await self.session.refresh(user)
        logger.info("user_registered", user_id=str(user.id))
        return user

    async def authenticate(self, email: str, password: str) -> User:
        user = await self.users.get_by_email(email)
        # Same error for unknown email and wrong password — never reveal
        # which one failed.
        if user is None or not verify_password(password, user.hashed_password):
            raise UnauthorizedError("Incorrect email or password")
        if not user.is_active:
            raise ForbiddenError("This account has been deactivated")
        return user

    def issue_tokens(self, user: User) -> TokenPair:
        return TokenPair(
            access_token=create_access_token(user.id, self.settings),
            refresh_token=create_refresh_token(user.id, self.settings),
        )

    async def refresh(self, refresh_token: str) -> TokenPair:
        payload = decode_token(refresh_token, self.settings, expected_type=REFRESH_TOKEN)
        try:
            user_id = uuid.UUID(payload["sub"])
        except (KeyError, ValueError) as exc:
            raise UnauthorizedError("Invalid token") from exc

        user = await self.users.get(user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("User no longer exists or is inactive")
        return self.issue_tokens(user)
