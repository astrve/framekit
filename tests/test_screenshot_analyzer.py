"""Tests for frame analyzer."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from framekit.core.tools import ToolRegistry  # noqa: E402
from framekit.modules.screenshot.analyzer import FrameAnalyzer  # noqa: E402


class TestFrameAnalyzer:
    """Test FrameAnalyzer class."""

    @pytest.fixture
    def mock_registry(self):
        """Create a mock ToolRegistry."""
        registry = Mock(spec=ToolRegistry)
        registry.resolve_tool_path.return_value = "ffprobe"
        return registry

    @pytest.fixture
    def analyzer(self, mock_registry):
        """Create a FrameAnalyzer instance."""
        return FrameAnalyzer(mock_registry)

    def test_initialization(self, mock_registry):
        """Test analyzer initialization."""
        analyzer = FrameAnalyzer(mock_registry)
        assert analyzer.registry == mock_registry

    def test_get_video_duration_success(self, analyzer, tmp_path):
        """Test getting video duration successfully."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"format": {"duration": "3600.5"}})

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            duration = analyzer.get_video_duration(video_path)

            assert duration == 3600.5
            mock_run.assert_called_once()
            # Verify command structure
            cmd = mock_run.call_args[0][0]
            assert isinstance(cmd, list)
            # ``subprocess_safe.run_safe`` resolves ``argv[0]`` to an absolute
            # path via ``shutil.which`` (ADR-0006), so accept both forms.
            assert cmd[0] == "ffprobe" or cmd[0].lower().endswith(("ffprobe", "ffprobe.exe"))
            assert str(video_path) in cmd

    def test_get_video_duration_ffprobe_not_found(self, mock_registry, tmp_path):
        """Test when ffprobe is not available."""
        mock_registry.resolve_tool_path.return_value = None
        analyzer = FrameAnalyzer(mock_registry)

        video_path = tmp_path / "video.mkv"
        duration = analyzer.get_video_duration(video_path)

        assert duration is None

    def test_get_video_duration_ffprobe_error(self, analyzer, tmp_path):
        """Test when ffprobe returns an error."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")

        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            duration = analyzer.get_video_duration(video_path)

            assert duration is None

    def test_get_video_duration_timeout(self, analyzer, tmp_path):
        """Test handling of timeout."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ffprobe", 10)):
            duration = analyzer.get_video_duration(video_path)

            assert duration is None

    def test_get_video_duration_invalid_json(self, analyzer, tmp_path):
        """Test handling of invalid JSON response."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "invalid json"

        with patch("subprocess.run", return_value=mock_result):
            duration = analyzer.get_video_duration(video_path)

            assert duration is None

    def test_generate_timestamps_evenly_distributed(self, analyzer):
        """Test generating evenly distributed timestamps."""
        timestamps = analyzer.generate_timestamps(
            duration=3600.0,
            count=6,
            skip_start=60,
            skip_end=120,
            min_interval=30,
        )

        assert len(timestamps) == 6
        # All timestamps should be within valid range
        # Note: last timestamp should be at duration - skip_end = 3480
        for ts in timestamps:
            assert 60 <= ts <= 3480  # 3600 - 120
        # Timestamps should be sorted
        assert timestamps == sorted(timestamps)
        # Minimum interval should be respected
        for i in range(len(timestamps) - 1):
            assert timestamps[i + 1] - timestamps[i] >= 30

    def test_generate_timestamps_short_video(self, analyzer):
        """Test generating timestamps for short video."""
        # Video too short for requested count
        timestamps = analyzer.generate_timestamps(
            duration=100.0,
            count=10,
            skip_start=10,
            skip_end=10,
            min_interval=30,
        )

        # Should return fewer timestamps due to constraints
        assert len(timestamps) <= 10
        assert len(timestamps) >= 1

    def test_generate_timestamps_respects_skip_regions(self, analyzer):
        """Test that skip regions are respected."""
        timestamps = analyzer.generate_timestamps(
            duration=3600.0,
            count=6,
            skip_start=300,
            skip_end=300,
            min_interval=30,
        )

        # No timestamp should be in skip regions
        for ts in timestamps:
            assert ts >= 300
            assert ts <= 3300  # 3600 - 300

    def test_detect_black_frames_success(self, analyzer, tmp_path):
        """Test detecting black frames."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")

        # Mock ffmpeg output with black frame detection
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = (
            "[blackdetect @ 0x123] black_start:10.5 black_end:11.0 black_duration:0.5\n"
            "[blackdetect @ 0x123] black_start:30.0 black_end:31.5 black_duration:1.5\n"
        )

        with patch("subprocess.run", return_value=mock_result):
            black_frames = analyzer.detect_black_frames(video_path, threshold=0.05, duration=0.5)

            assert len(black_frames) == 2
            assert 10.5 in black_frames
            assert 30.0 in black_frames

    def test_detect_black_frames_no_black_frames(self, analyzer, tmp_path):
        """Test when no black frames are detected."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            black_frames = analyzer.detect_black_frames(video_path)

            assert black_frames == []

    def test_detect_black_frames_ffmpeg_error(self, analyzer, tmp_path):
        """Test handling ffmpeg error."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")

        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Error"

        with patch("subprocess.run", return_value=mock_result):
            black_frames = analyzer.detect_black_frames(video_path)

            assert black_frames == []

    def test_filter_timestamps_removes_black_frames(self, analyzer):
        """Test filtering timestamps to remove black frames."""
        timestamps = [10.0, 20.0, 30.0, 40.0, 50.0]
        black_frames = [19.5, 20.5, 49.0, 51.0]  # Near 20.0 and 50.0

        filtered = analyzer.filter_black_frames(timestamps, black_frames, tolerance=2.0)

        # Should remove timestamps near black frames
        assert 10.0 in filtered
        assert 30.0 in filtered
        assert 40.0 in filtered
        assert 20.0 not in filtered  # Too close to black frame
        assert 50.0 not in filtered  # Too close to black frame

    def test_filter_timestamps_no_black_frames(self, analyzer):
        """Test filtering when no black frames exist."""
        timestamps = [10.0, 20.0, 30.0]
        black_frames = []

        filtered = analyzer.filter_black_frames(timestamps, black_frames)

        assert filtered == timestamps

    def test_get_video_info_success(self, analyzer, tmp_path):
        """Test getting complete video info."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {
                "format": {"duration": "3600.5"},
                "streams": [
                    {
                        "codec_type": "video",
                        "codec_name": "h264",
                        "width": 1920,
                        "height": 1080,
                        "r_frame_rate": "24000/1001",
                    }
                ],
            }
        )

        with patch("subprocess.run", return_value=mock_result):
            info = analyzer.get_video_info(video_path)

            assert info is not None
            assert info["duration"] == 3600.5
            assert info["width"] == 1920
            assert info["height"] == 1080
            assert info["codec"] == "h264"

    def test_get_video_info_no_video_stream(self, analyzer, tmp_path):
        """Test when video has no video stream."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {
                "format": {"duration": "3600.5"},
                "streams": [{"codec_type": "audio", "codec_name": "aac"}],
            }
        )

        with patch("subprocess.run", return_value=mock_result):
            info = analyzer.get_video_info(video_path)

            assert info is None


