"""Application factory: logging, middleware, exception handlers, routers."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import api_v1_router
from app.api.v1.routes import health
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.db.session import engine
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_context import RequestContextMiddleware

OPENAPI_TAGS = [
    {"name": "auth", "description": "Registration, login, and token refresh."},
    {"name": "users", "description": "Profiles and admin user management."},
    {"name": "projects", "description": "Projects owned by users. Soft-deletable."},
    {"name": "tasks", "description": "Tasks within projects, with file attachments."},
    {"name": "health", "description": "Probes and metrics for orchestrators."},
]


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings)
    logger = structlog.get_logger("app")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            "startup",
            environment=settings.environment.value,
            version=settings.app_version,
        )
        yield
        await engine.dispose()
        logger.info("shutdown")

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Production-style task management API. Register, log in via "
            "`POST /api/v1/auth/login`, then use the **Authorize** button "
            "with your access token."
        ),
        openapi_tags=OPENAPI_TAGS,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Middleware runs outermost-last-added: CORS → TrustedHost → GZip →
    # RequestContext (request id wraps everything below) → RateLimit.
    app.add_middleware(RateLimitMiddleware, settings=settings)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
