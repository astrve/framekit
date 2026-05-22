"""Rate limiter for metadata provider API calls.

Implements a token bucket algorithm for rate limiting with thread-safe
operations. Each provider can have its own rate limit configuration.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class RateLimit:
    """Rate limit configuration.

    Defines the maximum number of requests allowed within a time period.

    Attributes:
        requests: Maximum number of requests allowed
        period: Time period in seconds

    Example:
        >>> limit = RateLimit(requests=10, period=60.0)  # 10 requests per minute
    """

    requests: int
    period: float


class RateLimiter:
    """Token bucket rate limiter with thread-safe operations.

    Implements the token bucket algorithm where tokens are added at a constant
    rate and consumed by requests. When no tokens are available, requests must
    wait or fail immediately.

    The implementation is thread-safe and suitable for concurrent use in batch
    processing scenarios.

    Example:
        >>> limit = RateLimit(requests=10, period=60.0)
        >>> limiter = RateLimiter(rate_limit=limit)
        >>> if limiter.try_acquire():
        ...     # Make API call
        ...     pass
    """

    def __init__(self, rate_limit: RateLimit):
        """Initialize rate limiter.

        Args:
            rate_limit: Rate limit configuration
        """
        if rate_limit.requests <= 0:
            raise ValueError("Rate limit requests must be positive")
        if rate_limit.period <= 0:
            raise ValueError("Rate limit period must be positive")

        self.rate_limit = rate_limit
        self.tokens = float(rate_limit.requests)
        self.last_update = time.time()
        self.lock = threading.Lock()

    def _refill_tokens(self) -> None:
        """Refill tokens based on elapsed time.

        This method must be called while holding self.lock.
        """
        now = time.time()
        elapsed = now - self.last_update

        # Calculate tokens to add based on elapsed time
        tokens_to_add = (elapsed / self.rate_limit.period) * self.rate_limit.requests

        # Add tokens but don't exceed capacity
        self.tokens = min(self.tokens + tokens_to_add, float(self.rate_limit.requests))

        self.last_update = now

    def acquire(self, tokens: int = 1, timeout: float | None = None) -> bool:
        """Acquire tokens, blocking if necessary.

        Attempts to acquire the specified number of tokens. If not enough tokens
        are available, blocks until they become available or timeout expires.

        Args:
            tokens: Number of tokens to acquire (must be positive)
            timeout: Maximum wait time in seconds (None = wait forever)

        Returns:
            True if tokens acquired, False if timeout expired

        Raises:
            ValueError: If tokens is negative or zero
        """
        if tokens <= 0:
            raise ValueError("Tokens must be positive")

        if tokens > self.rate_limit.requests:
            # Requesting more than capacity - will never succeed
            if timeout is not None and timeout > 0:
                time.sleep(timeout)
            return False

        start_time = time.time()

        while True:
            with self.lock:
                self._refill_tokens()

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True

            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    return False

            # Sleep briefly before retrying
            time.sleep(0.01)

    def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens without blocking.

        Attempts to acquire tokens immediately. Returns False if not enough
        tokens are available.

        Args:
            tokens: Number of tokens to acquire (must be positive)

        Returns:
            True if tokens acquired, False otherwise

        Raises:
            ValueError: If tokens is negative
        """
        if tokens < 0:
            raise ValueError("Tokens cannot be negative")

        if tokens == 0:
            return True

        with self.lock:
            self._refill_tokens()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            return False
