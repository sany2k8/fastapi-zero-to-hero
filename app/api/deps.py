"""FastAPI dependencies: DB session, settings, current user, RBAC guards,
pagination params, service factories, and the login rate limit."""

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import ForbiddenError, RateLimitedError, UnauthorizedError
from app.core.security import ACCESS_TOKEN, decode_token
from app.db.session import get_db
from app.models.user import User, UserRole
from app.repositories.user import UserRepository
from app.services.auth import AuthService
from app.services.project import ProjectService
from app.services.task import TaskService
from app.services.user import UserService
from app.utils.rate_limit import SlidingWindowRateLimiter

DbSession = Annotated[AsyncSession, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DbSession,
    settings: SettingsDep,
) -> User:
    payload = decode_token(token, settings, expected_type=ACCESS_TOKEN)
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise UnauthorizedError("Invalid token") from exc

    user = await UserRepository(db).get(user_id)
    if user is None:
        raise UnauthorizedError("User no longer exists")
    if not user.is_active:
        raise ForbiddenError("This account has been deactivated")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole):
    """RBAC guard, e.g. `Depends(require_roles(UserRole.ADMIN))`."""

    def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise ForbiddenError("Not enough permissions")
        return user

    return checker


AdminUser = Annotated[User, Depends(require_roles(UserRole.ADMIN))]


@dataclass(frozen=True)
class PaginationParams:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def get_pagination(
    page: Annotated[int, Query(ge=1, description="1-based page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
) -> PaginationParams:
    return PaginationParams(page=page, page_size=page_size)


Pagination = Annotated[PaginationParams, Depends(get_pagination)]

SortDir = Annotated[
    str, Query(pattern="^(asc|desc)$", description="Sort direction")
]

# --- Service factories ------------------------------------------------------


def get_auth_service(db: DbSession, settings: SettingsDep) -> AuthService:
    return AuthService(db, settings)


def get_user_service(db: DbSession) -> UserService:
    return UserService(db)


def get_project_service(db: DbSession) -> ProjectService:
    return ProjectService(db)


def get_task_service(db: DbSession, settings: SettingsDep) -> TaskService:
    return TaskService(db, settings)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]

# --- Login rate limit (per IP, stricter than the global middleware) ---------

_login_limiter = SlidingWindowRateLimiter()


async def login_rate_limit(request: Request, settings: SettingsDep) -> None:
    if not settings.rate_limit_enabled:
        return
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = _login_limiter.check(
        f"login:{client_ip}",
        settings.login_rate_limit_requests,
        settings.login_rate_limit_window_seconds,
    )
    if not allowed:
        raise RateLimitedError(
            "Too many login attempts, please try again later", retry_after=retry_after
        )
