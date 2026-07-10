import uuid
from typing import Annotated

from fastapi import APIRouter, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import CurrentUser, Pagination, SortDir, TaskServiceDep
from app.models.task import TaskPriority, TaskStatus
from app.schemas.common import ErrorResponse, Page
from app.schemas.task import AttachmentRead, TaskCreate, TaskRead, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])

_OWNED = {403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}}


@router.post(
    "",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a task in one of my projects",
    responses=_OWNED,
)
async def create_task(
    payload: TaskCreate, user: CurrentUser, tasks: TaskServiceDep
) -> TaskRead:
    return await tasks.create(user, payload)


@router.get(
    "",
    response_model=Page[TaskRead],
    summary="List tasks across my projects",
    description="Combine any of: project, status, priority filters; keyword "
    "search over title/description; sorting; pagination.",
)
async def list_tasks(
    user: CurrentUser,
    tasks: TaskServiceDep,
    pagination: Pagination,
    project_id: Annotated[uuid.UUID | None, Query()] = None,
    status_filter: Annotated[TaskStatus | None, Query(alias="status")] = None,
    priority: Annotated[TaskPriority | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
    sort_by: Annotated[
        str, Query(pattern="^(created_at|updated_at|title|priority|due_date)$")
    ] = "created_at",
    sort_dir: SortDir = "desc",
) -> Page[TaskRead]:
    items, total = await tasks.list_for_user(
        user,
        offset=pagination.offset,
        limit=pagination.page_size,
        project_id=project_id,
        status=status_filter,
        priority=priority,
        search=search,
        sort_by=sort_by,
        sort_desc=sort_dir == "desc",
    )
    return Page[TaskRead].build(
        [TaskRead.model_validate(t) for t in items],
        total,
        pagination.page,
        pagination.page_size,
    )


@router.get("/{task_id}", response_model=TaskRead, summary="Get a task", responses=_OWNED)
async def read_task(task_id: uuid.UUID, user: CurrentUser, tasks: TaskServiceDep) -> TaskRead:
    return await tasks.get_accessible(task_id, user)


@router.patch("/{task_id}", response_model=TaskRead, summary="Update a task", responses=_OWNED)
async def update_task(
    task_id: uuid.UUID, payload: TaskUpdate, user: CurrentUser, tasks: TaskServiceDep
) -> TaskRead:
    return await tasks.update(task_id, user, payload)


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a task",
    responses=_OWNED,
)
async def delete_task(task_id: uuid.UUID, user: CurrentUser, tasks: TaskServiceDep) -> None:
    await tasks.soft_delete(task_id, user)


@router.post(
    "/{task_id}/restore",
    response_model=TaskRead,
    summary="Restore a soft-deleted task",
    responses={**_OWNED, 409: {"model": ErrorResponse}},
)
async def restore_task(task_id: uuid.UUID, user: CurrentUser, tasks: TaskServiceDep) -> TaskRead:
    return await tasks.restore(task_id, user)


# --- Attachments -------------------------------------------------------------


@router.post(
    "/{task_id}/attachments",
    response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an attachment (multipart)",
    responses={
        **_OWNED,
        400: {"model": ErrorResponse, "description": "Disallowed content type"},
        413: {"model": ErrorResponse, "description": "File too large"},
    },
)
async def upload_attachment(
    task_id: uuid.UUID, file: UploadFile, user: CurrentUser, tasks: TaskServiceDep
) -> AttachmentRead:
    return await tasks.add_attachment(task_id, user, file)


@router.get(
    "/{task_id}/attachments",
    response_model=list[AttachmentRead],
    summary="List a task's attachments",
    responses=_OWNED,
)
async def list_attachments(
    task_id: uuid.UUID, user: CurrentUser, tasks: TaskServiceDep
) -> list[AttachmentRead]:
    return await tasks.list_attachments(task_id, user)


@router.get(
    "/{task_id}/attachments/{attachment_id}",
    summary="Download an attachment",
    response_class=FileResponse,
    responses=_OWNED,
)
async def download_attachment(
    task_id: uuid.UUID,
    attachment_id: uuid.UUID,
    user: CurrentUser,
    tasks: TaskServiceDep,
) -> FileResponse:
    attachment, path = await tasks.get_attachment_file(task_id, attachment_id, user)
    return FileResponse(
        path, media_type=attachment.content_type, filename=attachment.filename
    )


@router.delete(
    "/{task_id}/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an attachment",
    responses=_OWNED,
)
async def delete_attachment(
    task_id: uuid.UUID,
    attachment_id: uuid.UUID,
    user: CurrentUser,
    tasks: TaskServiceDep,
) -> None:
    await tasks.delete_attachment(task_id, attachment_id, user)
