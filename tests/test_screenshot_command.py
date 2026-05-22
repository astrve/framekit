"""Tests for screenshot CLI command."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from framekit.commands.screenshot import screenshot_command  # noqa: E402
from framekit.core.models.screenshot import (  # noqa: E402
    ScreenshotReport,
    ScreenshotResult,
)


class TestScreenshotCommand:
    """Test screenshot CLI command."""

    @pytest.fixture
    def runner(self):
        """Create a Click test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_service(self):
        """Create a mock ScreenshotService."""
        with patch("framekit.commands.screenshot.ScreenshotService") as mock_cls:
            service = Mock()
            mock_cls.return_value = service

            # Default successful report
            result = ScreenshotResult(
                video_path=Path("video.mkv"),
                output_dir=Path("output"),
                screenshots=[Path("output/screenshot_001.png")],
                success=True,
            )
            report = ScreenshotReport(
                results=[result],
                total_videos=1,
                total_screenshots=1,
                total_failures=0,
                elapsed_seconds=1.5,
            )
            service.extract_screenshots.return_value = report
            service.extract_from_timestamps.return_value = result

            yield service

    def test_command_registration(self):
        """Test that command is properly registered."""
        assert screenshot_command.name == "screenshot"
        assert screenshot_command.callback is not None

    def test_basic_invocation(self, runner, mock_service, tmp_path):
        """Test basic command invocation with single video."""
        video = tmp_path / "video.mkv"
        video.write_text("fake video")

        result = runner.invoke(screenshot_command, [str(video)])

        assert result.exit_code == 0
        mock_service.extract_screenshots.assert_called_once()

    def test_count_option(self, runner, mock_service, tmp_path):
        """Test --count option."""
        video = tmp_path / "video.mkv"
        video.write_text("fake video")

        result = runner.invoke(screenshot_command, [str(video), "--count", "10"])

        assert result.exit_code == 0
        # Verify config has correct count
        call_args = mock_service.extract_screenshots.call_args
        config = call_args.kwargs["config"]
        assert config.count == 10

    def test_width_option(self, runner, mock_service, tmp_path):
        """Test --width option."""
        video = tmp_path / "video.mkv"
        video.write_text("fake video")

        result = runner.invoke(screenshot_command, [str(video), "--width", "1280"])

        assert result.exit_code == 0
        call_args = mock_service.extract_screenshots.call_args
        config = call_args.kwargs["config"]
        assert config.width == 1280

    def test_quality_option(self, runner, mock_service, tmp_path):
        """Test --quality option."""
        video = tmp_path / "video.mkv"
        video.write_text("fake video")

        result = runner.invoke(screenshot_command, [str(video), "--quality", "5"])

        assert result.exit_code == 0
        call_args = mock_service.extract_screenshots.call_args
        config = call_args.kwargs["config"]
        assert config.quality == 5

    def test_format_option(self, runner, mock_service, tmp_path):
        """Test --format option."""
        video = tmp_path / "video.mkv"
        video.write_text("fake video")

        result = runner.invoke(screenshot_command, [str(video), "--format", "jpg"])

        assert result.exit_code == 0
        call_args = mock_service.extract_screenshots.call_args
        config = call_args.kwargs["config"]
        assert config.format == "jpg"

    def test_output_option(self, runner, mock_service, tmp_path):
        """Test --output option."""
        video = tmp_path / "video.mkv"
        video.write_text("fake video")
        output_dir = tmp_path / "screenshots"

        result = runner.invoke(screenshot_command, [str(video), "--output", str(output_dir)])

        assert result.exit_code == 0
        call_args = mock_service.extract_screenshots.call_args
        assert call_args.kwargs["output_dir"] == output_dir

    def test_release_name_option(self, runner, mock_service, tmp_path):
        """Test --release-name option."""
        video = tmp_path / "video.mkv"
        video.write_text("fake video")

        result = runner.invoke(screenshot_command, [str(video), "--release-name", "My.Release"])

        assert result.exit_code == 0
        call_args = mock_service.extract_screenshots.call_args
        assert call_args.kwargs["release_name"] == "My.Release"

    def test_skip_intro_option(self, runner, mock_service, tmp_path):
        """Test --skip-intro option."""
        video = tmp_path / "video.mkv"
        video.write_text("fake video")

        result = runner.invoke(screenshot_command, [str(video), "--skip-intro", "120"])

        assert result.exit_code == 0
        call_args = mock_service.extract_screenshots.call_args
        config = call_args.kwargs["config"]
        assert config.skip_start_seconds == 120

    def test_skip_outro_option(self, runner, mock_service, tmp_path):
        """Test --skip-outro option."""
        video = tmp_path / "video.mkv"
        video.write_text("fake video")

        result = runner.invoke(screenshot_command, [str(video), "--skip-outro", "180"])

        assert result.exit_code == 0
        call_args = mock_service.extract_screenshots.call_args
        config = call_args.kwargs["config"]
        assert config.skip_end_seconds == 180

    def test_no_black_detection_flag(self, runner, mock_service, tmp_path):
        """Test --no-black-detection flag."""
        video = tmp_path / "video.mkv"
        video.write_text("fake video")

        result = runner.invoke(screenshot_command, [str(video), "--no-black-detection"])

        assert result.exit_code == 0
        call_args = mock_service.extract_screenshots.call_args
        config = call_args.kwargs["config"]
        assert config.avoid_black_frames is False

    def test_timestamps_option(self, runner, mock_service, tmp_path):
        """Test --timestamps option for manual timestamp mode."""
        video = tmp_path / "video.mkv"
        video.write_text("fake video")

        result = runner.invoke(screenshot_command, [str(video), "--timestamps", "120,240,360"])

        assert result.exit_code == 0
        # Should call extract_from_timestamps instead
        mock_service.extract_from_timestamps.assert_called_once()
        call_args = mock_service.extract_from_timestamps.call_args
        assert call_args.kwargs["timestamps"] == [120.0, 240.0, 360.0]

    def test_multiple_videos(self, runner, mock_service, tmp_path):
        """Test processing multiple videos."""
        video1 = tmp_path / "video1.mkv"
        video2 = tmp_path / "video2.mkv"
        video1.write_text("fake video 1")
        video2.write_text("fake video 2")

        # Update mock to return report for 2 videos
        result1 = ScreenshotResult(
            video_path=video1,
            output_dir=Path("output"),
            screenshots=[Path("output/screenshot_001.png")],
            success=True,
        )
        result2 = ScreenshotResult(
            video_path=video2,
            output_dir=Path("output"),
            screenshots=[Path("output/screenshot_001.png")],
            success=True,
        )
        report = ScreenshotReport(
            results=[result1, result2],
            total_videos=2,
            total_screenshots=2,
            total_failures=0,
            elapsed_seconds=3.0,
        )
        mock_service.extract_screenshots.return_value = report

        result = runner.invoke(screenshot_command, [str(video1), str(video2)])

        assert result.exit_code == 0
        call_args = mock_service.extract_screenshots.call_args
        assert len(call_args.kwargs["video_paths"]) == 2

    def test_missing_video_file(self, runner, mock_service, tmp_path):
        """Test error handling for missing video file."""
        video = tmp_path / "nonexistent.mkv"

        result = runner.invoke(screenshot_command, [str(video)])

        # Click should catch the missing file
        assert result.exit_code != 0

    def test_output_directory_creation(self, runner, mock_service, tmp_path):
        """Test that output directory is created if it doesn't exist."""
        video = tmp_path / "video.mkv"
        video.write_text("fake video")
        output_dir = tmp_path / "screenshots" / "nested"

        result = runner.invoke(screenshot_command, [str(video), "--output", str(output_dir)])

        assert result.exit_code == 0
        # Service should be called with the output dir
        call_args = mock_service.extract_screenshots.call_args
        assert call_args.kwargs["output_dir"] == output_dir

    def test_default_output_directory(self, runner, mock_service, tmp_path):
        """Test default output directory behavior."""
        video = tmp_path / "video.mkv"
        video.write_text("fake video")

        result = runner.invoke(screenshot_command, [str(video)])

        assert result.exit_code == 0
        # Should use video's parent directory by default
        call_args = mock_service.extract_screenshots.call_args
        output_dir = call_args.kwargs["output_dir"]
        assert output_dir == video.parent

    def test_error_reporting(self, runner, mock_service, tmp_path):
        """Test error reporting when extraction fails."""
        video = tmp_path / "video.mkv"
        video.write_text("fake video")

        # Mock service to return failure
        result_obj = ScreenshotResult(
            video_path=video,
            output_dir=Path("output"),
            success=False,
            error="FFmpeg not found",
        )
        report = ScreenshotReport(
            results=[result_obj],
            total_videos=1,
            total_screenshots=0,
            total_failures=1,
            elapsed_seconds=0.5,
        )
        mock_service.extract_screenshots.return_value = report

        result = runner.invoke(screenshot_command, [str(video)])

        # Should complete but show error
        assert result.exit_code == 0  # Command runs, but reports failure
        assert "error" in result.output.lower() or "fail" in result.output.lower()

    def test_progress_display(self, runner, mock_service, tmp_path):
        """Test that progress is displayed during extraction."""
        video = tmp_path / "video.mkv"
        video.write_text("fake video")

        result = runner.invoke(screenshot_command, [str(video)])

        assert result.exit_code == 0
        # Progress callback should be provided to service
        call_args = mock_service.extract_screenshots.call_args
        assert "progress_callback" in call_args.kwargs
        assert call_args.kwargs["progress_callback"] is not None

    def test_invalid_timestamp_format(self, runner, mock_service, tmp_path):
        """Test error handling for invalid timestamp format."""
        video = tmp_path / "video.mkv"
        video.write_text("fake video")

        result = runner.invoke(screenshot_command, [str(video), "--timestamps", "invalid,format"])

        # Should handle parsing error gracefully
        assert result.exit_code != 0

    def test_combined_options(self, runner, mock_service, tmp_path):
        """Test combining multiple options."""
        video = tmp_path / "video.mkv"
        video.write_text("fake video")
        output_dir = tmp_path / "screenshots"

        result = runner.invoke(
            screenshot_command,
            [
                str(video),
                "--count",
                "8",
                "--width",
                "1920",
                "--quality",
                "3",
                "--format",
                "jpg",
                "--output",
                str(output_dir),
                "--release-name",
                "Test.Release",
                "--skip-intro",
                "90",
                "--skip-outro",
                "150",
            ],
        )

        assert result.exit_code == 0
        call_args = mock_service.extract_screenshots.call_args
        config = call_args.kwargs["config"]

        assert config.count == 8
        assert config.width == 1920
        assert config.quality == 3
        assert config.format == "jpg"
        assert config.skip_start_seconds == 90
        assert config.skip_end_seconds == 150
        assert call_args.kwargs["output_dir"] == output_dir
        assert call_args.kwargs["release_name"] == "Test.Release"

    def test_help_text(self, runner):
        """Test that help text is displayed."""
        result = runner.invoke(screenshot_command, ["--help"])

        assert result.exit_code == 0
        assert "screenshot" in result.output.lower()
        assert "--count" in result.output
        assert "--width" in result.output
        assert "--quality" in result.output

    def test_glob_pattern_support(self, runner, mock_service, tmp_path):
        """Test that glob patterns work for multiple videos."""
        # Create multiple video files
        for i in range(3):
            video = tmp_path / f"video{i}.mkv"
            video.write_text(f"fake video {i}")

        # Update mock for multiple videos
        results = [
            ScreenshotResult(
                video_path=tmp_path / f"video{i}.mkv",
                output_dir=Path("output"),
                screenshots=[Path(f"output/screenshot_{i}_001.png")],
                success=True,
            )
            for i in range(3)
        ]
        report = ScreenshotReport(
            results=results,
            total_videos=3,
            total_screenshots=3,
            total_failures=0,
            elapsed_seconds=4.5,
        )
        mock_service.extract_screenshots.return_value = report

        # Note: Click doesn't expand globs automatically, shell does
        # So we test with explicit file list
        videos = [str(tmp_path / f"video{i}.mkv") for i in range(3)]
        result = runner.invoke(screenshot_command, videos)

        assert result.exit_code == 0
        call_args = mock_service.extract_screenshots.call_args
        assert len(call_args.kwargs["video_paths"]) == 3


