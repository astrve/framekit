"""Tests for screenshot timing improvements to avoid irrelevant first/last frames."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from ouro.core.tools import ToolRegistry  # noqa: E402
from ouro.modules.screenshot.analyzer import FrameAnalyzer  # noqa: E402


class TestTimestampMargins:
    """Test timestamp generation with percentage-based margins."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer with mock registry."""
        registry = Mock(spec=ToolRegistry)
        return FrameAnalyzer(registry)

    def test_timestamps_avoid_start_with_percentage_margin(self, analyzer):
        """Test that first timestamp is NOT at 0% when using percentage margins."""
        # 120-minute video (7200 seconds)
        duration = 7200.0
        count = 6

        # With 5% start margin, first timestamp should be at ~5% (360s)
        timestamps = analyzer.generate_timestamps(
            duration=duration,
            count=count,
            skip_start_percent=5.0,
            skip_end_percent=5.0,
        )

        assert len(timestamps) == count
        # First timestamp should NOT be at 0
        assert timestamps[0] > 0
        # First timestamp should be around 5% of duration (360s)
        expected_start = duration * 0.05
        assert abs(timestamps[0] - expected_start) < 1.0  # Within 1 second

    def test_timestamps_avoid_end_with_percentage_margin(self, analyzer):
        """Test that last timestamp is NOT at 100% when using percentage margins."""
        # 120-minute video (7200 seconds)
        duration = 7200.0
        count = 6

        # With 5% end margin, last timestamp should be at ~95% (6840s)
        timestamps = analyzer.generate_timestamps(
            duration=duration,
            count=count,
            skip_start_percent=5.0,
            skip_end_percent=5.0,
        )

        assert len(timestamps) == count
        # Last timestamp should NOT be at duration
        assert timestamps[-1] < duration
        # Last timestamp should be around 95% of duration (6840s)
        expected_end = duration * 0.95
        assert abs(timestamps[-1] - expected_end) < 1.0  # Within 1 second

    def test_timestamps_within_safe_range(self, analyzer):
        """Test that all timestamps are within the safe range (5%-95%)."""
        duration = 7200.0
        count = 6

        timestamps = analyzer.generate_timestamps(
            duration=duration,
            count=count,
            skip_start_percent=5.0,
            skip_end_percent=5.0,
        )

        safe_start = duration * 0.05  # 360s
        safe_end = duration * 0.95  # 6840s

        for ts in timestamps:
            assert ts >= safe_start, f"Timestamp {ts} is before safe start {safe_start}"
            assert ts <= safe_end, f"Timestamp {ts} is after safe end {safe_end}"

    def test_even_distribution_within_safe_zone(self, analyzer):
        """Test that timestamps are evenly distributed within the safe zone."""
        duration = 7200.0
        count = 6

        timestamps = analyzer.generate_timestamps(
            duration=duration,
            count=count,
            skip_start_percent=5.0,
            skip_end_percent=5.0,
        )

        # Calculate intervals between consecutive timestamps
        intervals = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]

        # All intervals should be roughly equal
        avg_interval = sum(intervals) / len(intervals)
        for interval in intervals:
            # Allow 1% variance
            assert abs(interval - avg_interval) / avg_interval < 0.01

    def test_percentage_margins_with_different_durations(self, analyzer):
        """Test percentage margins work correctly with different video durations."""
        test_cases = [
            (600.0, 4),  # 10-minute video, 4 screenshots
            (3600.0, 6),  # 60-minute video, 6 screenshots
            (7200.0, 8),  # 120-minute video, 8 screenshots
            (10800.0, 10),  # 180-minute video, 10 screenshots
        ]

        for duration, count in test_cases:
            timestamps = analyzer.generate_timestamps(
                duration=duration,
                count=count,
                skip_start_percent=5.0,
                skip_end_percent=5.0,
            )

            safe_start = duration * 0.05
            safe_end = duration * 0.95

            assert len(timestamps) == count
            assert timestamps[0] >= safe_start
            assert timestamps[-1] <= safe_end

    def test_backward_compatibility_with_seconds(self, analyzer):
        """Test that old skip_start/skip_end (in seconds) still works."""
        duration = 7200.0
        count = 6

        # Old API: skip_start and skip_end in seconds
        timestamps = analyzer.generate_timestamps(
            duration=duration,
            count=count,
            skip_start=60,
            skip_end=120,
        )

        assert len(timestamps) == count
        assert timestamps[0] >= 60
        assert timestamps[-1] <= (duration - 120)

    def test_percentage_margins_override_seconds(self, analyzer):
        """Test that percentage margins take precedence over second-based margins."""
        duration = 7200.0
        count = 6

        # If both are provided, percentage should take precedence
        timestamps = analyzer.generate_timestamps(
            duration=duration,
            count=count,
            skip_start=60,  # Old API
            skip_end=120,  # Old API
            skip_start_percent=5.0,  # New API - should override
            skip_end_percent=5.0,  # New API - should override
        )

        # Should use percentage margins (5% = 360s, not 60s)
        expected_start = duration * 0.05
        assert abs(timestamps[0] - expected_start) < 1.0

    def test_zero_percent_margins_uses_full_duration(self, analyzer):
        """Test that 0% margins uses the full video duration."""
        duration = 7200.0
        count = 6

        timestamps = analyzer.generate_timestamps(
            duration=duration,
            count=count,
            skip_start_percent=0.0,
            skip_end_percent=0.0,
        )

        # First timestamp should be at or near 0
        assert timestamps[0] < 10  # Within 10 seconds of start
        # Last timestamp should be at or near duration
        assert timestamps[-1] > (duration - 10)  # Within 10 seconds of end

    def test_custom_percentage_margins(self, analyzer):
        """Test custom percentage margins (e.g., 3% and 7%)."""
        duration = 7200.0
        count = 6

        timestamps = analyzer.generate_timestamps(
            duration=duration,
            count=count,
            skip_start_percent=3.0,
            skip_end_percent=7.0,
        )

        safe_start = duration * 0.03  # 216s
        safe_end = duration * 0.93  # 6696s (100% - 7%)

        assert timestamps[0] >= safe_start
        assert timestamps[-1] <= safe_end

    def test_single_screenshot_with_margins(self, analyzer):
        """Test single screenshot placement with percentage margins."""
        duration = 7200.0
        count = 1

        timestamps = analyzer.generate_timestamps(
            duration=duration,
            count=count,
            skip_start_percent=5.0,
            skip_end_percent=5.0,
        )

        assert len(timestamps) == 1
        # Single screenshot should be in the middle of safe zone
        safe_start = duration * 0.05
        safe_end = duration * 0.95
        safe_middle = (safe_start + safe_end) / 2

        assert abs(timestamps[0] - safe_middle) < 1.0

    def test_very_short_video_with_margins(self, analyzer):
        """Test that margins work sensibly with very short videos."""
        duration = 60.0  # 1-minute video
        count = 3

        timestamps = analyzer.generate_timestamps(
            duration=duration,
            count=count,
            skip_start_percent=5.0,
            skip_end_percent=5.0,
        )

        # Should still generate timestamps within safe zone
        safe_start = duration * 0.05  # 3s
        safe_end = duration * 0.95  # 57s

        assert len(timestamps) >= 1  # At least one timestamp
        for ts in timestamps:
            assert ts >= safe_start
            assert ts <= safe_end

    def test_margins_respect_min_interval(self, analyzer):
        """Test that percentage margins work with min_interval constraint."""
        duration = 7200.0
        count = 20
        min_interval = 300  # 5 minutes

        timestamps = analyzer.generate_timestamps(
            duration=duration,
            count=count,
            skip_start_percent=5.0,
            skip_end_percent=5.0,
            min_interval=min_interval,
        )

        # Check min_interval is respected
        for i in range(len(timestamps) - 1):
            assert timestamps[i + 1] - timestamps[i] >= min_interval

        # Check margins are respected
        safe_start = duration * 0.05
        safe_end = duration * 0.95
        assert timestamps[0] >= safe_start
        assert timestamps[-1] <= safe_end


