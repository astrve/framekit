"""Tests for subtitle extraction and conversion.

Following TDD principles - tests written before implementation.
Tests cover:
- Subtitle extraction using FFmpeg/mkvextract
- Format conversion (SRT, ASS, VTT)
- Language filtering
- Variant detection (forced, SDH)
- Error handling
- Path validation and security
"""

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

from swirrl.core.path_validation import PathValidationError  # noqa: E402
from swirrl.core.tools import ToolRegistry  # noqa: E402
from swirrl.modules.extract.models import (  # noqa: E402
    ExtractionOptions,
    SubtitleFormat,
    SubtitleTrack,
)


class TestSubtitleTrackModel:
    """Test SubtitleTrack data model."""

    def test_subtitle_track_creation(self):
        """Test creating a subtitle track."""
        track = SubtitleTrack(
            track_id=2,
            codec="subrip",
            language="eng",
            language_name="English",
            title="English Subtitles",
            forced=False,
            hearing_impaired=False,
            default=True,
            variant="full",
        )

        assert track.track_id == 2
        assert track.codec == "subrip"
        assert track.language == "eng"
        assert track.variant == "full"

    def test_subtitle_track_defaults(self):
        """Test subtitle track with default values."""
        track = SubtitleTrack(
            track_id=0,
            codec="ass",
        )

        assert track.language is None
        assert track.forced is False
        assert track.hearing_impaired is False
        assert track.default is False
        assert track.variant == "full"


class TestExtractionOptionsModel:
    """Test ExtractionOptions data model."""

    def test_extraction_options_defaults(self):
        """Test default extraction options."""
        options = ExtractionOptions()

        assert options.output_format == SubtitleFormat.ORIGINAL
        assert options.languages is None
        assert options.include_forced is True
        assert options.include_sdh is True
        assert options.extract_all is False

    def test_extraction_options_custom(self):
        """Test custom extraction options."""
        options = ExtractionOptions(
            output_format=SubtitleFormat.SRT,
            languages=["eng", "fra"],
            include_forced=False,
            extract_all=True,
        )

        assert options.output_format == SubtitleFormat.SRT
        assert options.languages == ["eng", "fra"]
        assert options.include_forced is False
        assert options.extract_all is True


