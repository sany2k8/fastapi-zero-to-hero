"""Request ID + timing + structured access logging + metrics."""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.utils.metrics import metrics

logger = structlog.get_logger("app.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration_ms, 1),
            )
            metrics.record(request.method, self._route_path(request), 500, duration_ms)
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = f"{duration_ms:.1f}"

        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 1),
            client=request.client.host if request.client else None,
        )
        metrics.record(
            request.method, self._route_path(request), response.status_code, duration_ms
        )
        return response

    @staticmethod
    def _route_path(request: Request) -> str:
        """Route template (e.g. /api/v1/tasks/{task_id}) to keep metric
        cardinality bounded; falls back to the raw path for unmatched routes."""
        route = request.scope.get("route")
        return getattr(route, "path", request.url.path)
