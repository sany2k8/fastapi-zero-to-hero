import uuid

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.mixins import utcnow
from app.models.project import Project, ProjectStatus
from app.models.user import User, UserRole
from app.repositories.project import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.projects = ProjectRepository(session)

    @staticmethod
    def accessible_project_ids(user: User) -> Select[tuple[uuid.UUID]]:
        """Subquery of live project ids the user may touch (admins see all)."""
        stmt = select(Project.id).where(Project.deleted_at.is_(None))
        if user.role != UserRole.ADMIN:
            stmt = stmt.where(Project.owner_id == user.id)
        return stmt

    async def _check_name_available(self, owner_id: uuid.UUID, name: str) -> None:
        if await self.projects.get_by_owner_and_name(owner_id, name):
            raise ConflictError(f"You already have a project named {name!r}")

    async def create(self, owner: User, payload: ProjectCreate) -> Project:
        await self._check_name_available(owner.id, payload.name)
        project = self.projects.add(
            Project(
                **payload.model_dump(),
                owner_id=owner.id,
                created_by=owner.id,
                updated_by=owner.id,
            )
        )
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def get_accessible(
        self, project_id: uuid.UUID, user: User, include_deleted: bool = False
    ) -> Project:
        """Fetch a project, enforcing ownership (admins bypass)."""
        project = await self.projects.get(project_id, include_deleted=include_deleted)
        if project is None:
            raise NotFoundError("Project not found")
        if user.role != UserRole.ADMIN and project.owner_id != user.id:
            raise ForbiddenError("You do not have access to this project")
        return project

    async def list_for_user(
        self,
        user: User,
        *,
        offset: int,
        limit: int,
        search: str | None = None,
        status: ProjectStatus | None = None,
        sort_by: str = "created_at",
        sort_desc: bool = True,
    ) -> tuple[list[Project], int]:
        where = []
        if user.role != UserRole.ADMIN:
            where.append(Project.owner_id == user.id)
        if status is not None:
            where.append(Project.status == status)
        return await self.projects.list_paginated(
            where=where,
            search=search,
            search_fields=ProjectRepository.SEARCH_FIELDS,
            sort_by=ProjectRepository.SORT_FIELDS[sort_by],
            sort_desc=sort_desc,
            offset=offset,
            limit=limit,
        )

    async def update(
        self, project_id: uuid.UUID, user: User, payload: ProjectUpdate
    ) -> Project:
        project = await self.get_accessible(project_id, user)
        data = payload.model_dump(exclude_unset=True)
        if "name" in data and data["name"] != project.name:
            await self._check_name_available(project.owner_id, data["name"])
        for field, value in data.items():
            setattr(project, field, value)
        project.updated_by = user.id
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def soft_delete(self, project_id: uuid.UUID, user: User) -> None:
        project = await self.get_accessible(project_id, user)
        project.deleted_at = utcnow()
        project.updated_by = user.id
        await self.session.commit()

    async def restore(self, project_id: uuid.UUID, user: User) -> Project:
        project = await self.get_accessible(project_id, user, include_deleted=True)
        if not project.is_deleted:
            raise ConflictError("Project is not deleted")
        project.deleted_at = None
        project.updated_by = user.id
        await self.session.commit()
        await self.session.refresh(project)
        return project