class TestSubtitleExtractor:
    """Test SubtitleExtractor class."""

    @pytest.fixture
    def mock_registry(self):
        """Create a mock ToolRegistry."""
        registry = Mock(spec=ToolRegistry)
        registry.resolve_tool_path.return_value = "/usr/bin/ffmpeg"
        return registry

    @pytest.fixture
    def extractor(self, mock_registry):
        """Create a SubtitleExtractor instance."""
        # Import here to avoid import errors before implementation
        from swirrl.modules.extract.subtitle_extractor import SubtitleExtractor

        return SubtitleExtractor(mock_registry)

    def test_initialization(self, mock_registry):
        """Test extractor initialization."""
        from swirrl.modules.extract.subtitle_extractor import SubtitleExtractor

        extractor = SubtitleExtractor(mock_registry)
        assert extractor.registry == mock_registry

    def test_detect_subtitle_format_from_codec(self, extractor):
        """Test detecting subtitle format from codec name."""
        assert extractor.detect_subtitle_format("subrip") == SubtitleFormat.SRT
        assert extractor.detect_subtitle_format("ass") == SubtitleFormat.ASS
        assert extractor.detect_subtitle_format("ssa") == SubtitleFormat.SSA
        assert extractor.detect_subtitle_format("webvtt") == SubtitleFormat.VTT
        assert extractor.detect_subtitle_format("hdmv_pgs_subtitle") == SubtitleFormat.PGS
        assert extractor.detect_subtitle_format("dvd_subtitle") == SubtitleFormat.VOBSUB

    def test_can_convert_format(self, extractor):
        """Test checking if format conversion is supported."""
        # Text-based formats can be converted
        assert extractor.can_convert_format(SubtitleFormat.SRT, SubtitleFormat.ASS) is True
        assert extractor.can_convert_format(SubtitleFormat.ASS, SubtitleFormat.VTT) is True

        # Image-based formats cannot be converted
        assert extractor.can_convert_format(SubtitleFormat.PGS, SubtitleFormat.SRT) is False
        assert extractor.can_convert_format(SubtitleFormat.VOBSUB, SubtitleFormat.ASS) is False

        # Same format doesn't need conversion
        assert extractor.can_convert_format(SubtitleFormat.SRT, SubtitleFormat.SRT) is False

    def test_build_extraction_command_ffmpeg(self, extractor, tmp_path):
        """Test building FFmpeg extraction command."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_path = tmp_path / "subtitle.srt"

        track = SubtitleTrack(
            track_id=2,
            codec="subrip",
            language="eng",
        )

        cmd = extractor.build_extraction_command(
            video_path=video_path,
            output_path=output_path,
            track=track,
            use_mkvextract=False,
        )

        # Verify command structure
        assert isinstance(cmd, list)
        assert cmd[0] == "/usr/bin/ffmpeg"
        assert "-i" in cmd
        assert str(video_path) in cmd
        assert str(output_path) in cmd
        assert "-map" in cmd
        # Verify no shell injection
        assert ";" not in " ".join(cmd)
        assert "|" not in " ".join(cmd)

    def test_build_extraction_command_mkvextract(self, extractor, tmp_path):
        """Test building mkvextract command."""
        extractor.registry.resolve_tool_path.side_effect = lambda tool: (
            "/usr/bin/mkvextract" if tool == "mkvextract" else "/usr/bin/ffmpeg"
        )

        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_path = tmp_path / "subtitle.srt"

        track = SubtitleTrack(
            track_id=2,
            codec="subrip",
            language="eng",
        )

        cmd = extractor.build_extraction_command(
            video_path=video_path,
            output_path=output_path,
            track=track,
            use_mkvextract=True,
        )

        # Verify mkvextract command structure
        assert isinstance(cmd, list)
        assert cmd[0] == "/usr/bin/mkvextract"
        assert "tracks" in cmd
        assert str(video_path) in cmd
        # mkvextract uses format: track_id:output_path
        assert any(":" in arg and str(output_path) in arg for arg in cmd)

    def test_build_conversion_command(self, extractor, tmp_path):
        """Test building format conversion command."""
        input_path = tmp_path / "subtitle.srt"
        input_path.write_text("fake subtitle")
        output_path = tmp_path / "subtitle.ass"

        cmd = extractor.build_conversion_command(
            input_path=input_path,
            output_path=output_path,
            target_format=SubtitleFormat.ASS,
        )

        # Verify FFmpeg conversion command
        assert isinstance(cmd, list)
        assert cmd[0] == "/usr/bin/ffmpeg"
        assert "-i" in cmd
        assert str(input_path) in cmd
        assert str(output_path) in cmd
        # Verify no shell injection
        assert ";" not in " ".join(cmd)

    def test_build_command_validates_paths(self, extractor, tmp_path):
        """Test that paths are validated in command building."""
        # Malicious video path
        malicious_video = tmp_path / "-i /etc/passwd"
        output_path = tmp_path / "subtitle.srt"

        track = SubtitleTrack(track_id=0, codec="subrip")

        with pytest.raises((PathValidationError, FileNotFoundError, ValueError)):
            extractor.build_extraction_command(
                video_path=malicious_video,
                output_path=output_path,
                track=track,
                use_mkvextract=False,
            )

    def test_extract_subtitle_success(self, extractor, tmp_path):
        """Test successful subtitle extraction."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_path = tmp_path / "subtitle.srt"

        track = SubtitleTrack(
            track_id=2,
            codec="subrip",
            language="eng",
        )

        # Mock subprocess.run
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = extractor.extract_subtitle(
                video_path=video_path,
                output_path=output_path,
                track=track,
            )

            assert result.success is True
            assert result.track == track
            assert result.source_file == video_path
            assert result.output_file == output_path
            assert result.error is None
            mock_run.assert_called_once()

    def test_extract_subtitle_with_conversion(self, extractor, tmp_path):
        """Test subtitle extraction with format conversion."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_path = tmp_path / "subtitle.ass"

        track = SubtitleTrack(
            track_id=2,
            codec="subrip",  # SRT codec
            language="eng",
        )

        # Mock subprocess.run for both extraction and conversion
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = extractor.extract_subtitle(
                video_path=video_path,
                output_path=output_path,
                track=track,
                target_format=SubtitleFormat.ASS,
            )

            assert result.success is True
            assert result.format_converted is True
            assert result.original_format == "srt"
            # Should be called twice: extraction + conversion
            assert mock_run.call_count == 2

    def test_extract_subtitle_failure(self, extractor, tmp_path):
        """Test subtitle extraction failure handling."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_path = tmp_path / "subtitle.srt"

        track = SubtitleTrack(
            track_id=2,
            codec="subrip",
            language="eng",
        )

        # Mock subprocess.run to fail
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=1,
                cmd=["ffmpeg"],
                stderr="Error: Invalid stream",
            )

            result = extractor.extract_subtitle(
                video_path=video_path,
                output_path=output_path,
                track=track,
            )

            assert result.success is False
            assert result.error is not None
            assert "Error" in result.error or "Invalid" in result.error

    def test_filter_tracks_by_language(self, extractor):
        """Test filtering tracks by language."""
        tracks = [
            SubtitleTrack(track_id=0, codec="subrip", language="eng"),
            SubtitleTrack(track_id=1, codec="ass", language="fra"),
            SubtitleTrack(track_id=2, codec="subrip", language="spa"),
        ]

        options = ExtractionOptions(languages=["eng", "fra"])

        filtered = extractor.filter_tracks(tracks, options)

        assert len(filtered) == 2
        assert filtered[0].language == "eng"
        assert filtered[1].language == "fra"

    def test_filter_tracks_exclude_forced(self, extractor):
        """Test filtering out forced subtitles."""
        tracks = [
            SubtitleTrack(track_id=0, codec="subrip", language="eng", forced=False),
            SubtitleTrack(track_id=1, codec="subrip", language="eng", forced=True),
        ]

        options = ExtractionOptions(include_forced=False)

        filtered = extractor.filter_tracks(tracks, options)

        assert len(filtered) == 1
        assert filtered[0].forced is False

    def test_filter_tracks_exclude_sdh(self, extractor):
        """Test filtering out SDH subtitles."""
        tracks = [
            SubtitleTrack(track_id=0, codec="subrip", language="eng", hearing_impaired=False),
            SubtitleTrack(track_id=1, codec="subrip", language="eng", hearing_impaired=True),
        ]

        options = ExtractionOptions(include_sdh=False)

        filtered = extractor.filter_tracks(tracks, options)

        assert len(filtered) == 1
        assert filtered[0].hearing_impaired is False

    def test_filter_tracks_extract_all(self, extractor):
        """Test extract_all option bypasses filters."""
        tracks = [
            SubtitleTrack(track_id=0, codec="subrip", language="eng"),
            SubtitleTrack(track_id=1, codec="ass", language="fra"),
            SubtitleTrack(track_id=2, codec="subrip", language="spa"),
        ]

        options = ExtractionOptions(
            languages=["eng"],  # Should be ignored
            extract_all=True,
        )

        filtered = extractor.filter_tracks(tracks, options)

        assert len(filtered) == 3  # All tracks included

    def test_generate_output_filename(self, extractor, tmp_path):
        """Test output filename generation."""
        video_path = tmp_path / "Movie.2024.1080p.mkv"

        track = SubtitleTrack(
            track_id=2,
            codec="subrip",
            language="eng",
            variant="full",
        )

        options = ExtractionOptions(
            output_format=SubtitleFormat.SRT,
            output_pattern="{basename}.{language}.{variant}.{format}",
        )

        output_path = extractor.generate_output_filename(
            video_path=video_path,
            track=track,
            options=options,
        )

        assert output_path.name == "Movie.2024.1080p.eng.full.srt"
        assert output_path.parent == video_path.parent

    def test_generate_output_filename_with_output_dir(self, extractor, tmp_path):
        """Test output filename generation with custom output directory."""
        video_path = tmp_path / "video.mkv"
        output_dir = tmp_path / "subtitles"

        track = SubtitleTrack(
            track_id=2,
            codec="subrip",
            language="eng",
            variant="full",
        )

        options = ExtractionOptions(
            output_format=SubtitleFormat.SRT,
            output_dir=output_dir,
        )

        output_path = extractor.generate_output_filename(
            video_path=video_path,
            track=track,
            options=options,
        )

        assert output_path.parent == output_dir

    def test_no_shell_injection_in_commands(self, extractor, tmp_path):
        """Test that commands never use shell=True."""
        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_path = tmp_path / "subtitle.srt"

        track = SubtitleTrack(track_id=2, codec="subrip")

        # Build various commands
        cmd1 = extractor.build_extraction_command(
            video_path, output_path, track, use_mkvextract=False
        )
        cmd2 = extractor.build_conversion_command(video_path, output_path, SubtitleFormat.ASS)

        # All commands should be lists (not strings)
        assert isinstance(cmd1, list)
        assert isinstance(cmd2, list)

        # Verify no dangerous characters in joined command
        for cmd in [cmd1, cmd2]:
            cmd_str = " ".join(cmd)
            assert ";" not in cmd_str
            assert "|" not in cmd_str
            assert "&&" not in cmd_str
            assert "`" not in cmd_str
            assert "$(" not in cmd_str