class TestScreenshotDirectorySupport:
    """Test directory input support for screenshot command."""

    @pytest.fixture
    def runner(self):
        """Create a Click test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_service(self):
        """Create a mock ScreenshotService."""
        with patch("framekit.commands.screenshot.ScreenshotService") as mock_cls:
            service = Mock()
            mock_cls.return_value = service

            # Default successful report
            result = ScreenshotResult(
                video_path=Path("video.mkv"),
                output_dir=Path("output"),
                screenshots=[Path("output/screenshot_001.png")],
                success=True,
            )
            report = ScreenshotReport(
                results=[result],
                total_videos=1,
                total_screenshots=1,
                total_failures=0,
                elapsed_seconds=1.5,
            )
            service.extract_screenshots.return_value = report

            yield service

    def test_directory_with_single_mkv_auto_processes(self, runner, mock_service, tmp_path):
        """Test that directory with single MKV file auto-processes without interaction."""
        # Create directory with single MKV
        video_dir = tmp_path / "videos"
        video_dir.mkdir()
        video = video_dir / "movie.mkv"
        video.write_text("fake video")

        result = runner.invoke(screenshot_command, [str(video_dir)])

        assert result.exit_code == 0
        # Should process the single file automatically
        mock_service.extract_screenshots.assert_called_once()
        call_args = mock_service.extract_screenshots.call_args
        video_paths = call_args.kwargs["video_paths"]
        assert len(video_paths) == 1
        assert video_paths[0].name == "movie.mkv"

    def test_directory_with_multiple_mkvs_shows_selector(self, runner, mock_service, tmp_path):
        """Test that directory with multiple MKV files shows interactive selector."""
        # Create directory with multiple MKVs
        video_dir = tmp_path / "videos"
        video_dir.mkdir()
        for i in range(3):
            video = video_dir / f"movie{i}.mkv"
            video.write_text(f"fake video {i}")

        # Mock the selector to return selected files
        with patch("framekit.commands.screenshot.select_many") as mock_selector:
            mock_selector.return_value = [
                video_dir / "movie0.mkv",
                video_dir / "movie2.mkv",
            ]

            result = runner.invoke(screenshot_command, [str(video_dir)])

            assert result.exit_code == 0
            # Should show selector
            mock_selector.assert_called_once()
            # Should process selected files
            mock_service.extract_screenshots.assert_called_once()
            call_args = mock_service.extract_screenshots.call_args
            video_paths = call_args.kwargs["video_paths"]
            assert len(video_paths) == 2

    def test_directory_with_all_flag_processes_all_files(self, runner, mock_service, tmp_path):
        """Test --all flag processes all MKV files without interaction."""
        # Create directory with multiple MKVs
        video_dir = tmp_path / "videos"
        video_dir.mkdir()
        for i in range(3):
            video = video_dir / f"movie{i}.mkv"
            video.write_text(f"fake video {i}")

        # Mock multiple results
        results = [
            ScreenshotResult(
                video_path=video_dir / f"movie{i}.mkv",
                output_dir=Path("output"),
                screenshots=[Path(f"output/screenshot_{i}_001.png")],
                success=True,
            )
            for i in range(3)
        ]
        report = ScreenshotReport(
            results=results,
            total_videos=3,
            total_screenshots=3,
            total_failures=0,
            elapsed_seconds=4.5,
        )
        mock_service.extract_screenshots.return_value = report

        result = runner.invoke(screenshot_command, [str(video_dir), "--all"])

        assert result.exit_code == 0
        # Should process all files without selector
        mock_service.extract_screenshots.assert_called_once()
        call_args = mock_service.extract_screenshots.call_args
        video_paths = call_args.kwargs["video_paths"]
        assert len(video_paths) == 3

    def test_directory_with_recursive_flag_scans_subdirectories(
        self, runner, mock_service, tmp_path
    ):
        """Test --recursive flag scans subdirectories for MKV files."""
        # Create nested directory structure
        video_dir = tmp_path / "videos"
        video_dir.mkdir()
        (video_dir / "movie1.mkv").write_text("fake video 1")

        subdir = video_dir / "season1"
        subdir.mkdir()
        (subdir / "episode1.mkv").write_text("fake video 2")
        (subdir / "episode2.mkv").write_text("fake video 3")

        # Mock multiple results
        results = [
            ScreenshotResult(
                video_path=Path("movie.mkv"),
                output_dir=Path("output"),
                screenshots=[Path("output/screenshot_001.png")],
                success=True,
            )
            for _ in range(3)
        ]
        report = ScreenshotReport(
            results=results,
            total_videos=3,
            total_screenshots=3,
            total_failures=0,
            elapsed_seconds=4.5,
        )
        mock_service.extract_screenshots.return_value = report

        result = runner.invoke(screenshot_command, [str(video_dir), "--recursive", "--all"])

        assert result.exit_code == 0
        # Should find all 3 MKV files recursively
        mock_service.extract_screenshots.assert_called_once()
        call_args = mock_service.extract_screenshots.call_args
        video_paths = call_args.kwargs["video_paths"]
        assert len(video_paths) == 3

    def test_directory_with_no_mkv_files_shows_error(self, runner, mock_service, tmp_path):
        """Test error handling when directory has no MKV files."""
        # Create empty directory
        video_dir = tmp_path / "videos"
        video_dir.mkdir()
        (video_dir / "readme.txt").write_text("not a video")

        result = runner.invoke(screenshot_command, [str(video_dir)])

        # Should show error about no MKV files
        assert result.exit_code != 0
        assert "no" in result.output.lower() and "mkv" in result.output.lower()

    def test_directory_filters_only_mkv_files(self, runner, mock_service, tmp_path):
        """Test that only MKV files are processed from directory."""
        # Create directory with mixed file types
        video_dir = tmp_path / "videos"
        video_dir.mkdir()
        (video_dir / "movie.mkv").write_text("fake video")
        (video_dir / "movie.mp4").write_text("fake video")
        (video_dir / "movie.avi").write_text("fake video")
        (video_dir / "readme.txt").write_text("not a video")

        result = runner.invoke(screenshot_command, [str(video_dir)])

        assert result.exit_code == 0
        # Should only process the MKV file
        mock_service.extract_screenshots.assert_called_once()
        call_args = mock_service.extract_screenshots.call_args
        video_paths = call_args.kwargs["video_paths"]
        assert len(video_paths) == 1
        assert video_paths[0].suffix == ".mkv"

    def test_mixed_files_and_directories(self, runner, mock_service, tmp_path):
        """Test processing mix of file paths and directory paths."""
        # Create a file and a directory
        video_file = tmp_path / "single.mkv"
        video_file.write_text("fake video")

        video_dir = tmp_path / "videos"
        video_dir.mkdir()
        (video_dir / "movie1.mkv").write_text("fake video 1")
        (video_dir / "movie2.mkv").write_text("fake video 2")

        # Mock multiple results
        results = [
            ScreenshotResult(
                video_path=Path("movie.mkv"),
                output_dir=Path("output"),
                screenshots=[Path("output/screenshot_001.png")],
                success=True,
            )
            for _ in range(3)
        ]
        report = ScreenshotReport(
            results=results,
            total_videos=3,
            total_screenshots=3,
            total_failures=0,
            elapsed_seconds=4.5,
        )
        mock_service.extract_screenshots.return_value = report

        result = runner.invoke(screenshot_command, [str(video_file), str(video_dir), "--all"])

        assert result.exit_code == 0
        # Should process 1 file + 2 from directory = 3 total
        mock_service.extract_screenshots.assert_called_once()
        call_args = mock_service.extract_screenshots.call_args
        video_paths = call_args.kwargs["video_paths"]
        assert len(video_paths) == 3

    def test_selector_cancellation_aborts_command(self, runner, mock_service, tmp_path):
        """Test that cancelling selector aborts the command."""
        # Create directory with multiple MKVs
        video_dir = tmp_path / "videos"
        video_dir.mkdir()
        for i in range(3):
            video = video_dir / f"movie{i}.mkv"
            video.write_text(f"fake video {i}")

        # Mock selector to raise KeyboardInterrupt (user cancellation)
        with patch("framekit.commands.screenshot.select_many") as mock_selector:
            mock_selector.side_effect = KeyboardInterrupt()

            result = runner.invoke(screenshot_command, [str(video_dir)])

            # Should abort gracefully
            assert result.exit_code != 0
            # Should not call service
            mock_service.extract_screenshots.assert_not_called()

    def test_backward_compatibility_file_paths_still_work(self, runner, mock_service, tmp_path):
        """Test that existing file path behavior is unchanged."""
        # Create individual video files
        video1 = tmp_path / "video1.mkv"
        video2 = tmp_path / "video2.mkv"
        video1.write_text("fake video 1")
        video2.write_text("fake video 2")

        # Mock multiple results
        results = [
            ScreenshotResult(
                video_path=Path("movie.mkv"),
                output_dir=Path("output"),
                screenshots=[Path("output/screenshot_001.png")],
                success=True,
            )
            for _ in range(2)
        ]
        report = ScreenshotReport(
            results=results,
            total_videos=2,
            total_screenshots=2,
            total_failures=0,
            elapsed_seconds=3.0,
        )
        mock_service.extract_screenshots.return_value = report

        result = runner.invoke(screenshot_command, [str(video1), str(video2)])

        assert result.exit_code == 0
        # Should work exactly as before
        mock_service.extract_screenshots.assert_called_once()
        call_args = mock_service.extract_screenshots.call_args
        video_paths = call_args.kwargs["video_paths"]
        assert len(video_paths) == 2


# Made with Bob
