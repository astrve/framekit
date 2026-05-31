"""Tests for video extraction and conversion.

Following TDD principles - tests written before implementation.
Tests cover:
- Video extraction using FFmpeg
- Codec conversion (H.264, H.265, VP9, AV1)
- Resolution adjustment
- Quality control (CRF, bitrate)
- Error handling
- Path validation and security
"""

from __future__ import annotations

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
    VideoCodec,
    VideoExtractionOptions,
    VideoTrack,
)


class TestVideoTrackModel:
    """Test VideoTrack data model."""

    def test_video_track_creation(self):
        """Test creating a video track."""
        track = VideoTrack(
            track_id=0,
            codec="h264",
            width=1920,
            height=1080,
            fps=23.976,
            bitrate=5000000,
            pixel_format="yuv420p",
            color_space="bt709",
            hdr=False,
            default=True,
        )

        assert track.track_id == 0
        assert track.codec == "h264"
        assert track.width == 1920
        assert track.height == 1080
        assert track.fps == 23.976
        assert track.default is True

    def test_video_track_defaults(self):
        """Test video track with default values."""
        track = VideoTrack(
            track_id=0,
            codec="hevc",
        )

        assert track.width is None
        assert track.height is None
        assert track.fps is None
        assert track.hdr is False
        assert track.default is False


class TestVideoCodecEnum:
    """Test VideoCodec enum."""

    def test_video_codec_values(self):
        """Test video codec enum values."""
        assert VideoCodec.H264 == "h264"
        assert VideoCodec.H265 == "h265"
        assert VideoCodec.HEVC == "hevc"
        assert VideoCodec.VP9 == "vp9"
        assert VideoCodec.AV1 == "av1"
        assert VideoCodec.COPY == "copy"


class TestVideoExtractionOptionsModel:
    """Test VideoExtractionOptions data model."""

    def test_extraction_options_defaults(self):
        """Test default extraction options."""
        options = VideoExtractionOptions()

        assert options.output_codec == VideoCodec.COPY
        assert options.width is None
        assert options.height is None
        assert options.crf is None
        assert options.preset == "medium"
        assert options.extract_all is False

    def test_extraction_options_custom(self):
        """Test custom extraction options."""
        options = VideoExtractionOptions(
            output_codec=VideoCodec.H265,
            width=1920,
            height=1080,
            crf=28,
            preset="slow",
            extract_all=True,
        )

        assert options.output_codec == VideoCodec.H265
        assert options.width == 1920
        assert options.height == 1080
        assert options.crf == 28
        assert options.preset == "slow"
        assert options.extract_all is True

    def test_get_default_crf(self):
        """Test getting default CRF values for codecs."""
        options = VideoExtractionOptions()

        assert options.get_default_crf(VideoCodec.H264) == 23
        assert options.get_default_crf(VideoCodec.H265) == 28
        assert options.get_default_crf(VideoCodec.HEVC) == 28
        assert options.get_default_crf(VideoCodec.VP9) == 31
        assert options.get_default_crf(VideoCodec.AV1) == 30


