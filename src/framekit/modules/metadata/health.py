"""Health monitoring for metadata providers.

Tracks provider health status and implements circuit breaker pattern to
prevent cascading failures when a provider becomes unavailable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum


class HealthStatus(Enum):
    """Provider health status.

    Attributes:
        HEALTHY: Provider is functioning normally
        DEGRADED: Provider has some failures but still usable
        UNHEALTHY: Provider has exceeded failure threshold (circuit broken)
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthMetrics:
    """Health metrics for a provider.

    Tracks request statistics and failure patterns to determine provider health.

    Attributes:
        total_requests: Total number of requests made
        successful_requests: Number of successful requests
        failed_requests: Number of failed requests
        last_success: Timestamp of last successful request
        last_failure: Timestamp of last failed request
        consecutive_failures: Number of consecutive failures
    """

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    last_success: float | None = None
    last_failure: float | None = None
    consecutive_failures: int = 0


class HealthMonitor:
    """Monitors provider health and implements circuit breaker pattern.

    Tracks success/failure rates for each provider and automatically opens
    the circuit (marks provider as unavailable) when failure threshold is
    exceeded. The circuit automatically closes after a recovery timeout.

    This prevents wasting time on providers that are known to be down and
    allows them to recover gracefully.

    Example:
        >>> monitor = HealthMonitor(failure_threshold=5, recovery_timeout=60.0)
        >>> monitor.record_failure("provider1")
        >>> if monitor.is_available("provider1"):
        ...     # Make request
        ...     pass
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
    ):
        """Initialize health monitor.

        Args:
            failure_threshold: Number of consecutive failures before circuit opens
            recovery_timeout: Seconds to wait before attempting recovery
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.metrics: dict[str, HealthMetrics] = {}

    def _get_or_create_metrics(self, provider_name: str) -> HealthMetrics:
        """Get or create metrics for a provider.

        Args:
            provider_name: Name of the provider

        Returns:
            HealthMetrics instance for the provider
        """
        if provider_name not in self.metrics:
            self.metrics[provider_name] = HealthMetrics()
        return self.metrics[provider_name]

    def record_success(self, provider_name: str) -> None:
        """Record successful request.

        Resets consecutive failure counter and updates success metrics.

        Args:
            provider_name: Name of the provider
        """
        metrics = self._get_or_create_metrics(provider_name)

        metrics.total_requests += 1
        metrics.successful_requests += 1
        metrics.last_success = time.time()
        metrics.consecutive_failures = 0

    def record_failure(self, provider_name: str) -> None:
        """Record failed request.

        Increments failure counters and may trigger circuit breaker.

        Args:
            provider_name: Name of the provider
        """
        metrics = self._get_or_create_metrics(provider_name)

        metrics.total_requests += 1
        metrics.failed_requests += 1
        metrics.last_failure = time.time()
        metrics.consecutive_failures += 1

    def get_status(self, provider_name: str) -> HealthStatus:
        """Get current health status for a provider.

        Determines status based on consecutive failures:
        - HEALTHY: No recent failures or below degraded threshold
        - DEGRADED: Some failures but below circuit breaker threshold
        - UNHEALTHY: Consecutive failures exceed threshold (circuit open)

        Args:
            provider_name: Name of the provider

        Returns:
            Current health status
        """
        if provider_name not in self.metrics:
            return HealthStatus.HEALTHY

        metrics = self.metrics[provider_name]

        if metrics.consecutive_failures >= self.failure_threshold:
            return HealthStatus.UNHEALTHY
        elif metrics.consecutive_failures > 0:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY

    def is_available(self, provider_name: str) -> bool:
        """Check if provider is available (circuit not broken).

        A provider is unavailable if:
        1. It has exceeded the failure threshold, AND
        2. The recovery timeout has not elapsed since last failure

        After the recovery timeout, the circuit enters "half-open" state
        and the provider is given another chance.

        Args:
            provider_name: Name of the provider

        Returns:
            True if provider is available, False if circuit is open
        """
        status = self.get_status(provider_name)

        if status != HealthStatus.UNHEALTHY:
            return True

        # Circuit is open - check if recovery timeout has elapsed
        metrics = self.metrics[provider_name]

        if metrics.last_failure is None:
            return True

        time_since_failure = time.time() - metrics.last_failure

        # Allow retry after recovery timeout (half-open state)
        return time_since_failure >= self.recovery_timeout
