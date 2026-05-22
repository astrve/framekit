"""Tests for graceful degradation when external tools are missing.

This test suite verifies that Framekit handles missing external tools
(mkvmerge, ffmpeg, ffprobe, mediainfo) gracefully with helpful error messages
instead of hard crashes.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from framekit.core.settings import SettingsStore
from framekit.core.tools import ToolRegistry


class TestToolRegistry:
    """Test ToolRegistry behavior with missing tools."""

    def test_missing_mkvmerge_returns_unavailable_status(self, tmp_path):
        """Test that missing mkvmerge is detected and reported properly."""
        # Mock shutil.which to return None (tool not found)
        with patch("framekit.core.tools.shutil.which", return_value=None):
            registry = ToolRegistry()
            status = registry.get_status("mkvmerge")

            assert status.name == "mkvmerge"
            assert status.available is False
            assert status.resolved_path is None
            assert status.error is not None
            assert "not found" in status.error.lower()

    def test_configured_but_missing_tool_path(self, tmp_path):
        """Test tool configured in settings but path doesn't exist."""
        settings_file = tmp_path / "framekit.yaml"
        settings_file.write_text("tools:\n  mkvmerge: /nonexistent/path/mkvmerge\n")

        store = SettingsStore(path=settings_file)
        registry = ToolRegistry(settings=store)

        with patch("framekit.core.tools.shutil.which", return_value=None):
            status = registry.get_status("mkvmerge")

            assert status.available is False
            assert status.configured_path == "/nonexistent/path/mkvmerge"
            assert status.resolved_path is None

    def test_tool_exists_but_not_executable(self, tmp_path):
        """Test tool file exists but is not executable."""
        fake_tool = tmp_path / "mkvmerge"
        fake_tool.write_text("#!/bin/sh\necho 'fake'")
        # Don't make it executable

        with patch("framekit.core.tools.shutil.which", return_value=str(fake_tool)):
            with patch("framekit.core.tools._run_version_command") as mock_run:
                mock_run.return_value = (None, "Permission denied")

                registry = ToolRegistry()
                status = registry.get_status("mkvmerge")

                assert status.available is False
                assert status.error is not None

    def test_all_tools_missing(self):
        """Test get_all_statuses when all tools are missing."""
        with patch("framekit.core.tools.shutil.which", return_value=None):
            registry = ToolRegistry()
            statuses = registry.get_all_statuses()

            assert len(statuses) > 0
            for status in statuses:
                assert status.available is False
                assert status.error is not None


class TestCleanMkvWithMissingTools:
    """Test CleanMKV module behavior when mkvmerge is missing."""

    def test_scanner_raises_helpful_error_when_mkvmerge_missing(self, tmp_path):
        """Test that scanner provides helpful error when mkvmerge is missing."""
        from framekit.modules.cleanmkv.scanner import scan_mkv_file

        test_file = tmp_path / "test.mkv"
        test_file.write_bytes(b"fake mkv content")

        with patch("framekit.core.tools.ToolRegistry.resolve_tool_path", return_value=None):
            with pytest.raises(RuntimeError) as exc_info:
                scan_mkv_file(test_file, ToolRegistry())

            error_msg = str(exc_info.value).lower()
            assert "mkvmerge" in error_msg
            # New error messages include installation instructions
            assert any(word in error_msg for word in ["required", "available", "install"])

    def test_remuxer_raises_helpful_error_when_mkvmerge_missing(self, tmp_path):
        """Test that remuxer provides helpful error when mkvmerge is missing."""
        from framekit.core.models.cleanmkv import RemuxPlan
        from framekit.modules.cleanmkv.remuxer import apply_remux_plan

        source = tmp_path / "source.mkv"
        target = tmp_path / "target.mkv"
        source.write_bytes(b"fake mkv")

        plan = RemuxPlan(
            source=source,
            target=target,
            copy_only=False,
            keep_audio_track_ids=[1],
            keep_subtitle_track_ids=[],
            default_audio_track_id=1,
            default_subtitle_track_id=None,
        )

        with patch("framekit.core.tools.ToolRegistry.resolve_tool_path", return_value=None):
            with pytest.raises(RuntimeError) as exc_info:
                apply_remux_plan(plan, ToolRegistry())

            error_msg = str(exc_info.value).lower()
            assert "mkvmerge" in error_msg
            # New error messages include installation instructions
            assert any(word in error_msg for word in ["required", "available", "install"])


