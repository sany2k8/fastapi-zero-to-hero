import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    PayloadTooLargeError,
)
from app.models.mixins import utcnow
from app.models.task import Attachment, Task, TaskPriority, TaskStatus
from app.models.user import User
from app.repositories.task import AttachmentRepository, TaskRepository
from app.schemas.task import TaskCreate, TaskUpdate
from app.services.project import ProjectService

_CHUNK_SIZE = 1024 * 1024  # 1 MiB


class TaskService:
    def __init__(self, session: AsyncSession, settings: Settings):
        self.session = session
        self.settings = settings
        self.tasks = TaskRepository(session)
        self.attachments = AttachmentRepository(session)
        self.projects = ProjectService(session)

    async def create(self, user: User, payload: TaskCreate) -> Task:
        # Also enforces ownership: raises 403/404 if the project isn't the user's.
        await self.projects.get_accessible(payload.project_id, user)
        task = self.tasks.add(
            Task(**payload.model_dump(), created_by=user.id, updated_by=user.id)
        )
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def get_accessible(
        self, task_id: uuid.UUID, user: User, include_deleted: bool = False
    ) -> Task:
        task = await self.tasks.get(task_id, include_deleted=include_deleted)
        if task is None:
            raise NotFoundError("Task not found")
        await self.projects.get_accessible(task.project_id, user)
        return task

    async def list_for_user(
        self,
        user: User,
        *,
        offset: int,
        limit: int,
        project_id: uuid.UUID | None = None,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        sort_desc: bool = True,
    ) -> tuple[list[Task], int]:
        # Scope to live projects the user can access (admins: all projects).
        where = [Task.project_id.in_(ProjectService.accessible_project_ids(user))]
        if project_id is not None:
            where.append(Task.project_id == project_id)
        if status is not None:
            where.append(Task.status == status)
        if priority is not None:
            where.append(Task.priority == priority)
        return await self.tasks.list_paginated(
            where=where,
            search=search,
            search_fields=TaskRepository.SEARCH_FIELDS,
            sort_by=TaskRepository.SORT_FIELDS[sort_by],
            sort_desc=sort_desc,
            offset=offset,
            limit=limit,
        )

    async def update(self, task_id: uuid.UUID, user: User, payload: TaskUpdate) -> Task:
        task = await self.get_accessible(task_id, user)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(task, field, value)
        task.updated_by = user.id
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def soft_delete(self, task_id: uuid.UUID, user: User) -> None:
        task = await self.get_accessible(task_id, user)
        task.deleted_at = utcnow()
        task.updated_by = user.id
        await self.session.commit()

    async def restore(self, task_id: uuid.UUID, user: User) -> Task:
        task = await self.get_accessible(task_id, user, include_deleted=True)
        if not task.is_deleted:
            raise ConflictError("Task is not deleted")
        task.deleted_at = None
        task.updated_by = user.id
        await self.session.commit()
        await self.session.refresh(task)
        return task

    # --- Attachments -----------------------------------------------------

    async def add_attachment(
        self, task_id: uuid.UUID, user: User, upload: UploadFile
    ) -> Attachment:
        task = await self.get_accessible(task_id, user)

        if upload.content_type not in self.settings.allowed_upload_content_types:
            raise BadRequestError(
                f"Content type {upload.content_type!r} is not allowed",
                details=[{"allowed": self.settings.allowed_upload_content_types}],
            )

        stored_name = f"{uuid.uuid4().hex}{Path(upload.filename or 'file').suffix}"
        dest = self.settings.upload_dir / stored_name
        dest.parent.mkdir(parents=True, exist_ok=True)

        # Stream to disk in chunks so the size limit holds without ever
        # buffering the whole file in memory.
        size = 0
        try:
            with dest.open("wb") as out:
                while chunk := await upload.read(_CHUNK_SIZE):
                    size += len(chunk)
                    if size > self.settings.max_upload_size_bytes:
                        raise PayloadTooLargeError(
                            f"File exceeds the {self.settings.max_upload_size_bytes} byte limit"
                        )
                    out.write(chunk)
        except PayloadTooLargeError:
            dest.unlink(missing_ok=True)
            raise

        attachment = self.attachments.add(
            Attachment(
                task_id=task.id,
                filename=upload.filename or stored_name,
                stored_name=stored_name,
                content_type=upload.content_type or "application/octet-stream",
                size_bytes=size,
                uploaded_by=user.id,
            )
        )
        await self.session.commit()
        await self.session.refresh(attachment)
        return attachment

    async def list_attachments(self, task_id: uuid.UUID, user: User) -> list[Attachment]:
        await self.get_accessible(task_id, user)
        return await self.attachments.list_for_task(task_id)

    async def get_attachment_file(
        self, task_id: uuid.UUID, attachment_id: uuid.UUID, user: User
    ) -> tuple[Attachment, Path]:
        await self.get_accessible(task_id, user)
        attachment = await self.attachments.get(attachment_id)
        if attachment is None or attachment.task_id != task_id:
            raise NotFoundError("Attachment not found")
        path = self.settings.upload_dir / attachment.stored_name
        if not path.is_file():
            raise NotFoundError("Attachment file is missing from storage")
        return attachment, path

    async def delete_attachment(
        self, task_id: uuid.UUID, attachment_id: uuid.UUID, user: User
    ) -> None:
        await self.get_accessible(task_id, user)
        attachment = await self.attachments.get(attachment_id)
        if attachment is None or attachment.task_id != task_id:
            raise NotFoundError("Attachment not found")
        (self.settings.upload_dir / attachment.stored_name).unlink(missing_ok=True)
        await self.attachments.delete(attachment)
        await self.session.commit()
