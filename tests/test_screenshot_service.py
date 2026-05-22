"""Tests for screenshot service."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from framekit.core.models.screenshot import (  # noqa: E402
    ScreenshotConfig,
    ScreenshotMetadata,
    ScreenshotReport,
    ScreenshotResult,
)
from framekit.core.tools import ToolRegistry  # noqa: E402
from framekit.modules.screenshot.analyzer import FrameAnalyzer  # noqa: E402
from framekit.modules.screenshot.extractor import ScreenshotExtractor  # noqa: E402
from framekit.modules.screenshot.service import ScreenshotService  # noqa: E402


class TestScreenshotService:
    """Test ScreenshotService class."""

    @pytest.fixture
    def mock_registry(self):
        """Create a mock ToolRegistry."""
        registry = Mock(spec=ToolRegistry)
        registry.resolve_tool_path.return_value = "ffmpeg"
        return registry

    @pytest.fixture
    def mock_analyzer(self):
        """Create a mock FrameAnalyzer."""
        analyzer = Mock(spec=FrameAnalyzer)
        analyzer.get_video_duration.return_value = 3600.0
        analyzer.get_video_info.return_value = {
            "duration": 3600.0,
            "width": 1920,
            "height": 1080,
            "codec": "h264",
            "fps": 23.976,
        }
        analyzer.generate_timestamps.return_value = [120.0, 600.0, 1200.0, 1800.0, 2400.0, 3000.0]
        analyzer.detect_black_frames.return_value = []
        analyzer.filter_black_frames.return_value = [120.0, 600.0, 1200.0, 1800.0, 2400.0, 3000.0]
        return analyzer

    @pytest.fixture
    def mock_extractor(self):
        """Create a mock ScreenshotExtractor."""
        extractor = Mock(spec=ScreenshotExtractor)
        extractor.extract_screenshot.return_value = True
        extractor.extract_multiple.return_value = [True, True, True, True, True, True]
        return extractor

    @pytest.fixture
    def service(self, mock_analyzer, mock_extractor):
        """Create a ScreenshotService instance with mocks."""
        return ScreenshotService(analyzer=mock_analyzer, extractor=mock_extractor)

    @pytest.fixture
    def config(self):
        """Create a default ScreenshotConfig."""
        return ScreenshotConfig(
            count=6,
            width=None,
            quality=2,
            format="png",
            skip_start_seconds=60,
            skip_end_seconds=120,
            avoid_black_frames=True,
        )

    def test_initialization_with_dependencies(self, mock_analyzer, mock_extractor):
        """Test service initialization with provided dependencies."""
        service = ScreenshotService(analyzer=mock_analyzer, extractor=mock_extractor)
        assert service.analyzer == mock_analyzer
        assert service.extractor == mock_extractor

    def test_initialization_without_dependencies(self, mock_registry):
        """Test service initialization creates default dependencies."""
        with (
            patch("framekit.modules.screenshot.service.FrameAnalyzer") as mock_analyzer_cls,
            patch("framekit.modules.screenshot.service.ScreenshotExtractor") as mock_extractor_cls,
        ):
            service = ScreenshotService()

            # Should create default instances
            mock_analyzer_cls.assert_called_once()
            mock_extractor_cls.assert_called_once()

    def test_extract_screenshots_single_video(
        self, service, mock_analyzer, mock_extractor, config, tmp_path
    ):
        """Test extracting screenshots from a single video."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        report = service.extract_screenshots(
            video_paths=[video_path],
            output_dir=output_dir,
            config=config,
            release_name="Test.Release",
        )

        # Verify report structure
        assert isinstance(report, ScreenshotReport)
        assert report.total_videos == 1
        assert len(report.results) == 1

        result = report.results[0]
        assert result.video_path == video_path
        assert result.output_dir == output_dir
        assert result.success is True

        # Verify analyzer was called
        mock_analyzer.get_video_info.assert_called_once_with(video_path)
        mock_analyzer.generate_timestamps.assert_called_once()

    def test_extract_screenshots_multiple_videos(
        self, service, mock_analyzer, mock_extractor, config, tmp_path
    ):
        """Test extracting screenshots from multiple videos."""
        video1 = tmp_path / "video1.mkv"
        video2 = tmp_path / "video2.mkv"
        video1.write_text("fake video 1")
        video2.write_text("fake video 2")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        report = service.extract_screenshots(
            video_paths=[video1, video2],
            output_dir=output_dir,
            config=config,
        )

        assert report.total_videos == 2
        assert len(report.results) == 2
        assert all(r.success for r in report.results)

    def test_extract_screenshots_with_progress_callback(
        self, service, mock_analyzer, mock_extractor, config, tmp_path
    ):
        """Test progress callback is invoked during extraction."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        progress_calls = []

        def progress_callback(message: str, current: int, total: int):
            progress_calls.append((message, current, total))

        service.extract_screenshots(
            video_paths=[video_path],
            output_dir=output_dir,
            config=config,
            progress_callback=progress_callback,
        )

        # Verify progress was reported
        assert len(progress_calls) > 0

    def test_extract_screenshots_handles_missing_video(self, service, config, tmp_path):
        """Test handling of missing video file."""
        video_path = tmp_path / "nonexistent.mkv"
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        report = service.extract_screenshots(
            video_paths=[video_path],
            output_dir=output_dir,
            config=config,
        )

        assert report.total_videos == 1
        assert report.total_failures == 1
        assert len(report.results) == 1
        assert report.results[0].success is False
        assert report.results[0].error is not None

    def test_extract_screenshots_creates_output_dir(
        self, service, mock_analyzer, mock_extractor, config, tmp_path
    ):
        """Test that output directory is created if it doesn't exist."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_dir = tmp_path / "output" / "nested"

        assert not output_dir.exists()

        service.extract_screenshots(
            video_paths=[video_path],
            output_dir=output_dir,
            config=config,
        )

        assert output_dir.exists()

    def test_extract_screenshots_with_black_frame_detection(
        self, service, mock_analyzer, mock_extractor, config, tmp_path
    ):
        """Test black frame detection is used when enabled."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Configure analyzer to return black frames
        mock_analyzer.detect_black_frames.return_value = [100.0, 200.0]
        mock_analyzer.filter_black_frames.return_value = [600.0, 1200.0, 1800.0, 2400.0, 3000.0]

        config.avoid_black_frames = True

        service.extract_screenshots(
            video_paths=[video_path],
            output_dir=output_dir,
            config=config,
        )

        # Verify black frame detection was called
        mock_analyzer.detect_black_frames.assert_called_once()
        mock_analyzer.filter_black_frames.assert_called_once()

    def test_extract_screenshots_without_black_frame_detection(
        self, service, mock_analyzer, mock_extractor, config, tmp_path
    ):
        """Test black frame detection is skipped when disabled."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        config.avoid_black_frames = False

        service.extract_screenshots(
            video_paths=[video_path],
            output_dir=output_dir,
            config=config,
        )

        # Verify black frame detection was NOT called
        mock_analyzer.detect_black_frames.assert_not_called()

    def test_extract_from_timestamps(
        self, service, mock_analyzer, mock_extractor, config, tmp_path
    ):
        """Test extracting screenshots at specific timestamps."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        timestamps = [120.0, 600.0, 1200.0]

        # Mock extract_multiple to create actual files
        def create_screenshots(video_path, timestamps, output_paths, *args, **kwargs):
            for output_path in output_paths:
                output_path.write_text("fake screenshot")
            return [True] * len(timestamps)

        mock_extractor.extract_multiple.side_effect = create_screenshots

        result = service.extract_from_timestamps(
            video_path=video_path,
            timestamps=timestamps,
            output_dir=output_dir,
            config=config,
            release_name="Test.Release",
        )

        assert isinstance(result, ScreenshotResult)
        assert result.video_path == video_path
        assert result.success is True
        assert len(result.screenshots) == len(timestamps)

    def test_extract_from_timestamps_with_progress(
        self, service, mock_analyzer, mock_extractor, config, tmp_path
    ):
        """Test timestamp extraction with progress callback."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        timestamps = [120.0, 600.0, 1200.0]
        progress_calls = []

        def progress_callback(message: str, current: int, total: int):
            progress_calls.append((message, current, total))

        # Mock extract_multiple to create actual files
        def create_screenshots(video_path, timestamps, output_paths, *args, **kwargs):
            # Call the progress callback if provided
            progress_cb = kwargs.get("progress_callback")
            for i, output_path in enumerate(output_paths, start=1):
                output_path.write_text("fake screenshot")
                if progress_cb:
                    progress_cb(i, len(output_paths))
            return [True] * len(timestamps)

        mock_extractor.extract_multiple.side_effect = create_screenshots

        service.extract_from_timestamps(
            video_path=video_path,
            timestamps=timestamps,
            output_dir=output_dir,
            config=config,
            progress_callback=progress_callback,
        )

        assert len(progress_calls) > 0

    def test_extract_screenshots_aggregates_errors(self, service, mock_analyzer, config, tmp_path):
        """Test that errors from multiple videos are aggregated."""
        video1 = tmp_path / "video1.mkv"
        video2 = tmp_path / "nonexistent.mkv"
        video1.write_text("fake video")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        report = service.extract_screenshots(
            video_paths=[video1, video2],
            output_dir=output_dir,
            config=config,
        )

        assert report.total_videos == 2
        assert report.total_failures == 1
        assert report.success_rate == 0.5

    def test_extract_screenshots_with_missing_ffmpeg(self, mock_analyzer, config, tmp_path):
        """Test graceful degradation when FFmpeg is missing."""
        # Create extractor that simulates missing FFmpeg
        mock_extractor = Mock(spec=ScreenshotExtractor)
        mock_extractor.extract_multiple.return_value = [False] * 6

        service = ScreenshotService(analyzer=mock_analyzer, extractor=mock_extractor)

        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        report = service.extract_screenshots(
            video_paths=[video_path],
            output_dir=output_dir,
            config=config,
        )

        # Should complete but report failure
        assert report.total_videos == 1
        assert report.total_failures == 1

    def test_batch_processing(self, service, mock_analyzer, mock_extractor, config, tmp_path):
        """Test batch processing of multiple videos."""
        videos = []
        for i in range(5):
            video = tmp_path / f"video{i}.mkv"
            video.write_text(f"fake video {i}")
            videos.append(video)

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        report = service.extract_screenshots(
            video_paths=videos,
            output_dir=output_dir,
            config=config,
        )

        assert report.total_videos == 5
        assert len(report.results) == 5
        assert all(r.success for r in report.results)

    def test_screenshot_metadata_populated(
        self, service, mock_analyzer, mock_extractor, config, tmp_path
    ):
        """Test that screenshot metadata is properly populated."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Mock extract_multiple to create actual files
        def create_screenshots(video_path, timestamps, output_paths, *args, **kwargs):
            for output_path in output_paths:
                output_path.write_text("fake screenshot")
            return [True] * len(timestamps)

        mock_extractor.extract_multiple.side_effect = create_screenshots

        report = service.extract_screenshots(
            video_paths=[video_path],
            output_dir=output_dir,
            config=config,
            release_name="Test.Release",
        )

        result = report.results[0]
        assert len(result.metadata) > 0

        for metadata in result.metadata:
            assert isinstance(metadata, ScreenshotMetadata)
            assert metadata.timestamp_seconds >= 0
            assert metadata.video_source == video_path

    def test_report_statistics(self, service, mock_analyzer, mock_extractor, config, tmp_path):
        """Test that report statistics are correctly calculated."""
        videos = []
        for i in range(3):
            video = tmp_path / f"video{i}.mkv"
            video.write_text(f"fake video {i}")
            videos.append(video)

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Mock extract_multiple to create actual screenshot files
        def create_screenshots(video_path, timestamps, output_paths, *args, **kwargs):
            for output_path in output_paths:
                output_path.write_text("fake screenshot")
            return [True] * len(timestamps)

        mock_extractor.extract_multiple.side_effect = create_screenshots

        report = service.extract_screenshots(
            video_paths=videos,
            output_dir=output_dir,
            config=config,
        )

        assert report.total_videos == 3
        assert report.total_screenshots > 0
        assert report.total_failures == 0
        assert report.success_rate == 1.0
        assert report.elapsed_seconds >= 0
