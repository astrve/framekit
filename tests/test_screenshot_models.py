"""Tests for screenshot data models."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from framekit.core.models.screenshot import (  # noqa: E402
    ScreenshotConfig,
    ScreenshotMetadata,
    ScreenshotReport,
    ScreenshotResult,
    TimestampConfig,
)


class TestScreenshotConfig:
    """Test ScreenshotConfig model."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        config = ScreenshotConfig()
        assert config.count == 6
        assert config.width is None
        assert config.height is None
        assert config.quality == 2
        assert config.format == "png"
        assert config.skip_start_seconds == 60
        assert config.skip_end_seconds == 120
        assert config.avoid_black_frames is True
        assert config.black_threshold == 0.05
        assert config.min_interval_seconds == 30

    def test_custom_values(self):
        """Test setting custom values."""
        config = ScreenshotConfig(
            count=10,
            width=1280,
            height=720,
            quality=5,
            format="jpg",
            skip_start_seconds=30,
            skip_end_seconds=60,
            avoid_black_frames=False,
            black_threshold=0.1,
            min_interval_seconds=15,
        )
        assert config.count == 10
        assert config.width == 1280
        assert config.height == 720
        assert config.quality == 5
        assert config.format == "jpg"
        assert config.skip_start_seconds == 30
        assert config.skip_end_seconds == 60
        assert config.avoid_black_frames is False
        assert config.black_threshold == 0.1
        assert config.min_interval_seconds == 15

    def test_count_validation_min(self):
        """Test that count must be at least 1."""
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            ScreenshotConfig(count=0)

    def test_count_validation_max(self):
        """Test that count must be at most 50."""
        with pytest.raises(ValidationError, match="less than or equal to 50"):
            ScreenshotConfig(count=51)

    def test_width_validation(self):
        """Test that width must be at least 320."""
        with pytest.raises(ValidationError, match="greater than or equal to 320"):
            ScreenshotConfig(width=100)

    def test_height_validation(self):
        """Test that height must be at least 240."""
        with pytest.raises(ValidationError, match="greater than or equal to 240"):
            ScreenshotConfig(height=100)

    def test_quality_validation_min(self):
        """Test that quality must be at least 1."""
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            ScreenshotConfig(quality=0)

    def test_quality_validation_max(self):
        """Test that quality must be at most 31."""
        with pytest.raises(ValidationError, match="less than or equal to 31"):
            ScreenshotConfig(quality=32)

    def test_format_validation(self):
        """Test that format must be png or jpg."""
        # Valid formats
        ScreenshotConfig(format="png")
        ScreenshotConfig(format="jpg")

        # Invalid format
        with pytest.raises(ValidationError):
            ScreenshotConfig(format="bmp")

    def test_black_threshold_validation_min(self):
        """Test that black_threshold must be at least 0.0."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            ScreenshotConfig(black_threshold=-0.1)

    def test_black_threshold_validation_max(self):
        """Test that black_threshold must be at most 1.0."""
        with pytest.raises(ValidationError, match="less than or equal to 1"):
            ScreenshotConfig(black_threshold=1.1)

    def test_min_interval_validation(self):
        """Test that min_interval_seconds must be at least 1."""
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            ScreenshotConfig(min_interval_seconds=0)


class TestTimestampConfig:
    """Test TimestampConfig model."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        config = TimestampConfig()
        assert config.timestamps == []
        assert config.width is None
        assert config.height is None
        assert config.quality == 2
        assert config.format == "png"

    def test_custom_timestamps(self):
        """Test setting custom timestamps."""
        config = TimestampConfig(
            timestamps=[10.5, 30.0, 60.5],
            width=1920,
            height=1080,
            quality=3,
            format="jpg",
        )
        assert config.timestamps == [10.5, 30.0, 60.5]
        assert config.width == 1920
        assert config.height == 1080
        assert config.quality == 3
        assert config.format == "jpg"

    def test_width_validation(self):
        """Test that width must be at least 320."""
        with pytest.raises(ValidationError, match="greater than or equal to 320"):
            TimestampConfig(width=100)

    def test_height_validation(self):
        """Test that height must be at least 240."""
        with pytest.raises(ValidationError, match="greater than or equal to 240"):
            TimestampConfig(height=100)