class TestRealWorldScenarios:
    """Test real-world scenarios from the task description."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer with mock registry."""
        registry = Mock(spec=ToolRegistry)
        return FrameAnalyzer(registry)

    def test_120_minute_video_6_screenshots(self, analyzer):
        """Test the exact scenario from task description: 120-min video, 6 screenshots."""
        duration = 7200.0  # 120 minutes
        count = 6

        timestamps = analyzer.generate_timestamps(
            duration=duration,
            count=count,
            skip_start_percent=5.0,
            skip_end_percent=5.0,
        )

        # Verify we get 6 screenshots
        assert len(timestamps) == 6

        # Verify first screenshot is around 5% (360s)
        first_pct = (timestamps[0] / duration) * 100
        assert 4.5 <= first_pct <= 5.5, f"First screenshot at {first_pct:.1f}%, expected ~5%"

        # Verify last screenshot is around 95% (6840s)
        last_pct = (timestamps[-1] / duration) * 100
        assert 94.5 <= last_pct <= 95.5, f"Last screenshot at {last_pct:.1f}%, expected ~95%"

        # Verify even distribution within safe zone
        intervals = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
        avg_interval = sum(intervals) / len(intervals)
        for interval in intervals:
            # Allow 5% variance in interval spacing
            assert abs(interval - avg_interval) / avg_interval < 0.05

    def test_no_black_screens_at_boundaries(self, analyzer):
        """Test that we avoid common black screen locations (0% and 100%)."""
        duration = 7200.0
        count = 6

        timestamps = analyzer.generate_timestamps(
            duration=duration,
            count=count,
            skip_start_percent=5.0,
            skip_end_percent=5.0,
        )

        # First 5% (360s) often contains: studio logos, black screens, intros
        # Last 5% (360s) often contains: credits, black screens, outros

        # Verify we skip these regions
        assert timestamps[0] >= 360, "First screenshot should skip intro region"
        assert timestamps[-1] <= 6840, "Last screenshot should skip outro region"
