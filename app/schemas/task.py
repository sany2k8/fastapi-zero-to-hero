import uuid
from datetime import UTC, datetime

from pydantic import Field, field_validator

from app.models.task import TaskPriority, TaskStatus
from app.schemas.common import APIModel


def _validate_future_due_date(value: datetime | None) -> datetime | None:
    """Naive datetimes are assumed UTC; due dates cannot be in the past."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    if value <= datetime.now(UTC):
        raise ValueError("due_date must be in the future")
    return value


class TaskCreate(APIModel):
    project_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200, examples=["Design landing page"])
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: datetime | None = None
    assignee_id: uuid.UUID | None = None

    _check_due_date = field_validator("due_date")(_validate_future_due_date)


class TaskUpdate(APIModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: datetime | None = None
    assignee_id: uuid.UUID | None = None

    _check_due_date = field_validator("due_date")(_validate_future_due_date)


class TaskRead(APIModel):
    id: uuid.UUID
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    due_date: datetime | None
    project_id: uuid.UUID
    assignee_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class AttachmentRead(APIModel):
    id: uuid.UUID
    task_id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime
