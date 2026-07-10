"""Global per-IP rate limiting.

A stricter per-endpoint budget for login lives in `app.api.deps.login_rate_limit`
(dependency-based, so it can also key on the authenticated user).
"""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import Settings
from app.utils.rate_limit import SlidingWindowRateLimiter

_EXEMPT_PATHS = {"/health", "/live", "/ready", "/metrics"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self.settings = settings
        self.limiter = SlidingWindowRateLimiter()

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not self.settings.rate_limit_enabled or request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        allowed, retry_after = self.limiter.check(
            f"ip:{client_ip}",
            self.settings.rate_limit_requests,
            self.settings.rate_limit_window_seconds,
        )
        if not allowed:
            # Middleware responses bypass exception handlers, so build the
            # standard error envelope directly.
            return JSONResponse(
                status_code=429,
                content={
                    "error": {"code": "rate_limited", "message": "Too many requests"}
                },
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)
