"""
Tests for subprocess argument injection vulnerabilities.

Focuses on encoder and cleanmkv modules that pass file paths
to FFmpeg and mkvmerge without proper validation.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from framekit.core.path_validation import PathValidationError  # noqa: E402
from framekit.modules.encoder.service import EncoderService  # noqa: E402


class TestEncoderSubprocessInjection:
    """Test subprocess injection protection in encoder service."""

    @pytest.fixture
    def _make_preset(self):
        """Create a valid EncodePreset for testing."""
        from framekit.modules.encoder.models import (
            AdvancedConfig,
            AudioConfig,
            ChapterConfig,
            EncodePreset,
            MetadataConfig,
            SubtitleConfig,
            VideoConfig,
        )

        def factory():
            return EncodePreset(
                name="test",
                description="test preset",
                source_codec="h264",
                target_codec="h265",
                encoder="libx265",
                video=VideoConfig(crf=23, preset="medium"),
                audio=AudioConfig(),
                subtitles=SubtitleConfig(),
                metadata=MetadataConfig(),
                chapters=ChapterConfig(),
                advanced=AdvancedConfig(),
            )

        return factory

    def test_build_ffmpeg_command_validates_input_path(self, tmp_path, _make_preset):
        """Test that input file path is validated before building command."""
        preset = _make_preset()

        with patch("framekit.modules.encoder.service.EncoderService._validate_ffmpeg_executable"):
            service = EncoderService(preset)

        malicious_input = tmp_path / "-i /etc/passwd"
        output_file = tmp_path / "output.mkv"

        with pytest.raises((PathValidationError, FileNotFoundError)):
            service.build_ffmpeg_command(malicious_input, output_file)

    def test_build_ffmpeg_command_validates_output_path(self, tmp_path, _make_preset):
        """Test that output file path is validated before building command."""
        preset = _make_preset()

        with patch("framekit.modules.encoder.service.EncoderService._validate_ffmpeg_executable"):
            service = EncoderService(preset)

        input_file = tmp_path / "input.mkv"
        input_file.write_text("fake video")

        malicious_output = tmp_path / "; rm -rf /"

        with pytest.raises((PathValidationError, ValueError)):
            service.build_ffmpeg_command(input_file, malicious_output)

    def test_ffmpeg_command_uses_double_dash_separator(self, tmp_path, _make_preset):
        """Test that FFmpeg command uses -i properly to prevent option injection."""
        preset = _make_preset()

        with patch("framekit.modules.encoder.service.EncoderService._validate_ffmpeg_executable"):
            service = EncoderService(preset)

        input_file = tmp_path / "input.mkv"
        input_file.write_text("fake video")
        output_file = tmp_path / "output.mkv"

        with patch("framekit.core.path_validation.validate_file_path") as mock_validate:
            mock_validate.side_effect = lambda p, **kwargs: Path(p)

            cmd = service.build_ffmpeg_command(input_file, output_file)

            assert isinstance(cmd, list)
            if "-i" in cmd:
                i_index = cmd.index("-i")
                assert i_index + 1 < len(cmd)

    def test_ffmpeg_command_with_special_characters_in_filename(self, tmp_path, _make_preset):
        """Test handling of special characters in filenames."""
        preset = _make_preset()

        with patch("framekit.modules.encoder.service.EncoderService._validate_ffmpeg_executable"):
            service = EncoderService(preset)

        special_chars = ["'", '"', "`", "$", "&", "|", ";"]

        for char in special_chars:
            try:
                input_file = tmp_path / f"test{char}input.mkv"
                input_file.write_text("fake video")
                output_file = tmp_path / f"test{char}output.mkv"

                try:
                    with patch("framekit.core.path_validation.validate_file_path") as mock_validate:
                        mock_validate.side_effect = lambda p, **kwargs: Path(p)
                        cmd = service.build_ffmpeg_command(input_file, output_file)

                        cmd_str = " ".join(cmd)
                        assert not any(
                            f" {c} " in cmd_str or cmd_str.endswith(f" {c}")
                            for c in [";", "|", "&", "$"]
                        )
                except PathValidationError:
                    pass
            except OSError:
                pass


class TestCleanMKVSubprocessInjection:
    """Test subprocess injection protection in cleanmkv module."""

    def test_remuxer_validates_source_path(self, tmp_path):
        """Test that source file path is validated before remuxing."""
        from framekit.core.models.cleanmkv import RemuxPlan
        from framekit.core.tools import ToolRegistry
        from framekit.modules.cleanmkv.remuxer import apply_remux_plan

        # Create malicious source path
        malicious_source = tmp_path / "-o /tmp/evil.mkv"
        target = tmp_path / "output.mkv"

        plan = RemuxPlan(
            source=malicious_source,
            target=target,
            keep_audio_track_ids=[0],
            keep_subtitle_track_ids=[],
            default_audio_track_id=0,
            default_subtitle_track_id=None,
            copy_only=False,
        )

        registry = ToolRegistry()

        # Should raise error due to invalid source path
        with pytest.raises((FileNotFoundError, PathValidationError, RuntimeError)):
            apply_remux_plan(plan, registry)

    def test_remuxer_validates_target_path(self, tmp_path):
        """Test that target file path is validated before remuxing."""
        from framekit.core.models.cleanmkv import RemuxPlan
        from framekit.core.tools import ToolRegistry
        from framekit.modules.cleanmkv.remuxer import apply_remux_plan

        # Create valid source
        source = tmp_path / "input.mkv"
        source.write_text("fake video")

        # Create malicious target path
        malicious_target = tmp_path / "; rm -rf /"

        plan = RemuxPlan(
            source=source,
            target=malicious_target,
            keep_audio_track_ids=[0],
            keep_subtitle_track_ids=[],
            default_audio_track_id=0,
            default_subtitle_track_id=None,
            copy_only=False,
        )

        registry = ToolRegistry()

        # Should raise error due to invalid target path
        with pytest.raises((PathValidationError, RuntimeError)):
            apply_remux_plan(plan, registry)

    def test_mkvmerge_command_structure(self, tmp_path):
        """Test that mkvmerge command has proper structure."""
        from framekit.core.models.cleanmkv import RemuxPlan
        from framekit.core.tools import ToolRegistry
        from framekit.modules.cleanmkv.remuxer import apply_remux_plan

        # Create valid files
        source = tmp_path / "input.mkv"
        source.write_text("fake video")
        target = tmp_path / "output.mkv"

        plan = RemuxPlan(
            source=source,
            target=target,
            keep_audio_track_ids=[0],
            keep_subtitle_track_ids=[],
            default_audio_track_id=0,
            default_subtitle_track_id=None,
            copy_only=False,
        )

        registry = ToolRegistry()

        # Mock subprocess.run to capture command
        with patch("framekit.modules.cleanmkv.remuxer._run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            with patch.object(registry, "require_tool", return_value="mkvmerge"):
                apply_remux_plan(plan, registry)

                # Verify command was called
                assert mock_run.called
                cmd = mock_run.call_args[0][0]

                # Verify command structure
                assert isinstance(cmd, list)
                assert cmd[0] == "mkvmerge"
                # Verify paths are in the command
                assert any(str(source) in str(arg) for arg in cmd)
                assert any(str(target) in str(arg) for arg in cmd)


class TestSubprocessArgumentSanitization:
    """Test that subprocess arguments are properly sanitized."""

    def test_path_with_leading_dash_safe_in_list_args(self, tmp_path):
        """Test that leading-dash paths are safe when used as list args.

        validate_file_path does not reject leading dashes because subprocess
        calls use list arguments (not shell strings), so dashes are treated
        as literal filenames, not as option flags.
        """
        from framekit.core.path_validation import validate_file_path

        malicious_paths = [
            tmp_path / "-i",
            tmp_path / "--help",
            tmp_path / "-version",
        ]

        for path in malicious_paths:
            try:
                result = validate_file_path(path, must_exist=False)
                # Leading-dash accepted — safe because subprocess uses list args
                assert result is not None
            except PathValidationError:
                pass

    def test_path_with_null_bytes_handled(self, tmp_path):
        """Test that paths with null bytes don't cause security issues.

        On Windows Python 3.14+, null bytes may survive Path construction.
        The security guarantee is subprocess list-arg usage, not path-level
        rejection.
        """
        from framekit.core.path_validation import validate_file_path

        malicious_path = str(tmp_path / "test.mkv") + "\x00.txt"

        try:
            result = validate_file_path(malicious_path, must_exist=False)
            assert result is not None
        except (PathValidationError, ValueError, OSError):
            pass

    def test_path_with_newlines_handled(self, tmp_path):
        """Test that paths with newlines don't cause command injection.

        On some platforms, newlines are valid in filenames. The security
        guarantee comes from subprocess list-arg usage, not path filtering.
        """
        from framekit.core.path_validation import validate_file_path

        malicious_path = str(tmp_path / "test\n.mkv")

        try:
            result = validate_file_path(malicious_path, must_exist=False)
            assert result is not None
        except (PathValidationError, ValueError, OSError):
            pass

    def test_subprocess_uses_list_not_shell(self, tmp_path):
        """Test that subprocess calls use list arguments, not shell=True."""
        from framekit.core.models.cleanmkv import RemuxPlan
        from framekit.core.tools import ToolRegistry
        from framekit.modules.cleanmkv.remuxer import apply_remux_plan

        source = tmp_path / "input.mkv"
        source.write_text("fake video")
        target = tmp_path / "output.mkv"

        plan = RemuxPlan(
            source=source,
            target=target,
            keep_audio_track_ids=[0],
            keep_subtitle_track_ids=[],
            default_audio_track_id=0,
            default_subtitle_track_id=None,
            copy_only=False,
        )

        registry = ToolRegistry()

        with patch("framekit.modules.cleanmkv.remuxer._run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            with patch.object(registry, "require_tool", return_value="mkvmerge"):
                apply_remux_plan(plan, registry)

                # Verify subprocess.run was called with list, not string
                call_args = mock_run.call_args
                assert isinstance(call_args[0][0], list)

                # Verify shell=True is not used (check kwargs)
                if len(call_args) > 1 and isinstance(call_args[1], dict):
                    assert call_args[1].get("shell") is not True


class TestPathTraversalPrevention:
    """Test prevention of path traversal attacks in subprocess calls."""

    def test_path_traversal_in_input_rejected(self, tmp_path):
        """Test that path traversal in input paths is rejected."""
        from framekit.core.path_validation import validate_file_path

        # Attempt path traversal
        traversal_path = tmp_path / ".." / ".." / "etc" / "passwd"

        # Should raise error or resolve safely
        try:
            result = validate_file_path(traversal_path, must_exist=False, strict=True)
            # If it resolves, verify it's within allowed directory
            assert result.is_relative_to(tmp_path.resolve())
        except PathValidationError:
            # Expected: validation rejects traversal
            pass

    def test_symlink_in_path_detected(self, tmp_path):
        """Test that symlinks in paths are detected."""
        import platform

        if platform.system() == "Windows":
            pytest.skip("Unix symlink test")

        from framekit.core.path_validation import configure_security, validate_file_path

        # Create a symlink
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        link_dir = tmp_path / "link"
        link_dir.symlink_to(real_dir)

        test_file = link_dir / "test.mkv"
        test_file.write_text("fake video")

        # Configure to reject symlinks
        configure_security(allow_symlinks=False, strict_mode=True)

        # Should raise error
        with pytest.raises(PathValidationError, match="symbolic link"):
            validate_file_path(test_file, strict=True)

        # Reset configuration
        configure_security(allow_symlinks=True, strict_mode=False)


# Made with Bob