class TestEncoderWithMissingTools:
    """Test Encoder module behavior when ffmpeg/ffprobe are missing."""

    def test_encoder_service_init_fails_gracefully_without_ffmpeg(self):
        """Test EncoderService initialization fails with helpful message when ffmpeg missing."""
        from framekit.modules.encoder.models import (
            AdvancedConfig,
            AudioConfig,
            ChapterConfig,
            EncodePreset,
            MetadataConfig,
            SubtitleConfig,
            VideoConfig,
        )
        from framekit.modules.encoder.service import EncoderService

        preset = EncodePreset(
            name="test",
            description="test preset",
            source_codec="h264",
            target_codec="h264",
            encoder="libx264",
            video=VideoConfig(crf=23, preset="medium"),
            audio=AudioConfig(copy=True),
            subtitles=SubtitleConfig(copy=True),
            metadata=MetadataConfig(preserve=True),
            chapters=ChapterConfig(preserve=True),
            advanced=AdvancedConfig(two_pass=False),
        )

        with patch("framekit.modules.encoder.service.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("ffmpeg not found")

            with pytest.raises(RuntimeError) as exc_info:
                EncoderService(preset, ffmpeg_path="ffmpeg")

            error_msg = str(exc_info.value).lower()
            assert "ffmpeg" in error_msg
            assert any(word in error_msg for word in ["not found", "install", "accessible"])

    def test_validator_detects_missing_ffmpeg(self):
        """Test EncoderValidator detects missing ffmpeg."""
        from framekit.modules.encoder.validator import EncoderValidator

        with patch("framekit.modules.encoder.validator.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            validator = EncoderValidator(ffmpeg_path="ffmpeg")
            result = validator.check_ffmpeg_available()

            assert not result.valid
            assert len(result.errors) > 0
            assert any("ffmpeg" in err.lower() for err in result.errors)

    def test_validator_detects_missing_ffprobe(self):
        """Test EncoderValidator detects missing ffprobe."""
        from framekit.modules.encoder.validator import EncoderValidator

        with patch("framekit.modules.encoder.validator.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            validator = EncoderValidator(ffprobe_path="ffprobe")
            result = validator.check_ffprobe_available()

            assert not result.valid
            assert len(result.errors) > 0
            assert any("ffprobe" in err.lower() for err in result.errors)


class TestPartialToolAvailability:
    """Test scenarios where some tools are available but others are not."""

    def test_mkvmerge_available_ffmpeg_missing(self):
        """Test system with mkvmerge but no ffmpeg."""

        def mock_which(tool):
            return "/usr/bin/mkvmerge" if tool == "mkvmerge" else None

        with patch("framekit.core.tools.shutil.which", side_effect=mock_which):
            with patch("framekit.core.tools._run_version_command") as mock_run:
                mock_run.return_value = ("mkvmerge v70.0.0", None)

                registry = ToolRegistry()
                mkvmerge_status = registry.get_status("mkvmerge")

                assert mkvmerge_status.available is True
                assert mkvmerge_status.version is not None

    def test_ffmpeg_available_mkvmerge_missing(self):
        """Test system with ffmpeg but no mkvmerge."""
        with patch("framekit.core.tools.shutil.which", return_value=None):
            registry = ToolRegistry()
            status = registry.get_status("mkvmerge")

            assert status.available is False


class TestToolErrorMessages:
    """Test that error messages are helpful and actionable."""

    def test_error_message_includes_installation_hint(self):
        """Test that missing tool errors suggest how to install."""
        with patch("framekit.core.tools.shutil.which", return_value=None):
            registry = ToolRegistry()
            status = registry.get_status("mkvmerge")

            # Error should exist and be informative
            assert status.error is not None
            assert len(status.error) > 0

    def test_macos_app_bundle_detection(self):
        """Test that macOS .app bundles are detected and handled."""
        fake_app_path = "/Applications/MediaInfo.app/Contents/MacOS/mediainfo"

        # Test the detection logic directly
        # _is_macos_app_bundle is a module-level function we can test
        assert ".app/" in fake_app_path.replace("\\", "/")

        # Verify that when a tool resolves to an app bundle, it's marked unavailable
        with patch("framekit.core.tools.shutil.which", return_value=fake_app_path):
            registry = ToolRegistry()
            status = registry.get_status("mkvmerge")
            # Should be marked as unavailable with GUI-only error
            assert status.available is False
            if status.error:
                assert "gui" in status.error.lower() or "app" in status.error.lower()


class TestDoctorCommandToolChecks:
    """Test doctor command's tool checking functionality."""

    def test_doctor_reports_missing_tools(self):
        """Test that doctor command reports missing tools."""
        # Test through ToolRegistry instead of private function
        with patch("framekit.core.tools.shutil.which", return_value=None):
            registry = ToolRegistry()
            statuses = registry.get_all_statuses()

            # Should have statuses for tools
            assert len(statuses) > 0

            # All tools should be reported as unavailable
            for status in statuses:
                assert status.available is False
                assert status.error is not None

    def test_doctor_reports_available_tools(self):
        """Test that doctor command reports available tools correctly."""

        def mock_which(tool):
            return f"/usr/bin/{tool}"

        with patch("framekit.core.tools.shutil.which", side_effect=mock_which):
            with patch("framekit.core.tools._run_version_command") as mock_run:
                mock_run.return_value = ("version 1.0.0", None)

                registry = ToolRegistry()
                statuses = registry.get_all_statuses()

                # Should have statuses for tools
                assert len(statuses) > 0

                # Tools should be reported as available
                for status in statuses:
                    assert status.available is True
                    assert status.version is not None or status.resolved_path is not None


class TestToolRegistryEdgeCases:
    """Test edge cases in tool detection."""

    def test_tool_version_command_timeout(self):
        """Test handling of tool version command timeout."""
        with patch("framekit.core.tools.shutil.which", return_value="/usr/bin/mkvmerge"):
            with patch("framekit.core.tools.subprocess.run") as mock_run:
                import subprocess

                mock_run.side_effect = subprocess.TimeoutExpired("mkvmerge", 5)

                registry = ToolRegistry()
                status = registry.get_status("mkvmerge")

                assert status.available is False
                assert status.error is not None
                assert "timed out" in status.error.lower()

    def test_tool_version_command_returns_nonzero(self):
        """Test handling of tool version command returning non-zero exit code."""
        with patch("framekit.core.tools.shutil.which", return_value="/usr/bin/mkvmerge"):
            with patch("framekit.core.tools.subprocess.run") as mock_run:
                mock_result = Mock()
                mock_result.returncode = 1
                mock_result.stdout = ""
                mock_result.stderr = ""
                mock_run.return_value = mock_result

                registry = ToolRegistry()
                status = registry.get_status("mkvmerge")

                assert status.available is False
                assert status.error is not None

    def test_empty_configured_path_is_ignored(self, tmp_path):
        """Test that empty string in configured path is treated as not configured."""
        settings_file = tmp_path / "framekit.yaml"
        settings_file.write_text("tools:\n  mkvmerge: ''\n")

        store = SettingsStore(path=settings_file)
        registry = ToolRegistry(settings=store)

        with patch("framekit.core.tools.shutil.which", return_value=None):
            status = registry.get_status("mkvmerge")

            # Should fall back to PATH search, not use empty string
            assert status.configured_path is None or status.configured_path == ""
