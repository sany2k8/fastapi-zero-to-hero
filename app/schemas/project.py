import uuid
from datetime import datetime

from pydantic import Field

from app.models.project import ProjectStatus
from app.schemas.common import APIModel


class ProjectCreate(APIModel):
    name: str = Field(min_length=1, max_length=120, examples=["Website redesign"])
    description: str | None = Field(default=None, max_length=2000)
    status: ProjectStatus = ProjectStatus.ACTIVE


class ProjectUpdate(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    status: ProjectStatus | None = None


class ProjectRead(APIModel):
    id: uuid.UUID
    name: str
    description: str | None
    status: ProjectStatus
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
