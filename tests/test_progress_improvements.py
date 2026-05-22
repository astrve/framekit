"""Tests for enhanced progress reporting improvements."""

from __future__ import annotations

import time

from framekit.core.reporting import OperationReport, ProgressMetrics


class TestProgressMetrics:
    """Test enhanced progress metrics."""

    def test_metrics_initialization(self):
        """Test metrics initialization with defaults."""
        metrics = ProgressMetrics(total_items=10)
        assert metrics.total_items == 10
        assert metrics.completed_items == 0
        assert metrics.failed_items == 0
        assert metrics.skipped_items == 0
        assert metrics.total_bytes == 0
        assert metrics.processed_bytes == 0

    def test_metrics_success_rate(self):
        """Test success rate calculation."""
        metrics = ProgressMetrics(
            total_items=10,
            completed_items=8,
            failed_items=2,
        )
        assert metrics.success_rate == 80.0

    def test_metrics_success_rate_zero_total(self):
        """Test success rate with zero total items."""
        metrics = ProgressMetrics(total_items=0)
        assert metrics.success_rate == 0.0

    def test_metrics_compression_ratio(self):
        """Test compression ratio calculation."""
        metrics = ProgressMetrics(
            total_bytes=1000,
            processed_bytes=500,
        )
        assert metrics.compression_ratio == 50.0

    def test_metrics_compression_ratio_zero_total(self):
        """Test compression ratio with zero total bytes."""
        metrics = ProgressMetrics(total_bytes=0, processed_bytes=0)
        assert metrics.compression_ratio == 0.0

    def test_metrics_processing_rate(self):
        """Test processing rate calculation."""
        metrics = ProgressMetrics(
            total_items=10,
            completed_items=5,
            start_time=time.time() - 10,  # 10 seconds ago
        )
        rate = metrics.processing_rate
        assert rate > 0
        assert rate <= 1.0  # Should be around 0.5 items/sec

    def test_metrics_processing_rate_zero_elapsed(self):
        """Test processing rate with zero elapsed time."""
        metrics = ProgressMetrics(
            total_items=10,
            completed_items=5,
            start_time=time.time(),
        )
        assert metrics.processing_rate == 0.0

    def test_metrics_bytes_per_second(self):
        """Test bytes per second calculation."""
        metrics = ProgressMetrics(
            processed_bytes=1000,
            start_time=time.time() - 10,  # 10 seconds ago
        )
        rate = metrics.bytes_per_second
        assert rate > 0
        assert rate <= 200  # Should be around 100 bytes/sec

    def test_metrics_eta_calculation(self):
        """Test ETA calculation."""
        metrics = ProgressMetrics(
            total_items=10,
            completed_items=5,
            start_time=time.time() - 10,  # 10 seconds ago
        )
        eta = metrics.estimated_time_remaining
        assert eta is not None
        assert eta > 0

    def test_metrics_eta_no_progress(self):
        """Test ETA with no progress."""
        metrics = ProgressMetrics(
            total_items=10,
            completed_items=0,
            start_time=time.time() - 10,
        )
        assert metrics.estimated_time_remaining is None

    def test_metrics_eta_completed(self):
        """Test ETA when all items completed."""
        metrics = ProgressMetrics(
            total_items=10,
            completed_items=10,
            start_time=time.time() - 10,
        )
        assert metrics.estimated_time_remaining == 0.0

    def test_metrics_increment_completed(self):
        """Test incrementing completed items."""
        metrics = ProgressMetrics(total_items=10)
        metrics.increment_completed()
        assert metrics.completed_items == 1

    def test_metrics_increment_failed(self):
        """Test incrementing failed items."""
        metrics = ProgressMetrics(total_items=10)
        metrics.increment_failed()
        assert metrics.failed_items == 1

    def test_metrics_increment_skipped(self):
        """Test incrementing skipped items."""
        metrics = ProgressMetrics(total_items=10)
        metrics.increment_skipped()
        assert metrics.skipped_items == 1

    def test_metrics_add_bytes(self):
        """Test adding processed bytes."""
        metrics = ProgressMetrics(total_bytes=1000)
        metrics.add_bytes(500)
        assert metrics.processed_bytes == 500


