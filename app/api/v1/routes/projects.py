import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, Pagination, ProjectServiceDep, SortDir
from app.models.project import ProjectStatus
from app.schemas.common import ErrorResponse, Page
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])

_NOT_FOUND = {404: {"model": ErrorResponse}}
_OWNED = {403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}}


@router.post(
    "",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project",
    responses={409: {"model": ErrorResponse, "description": "Duplicate project name"}},
)
async def create_project(
    payload: ProjectCreate, user: CurrentUser, projects: ProjectServiceDep
) -> ProjectRead:
    return await projects.create(user, payload)


@router.get(
    "",
    response_model=Page[ProjectRead],
    summary="List my projects",
    description="Members see their own projects; admins see everyone's. "
    "Supports pagination, status filtering, keyword search, and sorting.",
)
async def list_projects(
    user: CurrentUser,
    projects: ProjectServiceDep,
    pagination: Pagination,
    search: Annotated[
        str | None, Query(max_length=100, description="Match name or description")
    ] = None,
    status_filter: Annotated[ProjectStatus | None, Query(alias="status")] = None,
    sort_by: Annotated[str, Query(pattern="^(created_at|updated_at|name)$")] = "created_at",
    sort_dir: SortDir = "desc",
) -> Page[ProjectRead]:
    items, total = await projects.list_for_user(
        user,
        offset=pagination.offset,
        limit=pagination.page_size,
        search=search,
        status=status_filter,
        sort_by=sort_by,
        sort_desc=sort_dir == "desc",
    )
    return Page[ProjectRead].build(
        [ProjectRead.model_validate(p) for p in items],
        total,
        pagination.page,
        pagination.page_size,
    )


@router.get("/{project_id}", response_model=ProjectRead, summary="Get a project", responses=_OWNED)
async def read_project(
    project_id: uuid.UUID, user: CurrentUser, projects: ProjectServiceDep
) -> ProjectRead:
    return await projects.get_accessible(project_id, user)


@router.patch(
    "/{project_id}",
    response_model=ProjectRead,
    summary="Update a project",
    responses={**_OWNED, 409: {"model": ErrorResponse}},
)
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    user: CurrentUser,
    projects: ProjectServiceDep,
) -> ProjectRead:
    return await projects.update(project_id, user, payload)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a project",
    responses=_OWNED,
)
async def delete_project(
    project_id: uuid.UUID, user: CurrentUser, projects: ProjectServiceDep
) -> None:
    await projects.soft_delete(project_id, user)


@router.post(
    "/{project_id}/restore",
    response_model=ProjectRead,
    summary="Restore a soft-deleted project",
    responses={**_OWNED, 409: {"model": ErrorResponse, "description": "Not deleted"}},
)
async def restore_project(
    project_id: uuid.UUID, user: CurrentUser, projects: ProjectServiceDep
) -> ProjectRead:
    return await projects.restore(project_id, user)
