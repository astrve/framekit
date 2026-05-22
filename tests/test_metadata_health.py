"""Tests for metadata provider health monitoring."""

from __future__ import annotations

import time

from framekit.modules.metadata.health import HealthMetrics, HealthMonitor, HealthStatus


def test_health_status_enum():
    """Test HealthStatus enum values."""
    assert HealthStatus.HEALTHY.value == "healthy"
    assert HealthStatus.DEGRADED.value == "degraded"
    assert HealthStatus.UNHEALTHY.value == "unhealthy"


def test_health_metrics_dataclass():
    """Test HealthMetrics dataclass."""
    metrics = HealthMetrics()

    assert metrics.total_requests == 0
    assert metrics.successful_requests == 0
    assert metrics.failed_requests == 0
    assert metrics.last_success is None
    assert metrics.last_failure is None
    assert metrics.consecutive_failures == 0


def test_health_monitor_initialization():
    """Test health monitor initialization."""
    monitor = HealthMonitor(failure_threshold=5, recovery_timeout=60.0)

    assert monitor.failure_threshold == 5
    assert monitor.recovery_timeout == 60.0
    assert len(monitor.metrics) == 0


def test_health_monitor_record_success():
    """Test recording successful request."""
    monitor = HealthMonitor()

    monitor.record_success("provider1")

    metrics = monitor.metrics["provider1"]
    assert metrics.total_requests == 1
    assert metrics.successful_requests == 1
    assert metrics.failed_requests == 0
    assert metrics.consecutive_failures == 0
    assert metrics.last_success is not None


def test_health_monitor_record_failure():
    """Test recording failed request."""
    monitor = HealthMonitor()

    monitor.record_failure("provider1")

    metrics = monitor.metrics["provider1"]
    assert metrics.total_requests == 1
    assert metrics.successful_requests == 0
    assert metrics.failed_requests == 1
    assert metrics.consecutive_failures == 1
    assert metrics.last_failure is not None


def test_health_monitor_consecutive_failures():
    """Test tracking consecutive failures."""
    monitor = HealthMonitor()

    for _ in range(3):
        monitor.record_failure("provider1")

    metrics = monitor.metrics["provider1"]
    assert metrics.consecutive_failures == 3
    assert metrics.failed_requests == 3


def test_health_monitor_reset_consecutive_failures_on_success():
    """Test that success resets consecutive failures."""
    monitor = HealthMonitor()

    # Record failures
    for _ in range(3):
        monitor.record_failure("provider1")

    # Record success
    monitor.record_success("provider1")

    metrics = monitor.metrics["provider1"]
    assert metrics.consecutive_failures == 0
    assert metrics.successful_requests == 1
    assert metrics.failed_requests == 3


def test_health_monitor_get_status_healthy():
    """Test getting healthy status."""
    monitor = HealthMonitor(failure_threshold=5)

    monitor.record_success("provider1")

    status = monitor.get_status("provider1")
    assert status == HealthStatus.HEALTHY


def test_health_monitor_get_status_degraded():
    """Test getting degraded status."""
    monitor = HealthMonitor(failure_threshold=5)

    # Record some failures but below threshold
    for _ in range(3):
        monitor.record_failure("provider1")

    status = monitor.get_status("provider1")
    assert status == HealthStatus.DEGRADED


def test_health_monitor_get_status_unhealthy():
    """Test getting unhealthy status."""
    monitor = HealthMonitor(failure_threshold=5)

    # Record failures above threshold
    for _ in range(5):
        monitor.record_failure("provider1")

    status = monitor.get_status("provider1")
    assert status == HealthStatus.UNHEALTHY


def test_health_monitor_get_status_unknown_provider():
    """Test getting status for unknown provider."""
    monitor = HealthMonitor()

    status = monitor.get_status("unknown_provider")
    assert status == HealthStatus.HEALTHY  # Default to healthy


def test_health_monitor_is_available_healthy():
    """Test is_available for healthy provider."""
    monitor = HealthMonitor(failure_threshold=5)

    monitor.record_success("provider1")

    assert monitor.is_available("provider1") is True


def test_health_monitor_is_available_degraded():
    """Test is_available for degraded provider."""
    monitor = HealthMonitor(failure_threshold=5)

    # Record some failures but below threshold
    for _ in range(3):
        monitor.record_failure("provider1")

    # Should still be available
    assert monitor.is_available("provider1") is True


