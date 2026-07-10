import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.repositories.user import UserRepository
from app.schemas.user import AdminUserUpdate, UserUpdate


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = UserRepository(session)

    async def get(self, user_id: uuid.UUID) -> User:
        user = await self.users.get(user_id)
        if user is None:
            raise NotFoundError("User not found")
        return user

    async def list_users(
        self,
        *,
        offset: int,
        limit: int,
        search: str | None = None,
        role: UserRole | None = None,
        is_active: bool | None = None,
        sort_by: str = "created_at",
        sort_desc: bool = True,
    ) -> tuple[list[User], int]:
        where = []
        if role is not None:
            where.append(User.role == role)
        if is_active is not None:
            where.append(User.is_active == is_active)
        return await self.users.list_paginated(
            where=where,
            search=search,
            search_fields=UserRepository.SEARCH_FIELDS,
            sort_by=UserRepository.SORT_FIELDS[sort_by],
            sort_desc=sort_desc,
            offset=offset,
            limit=limit,
        )

    async def update_profile(self, user: User, payload: UserUpdate) -> User:
        data = payload.model_dump(exclude_unset=True)
        if "password" in data:
            user.hashed_password = hash_password(data.pop("password"))
        for field, value in data.items():
            setattr(user, field, value)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def admin_update(self, user_id: uuid.UUID, payload: AdminUserUpdate) -> User:
        user = await self.get(user_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def deactivate(self, user_id: uuid.UUID) -> None:
        """Users are deactivated, never hard-deleted, so audit trails stay intact."""
        user = await self.get(user_id)
        user.is_active = False
        await self.session.commit()
