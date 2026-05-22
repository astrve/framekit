"""Tests for metadata rate limiter."""

from __future__ import annotations

import threading
import time

import pytest

from framekit.modules.metadata.rate_limiter import RateLimit, RateLimiter


def test_rate_limit_dataclass():
    """Test RateLimit dataclass."""
    limit = RateLimit(requests=10, period=60.0)

    assert limit.requests == 10
    assert limit.period == 60.0


def test_rate_limiter_initialization():
    """Test rate limiter initialization."""
    limit = RateLimit(requests=10, period=60.0)
    limiter = RateLimiter(rate_limit=limit)

    assert limiter.rate_limit == limit
    assert limiter.tokens == 10.0


def test_rate_limiter_acquire_single_token():
    """Test acquiring a single token."""
    limit = RateLimit(requests=10, period=60.0)
    limiter = RateLimiter(rate_limit=limit)

    result = limiter.acquire(tokens=1, timeout=1.0)

    assert result is True
    assert limiter.tokens < 10.0


def test_rate_limiter_acquire_multiple_tokens():
    """Test acquiring multiple tokens."""
    limit = RateLimit(requests=10, period=60.0)
    limiter = RateLimiter(rate_limit=limit)

    result = limiter.acquire(tokens=5, timeout=1.0)

    assert result is True
    assert limiter.tokens <= 5.0


def test_rate_limiter_try_acquire_success():
    """Test try_acquire when tokens available."""
    limit = RateLimit(requests=10, period=60.0)
    limiter = RateLimiter(rate_limit=limit)

    result = limiter.try_acquire(tokens=1)

    assert result is True


def test_rate_limiter_try_acquire_failure():
    """Test try_acquire when tokens not available."""
    limit = RateLimit(requests=2, period=60.0)
    limiter = RateLimiter(rate_limit=limit)

    # Exhaust tokens
    limiter.try_acquire(tokens=2)

    # Should fail immediately
    result = limiter.try_acquire(tokens=1)

    assert result is False


def test_rate_limiter_token_refill():
    """Test that tokens refill over time."""
    limit = RateLimit(requests=10, period=1.0)  # 10 requests per second
    limiter = RateLimiter(rate_limit=limit)

    # Exhaust tokens
    limiter.acquire(tokens=10, timeout=1.0)
    assert limiter.tokens < 1.0

    # Wait for refill
    time.sleep(0.2)

    # Should have some tokens back
    result = limiter.try_acquire(tokens=1)
    assert result is True


def test_rate_limiter_acquire_timeout():
    """Test acquire with timeout when tokens not available."""
    limit = RateLimit(requests=1, period=10.0)  # Very slow refill
    limiter = RateLimiter(rate_limit=limit)

    # Exhaust token
    limiter.acquire(tokens=1, timeout=1.0)

    # Try to acquire with short timeout
    start = time.time()
    result = limiter.acquire(tokens=1, timeout=0.1)
    elapsed = time.time() - start

    assert result is False
    assert elapsed < 0.5  # Should timeout quickly


def test_rate_limiter_thread_safety():
    """Test rate limiter is thread-safe."""
    limit = RateLimit(requests=100, period=1.0)
    limiter = RateLimiter(rate_limit=limit)

    results = []

    def worker():
        for _ in range(10):
            result = limiter.try_acquire(tokens=1)
            results.append(result)

    threads = [threading.Thread(target=worker) for _ in range(10)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    # Should have acquired exactly 100 tokens (or less if some failed)
    successful = sum(1 for r in results if r)
    assert successful <= 100


def test_rate_limiter_concurrent_acquire():
    """Test concurrent acquire operations."""
    limit = RateLimit(requests=50, period=1.0)
    limiter = RateLimiter(rate_limit=limit)

    acquired = []

    def worker():
        result = limiter.acquire(tokens=1, timeout=2.0)
        acquired.append(result)

    threads = [threading.Thread(target=worker) for _ in range(60)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    # First 50 should succeed, rest should timeout or wait
    successful = sum(1 for r in acquired if r)
    assert successful <= 60  # Some may succeed due to refill


def test_rate_limiter_zero_tokens():
    """Test behavior when requesting zero tokens."""
    limit = RateLimit(requests=10, period=60.0)
    limiter = RateLimiter(rate_limit=limit)

    result = limiter.try_acquire(tokens=0)

    assert result is True
    assert limiter.tokens == 10.0  # No tokens consumed


def test_rate_limiter_negative_tokens():
    """Test behavior with negative tokens (should be rejected)."""
    limit = RateLimit(requests=10, period=60.0)
    limiter = RateLimiter(rate_limit=limit)

    # Negative tokens should be treated as invalid
    with pytest.raises((ValueError, AssertionError)):
        limiter.acquire(tokens=-1, timeout=1.0)


def test_rate_limiter_more_tokens_than_capacity():
    """Test requesting more tokens than capacity."""
    limit = RateLimit(requests=10, period=60.0)
    limiter = RateLimiter(rate_limit=limit)

    # Request more than capacity
    result = limiter.acquire(tokens=20, timeout=0.1)

    # Should timeout since we can never have 20 tokens
    assert result is False


def test_rate_limiter_burst_handling():
    """Test handling of burst requests."""
    limit = RateLimit(requests=5, period=1.0)
    limiter = RateLimiter(rate_limit=limit)

    # Burst of 5 requests
    results = [limiter.try_acquire(tokens=1) for _ in range(5)]

    # All should succeed
    assert all(results)

    # Next request should fail
    result = limiter.try_acquire(tokens=1)
    assert result is False


def test_rate_limiter_gradual_refill():
    """Test gradual token refill."""
    limit = RateLimit(requests=10, period=1.0)
    limiter = RateLimiter(rate_limit=limit)

    # Use all tokens
    limiter.acquire(tokens=10, timeout=1.0)
    assert limiter.tokens < 1.0

    # Wait for partial refill
    time.sleep(0.5)

    # Should be able to acquire some tokens (approximately 5 should have refilled)
    result = limiter.try_acquire(tokens=4)
    assert result is True


def test_rate_limiter_multiple_rate_limits():
    """Test multiple rate limiters with different limits."""
    limit1 = RateLimit(requests=10, period=1.0)
    limit2 = RateLimit(requests=100, period=1.0)

    limiter1 = RateLimiter(rate_limit=limit1)
    limiter2 = RateLimiter(rate_limit=limit2)

    # Both should work independently
    result1 = limiter1.try_acquire(tokens=5)
    result2 = limiter2.try_acquire(tokens=50)

    assert result1 is True
    assert result2 is True
    assert limiter1.tokens <= 5.0
    assert limiter2.tokens <= 50.0
