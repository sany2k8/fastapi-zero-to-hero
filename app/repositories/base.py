"""Generic repository: data access only — no business rules, no commits.

Soft-deletable models are filtered to live rows by default; pass
`include_deleted=True` to see everything (used by restore endpoints).
"""

import uuid
from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession):
        self.session = session

    def _select(self, include_deleted: bool = False) -> Select[tuple[ModelT]]:
        stmt = select(self.model)
        if not include_deleted and hasattr(self.model, "deleted_at"):
            stmt = stmt.where(self.model.deleted_at.is_(None))
        return stmt

    async def get(self, entity_id: uuid.UUID, include_deleted: bool = False) -> ModelT | None:
        stmt = self._select(include_deleted).where(self.model.id == entity_id)
        return await self.session.scalar(stmt)

    def add(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        return instance

    async def delete(self, instance: ModelT) -> None:
        """Hard delete. Soft delete is a service concern (sets deleted_at)."""
        await self.session.delete(instance)

    async def list_paginated(
        self,
        *,
        where: Sequence[ColumnElement[bool]] = (),
        search: str | None = None,
        search_fields: Sequence[InstrumentedAttribute[Any]] = (),
        sort_by: InstrumentedAttribute[Any] | None = None,
        sort_desc: bool = True,
        offset: int = 0,
        limit: int = 20,
        include_deleted: bool = False,
    ) -> tuple[list[ModelT], int]:
        """Filtered, searched, sorted page of rows plus the total match count."""
        stmt = self._select(include_deleted)
        for condition in where:
            stmt = stmt.where(condition)
        if search and search_fields:
            pattern = f"%{search}%"
            stmt = stmt.where(or_(*(field.ilike(pattern) for field in search_fields)))

        total = (
            await self.session.scalar(select(func.count()).select_from(stmt.subquery()))
        ) or 0

        if sort_by is not None:
            stmt = stmt.order_by(sort_by.desc() if sort_desc else sort_by.asc())
        result = await self.session.scalars(stmt.offset(offset).limit(limit))
        return list(result.all()), total