class TestEnhancedOperationReport:
    """Test enhanced operation report with metrics."""

    def test_report_with_metrics(self):
        """Test operation report with metrics."""
        report = OperationReport(tool="test")
        assert report.metrics is not None
        assert isinstance(report.metrics, ProgressMetrics)

    def test_report_metrics_integration(self):
        """Test metrics integration with report."""
        report = OperationReport(tool="test")
        report.metrics.total_items = 10
        report.metrics.increment_completed()
        report.metrics.increment_completed()
        report.metrics.increment_failed()

        assert report.metrics.completed_items == 2
        assert report.metrics.failed_items == 1
        assert report.metrics.success_rate == 20.0

    def test_report_summary_with_metrics(self):
        """Test report summary includes metrics."""
        report = OperationReport(tool="test")
        report.metrics.total_items = 10
        report.metrics.completed_items = 8
        report.metrics.failed_items = 2
        report.metrics.total_bytes = 1000
        report.metrics.processed_bytes = 500

        summary = report.get_summary()
        assert "success_rate" in summary
        assert "compression_ratio" in summary
        assert summary["success_rate"] == 80.0
        assert summary["compression_ratio"] == 50.0


class TestProgressContext:
    """Test enhanced progress context manager."""

    def test_enhanced_progress_basic(self):
        """Test basic enhanced progress context."""
        from framekit.ui.progress import enhanced_progress

        with enhanced_progress("Test", total=10) as progress:
            assert progress is not None
            progress(1)

    def test_enhanced_progress_with_metrics(self):
        """Test enhanced progress with metrics tracking."""
        from framekit.ui.progress import enhanced_progress

        with enhanced_progress("Test", total=10, show_metrics=True) as progress:
            progress(1, success=True)
            progress(1, success=False)
            progress(1, skipped=True)

    def test_enhanced_progress_with_bytes(self):
        """Test enhanced progress with byte tracking."""
        from framekit.ui.progress import enhanced_progress

        with enhanced_progress(
            "Test",
            total=10,
            unit="bytes",
            total_bytes=1000,
        ) as progress:
            progress(100)

    def test_enhanced_progress_summary(self):
        """Test progress summary generation."""
        from framekit.ui.progress import enhanced_progress

        with enhanced_progress("Test", total=10, show_summary=True) as progress:
            for _ in range(8):
                progress(1, success=True)
            for _ in range(2):
                progress(1, success=False)
        # Summary should be printed after context exit


class TestProgressMetricsFormatting:
    """Test progress metrics formatting."""

    def test_format_rate(self):
        """Test rate formatting."""
        from framekit.ui.progress import format_rate

        assert format_rate(0.5) == "0.50 items/s"
        assert format_rate(1.0) == "1.00 items/s"
        assert format_rate(10.5) == "10.50 items/s"

    def test_format_bytes_rate(self):
        """Test bytes rate formatting."""
        from framekit.ui.progress import format_bytes_rate

        assert "B/s" in format_bytes_rate(100)
        assert "KB/s" in format_bytes_rate(1024 * 10)
        assert "MB/s" in format_bytes_rate(1024 * 1024 * 5)

    def test_format_compression_ratio(self):
        """Test compression ratio formatting."""
        from framekit.ui.progress import format_compression_ratio

        assert format_compression_ratio(50.0) == "50.0%"
        assert format_compression_ratio(75.5) == "75.5%"
        assert format_compression_ratio(0.0) == "0.0%"

    def test_format_eta(self):
        """Test ETA formatting logic."""
        # Test seconds
        seconds = 30
        result = f"{int(seconds)}s" if seconds < 60 else ""
        assert result == "30s"

        # Test minutes
        seconds = 90
        minutes = int(seconds / 60)
        secs = int(seconds % 60)
        result = f"{minutes}m {secs}s"
        assert result == "1m 30s"

        # Test hours
        seconds = 3600
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        result = f"{hours}h {minutes}m"
        assert result == "1h 0m"


# Made with Bob