class TestScreenshotMetadata:
    """Test ScreenshotMetadata dataclass."""

    def test_creation(self, tmp_path):
        """Test creating metadata instance."""
        video_path = tmp_path / "video.mkv"
        metadata = ScreenshotMetadata(
            timestamp_seconds=30.5,
            frame_number=732,
            width=1920,
            height=1080,
            file_size_bytes=1024000,
            quality_score=0.85,
            is_black_frame=False,
            video_source=video_path,
        )
        assert metadata.timestamp_seconds == 30.5
        assert metadata.frame_number == 732
        assert metadata.width == 1920
        assert metadata.height == 1080
        assert metadata.file_size_bytes == 1024000
        assert metadata.quality_score == 0.85
        assert metadata.is_black_frame is False
        assert metadata.video_source == video_path

    def test_optional_fields(self, tmp_path):
        """Test that optional fields can be None."""
        video_path = tmp_path / "video.mkv"
        metadata = ScreenshotMetadata(
            timestamp_seconds=30.5,
            frame_number=None,
            width=1920,
            height=1080,
            file_size_bytes=1024000,
            quality_score=None,
            is_black_frame=False,
            video_source=video_path,
        )
        assert metadata.frame_number is None
        assert metadata.quality_score is None


class TestScreenshotResult:
    """Test ScreenshotResult dataclass."""

    def test_creation(self, tmp_path):
        """Test creating result instance."""
        video_path = tmp_path / "video.mkv"
        output_dir = tmp_path / "screenshots"
        result = ScreenshotResult(
            video_path=video_path,
            output_dir=output_dir,
            screenshots=[],
            metadata=[],
            skipped_black_frames=0,
            total_frames_analyzed=0,
            duration_seconds=0.0,
            success=True,
            error=None,
        )
        assert result.video_path == video_path
        assert result.output_dir == output_dir
        assert result.screenshots == []
        assert result.metadata == []
        assert result.skipped_black_frames == 0
        assert result.total_frames_analyzed == 0
        assert result.duration_seconds == 0.0
        assert result.success is True
        assert result.error is None

    def test_with_screenshots(self, tmp_path):
        """Test result with screenshots."""
        video_path = tmp_path / "video.mkv"
        output_dir = tmp_path / "screenshots"
        screenshot1 = output_dir / "screenshot_001.png"
        screenshot2 = output_dir / "screenshot_002.png"

        metadata1 = ScreenshotMetadata(
            timestamp_seconds=30.0,
            frame_number=720,
            width=1920,
            height=1080,
            file_size_bytes=1024000,
            quality_score=0.9,
            is_black_frame=False,
            video_source=video_path,
        )

        result = ScreenshotResult(
            video_path=video_path,
            output_dir=output_dir,
            screenshots=[screenshot1, screenshot2],
            metadata=[metadata1],
            skipped_black_frames=2,
            total_frames_analyzed=10,
            duration_seconds=3600.0,
            success=True,
            error=None,
        )
        assert len(result.screenshots) == 2
        assert len(result.metadata) == 1
        assert result.skipped_black_frames == 2
        assert result.total_frames_analyzed == 10

    def test_failure_result(self, tmp_path):
        """Test result for failed extraction."""
        video_path = tmp_path / "video.mkv"
        output_dir = tmp_path / "screenshots"
        result = ScreenshotResult(
            video_path=video_path,
            output_dir=output_dir,
            screenshots=[],
            metadata=[],
            skipped_black_frames=0,
            total_frames_analyzed=0,
            duration_seconds=0.0,
            success=False,
            error="FFmpeg not found",
        )
        assert result.success is False
        assert result.error == "FFmpeg not found"


class TestScreenshotReport:
    """Test ScreenshotReport dataclass."""

    def test_creation(self):
        """Test creating report instance."""
        report = ScreenshotReport(
            results=[],
            total_videos=0,
            total_screenshots=0,
            total_failures=0,
            elapsed_seconds=0.0,
        )
        assert report.results == []
        assert report.total_videos == 0
        assert report.total_screenshots == 0
        assert report.total_failures == 0
        assert report.elapsed_seconds == 0.0

    def test_success_rate_no_videos(self):
        """Test success rate with no videos."""
        report = ScreenshotReport()
        assert report.success_rate == 0.0

    def test_success_rate_all_success(self):
        """Test success rate with all successful."""
        report = ScreenshotReport(
            total_videos=10,
            total_screenshots=60,
            total_failures=0,
        )
        assert report.success_rate == 1.0

    def test_success_rate_partial_success(self):
        """Test success rate with partial success."""
        report = ScreenshotReport(
            total_videos=10,
            total_screenshots=54,
            total_failures=3,
        )
        assert report.success_rate == 0.7

    def test_success_rate_all_failures(self):
        """Test success rate with all failures."""
        report = ScreenshotReport(
            total_videos=10,
            total_screenshots=0,
            total_failures=10,
        )
        assert report.success_rate == 0.0


# Made with Bob