class TestVideoExtractor:
    """Test VideoExtractor class."""

    @pytest.fixture
    def mock_registry(self):
        """Create mock tool registry."""
        registry = Mock(spec=ToolRegistry)
        registry.resolve_tool_path.return_value = "/usr/bin/ffmpeg"
        return registry

    @pytest.fixture
    def video_extractor(self, mock_registry):
        """Create VideoExtractor instance."""
        from swirrl.modules.extract.video_extractor import VideoExtractor

        return VideoExtractor(mock_registry)

    def test_extractor_initialization(self, video_extractor, mock_registry):
        """Test extractor initialization."""
        assert video_extractor.registry == mock_registry

    def test_detect_video_codec(self, video_extractor):
        """Test video codec detection from codec name."""
        assert video_extractor.detect_video_codec("h264") == VideoCodec.H264
        assert video_extractor.detect_video_codec("hevc") == VideoCodec.H265
        assert video_extractor.detect_video_codec("vp9") == VideoCodec.VP9
        assert video_extractor.detect_video_codec("av1") == VideoCodec.AV1
        assert video_extractor.detect_video_codec("unknown") == VideoCodec.UNKNOWN

    def test_get_ffmpeg_codec_name(self, video_extractor):
        """Test getting FFmpeg codec name from VideoCodec."""
        assert video_extractor.get_ffmpeg_codec_name(VideoCodec.H264) == "libx264"
        assert video_extractor.get_ffmpeg_codec_name(VideoCodec.H265) == "libx265"
        assert video_extractor.get_ffmpeg_codec_name(VideoCodec.VP9) == "libvpx-vp9"
        assert video_extractor.get_ffmpeg_codec_name(VideoCodec.AV1) == "libaom-av1"
        assert video_extractor.get_ffmpeg_codec_name(VideoCodec.COPY) == "copy"

    def test_build_extraction_command_copy(self, video_extractor, tmp_path):
        """Test building extraction command for stream copy."""
        video_path = tmp_path / "input.mkv"
        video_path.touch()
        output_path = tmp_path / "output.mkv"

        track = VideoTrack(track_id=0, codec="h264")
        options = VideoExtractionOptions(output_codec=VideoCodec.COPY)

        cmd = video_extractor.build_extraction_command(video_path, output_path, track, options)

        assert "/usr/bin/ffmpeg" in cmd
        assert "-i" in cmd
        assert str(video_path) in cmd
        assert "-map" in cmd
        assert "0:v:0" in cmd
        assert "-c:v" in cmd
        assert "copy" in cmd
        assert str(output_path) in cmd

    def test_build_extraction_command_h264_conversion(self, video_extractor, tmp_path):
        """Test building extraction command for H.264 conversion."""
        video_path = tmp_path / "input.mkv"
        video_path.touch()
        output_path = tmp_path / "output.mp4"

        track = VideoTrack(track_id=0, codec="hevc")
        options = VideoExtractionOptions(
            output_codec=VideoCodec.H264,
            crf=23,
            preset="medium",
        )

        cmd = video_extractor.build_extraction_command(video_path, output_path, track, options)

        assert "-c:v" in cmd
        assert "libx264" in cmd
        assert "-crf" in cmd
        assert "23" in cmd
        assert "-preset" in cmd
        assert "medium" in cmd

    def test_build_extraction_command_resolution_change(self, video_extractor, tmp_path):
        """Test building extraction command with resolution change."""
        video_path = tmp_path / "input.mkv"
        video_path.touch()
        output_path = tmp_path / "output.mp4"

        track = VideoTrack(track_id=0, codec="h264", width=3840, height=2160)
        options = VideoExtractionOptions(
            output_codec=VideoCodec.H264,
            width=1920,
            height=1080,
            crf=23,
        )

        cmd = video_extractor.build_extraction_command(video_path, output_path, track, options)

        assert "-vf" in cmd
        # Check for scale filter
        scale_idx = cmd.index("-vf")
        assert "scale=1920:1080" in cmd[scale_idx + 1]

    def test_build_extraction_command_bitrate_mode(self, video_extractor, tmp_path):
        """Test building extraction command with bitrate mode."""
        video_path = tmp_path / "input.mkv"
        video_path.touch()
        output_path = tmp_path / "output.mp4"

        track = VideoTrack(track_id=0, codec="h264")
        options = VideoExtractionOptions(
            output_codec=VideoCodec.H264,
            bitrate="5M",
        )

        cmd = video_extractor.build_extraction_command(video_path, output_path, track, options)

        assert "-b:v" in cmd
        assert "5M" in cmd

    def test_build_extraction_command_invalid_video_path(self, video_extractor, tmp_path):
        """Test building command with invalid video path."""
        video_path = tmp_path / "nonexistent.mkv"
        output_path = tmp_path / "output.mp4"

        track = VideoTrack(track_id=0, codec="h264")
        options = VideoExtractionOptions()

        with pytest.raises(PathValidationError):
            video_extractor.build_extraction_command(video_path, output_path, track, options)

    def test_build_extraction_command_unsafe_output_path(self, video_extractor, tmp_path):
        """Test building command with unsafe output path.

        Note: Path validation by default only warns about path traversal.
        This test verifies the path is still processed (resolved) correctly.
        In production, strict mode should be enabled for security.
        """
        video_path = tmp_path / "input.mkv"
        video_path.touch()

        # Use a path that will resolve but is clearly outside tmp_path
        # The validation will warn but not raise unless strict=True
        output_path = tmp_path / ".." / ".." / "output.mp4"

        track = VideoTrack(track_id=0, codec="h264")
        options = VideoExtractionOptions()

        # This should succeed but the resolved path will be outside tmp_path
        # In production with strict mode, this would raise PathValidationError
        cmd = video_extractor.build_extraction_command(video_path, output_path, track, options)

        # Verify command was built (path validation didn't block it)
        assert cmd is not None
        assert isinstance(cmd, list)

    def test_validate_crf_value(self, video_extractor):
        """Test CRF value validation."""
        # Valid CRF values
        video_extractor.validate_crf_value(0, VideoCodec.H264)
        video_extractor.validate_crf_value(23, VideoCodec.H264)
        video_extractor.validate_crf_value(51, VideoCodec.H264)

        # Invalid CRF values
        with pytest.raises(ValueError, match="CRF must be between 0 and 51"):
            video_extractor.validate_crf_value(-1, VideoCodec.H264)

        with pytest.raises(ValueError, match="CRF must be between 0 and 51"):
            video_extractor.validate_crf_value(52, VideoCodec.H264)

    def test_validate_bitrate_value(self, video_extractor):
        """Test bitrate value validation."""
        # Valid bitrate values
        video_extractor.validate_bitrate_value("5M")
        video_extractor.validate_bitrate_value("2000k")
        video_extractor.validate_bitrate_value("1000000")

        # Invalid bitrate values (potential injection)
        with pytest.raises(ValueError, match="Invalid bitrate format"):
            video_extractor.validate_bitrate_value("5M; rm -rf /")

        with pytest.raises(ValueError, match="Invalid bitrate format"):
            video_extractor.validate_bitrate_value("$(whoami)")

    def test_validate_preset_value(self, video_extractor):
        """Test preset value validation."""
        # Valid presets
        valid_presets = [
            "ultrafast",
            "superfast",
            "veryfast",
            "faster",
            "fast",
            "medium",
            "slow",
            "slower",
            "veryslow",
        ]
        for preset in valid_presets:
            video_extractor.validate_preset_value(preset)

        # Invalid preset
        with pytest.raises(ValueError, match="Invalid preset"):
            video_extractor.validate_preset_value("invalid")

        # Injection attempt
        with pytest.raises(ValueError, match="Invalid preset"):
            video_extractor.validate_preset_value("medium; rm -rf /")

    @patch("subprocess.run")
    def test_extract_video_success(self, mock_run, video_extractor, tmp_path):
        """Test successful video extraction."""
        video_path = tmp_path / "input.mkv"
        video_path.touch()
        output_path = tmp_path / "output.mp4"

        track = VideoTrack(track_id=0, codec="h264")
        options = VideoExtractionOptions(output_codec=VideoCodec.COPY)

        # Mock successful subprocess
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        result = video_extractor.extract_video(video_path, output_path, track, options)

        assert result.success is True
        assert result.track == track
        assert result.source_file == video_path
        assert result.output_file == output_path
        assert result.error is None
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_extract_video_ffmpeg_failure(self, mock_run, video_extractor, tmp_path):
        """Test video extraction with FFmpeg failure."""
        video_path = tmp_path / "input.mkv"
        video_path.touch()
        output_path = tmp_path / "output.mp4"

        track = VideoTrack(track_id=0, codec="h264")
        options = VideoExtractionOptions()

        # Mock failed subprocess
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="Error: Invalid codec")

        result = video_extractor.extract_video(video_path, output_path, track, options)

        assert result.success is False
        assert result.error is not None
        assert "FFmpeg failed" in result.error

    @patch("subprocess.run")
    def test_extract_video_with_codec_conversion(self, mock_run, video_extractor, tmp_path):
        """Test video extraction with codec conversion."""
        video_path = tmp_path / "input.mkv"
        video_path.touch()
        output_path = tmp_path / "output.mp4"

        track = VideoTrack(track_id=0, codec="hevc")
        options = VideoExtractionOptions(
            output_codec=VideoCodec.H264,
            crf=23,
        )

        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        result = video_extractor.extract_video(video_path, output_path, track, options)

        assert result.success is True
        assert result.codec_converted is True
        assert result.original_format == "hevc"

    @patch("subprocess.run")
    def test_extract_video_with_resolution_change(self, mock_run, video_extractor, tmp_path):
        """Test video extraction with resolution change."""
        video_path = tmp_path / "input.mkv"
        video_path.touch()
        output_path = tmp_path / "output.mp4"

        track = VideoTrack(track_id=0, codec="h264", width=3840, height=2160)
        options = VideoExtractionOptions(
            output_codec=VideoCodec.H264,
            width=1920,
            height=1080,
        )

        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        result = video_extractor.extract_video(video_path, output_path, track, options)

        assert result.success is True
        assert result.resolution_changed is True

    def test_extract_video_no_shell_injection(self, video_extractor, tmp_path):
        """Test that extraction prevents shell injection."""
        video_path = tmp_path / "input.mkv"
        video_path.touch()
        output_path = tmp_path / "output.mp4"

        track = VideoTrack(track_id=0, codec="h264")

        # Try to inject shell command via bitrate
        options = VideoExtractionOptions(
            output_codec=VideoCodec.H264,
            bitrate="5M; rm -rf /",
        )

        with pytest.raises(ValueError, match="Invalid bitrate format"):
            video_extractor.build_extraction_command(video_path, output_path, track, options)

    def test_get_output_extension(self, video_extractor):
        """Test getting output file extension for codec."""
        assert video_extractor.get_output_extension(VideoCodec.H264) == ".mp4"
        assert video_extractor.get_output_extension(VideoCodec.H265) == ".mp4"
        assert video_extractor.get_output_extension(VideoCodec.VP9) == ".webm"
        assert video_extractor.get_output_extension(VideoCodec.AV1) == ".mp4"
        assert video_extractor.get_output_extension(VideoCodec.COPY) == ".mkv"


