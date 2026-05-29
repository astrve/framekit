"""Tests for audio extraction and conversion.

Following TDD principles - tests written before implementation.
Tests cover:
- Audio extraction using FFmpeg
- Format conversion (AAC, MP3, FLAC, Opus)
- Bitrate control
- Audio normalization
- Language filtering
- Codec filtering
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

from ouro.core.tools import ToolRegistry  # noqa: E402
from ouro.modules.extract.models import (  # noqa: E402
    AudioExtractionOptions,
    AudioFormat,
    AudioTrack,
)


class TestAudioTrackModel:
    """Test AudioTrack data model."""

    def test_audio_track_creation(self):
        """Test creating an audio track."""
        track = AudioTrack(
            track_id=1,
            codec="aac",
            language="eng",
            language_name="English",
            title="English Audio",
            channels=6,
            channel_layout="5.1",
            sample_rate=48000,
            bitrate=192000,
            default=True,
            commentary=False,
        )

        assert track.track_id == 1
        assert track.codec == "aac"
        assert track.language == "eng"
        assert track.channels == 6
        assert track.channel_layout == "5.1"
        assert track.sample_rate == 48000
        assert track.bitrate == 192000
        assert track.default is True
        assert track.commentary is False

    def test_audio_track_defaults(self):
        """Test audio track with default values."""
        track = AudioTrack(
            track_id=0,
            codec="ac3",
        )

        assert track.language is None
        assert track.channels is None
        assert track.sample_rate is None
        assert track.bitrate is None
        assert track.default is False
        assert track.commentary is False


class TestAudioExtractionOptionsModel:
    """Test AudioExtractionOptions data model."""

    def test_audio_extraction_options_defaults(self):
        """Test default audio extraction options."""
        options = AudioExtractionOptions()

        assert options.output_format == AudioFormat.ORIGINAL
        assert options.languages is None
        assert options.bitrate is None
        assert options.normalize is False
        assert options.normalize_target_lufs == -16.0
        assert options.extract_all is False
        assert options.include_commentary is False

    def test_audio_extraction_options_custom(self):
        """Test custom audio extraction options."""
        options = AudioExtractionOptions(
            output_format=AudioFormat.MP3,
            languages=["eng", "fra"],
            bitrate="320k",
            normalize=True,
            normalize_target_lufs=-18.0,
            extract_all=True,
            include_commentary=True,
        )

        assert options.output_format == AudioFormat.MP3
        assert options.languages == ["eng", "fra"]
        assert options.bitrate == "320k"
        assert options.normalize is True
        assert options.normalize_target_lufs == -18.0
        assert options.extract_all is True
        assert options.include_commentary is True


class TestAudioExtractor:
    """Test AudioExtractor class."""

    @pytest.fixture
    def mock_registry(self):
        """Create a mock ToolRegistry."""
        registry = Mock(spec=ToolRegistry)
        registry.resolve_tool_path.return_value = "/usr/bin/ffmpeg"
        return registry

    @pytest.fixture
    def audio_extractor(self, mock_registry):
        """Create AudioExtractor instance with mocked registry."""
        from ouro.modules.extract.audio_extractor import AudioExtractor

        return AudioExtractor(mock_registry)

    def test_detect_audio_format(self, audio_extractor):
        """Test audio format detection from codec."""
        assert audio_extractor.detect_audio_format("aac") == AudioFormat.AAC
        assert audio_extractor.detect_audio_format("mp3") == AudioFormat.MP3
        assert audio_extractor.detect_audio_format("flac") == AudioFormat.FLAC
        assert audio_extractor.detect_audio_format("ac3") == AudioFormat.AC3
        assert audio_extractor.detect_audio_format("dts") == AudioFormat.DTS
        assert audio_extractor.detect_audio_format("opus") == AudioFormat.OPUS
        assert audio_extractor.detect_audio_format("vorbis") == AudioFormat.VORBIS

    def test_can_convert_format(self, audio_extractor):
        """Test format conversion capability detection."""
        # Same format doesn't need conversion
        assert not audio_extractor.can_convert_format(AudioFormat.AAC, AudioFormat.AAC)

        # Lossy to lossy conversion supported
        assert audio_extractor.can_convert_format(AudioFormat.AAC, AudioFormat.MP3)
        assert audio_extractor.can_convert_format(AudioFormat.MP3, AudioFormat.OPUS)

        # Lossless to lossy conversion supported
        assert audio_extractor.can_convert_format(AudioFormat.FLAC, AudioFormat.AAC)

        # Lossy to lossless conversion supported (but not recommended)
        assert audio_extractor.can_convert_format(AudioFormat.AAC, AudioFormat.FLAC)

    def test_validate_bitrate(self, audio_extractor):
        """Test bitrate validation."""
        # Valid bitrates
        assert audio_extractor.validate_bitrate("128k") == "128k"
        assert audio_extractor.validate_bitrate("192k") == "192k"
        assert audio_extractor.validate_bitrate("320k") == "320k"

        # Invalid bitrates should raise ValueError
        with pytest.raises(ValueError, match="Invalid bitrate format"):
            audio_extractor.validate_bitrate("invalid")

        with pytest.raises(ValueError, match="Invalid bitrate format"):
            audio_extractor.validate_bitrate("999999k")

    @patch("subprocess.run")
    def test_extract_audio_copy_mode(self, mock_run, audio_extractor, tmp_path):
        """Test audio extraction in copy mode (no conversion)."""
        # Setup
        video_path = tmp_path / "input.mkv"
        video_path.touch()
        output_path = tmp_path / "output.aac"

        track = AudioTrack(
            track_id=1,
            codec="aac",
            language="eng",
        )

        options = AudioExtractionOptions(
            output_format=AudioFormat.ORIGINAL,
        )

        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        # Execute
        result = audio_extractor.extract_audio(video_path, track, output_path, options)

        # Verify
        assert result.success is True
        assert result.format_converted is False
        assert mock_run.called

        # Check command structure (no shell=True)
        call_args = mock_run.call_args
        assert call_args[1].get("shell") is not True
        cmd = call_args[0][0]
        assert "-c:a" in cmd
        assert "copy" in cmd

    @patch("subprocess.run")
    def test_extract_audio_with_conversion(self, mock_run, audio_extractor, tmp_path):
        """Test audio extraction with format conversion."""
        # Setup
        video_path = tmp_path / "input.mkv"
        video_path.touch()
        output_path = tmp_path / "output.mp3"

        track = AudioTrack(
            track_id=1,
            codec="aac",
            language="eng",
        )

        options = AudioExtractionOptions(
            output_format=AudioFormat.MP3,
            bitrate="320k",
        )

        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        # Execute
        result = audio_extractor.extract_audio(video_path, track, output_path, options)

        # Verify
        assert result.success is True
        assert result.format_converted is True
        assert result.original_format == "aac"
        assert mock_run.called

        # Check command includes conversion parameters
        cmd = mock_run.call_args[0][0]
        assert "-c:a" in cmd
        assert "libmp3lame" in cmd
        assert "-b:a" in cmd
        assert "320k" in cmd

    @patch("subprocess.run")
    def test_extract_audio_with_normalization(self, mock_run, audio_extractor, tmp_path):
        """Test audio extraction with normalization."""
        # Setup
        video_path = tmp_path / "input.mkv"
        video_path.touch()
        output_path = tmp_path / "output.aac"
        temp_output = output_path.with_suffix(output_path.suffix + ".tmp")

        track = AudioTrack(
            track_id=1,
            codec="aac",
            language="eng",
        )

        options = AudioExtractionOptions(
            output_format=AudioFormat.AAC,
            normalize=True,
            normalize_target_lufs=-16.0,
        )

        # Mock extraction and two-pass normalization
        def mock_subprocess_run(*args, **kwargs):
            # Create output file after extraction
            if not output_path.exists():
                output_path.touch()
            # Create temp file for normalization
            if not temp_output.exists():
                temp_output.touch()
            return Mock(
                returncode=0, stdout="", stderr="input_i: -23.0\ninput_tp: -1.5\ninput_lra: 11.0"
            )

        mock_run.side_effect = mock_subprocess_run

        # Execute
        result = audio_extractor.extract_audio(video_path, track, output_path, options)

        # Verify
        assert result.success is True
        assert result.normalized is True
        assert mock_run.call_count == 3  # Extraction + two-pass normalization

    @patch("subprocess.run")
    def test_extract_audio_flac_lossless(self, mock_run, audio_extractor, tmp_path):
        """Test audio extraction to FLAC (lossless)."""
        # Setup
        video_path = tmp_path / "input.mkv"
        video_path.touch()
        output_path = tmp_path / "output.flac"

        track = AudioTrack(
            track_id=1,
            codec="dts",
            language="eng",
        )

        options = AudioExtractionOptions(
            output_format=AudioFormat.FLAC,
        )

        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        # Execute
        result = audio_extractor.extract_audio(video_path, track, output_path, options)

        # Verify
        assert result.success is True
        assert result.format_converted is True

        # Check command uses FLAC codec
        cmd = mock_run.call_args[0][0]
        assert "-c:a" in cmd
        assert "flac" in cmd
        # FLAC is lossless, no bitrate parameter
        assert "-b:a" not in cmd

    def test_extract_audio_invalid_path(self, audio_extractor, tmp_path):
        """Test audio extraction with invalid path."""
        # Setup
        video_path = tmp_path / "nonexistent.mkv"
        output_path = tmp_path / "output.aac"

        track = AudioTrack(
            track_id=1,
            codec="aac",
        )

        options = AudioExtractionOptions()

        # Execute
        result = audio_extractor.extract_audio(video_path, track, output_path, options)

        # Verify - should return error result, not raise exception
        assert result.success is False
        assert result.error is not None

    @patch("subprocess.run")
    def test_extract_audio_ffmpeg_failure(self, mock_run, audio_extractor, tmp_path):
        """Test audio extraction when FFmpeg fails."""
        # Setup
        video_path = tmp_path / "input.mkv"
        video_path.touch()
        output_path = tmp_path / "output.aac"

        track = AudioTrack(
            track_id=1,
            codec="aac",
        )

        options = AudioExtractionOptions()

        # Mock FFmpeg failure
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["ffmpeg"],
            stderr="FFmpeg error: invalid data",
        )

        # Execute
        result = audio_extractor.extract_audio(video_path, track, output_path, options)

        # Verify
        assert result.success is False
        assert result.error is not None
        assert "Extraction failed" in result.error

    def test_build_extraction_command_security(self, audio_extractor, tmp_path):
        """Test that extraction command is built securely (no shell=True)."""
        # Setup
        video_path = tmp_path / "input.mkv"
        video_path.touch()
        output_path = tmp_path / "output.aac"

        track = AudioTrack(
            track_id=1,
            codec="aac",
        )

        options = AudioExtractionOptions()

        # Execute
        cmd = audio_extractor.build_extraction_command(video_path, track, output_path, options)

        # Verify
        assert isinstance(cmd, list)  # List form, not string
        assert all(isinstance(arg, str) for arg in cmd)
        # Check no shell metacharacters that could be exploited
        assert not any(";" in arg or "|" in arg or "&" in arg for arg in cmd)

    def test_filter_tracks_by_language(self, audio_extractor):
        """Test filtering audio tracks by language."""
        tracks = [
            AudioTrack(track_id=1, codec="aac", language="eng"),
            AudioTrack(track_id=2, codec="ac3", language="fra"),
            AudioTrack(track_id=3, codec="dts", language="eng"),
            AudioTrack(track_id=4, codec="aac", language="jpn"),
        ]

        options = AudioExtractionOptions(languages=["eng"])

        filtered = audio_extractor.filter_tracks(tracks, options)

        assert len(filtered) == 2
        assert all(t.language == "eng" for t in filtered)

    def test_filter_tracks_exclude_commentary(self, audio_extractor):
        """Test filtering out commentary tracks."""
        tracks = [
            AudioTrack(track_id=1, codec="aac", language="eng", commentary=False),
            AudioTrack(track_id=2, codec="aac", language="eng", commentary=True),
            AudioTrack(track_id=3, codec="ac3", language="eng", commentary=False),
        ]

        options = AudioExtractionOptions(include_commentary=False)

        filtered = audio_extractor.filter_tracks(tracks, options)

        assert len(filtered) == 2
        assert all(not t.commentary for t in filtered)

    def test_filter_tracks_extract_all(self, audio_extractor):
        """Test extracting all tracks regardless of filters."""
        tracks = [
            AudioTrack(track_id=1, codec="aac", language="eng"),
            AudioTrack(track_id=2, codec="ac3", language="fra"),
            AudioTrack(track_id=3, codec="dts", language="jpn"),
        ]

        options = AudioExtractionOptions(
            languages=["eng"],  # This should be ignored
            extract_all=True,
        )

        filtered = audio_extractor.filter_tracks(tracks, options)

        assert len(filtered) == 3  # All tracks included

    def test_get_default_bitrate(self, audio_extractor):
        """Test getting default bitrate for different formats."""
        assert audio_extractor.get_default_bitrate(AudioFormat.AAC) == "192k"
        assert audio_extractor.get_default_bitrate(AudioFormat.MP3) == "192k"
        assert audio_extractor.get_default_bitrate(AudioFormat.OPUS) == "128k"
        assert audio_extractor.get_default_bitrate(AudioFormat.VORBIS) == "192k"
        # Lossless formats don't have default bitrate
        assert audio_extractor.get_default_bitrate(AudioFormat.FLAC) is None

    def test_is_lossless_format(self, audio_extractor):
        """Test lossless format detection."""
        assert audio_extractor.is_lossless_format(AudioFormat.FLAC) is True
        assert audio_extractor.is_lossless_format(AudioFormat.ALAC) is True
        assert audio_extractor.is_lossless_format(AudioFormat.WAV) is True
        assert audio_extractor.is_lossless_format(AudioFormat.AAC) is False
        assert audio_extractor.is_lossless_format(AudioFormat.MP3) is False
        assert audio_extractor.is_lossless_format(AudioFormat.OPUS) is False

    @patch("subprocess.run")
    def test_extract_audio_opus_format(self, mock_run, audio_extractor, tmp_path):
        """Test audio extraction to Opus format."""
        # Setup
        video_path = tmp_path / "input.mkv"
        video_path.touch()
        output_path = tmp_path / "output.opus"

        track = AudioTrack(
            track_id=1,
            codec="aac",
            language="eng",
        )

        options = AudioExtractionOptions(
            output_format=AudioFormat.OPUS,
            bitrate="128k",
        )

        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        # Execute
        result = audio_extractor.extract_audio(video_path, track, output_path, options)

        # Verify
        assert result.success is True
        assert result.format_converted is True

        # Check command uses Opus codec
        cmd = mock_run.call_args[0][0]
        assert "-c:a" in cmd
        assert "libopus" in cmd
        assert "-b:a" in cmd
        assert "128k" in cmd
