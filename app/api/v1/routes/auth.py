from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import AuthServiceDep, login_rate_limit
from app.schemas.auth import RefreshRequest, TokenPair
from app.schemas.common import ErrorResponse
from app.schemas.user import UserCreate, UserRead
from app.services.email import send_welcome_email

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    responses={409: {"model": ErrorResponse, "description": "Email already registered"}},
)
async def register(
    payload: UserCreate,
    background_tasks: BackgroundTasks,
    auth: AuthServiceDep,
) -> UserRead:
    """Create an account. A welcome email is sent as a background task so the
    response doesn't wait on the mail provider."""
    user = await auth.register(payload)
    background_tasks.add_task(send_welcome_email, user.email, user.full_name)
    return user


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Log in (OAuth2 password flow)",
    dependencies=[Depends(login_rate_limit)],
    responses={
        401: {"model": ErrorResponse, "description": "Bad credentials"},
        429: {"model": ErrorResponse, "description": "Too many attempts"},
    },
)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth: AuthServiceDep,
) -> TokenPair:
    """Exchange email (as `username`) + password for an access/refresh token pair."""
    user = await auth.authenticate(form_data.username, form_data.password)
    return auth.issue_tokens(user)


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Rotate tokens using a refresh token",
    responses={401: {"model": ErrorResponse, "description": "Invalid or expired token"}},
)
async def refresh(payload: RefreshRequest, auth: AuthServiceDep) -> TokenPair:
    return await auth.refresh(payload.refresh_token)