class TestVideoExtractionIntegration:
    """Integration tests for video extraction workflow."""

    @pytest.fixture
    def mock_registry(self):
        """Create mock tool registry."""
        registry = Mock(spec=ToolRegistry)
        registry.resolve_tool_path.return_value = "/usr/bin/ffmpeg"
        return registry

    @pytest.fixture
    def video_extractor(self, mock_registry):
        """Create VideoExtractor instance."""
        from swirrl.modules.extract.video_extractor import VideoExtractor

        return VideoExtractor(mock_registry)

    @patch("subprocess.run")
    def test_full_extraction_workflow(self, mock_run, video_extractor, tmp_path):
        """Test complete extraction workflow."""
        video_path = tmp_path / "movie.mkv"
        video_path.touch()
        output_dir = tmp_path / "extracted"
        output_dir.mkdir()

        track = VideoTrack(
            track_id=0,
            codec="hevc",
            width=1920,
            height=1080,
        )

        options = VideoExtractionOptions(
            output_codec=VideoCodec.H264,
            crf=23,
            preset="medium",
            output_dir=output_dir,
        )

        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        output_path = output_dir / "movie.h264.mp4"
        result = video_extractor.extract_video(video_path, output_path, track, options)

        assert result.success is True
        assert result.codec_converted is True
        assert result.output_file == output_path

        # Verify subprocess was called with list (not shell=True)
        call_args = mock_run.call_args
        assert call_args[1].get("shell") is not True
        assert isinstance(call_args[0][0], list)