def test_health_monitor_is_available_unhealthy():
    """Test is_available for unhealthy provider (circuit broken)."""
    monitor = HealthMonitor(failure_threshold=5, recovery_timeout=60.0)

    # Record failures above threshold
    for _ in range(5):
        monitor.record_failure("provider1")

    # Should not be available (circuit broken)
    assert monitor.is_available("provider1") is False


def test_health_monitor_circuit_breaker_recovery():
    """Test circuit breaker recovery after timeout."""
    monitor = HealthMonitor(failure_threshold=3, recovery_timeout=0.1)

    # Trigger circuit breaker
    for _ in range(3):
        monitor.record_failure("provider1")

    assert monitor.is_available("provider1") is False

    # Wait for recovery timeout
    time.sleep(0.2)

    # Should be available again (half-open state)
    assert monitor.is_available("provider1") is True


def test_health_monitor_multiple_providers():
    """Test monitoring multiple providers independently."""
    monitor = HealthMonitor(failure_threshold=3)

    # Provider1: healthy
    monitor.record_success("provider1")

    # Provider2: degraded
    monitor.record_failure("provider2")
    monitor.record_failure("provider2")

    # Provider3: unhealthy
    for _ in range(3):
        monitor.record_failure("provider3")

    assert monitor.get_status("provider1") == HealthStatus.HEALTHY
    assert monitor.get_status("provider2") == HealthStatus.DEGRADED
    assert monitor.get_status("provider3") == HealthStatus.UNHEALTHY


def test_health_monitor_mixed_success_failure():
    """Test mixed success and failure patterns."""
    monitor = HealthMonitor(failure_threshold=5)

    # Alternating success and failure
    monitor.record_success("provider1")
    monitor.record_failure("provider1")
    monitor.record_success("provider1")
    monitor.record_failure("provider1")

    metrics = monitor.metrics["provider1"]
    assert metrics.total_requests == 4
    assert metrics.successful_requests == 2
    assert metrics.failed_requests == 2
    assert metrics.consecutive_failures == 1  # Only last failure counts


def test_health_monitor_recovery_after_success():
    """Test that provider recovers after successful request."""
    monitor = HealthMonitor(failure_threshold=3)

    # Trigger circuit breaker
    for _ in range(3):
        monitor.record_failure("provider1")

    assert monitor.get_status("provider1") == HealthStatus.UNHEALTHY

    # Record success
    monitor.record_success("provider1")

    # Should be healthy again
    assert monitor.get_status("provider1") == HealthStatus.HEALTHY
    assert monitor.is_available("provider1") is True


def test_health_monitor_get_metrics():
    """Test getting metrics for a provider."""
    monitor = HealthMonitor()

    monitor.record_success("provider1")
    monitor.record_failure("provider1")

    metrics = monitor.metrics.get("provider1")
    assert metrics is not None
    assert metrics.total_requests == 2
    assert metrics.successful_requests == 1
    assert metrics.failed_requests == 1


def test_health_monitor_timestamp_tracking():
    """Test that timestamps are tracked correctly."""
    monitor = HealthMonitor()

    before_success = time.time()
    monitor.record_success("provider1")
    after_success = time.time()

    metrics = monitor.metrics["provider1"]
    assert metrics.last_success is not None
    assert before_success <= metrics.last_success <= after_success

    before_failure = time.time()
    monitor.record_failure("provider1")
    after_failure = time.time()

    assert metrics.last_failure is not None
    assert before_failure <= metrics.last_failure <= after_failure


def test_health_monitor_zero_threshold():
    """Test behavior with zero failure threshold."""
    monitor = HealthMonitor(failure_threshold=0)

    # Single failure should make it unhealthy
    monitor.record_failure("provider1")

    assert monitor.get_status("provider1") == HealthStatus.UNHEALTHY


def test_health_monitor_high_threshold():
    """Test behavior with high failure threshold."""
    monitor = HealthMonitor(failure_threshold=100)

    # Many failures should still be degraded
    for _ in range(50):
        monitor.record_failure("provider1")

    status = monitor.get_status("provider1")
    assert status in (HealthStatus.DEGRADED, HealthStatus.UNHEALTHY)


def test_health_monitor_success_rate():
    """Test calculating success rate."""
    monitor = HealthMonitor()

    # 7 successes, 3 failures = 70% success rate
    for _ in range(7):
        monitor.record_success("provider1")
    for _ in range(3):
        monitor.record_failure("provider1")

    metrics = monitor.metrics["provider1"]
    success_rate = metrics.successful_requests / metrics.total_requests
    assert success_rate == 0.7
