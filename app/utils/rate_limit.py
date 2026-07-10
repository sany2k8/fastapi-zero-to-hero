"""In-memory sliding-window rate limiter.

Suitable for a single process. When running multiple workers or replicas,
replace with a shared store (e.g. Redis + the same algorithm) — the calling
code only depends on `check()`.
"""

import time
from collections import defaultdict, deque

_PRUNE_THRESHOLD = 10_000


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, window_seconds: float) -> tuple[bool, int]:
        """Record a hit for `key`. Returns (allowed, retry_after_seconds)."""
        now = time.monotonic()
        hits = self._hits[key]
        cutoff = now - window_seconds
        while hits and hits[0] <= cutoff:
            hits.popleft()

        if len(hits) >= limit:
            retry_after = int(hits[0] + window_seconds - now) + 1
            return False, retry_after

        hits.append(now)
        if len(self._hits) > _PRUNE_THRESHOLD:
            self._prune(cutoff)
        return True, 0

    def _prune(self, cutoff: float) -> None:
        for key in [k for k, v in self._hits.items() if not v or v[-1] <= cutoff]:
            del self._hits[key]
