import time

from app.utils.rate_limit import SlidingWindowRateLimiter


def test_allows_up_to_limit():
    limiter = SlidingWindowRateLimiter()
    for _ in range(5):
        allowed, _ = limiter.check("k", limit=5, window_seconds=60)
        assert allowed


def test_blocks_over_limit_with_retry_after():
    limiter = SlidingWindowRateLimiter()
    for _ in range(3):
        limiter.check("k", limit=3, window_seconds=60)
    allowed, retry_after = limiter.check("k", limit=3, window_seconds=60)
    assert not allowed
    assert 0 < retry_after <= 61


def test_window_expiry_frees_budget():
    limiter = SlidingWindowRateLimiter()
    limiter.check("k", limit=1, window_seconds=0.05)
    allowed, _ = limiter.check("k", limit=1, window_seconds=0.05)
    assert not allowed
    time.sleep(0.06)
    allowed, _ = limiter.check("k", limit=1, window_seconds=0.05)
    assert allowed


def test_keys_are_independent():
    limiter = SlidingWindowRateLimiter()
    limiter.check("a", limit=1, window_seconds=60)
    allowed, _ = limiter.check("b", limit=1, window_seconds=60)
    assert allowed
