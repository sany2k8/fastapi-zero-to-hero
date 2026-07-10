import uuid

from app.models.project import Project
from app.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    model = Project

    SEARCH_FIELDS = (Project.name, Project.description)
    SORT_FIELDS = {
        "created_at": Project.created_at,
        "updated_at": Project.updated_at,
        "name": Project.name,
    }

    async def get_by_owner_and_name(self, owner_id: uuid.UUID, name: str) -> Project | None:
        return await self.session.scalar(
            self._select().where(Project.owner_id == owner_id, Project.name == name)
        )
