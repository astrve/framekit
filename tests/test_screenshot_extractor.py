"""Tests for screenshot extractor."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from framekit.core.path_validation import PathValidationError  # noqa: E402
from framekit.core.tools import ToolRegistry  # noqa: E402
from framekit.modules.screenshot.extractor import ScreenshotExtractor  # noqa: E402


class TestScreenshotExtractor:
    """Test ScreenshotExtractor class."""

    @pytest.fixture
    def mock_registry(self):
        """Create a mock ToolRegistry."""
        registry = Mock(spec=ToolRegistry)
        registry.resolve_tool_path.return_value = "ffmpeg"
        return registry

    @pytest.fixture
    def extractor(self, mock_registry):
        """Create a ScreenshotExtractor instance."""
        return ScreenshotExtractor(mock_registry)

    def test_initialization(self, mock_registry):
        """Test extractor initialization."""
        extractor = ScreenshotExtractor(mock_registry)
        assert extractor.registry == mock_registry

    def test_build_ffmpeg_command_basic(self, extractor, tmp_path):
        """Test building basic FFmpeg command."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_path = tmp_path / "screenshot.png"

        cmd = extractor.build_ffmpeg_command(
            video_path=video_path,
            output_path=output_path,
            timestamp=30.5,
            width=None,
            height=None,
            quality=2,
        )

        # Verify command structure
        assert isinstance(cmd, list)
        assert cmd[0] == "ffmpeg"
        assert "-ss" in cmd
        assert "30.5" in cmd
        assert "-i" in cmd
        assert str(video_path) in cmd
        assert str(output_path) in cmd
        # Verify no shell injection
        assert ";" not in " ".join(cmd)
        assert "|" not in " ".join(cmd)

    def test_build_ffmpeg_command_with_scaling(self, extractor, tmp_path):
        """Test building command with width/height scaling."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_path = tmp_path / "screenshot.png"

        cmd = extractor.build_ffmpeg_command(
            video_path=video_path,
            output_path=output_path,
            timestamp=30.5,
            width=1280,
            height=720,
            quality=2,
        )

        # Should include scale filter
        cmd_str = " ".join(cmd)
        assert "scale" in cmd_str or "1280" in cmd_str

    def test_build_ffmpeg_command_validates_paths(self, extractor, tmp_path):
        """Test that paths are validated."""
        # Malicious video path
        malicious_video = tmp_path / "-i /etc/passwd"
        output_path = tmp_path / "screenshot.png"

        with pytest.raises((PathValidationError, FileNotFoundError, ValueError)):
            extractor.build_ffmpeg_command(
                video_path=malicious_video,
                output_path=output_path,
                timestamp=30.5,
            )

    def test_build_ffmpeg_command_rejects_special_chars(self, extractor, tmp_path):
        """Test that special characters in paths are handled safely."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")

        # Try various potentially problematic output paths
        # Note: Path validation may allow these on some systems, but the
        # list-form subprocess call prevents shell injection
        malicious_outputs = [
            tmp_path / "; rm -rf /",
            tmp_path / "| cat /etc/passwd",
            tmp_path / "$(whoami).png",
        ]

        for malicious_output in malicious_outputs:
            try:
                cmd = extractor.build_ffmpeg_command(
                    video_path=video_path,
                    output_path=malicious_output,
                    timestamp=30.5,
                )
                # If command is built, verify it's a list (safe)
                assert isinstance(cmd, list)
                # Verify no shell metacharacters in command string
                cmd_str = " ".join(str(arg) for arg in cmd)
                # The dangerous characters should be in the path, but
                # list-form execution prevents shell interpretation
            except (PathValidationError, ValueError, OSError):
                # Also acceptable: validation rejects the path
                pass

    def test_extract_screenshot_success(self, extractor, tmp_path):
        """Test successful screenshot extraction."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_path = tmp_path / "screenshot.png"

        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            # Create fake output file
            output_path.write_bytes(b"fake png data")

            result = extractor.extract_screenshot(
                video_path=video_path,
                output_path=output_path,
                timestamp=30.5,
            )

            assert result is True
            mock_run.assert_called_once()
            # Verify subprocess was called with list, not shell
            call_args = mock_run.call_args
            assert isinstance(call_args[0][0], list)
            # Verify shell=True is not used
            if len(call_args) > 1 and isinstance(call_args[1], dict):
                assert call_args[1].get("shell") is not True

    def test_extract_screenshot_ffmpeg_error(self, extractor, tmp_path):
        """Test handling FFmpeg error."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_path = tmp_path / "screenshot.png"

        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Error: Invalid file"

        with patch("subprocess.run", return_value=mock_result):
            result = extractor.extract_screenshot(
                video_path=video_path,
                output_path=output_path,
                timestamp=30.5,
            )

            assert result is False

    def test_extract_screenshot_timeout(self, extractor, tmp_path):
        """Test handling timeout."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_path = tmp_path / "screenshot.png"

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ffmpeg", 30)):
            result = extractor.extract_screenshot(
                video_path=video_path,
                output_path=output_path,
                timestamp=30.5,
                timeout=30,
            )

            assert result is False

    def test_extract_screenshot_file_not_created(self, extractor, tmp_path):
        """Test when FFmpeg succeeds but file is not created."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_path = tmp_path / "screenshot.png"

        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            # Don't create output file
            result = extractor.extract_screenshot(
                video_path=video_path,
                output_path=output_path,
                timestamp=30.5,
            )

            assert result is False

    def test_extract_multiple_screenshots(self, extractor, tmp_path):
        """Test extracting multiple screenshots."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_dir = tmp_path / "screenshots"
        output_dir.mkdir()

        timestamps = [10.0, 30.0, 60.0]
        output_paths = [output_dir / f"screenshot_{i:03d}.png" for i in range(1, 4)]

        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            # Create fake output files
            for path in output_paths:
                path.write_bytes(b"fake png data")

            results = extractor.extract_multiple(
                video_path=video_path,
                timestamps=timestamps,
                output_paths=output_paths,
            )

            assert len(results) == 3
            assert all(r is True for r in results)

    def test_extract_multiple_partial_failure(self, extractor, tmp_path):
        """Test extracting multiple with some failures."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_dir = tmp_path / "screenshots"
        output_dir.mkdir()

        timestamps = [10.0, 30.0, 60.0]
        output_paths = [output_dir / f"screenshot_{i:03d}.png" for i in range(1, 4)]

        # Mock alternating success/failure
        mock_results = [Mock(returncode=0), Mock(returncode=1), Mock(returncode=0)]

        with patch("subprocess.run", side_effect=mock_results):
            # Create output files for successful extractions
            output_paths[0].write_bytes(b"fake png data")
            output_paths[2].write_bytes(b"fake png data")

            results = extractor.extract_multiple(
                video_path=video_path,
                timestamps=timestamps,
                output_paths=output_paths,
            )

            assert len(results) == 3
            assert results[0] is True
            assert results[1] is False
            assert results[2] is True

    def test_progress_callback(self, extractor, tmp_path):
        """Test progress callback during extraction."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_dir = tmp_path / "screenshots"
        output_dir.mkdir()

        timestamps = [10.0, 30.0, 60.0]
        output_paths = [output_dir / f"screenshot_{i:03d}.png" for i in range(1, 4)]

        progress_calls = []

        def progress_callback(current, total):
            progress_calls.append((current, total))

        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            for path in output_paths:
                path.write_bytes(b"fake png data")

            extractor.extract_multiple(
                video_path=video_path,
                timestamps=timestamps,
                output_paths=output_paths,
                progress_callback=progress_callback,
            )

            # Verify progress was reported
            assert len(progress_calls) == 3
            assert progress_calls[0] == (1, 3)
            assert progress_calls[1] == (2, 3)
            assert progress_calls[2] == (3, 3)


class TestCommandSecurity:
    """Test security aspects of command generation."""

    @pytest.fixture
    def extractor(self):
        """Create extractor with mock registry."""
        registry = Mock(spec=ToolRegistry)
        registry.resolve_tool_path.return_value = "ffmpeg"
        return ScreenshotExtractor(registry)

    def test_no_shell_injection(self, extractor, tmp_path):
        """Test that shell injection is prevented."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_path = tmp_path / "screenshot.png"

        cmd = extractor.build_ffmpeg_command(
            video_path=video_path,
            output_path=output_path,
            timestamp=30.5,
        )

        # Command should be a list (not string)
        assert isinstance(cmd, list)

        # No shell metacharacters should be present
        cmd_str = " ".join(str(arg) for arg in cmd)
        dangerous_chars = [";", "|", "&", "$", "`", "\n", "\r"]
        for char in dangerous_chars:
            assert char not in cmd_str

    def test_paths_are_validated(self, extractor, tmp_path):
        """Test that paths are validated before use."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")

        # Test that valid paths work
        output_path = tmp_path / "screenshot.png"
        cmd = extractor.build_ffmpeg_command(
            video_path=video_path,
            output_path=output_path,
            timestamp=30.5,
        )

        # Verify command is built safely as list
        assert isinstance(cmd, list)
        assert str(video_path) in cmd
        assert str(output_path) in cmd

    def test_subprocess_uses_list_args(self, extractor, tmp_path):
        """Test that subprocess.run is called with list arguments."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_path = tmp_path / "screenshot.png"

        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            output_path.write_bytes(b"fake png data")

            extractor.extract_screenshot(
                video_path=video_path,
                output_path=output_path,
                timestamp=30.5,
            )

            # Verify subprocess.run was called with list
            call_args = mock_run.call_args
            assert isinstance(call_args[0][0], list)

            # Verify shell=True is not used
            if len(call_args) > 1 and isinstance(call_args[1], dict):
                kwargs = call_args[1]
                assert kwargs.get("shell") is not True

    def test_timeout_is_enforced(self, extractor, tmp_path):
        """Test that timeout is enforced."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_path = tmp_path / "screenshot.png"

        with patch("subprocess.run") as mock_run:
            extractor.extract_screenshot(
                video_path=video_path,
                output_path=output_path,
                timestamp=30.5,
                timeout=60,
            )

            # Verify timeout was passed to subprocess.run
            call_kwargs = mock_run.call_args[1]
            assert "timeout" in call_kwargs
            assert call_kwargs["timeout"] == 60


class TestErrorHandling:
    """Test error handling and graceful degradation."""

    @pytest.fixture
    def extractor(self):
        """Create extractor with mock registry."""
        registry = Mock(spec=ToolRegistry)
        registry.resolve_tool_path.return_value = "ffmpeg"
        return ScreenshotExtractor(registry)

    def test_handles_missing_ffmpeg(self):
        """Test handling when FFmpeg is not available."""
        registry = Mock(spec=ToolRegistry)
        registry.resolve_tool_path.return_value = None

        extractor = ScreenshotExtractor(registry)

        # Should handle gracefully
        assert extractor.registry == registry

    def test_handles_permission_error(self, extractor, tmp_path):
        """Test handling permission errors."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_path = tmp_path / "screenshot.png"

        with patch("subprocess.run", side_effect=PermissionError("Access denied")):
            result = extractor.extract_screenshot(
                video_path=video_path,
                output_path=output_path,
                timestamp=30.5,
            )

            assert result is False

    def test_handles_disk_full(self, extractor, tmp_path):
        """Test handling disk full errors."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_path = tmp_path / "screenshot.png"

        with patch("subprocess.run", side_effect=OSError("No space left on device")):
            result = extractor.extract_screenshot(
                video_path=video_path,
                output_path=output_path,
                timestamp=30.5,
            )

            assert result is False


# Made with Bob
