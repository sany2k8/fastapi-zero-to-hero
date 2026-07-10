"""Minimal in-process metrics, exposed as JSON at /metrics.

For real deployments swap this for prometheus-client; the middleware hook
(`record`) is the single integration point.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class _RouteStats:
    count: int = 0
    errors: int = 0
    total_duration_ms: float = 0.0
    by_status: dict[int, int] = field(default_factory=lambda: defaultdict(int))


class MetricsCollector:
    def __init__(self) -> None:
        self._started_at = time.time()
        self._routes: dict[str, _RouteStats] = defaultdict(_RouteStats)

    def record(self, method: str, path: str, status_code: int, duration_ms: float) -> None:
        stats = self._routes[f"{method} {path}"]
        stats.count += 1
        stats.total_duration_ms += duration_ms
        stats.by_status[status_code] += 1
        if status_code >= 500:
            stats.errors += 1

    def snapshot(self) -> dict:
        return {
            "uptime_seconds": round(time.time() - self._started_at, 1),
            "routes": {
                route: {
                    "requests": s.count,
                    "errors_5xx": s.errors,
                    "avg_duration_ms": round(s.total_duration_ms / s.count, 2) if s.count else 0,
                    "by_status": dict(s.by_status),
                }
                for route, s in sorted(self._routes.items())
            },
        }


metrics = MetricsCollector()
