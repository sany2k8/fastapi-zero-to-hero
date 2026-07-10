"""Health, liveness, readiness, and metrics endpoints.

Mounted at the app root (unversioned) — orchestrators and load balancers
shouldn't have to care about API versions.
"""

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.api.deps import DbSession, SettingsDep
from app.utils.metrics import metrics

router = APIRouter(tags=["health"])


@router.get("/health", summary="Basic service info")
async def health(settings: SettingsDep) -> dict:
    return {
        "status": "ok",
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment.value,
    }


@router.get("/live", summary="Liveness probe")
async def live() -> dict:
    """Process is up and serving requests."""
    return {"status": "alive"}


@router.get("/ready", summary="Readiness probe")
async def ready(db: DbSession, response: Response) -> dict:
    """Ready to take traffic — verifies database connectivity."""
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "database": "unreachable"}
    return {"status": "ready", "database": "ok"}


@router.get("/metrics", summary="In-process request metrics (JSON)")
async def get_metrics() -> dict:
    return metrics.snapshot()
