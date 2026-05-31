"""Tests for extraction CLI commands.

Following TDD principles - tests written before implementation.
Tests cover:
- CLI command invocation
- Option parsing
- Batch processing
- Error handling
- Progress reporting
- Mock service layer
"""

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

from swirrl.core.reporting import OperationReport  # noqa: E402


class TestExtractCLI:
    """Test extraction CLI commands."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_service(self):
        """Create mock extraction service."""
        service = Mock()
        service.extract_subtitles.return_value = (
            OperationReport(tool="extract", processed=1, modified=1),
            [],
        )
        service.extract_audio.return_value = (
            OperationReport(tool="extract", processed=1, modified=1),
            [],
        )
        service.extract_video.return_value = (
            OperationReport(tool="extract", processed=1, modified=1),
            [],
        )
        return service

    def test_extract_command_group_exists(self, runner):
        """Test that extract command group exists."""
        from swirrl.commands.extract import extract_command

        result = runner.invoke(extract_command, ["--help"])
        assert result.exit_code == 0
        assert "extract" in result.output.lower()

    def test_extract_subtitle_command_exists(self, runner):
        """Test that subtitle subcommand exists."""
        from swirrl.commands.extract import extract_command

        result = runner.invoke(extract_command, ["subtitle", "--help"])
        assert result.exit_code == 0
        assert "subtitle" in result.output.lower()

    def test_extract_audio_command_exists(self, runner):
        """Test that audio subcommand exists."""
        from swirrl.commands.extract import extract_command

        result = runner.invoke(extract_command, ["audio", "--help"])
        assert result.exit_code == 0
        assert "audio" in result.output.lower()

    def test_extract_video_command_exists(self, runner):
        """Test that video subcommand exists."""
        from swirrl.commands.extract import extract_command

        result = runner.invoke(extract_command, ["video", "--help"])
        assert result.exit_code == 0
        assert "video" in result.output.lower()

    def test_extract_video_short_help_flag(self, runner):
        """`-h` must resolve to help, not to `--height`."""
        from swirrl.commands.extract import extract_command

        result = runner.invoke(extract_command, ["video", "-h"])
        assert result.exit_code == 0
        assert "--height" in result.output

    def test_extract_subtitle_single_file(self, runner, mock_service, tmp_path):
        """Test extracting subtitle from single file."""
        from swirrl.commands.extract import extract_subtitle_command

        # Create test file
        test_file = tmp_path / "test.mkv"
        test_file.touch()

        with patch("swirrl.commands.extract.ExtractionService", return_value=mock_service):
            result = runner.invoke(
                extract_subtitle_command,
                [str(test_file), "--format", "srt"],
            )

            assert result.exit_code == 0
            mock_service.extract_subtitles.assert_called_once()

    def test_extract_subtitle_with_language_filter(self, runner, mock_service, tmp_path):
        """Test extracting subtitle with language filter."""
        from swirrl.commands.extract import extract_subtitle_command

        test_file = tmp_path / "test.mkv"
        test_file.touch()

        with patch("swirrl.commands.extract.ExtractionService", return_value=mock_service):
            result = runner.invoke(
                extract_subtitle_command,
                [str(test_file), "--language", "eng", "--format", "srt"],
            )

            assert result.exit_code == 0
            # Verify language filter was passed
            call_args = mock_service.extract_subtitles.call_args
            options = call_args.kwargs["options"]
            assert "eng" in options.languages

    def test_extract_subtitle_batch(self, runner, mock_service, tmp_path):
        """Test batch subtitle extraction."""
        from swirrl.commands.extract import extract_subtitle_command

        # Create multiple test files
        test_files = [tmp_path / f"test{i}.mkv" for i in range(3)]
        for f in test_files:
            f.touch()

        with patch("swirrl.commands.extract.ExtractionService", return_value=mock_service):
            result = runner.invoke(
                extract_subtitle_command,
                [str(f) for f in test_files] + ["--format", "srt"],
            )

            assert result.exit_code == 0
            # Should process all files
            call_args = mock_service.extract_subtitles.call_args
            files = call_args.kwargs["files"]
            assert len(files) == 3

    def test_extract_audio_single_file(self, runner, mock_service, tmp_path):
        """Test extracting audio from single file."""
        from swirrl.commands.extract import extract_audio_command

        test_file = tmp_path / "test.mkv"
        test_file.touch()

        with patch("swirrl.commands.extract.ExtractionService", return_value=mock_service):
            result = runner.invoke(
                extract_audio_command,
                [str(test_file), "--format", "aac"],
            )

            assert result.exit_code == 0
            mock_service.extract_audio.assert_called_once()

    def test_extract_audio_with_bitrate(self, runner, mock_service, tmp_path):
        """Test extracting audio with bitrate option."""
        from swirrl.commands.extract import extract_audio_command

        test_file = tmp_path / "test.mkv"
        test_file.touch()

        with patch("swirrl.commands.extract.ExtractionService", return_value=mock_service):
            result = runner.invoke(
                extract_audio_command,
                [str(test_file), "--format", "mp3", "--bitrate", "320k"],
            )

            assert result.exit_code == 0
            call_args = mock_service.extract_audio.call_args
            options = call_args.kwargs["options"]
            assert options.bitrate == "320k"

    def test_extract_audio_with_normalization(self, runner, mock_service, tmp_path):
        """Test extracting audio with normalization."""
        from swirrl.commands.extract import extract_audio_command

        test_file = tmp_path / "test.mkv"
        test_file.touch()

        with patch("swirrl.commands.extract.ExtractionService", return_value=mock_service):
            result = runner.invoke(
                extract_audio_command,
                [str(test_file), "--normalize"],
            )

            assert result.exit_code == 0
            call_args = mock_service.extract_audio.call_args
            options = call_args.kwargs["options"]
            assert options.normalize is True

    def test_extract_video_single_file(self, runner, mock_service, tmp_path):
        """Test extracting video from single file."""
        from swirrl.commands.extract import extract_video_command

        test_file = tmp_path / "test.mkv"
        test_file.touch()

        with patch("swirrl.commands.extract.ExtractionService", return_value=mock_service):
            result = runner.invoke(
                extract_video_command,
                [str(test_file), "--codec", "h264"],
            )

            assert result.exit_code == 0
            mock_service.extract_video.assert_called_once()

    def test_extract_video_with_crf(self, runner, mock_service, tmp_path):
        """Test extracting video with CRF quality setting."""
        from swirrl.commands.extract import extract_video_command

        test_file = tmp_path / "test.mkv"
        test_file.touch()

        with patch("swirrl.commands.extract.ExtractionService", return_value=mock_service):
            result = runner.invoke(
                extract_video_command,
                [str(test_file), "--codec", "h265", "--crf", "28"],
            )

            assert result.exit_code == 0
            call_args = mock_service.extract_video.call_args
            options = call_args.kwargs["options"]
            assert options.crf == 28

    def test_extract_video_with_resolution(self, runner, mock_service, tmp_path):
        """Test extracting video with resolution change."""
        from swirrl.commands.extract import extract_video_command

        test_file = tmp_path / "test.mkv"
        test_file.touch()

        with patch("swirrl.commands.extract.ExtractionService", return_value=mock_service):
            result = runner.invoke(
                extract_video_command,
                [str(test_file), "--width", "1920", "--height", "1080"],
            )

            assert result.exit_code == 0
            call_args = mock_service.extract_video.call_args
            options = call_args.kwargs["options"]
            assert options.width == 1920
            assert options.height == 1080

    def test_extract_with_output_directory(self, runner, mock_service, tmp_path):
        """Test extraction with custom output directory."""
        from swirrl.commands.extract import extract_subtitle_command

        test_file = tmp_path / "test.mkv"
        test_file.touch()

        output_dir = tmp_path / "extracted"

        with patch("swirrl.commands.extract.ExtractionService", return_value=mock_service):
            result = runner.invoke(
                extract_subtitle_command,
                [str(test_file), "--output", str(output_dir), "--format", "srt"],
            )

            assert result.exit_code == 0
            call_args = mock_service.extract_subtitles.call_args
            options = call_args.kwargs["options"]
            assert options.output_dir == output_dir

    def test_extract_nonexistent_file(self, runner, mock_service):
        """Test handling of nonexistent file."""
        from swirrl.commands.extract import extract_subtitle_command

        with patch("swirrl.commands.extract.ExtractionService", return_value=mock_service):
            result = runner.invoke(
                extract_subtitle_command,
                ["/nonexistent/file.mkv", "--format", "srt"],
            )

            # Should handle gracefully (either error or pass to service)
            assert result.exit_code in [0, 1, 2]

    def test_extract_all_flag(self, runner, mock_service, tmp_path):
        """Test --all flag to extract all tracks."""
        from swirrl.commands.extract import extract_subtitle_command

        test_file = tmp_path / "test.mkv"
        test_file.touch()

        with patch("swirrl.commands.extract.ExtractionService", return_value=mock_service):
            result = runner.invoke(
                extract_subtitle_command,
                [str(test_file), "--all"],
            )

            assert result.exit_code == 0
            call_args = mock_service.extract_subtitles.call_args
            options = call_args.kwargs["options"]
            assert options.extract_all is True

    def test_format_choices_validation(self, runner):
        """Test that format choices are validated."""
        from swirrl.commands.extract import extract_subtitle_command

        result = runner.invoke(
            extract_subtitle_command,
            ["test.mkv", "--format", "invalid_format"],
        )

        # Should fail with invalid format
        assert result.exit_code != 0
        assert "invalid" in result.output.lower() or "choice" in result.output.lower()