class TestTimestampGeneration:
    """Test timestamp generation algorithms."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer with mock registry."""
        registry = Mock(spec=ToolRegistry)
        return FrameAnalyzer(registry)

    def test_even_distribution(self, analyzer):
        """Test that timestamps are evenly distributed."""
        timestamps = analyzer.generate_timestamps(
            duration=1000.0,
            count=5,
            skip_start=0,
            skip_end=0,
            min_interval=1,
        )

        # Check spacing is roughly equal
        intervals = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
        avg_interval = sum(intervals) / len(intervals)

        for interval in intervals:
            # Allow 10% variance
            assert abs(interval - avg_interval) / avg_interval < 0.1

    def test_respects_minimum_interval(self, analyzer):
        """Test that minimum interval is always respected."""
        timestamps = analyzer.generate_timestamps(
            duration=1000.0,
            count=20,
            skip_start=0,
            skip_end=0,
            min_interval=50,
        )

        for i in range(len(timestamps) - 1):
            assert timestamps[i + 1] - timestamps[i] >= 50

    def test_handles_impossible_constraints(self, analyzer):
        """Test handling of impossible constraints."""
        # Request more screenshots than possible with min_interval
        timestamps = analyzer.generate_timestamps(
            duration=100.0,
            count=50,
            skip_start=0,
            skip_end=0,
            min_interval=10,
        )

        # Should return maximum possible (100 / 10 = 10, plus 1 for endpoints)
        assert len(timestamps) <= 11  # 100 / 10 + 1
