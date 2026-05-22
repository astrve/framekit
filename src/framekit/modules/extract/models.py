"""Data models for media extraction."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class SubtitleFormat(str, Enum):
    """Supported subtitle formats."""

    SRT = "srt"
    ASS = "ass"
    SSA = "ssa"
    VTT = "vtt"
    SUB = "sub"
    PGS = "pgs"  # Image-based (extraction only)
    VOBSUB = "vobsub"  # Image-based (extraction only)
    ORIGINAL = "original"  # Keep original format


class SubtitleTrack(BaseModel):
    """Subtitle track information."""

    track_id: int = Field(..., description="Track ID in the source file")
    codec: str = Field(..., description="Subtitle codec (e.g., 'subrip', 'ass')")
    language: str | None = Field(None, description="Language code (e.g., 'eng', 'fra')")
    language_name: str | None = Field(None, description="Human-readable language name")
    title: str | None = Field(None, description="Track title/name")
    forced: bool = Field(False, description="Whether this is a forced subtitle track")
    hearing_impaired: bool = Field(False, description="Whether this is SDH/HI track")
    default: bool = Field(False, description="Whether this is the default track")
    variant: str = Field("full", description="Subtitle variant: 'full', 'forced', or 'sdh'")

    model_config = ConfigDict(frozen=False)


class ExtractionOptions(BaseModel):
    """Options for subtitle extraction."""

    output_format: SubtitleFormat = Field(
        SubtitleFormat.ORIGINAL,
        description="Target subtitle format",
    )
    languages: list[str] | None = Field(
        None,
        description="Filter by language codes (e.g., ['eng', 'fra'])",
    )
    include_forced: bool = Field(
        True,
        description="Include forced subtitle tracks",
    )
    include_sdh: bool = Field(
        True,
        description="Include SDH/hearing impaired tracks",
    )
    extract_all: bool = Field(
        False,
        description="Extract all subtitle tracks regardless of filters",
    )
    output_dir: Path | None = Field(
        None,
        description="Output directory (default: same as source)",
    )
    output_pattern: str = Field(
        "{basename}.{language}.{variant}.{format}",
        description="Output filename pattern",
    )

    model_config = ConfigDict(frozen=False)


class ExtractionResult(BaseModel):
    """Result of a single track extraction."""

    track: SubtitleTrack | AudioTrack | VideoTrack = Field(
        ..., description="Extracted track information"
    )
    source_file: Path = Field(..., description="Source video file")
    output_file: Path = Field(..., description="Output file")
    success: bool = Field(..., description="Whether extraction succeeded")
    error: str | None = Field(None, description="Error message if failed")
    format_converted: bool = Field(
        False,
        description="Whether format conversion was performed",
    )
    original_format: str | None = Field(
        None,
        description="Original format before conversion",
    )
    normalized: bool = Field(
        False,
        description="Whether audio normalization was applied",
    )
    codec_converted: bool = Field(
        False,
        description="Whether video codec conversion was performed",
    )
    resolution_changed: bool = Field(
        False,
        description="Whether video resolution was changed",
    )

    model_config = ConfigDict(frozen=False, arbitrary_types_allowed=True)


class AudioFormat(str, Enum):
    """Supported audio formats."""

    AAC = "aac"
    MP3 = "mp3"
    FLAC = "flac"
    ALAC = "alac"
    WAV = "wav"
    OPUS = "opus"
    VORBIS = "vorbis"
    AC3 = "ac3"
    EAC3 = "eac3"
    DTS = "dts"
    DTS_HD = "dts-hd"
    TRUEHD = "truehd"
    ORIGINAL = "original"  # Keep original format (copy)


class AudioCodec(str, Enum):
    """Audio codec identifiers."""

    AAC = "aac"
    MP3 = "mp3"
    FLAC = "flac"
    ALAC = "alac"
    PCM = "pcm"
    OPUS = "opus"
    VORBIS = "vorbis"
    AC3 = "ac3"
    EAC3 = "eac3"
    DTS = "dts"
    DTS_HD = "dts-hd"
    DTS_MA = "dts-ma"
    TRUEHD = "truehd"
    UNKNOWN = "unknown"


class AudioTrack(BaseModel):
    """Audio track information."""

    track_id: int = Field(..., description="Track ID in the source file")
    codec: str = Field(..., description="Audio codec (e.g., 'aac', 'ac3', 'dts')")
    language: str | None = Field(None, description="Language code (e.g., 'eng', 'fra')")
    language_name: str | None = Field(None, description="Human-readable language name")
    title: str | None = Field(None, description="Track title/name")
    channels: int | None = Field(None, description="Number of audio channels")
    channel_layout: str | None = Field(None, description="Channel layout (e.g., '5.1', 'stereo')")
    sample_rate: int | None = Field(None, description="Sample rate in Hz")
    bitrate: int | None = Field(None, description="Bitrate in bits per second")
    default: bool = Field(False, description="Whether this is the default track")
    commentary: bool = Field(False, description="Whether this is a commentary track")

    model_config = ConfigDict(frozen=False)


class AudioExtractionOptions(BaseModel):
    """Options for audio extraction."""

    output_format: AudioFormat = Field(
        AudioFormat.ORIGINAL,
        description="Target audio format",
    )
    languages: list[str] | None = Field(
        None,
        description="Filter by language codes (e.g., ['eng', 'fra'])",
    )
    bitrate: str | None = Field(
        None,
        description="Target bitrate for lossy formats (e.g., '192k', '320k')",
    )
    normalize: bool = Field(
        False,
        description="Apply audio normalization (loudnorm filter)",
    )
    normalize_target_lufs: float = Field(
        -16.0,
        description="Target LUFS for normalization (EBU R128 standard)",
    )
    extract_all: bool = Field(
        False,
        description="Extract all audio tracks regardless of filters",
    )
    include_commentary: bool = Field(
        False,
        description="Include commentary tracks",
    )
    output_dir: Path | None = Field(
        None,
        description="Output directory (default: same as source)",
    )
    output_pattern: str = Field(
        "{basename}.{language}.{format}",
        description="Output filename pattern",
    )

    model_config = ConfigDict(frozen=False)


class VideoCodec(str, Enum):
    """Video codec identifiers."""

    H264 = "h264"
    H265 = "h265"
    HEVC = "hevc"  # Alias for H265
    VP9 = "vp9"
    AV1 = "av1"
    MPEG2 = "mpeg2"
    MPEG4 = "mpeg4"
    VC1 = "vc1"
    COPY = "copy"  # Passthrough (no re-encoding)
    UNKNOWN = "unknown"


class VideoTrack(BaseModel):
    """Video track information."""

    track_id: int = Field(..., description="Track ID in the source file")
    codec: str = Field(..., description="Video codec (e.g., 'h264', 'hevc', 'vp9')")
    width: int | None = Field(None, description="Video width in pixels")
    height: int | None = Field(None, description="Video height in pixels")
    fps: float | None = Field(None, description="Frames per second")
    bitrate: int | None = Field(None, description="Bitrate in bits per second")
    pixel_format: str | None = Field(None, description="Pixel format (e.g., 'yuv420p')")
    color_space: str | None = Field(None, description="Color space (e.g., 'bt709')")
    hdr: bool = Field(False, description="Whether video has HDR metadata")
    default: bool = Field(False, description="Whether this is the default track")

    model_config = ConfigDict(frozen=False)


class VideoExtractionOptions(BaseModel):
    """Options for video extraction."""

    output_codec: VideoCodec = Field(
        VideoCodec.COPY,
        description="Target video codec (copy = no re-encoding)",
    )
    width: int | None = Field(
        None,
        description="Target width in pixels (None = keep original)",
    )
    height: int | None = Field(
        None,
        description="Target height in pixels (None = keep original)",
    )
    crf: int | None = Field(
        None,
        description="Constant Rate Factor for quality (lower = better, codec-specific)",
    )
    preset: str = Field(
        "medium",
        description="Encoding preset (ultrafast, fast, medium, slow, veryslow)",
    )
    bitrate: str | None = Field(
        None,
        description="Target bitrate (e.g., '5M', '2000k')",
    )
    extract_all: bool = Field(
        False,
        description="Extract all video tracks",
    )
    output_dir: Path | None = Field(
        None,
        description="Output directory (default: same as source)",
    )
    output_pattern: str = Field(
        "{basename}.{codec}.{format}",
        description="Output filename pattern",
    )

    model_config = ConfigDict(frozen=False)

    def get_default_crf(self, codec: VideoCodec) -> int:
        """Get default CRF value for codec.

        Args:
            codec: Video codec

        Returns:
            Default CRF value
        """
        defaults = {
            VideoCodec.H264: 23,
            VideoCodec.H265: 28,
            VideoCodec.HEVC: 28,
            VideoCodec.VP9: 31,
            VideoCodec.AV1: 30,
        }
        return defaults.get(codec, 23)