class TestSubtitleExtractorIntegration:
    """Integration tests for subtitle extraction."""

    @pytest.fixture
    def mock_registry(self):
        """Create a mock ToolRegistry."""
        registry = Mock(spec=ToolRegistry)
        registry.resolve_tool_path.side_effect = lambda tool: (
            f"/usr/bin/{tool}" if tool in ["ffmpeg", "mkvextract"] else None
        )
        return registry

    def test_extract_multiple_subtitles(self, mock_registry, tmp_path):
        """Test extracting multiple subtitle tracks."""
        from swirrl.modules.extract.subtitle_extractor import SubtitleExtractor

        extractor = SubtitleExtractor(mock_registry)

        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")

        tracks = [
            SubtitleTrack(track_id=2, codec="subrip", language="eng"),
            SubtitleTrack(track_id=3, codec="ass", language="fra"),
        ]

        options = ExtractionOptions(output_format=SubtitleFormat.SRT)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            results = extractor.extract_subtitles(
                video_path=video_path,
                tracks=tracks,
                options=options,
            )

            assert len(results) == 2
            assert all(r.success for r in results)

    def test_graceful_degradation_no_mkvextract(self, tmp_path):
        """Test graceful fallback when mkvextract is unavailable."""
        from swirrl.modules.extract.subtitle_extractor import SubtitleExtractor

        registry = Mock(spec=ToolRegistry)
        registry.resolve_tool_path.side_effect = lambda tool: (
            "/usr/bin/ffmpeg" if tool == "ffmpeg" else None
        )

        extractor = SubtitleExtractor(registry)

        video_path = tmp_path / "video.mkv"
        video_path.write_text("fake video")
        output_path = tmp_path / "subtitle.srt"

        track = SubtitleTrack(track_id=2, codec="subrip")

        # Should use FFmpeg instead of mkvextract
        cmd = extractor.build_extraction_command(
            video_path, output_path, track, use_mkvextract=False
        )

        assert "ffmpeg" in cmd[0]
        assert "mkvextract" not in cmd[0]
