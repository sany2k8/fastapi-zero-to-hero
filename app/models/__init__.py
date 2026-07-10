"""Import every model here so Base.metadata (and Alembic autogenerate)
sees the full schema."""

from app.models.project import Project, ProjectStatus
from app.models.task import Attachment, Task, TaskPriority, TaskStatus
from app.models.user import User, UserRole

__all__ = [
    "Attachment",
    "Project",
    "ProjectStatus",
    "Task",
    "TaskPriority",
    "TaskStatus",
    "User",
    "UserRole",
]
