"""Test fixtures: in-memory SQLite, dependency-overridden app, auth helpers.

Environment variables are set *before* any app import because settings are
read (and cached) at import time.
"""

import os
import tempfile
import uuid

os.environ.update(
    {
        "ENVIRONMENT": "test",
        "SECRET_KEY": "test-secret-key-not-for-production",
        "DATABASE_URL": "sqlite+aiosqlite://",
        "RATE_LIMIT_ENABLED": "false",
        "UPLOAD_DIR": tempfile.mkdtemp(prefix="taskhub-test-uploads-"),
        "MAX_UPLOAD_SIZE_BYTES": "10000",
        "LOG_JSON": "false",
        "LOG_LEVEL": "WARNING",
    }
)

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — register all tables on Base.metadata
from app.db.base import Base
from app.db.session import get_db
from app.main import app as fastapi_app
from app.models.user import User, UserRole


@pytest.fixture
async def engine():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_maker(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def client(session_maker):
    async def override_get_db():
        async with session_maker() as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
    fastapi_app.dependency_overrides.clear()


MEMBER = {"email": "member@example.com", "full_name": "Member One", "password": "password1"}
OTHER = {"email": "other@example.com", "full_name": "Other User", "password": "password2"}
ADMIN = {"email": "admin@example.com", "full_name": "Admin User", "password": "password9"}


async def register(client: AsyncClient, creds: dict) -> dict:
    resp = await client.post("/api/v1/auth/register", json=creds)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def login_headers(client: AsyncClient, creds: dict) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": creds["email"], "password": creds["password"]},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
async def member_user(client):
    return await register(client, MEMBER)


@pytest.fixture
async def member_headers(client, member_user):
    return await login_headers(client, MEMBER)


@pytest.fixture
async def other_headers(client):
    await register(client, OTHER)
    return await login_headers(client, OTHER)


@pytest.fixture
async def admin_headers(client, session_maker):
    user = await register(client, ADMIN)
    async with session_maker() as session:
        db_user = await session.get(User, uuid.UUID(user["id"]))
        db_user.role = UserRole.ADMIN
        await session.commit()
    return await login_headers(client, ADMIN)


@pytest.fixture
async def project(client, member_headers) -> dict:
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "Test Project", "description": "A project for tests"},
        headers=member_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
async def task(client, member_headers, project) -> dict:
    resp = await client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "title": "Test Task"},
        headers=member_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()
