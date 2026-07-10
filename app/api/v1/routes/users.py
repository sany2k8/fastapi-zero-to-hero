import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import (
    AdminUser,
    CurrentUser,
    Pagination,
    SortDir,
    UserServiceDep,
)
from app.core.exceptions import ForbiddenError
from app.models.user import UserRole
from app.schemas.common import ErrorResponse, Page
from app.schemas.user import AdminUserUpdate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead, summary="Get my profile")
async def read_me(user: CurrentUser) -> UserRead:
    return user


@router.patch("/me", response_model=UserRead, summary="Update my profile")
async def update_me(
    payload: UserUpdate, user: CurrentUser, users: UserServiceDep
) -> UserRead:
    return await users.update_profile(user, payload)


@router.get(
    "",
    response_model=Page[UserRead],
    summary="List users (admin only)",
    responses={403: {"model": ErrorResponse}},
)
async def list_users(
    _admin: AdminUser,
    users: UserServiceDep,
    pagination: Pagination,
    search: Annotated[str | None, Query(max_length=100, description="Match email or name")] = None,
    role: Annotated[UserRole | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
    sort_by: Annotated[str, Query(pattern="^(created_at|email|full_name)$")] = "created_at",
    sort_dir: SortDir = "desc",
) -> Page[UserRead]:
    items, total = await users.list_users(
        offset=pagination.offset,
        limit=pagination.page_size,
        search=search,
        role=role,
        is_active=is_active,
        sort_by=sort_by,
        sort_desc=sort_dir == "desc",
    )
    return Page[UserRead].build(
        [UserRead.model_validate(u) for u in items],
        total,
        pagination.page,
        pagination.page_size,
    )


@router.get(
    "/{user_id}",
    response_model=UserRead,
    summary="Get a user (self or admin)",
    responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def read_user(
    user_id: uuid.UUID, current: CurrentUser, users: UserServiceDep
) -> UserRead:
    if current.role != UserRole.ADMIN and current.id != user_id:
        raise ForbiddenError("You may only view your own profile")
    return await users.get(user_id)


@router.patch(
    "/{user_id}",
    response_model=UserRead,
    summary="Update role/active flag (admin only)",
    responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def admin_update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
    _admin: AdminUser,
    users: UserServiceDep,
) -> UserRead:
    return await users.admin_update(user_id, payload)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate a user (admin only)",
    responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def deactivate_user(
    user_id: uuid.UUID, _admin: AdminUser, users: UserServiceDep
) -> None:
    await users.deactivate(user_id)
