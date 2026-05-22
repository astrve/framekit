"""Per-tracker rate limiting for upload operations.

Provides a shared registry of rate limiters keyed by tracker name,
ensuring concurrent uploads to the same tracker respect API rate limits.
"""

from __future__ import annotations

import threading
import time

from loguru import logger

from .models import TrackerConfig


class _TokenBucket:
    """Thread-safe token bucket rate limiter."""

    __slots__ = ("_capacity", "_last_refill", "_lock", "_refill_rate", "_tokens")

    def __init__(self, capacity: int, period: float):
        self._capacity = capacity
        self._tokens = float(capacity)
        self._refill_rate = capacity / period
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, timeout: float = 30.0) -> bool:
        """Acquire a token, blocking up to timeout seconds.

        Returns True if acquired, False if timed out.
        """
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return True
                wait_time = (1.0 - self._tokens) / self._refill_rate

            if time.monotonic() + wait_time > deadline:
                return False
            time.sleep(min(wait_time, 0.5))

    def try_acquire(self) -> bool:
        """Try to acquire a token without blocking."""
        with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_rate)
        self._last_refill = now


class TrackerRateLimiterRegistry:
    """Global registry of per-tracker rate limiters.

    Thread-safe singleton that creates and caches rate limiters
    for each tracker based on its configuration.
    """

    _instance: TrackerRateLimiterRegistry | None = None
    _lock = threading.Lock()

    def __init__(self):
        self._limiters: dict[str, _TokenBucket] = {}
        self._registry_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> TrackerRateLimiterRegistry:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get_limiter(self, config: TrackerConfig) -> _TokenBucket:
        """Get or create a rate limiter for a tracker.

        Args:
            config: Tracker configuration with rate limit settings

        Returns:
            Token bucket rate limiter for this tracker
        """
        with self._registry_lock:
            if config.name not in self._limiters:
                self._limiters[config.name] = _TokenBucket(
                    capacity=config.rate_limit_requests,
                    period=config.rate_limit_period,
                )
                logger.debug(
                    f"Created rate limiter for {config.name}: "
                    f"{config.rate_limit_requests} req/{config.rate_limit_period}s"
                )
            return self._limiters[config.name]

    def acquire(self, config: TrackerConfig, timeout: float = 30.0) -> bool:
        """Acquire a rate limit token for a tracker.

        Blocks until a token is available or timeout is reached.

        Args:
            config: Tracker configuration
            timeout: Maximum wait time in seconds

        Returns:
            True if acquired, False if timed out
        """
        limiter = self.get_limiter(config)
        acquired = limiter.acquire(timeout=timeout)
        if not acquired:
            logger.warning(f"Rate limit timeout for tracker {config.name}")
        return acquired

    def reset(self, tracker_name: str | None = None) -> None:
        """Reset rate limiter(s).

        Args:
            tracker_name: Specific tracker to reset, or None for all
        """
        with self._registry_lock:
            if tracker_name:
                self._limiters.pop(tracker_name, None)
            else:
                self._limiters.clear()
