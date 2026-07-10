import uuid

from app.models.task import Attachment, Task
from app.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    model = Task

    SEARCH_FIELDS = (Task.title, Task.description)
    SORT_FIELDS = {
        "created_at": Task.created_at,
        "updated_at": Task.updated_at,
        "title": Task.title,
        "priority": Task.priority,
        "due_date": Task.due_date,
    }


class AttachmentRepository(BaseRepository[Attachment]):
    model = Attachment

    async def list_for_task(self, task_id: uuid.UUID) -> list[Attachment]:
        result = await self.session.scalars(
            self._select().where(Attachment.task_id == task_id).order_by(Attachment.created_at)
        )
        return list(result.all())
