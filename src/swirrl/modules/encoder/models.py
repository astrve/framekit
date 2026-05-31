"""Data models for the Encoder module."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class VideoConfig:
    """Video encoding configuration."""

    crf: int
    preset: str
    tune: str | None = None
    profile: str = "main"
    level: str = "4.1"
    pix_fmt: str = "yuv420p"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "crf": self.crf,
            "preset": self.preset,
            "tune": self.tune,
            "profile": self.profile,
            "level": self.level,
            "pix_fmt": self.pix_fmt,
        }


@dataclass
class AudioConfig:
    """Audio encoding configuration."""

    copy: bool = True
    codec: str | None = None
    bitrate: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {"copy": self.copy, "codec": self.codec, "bitrate": self.bitrate}


@dataclass
class SubtitleConfig:
    """Subtitle configuration."""

    copy: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {"copy": self.copy}


@dataclass
class MetadataConfig:
    """Metadata configuration."""

    preserve: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {"preserve": self.preserve}


@dataclass
class ChapterConfig:
    """Chapter configuration."""

    preserve: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {"preserve": self.preserve}


@dataclass
class AdvancedConfig:
    """Advanced encoding configuration."""

    two_pass: bool = False
    x264_params: list[str] = field(default_factory=list)
    x265_params: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "two_pass": self.two_pass,
            "x264_params": self.x264_params,
            "x265_params": self.x265_params,
        }


@dataclass
class EncodePreset:
    """Complete encoding preset configuration."""

    name: str
    description: str
    source_codec: str
    target_codec: str
    encoder: str
    video: VideoConfig
    audio: AudioConfig
    subtitles: SubtitleConfig
    metadata: MetadataConfig
    chapters: ChapterConfig
    advanced: AdvancedConfig
    max_encoding_time: int = 3600  # Maximum encoding time in seconds (default: 1 hour)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "source_codec": self.source_codec,
            "target_codec": self.target_codec,
            "encoder": self.encoder,
            "video": self.video.to_dict(),
            "audio": self.audio.to_dict(),
            "subtitles": self.subtitles.to_dict(),
            "metadata": self.metadata.to_dict(),
            "chapters": self.chapters.to_dict(),
            "advanced": self.advanced.to_dict(),
            "max_encoding_time": self.max_encoding_time,
        }


@dataclass
class ProgressInfo:
    """Encoding progress information."""

    frame: int = 0
    fps: float = 0.0
    time: str = "00:00:00"
    bitrate: str = "0kbits/s"
    speed: str = "0x"
    size: str = "0kB"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "frame": self.frame,
            "fps": self.fps,
            "time": self.time,
            "bitrate": self.bitrate,
            "speed": self.speed,
            "size": self.size,
        }


@dataclass
class ValidationResult:
    """Validation result."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, error: str) -> None:
        """Add an error message."""
        self.errors.append(error)
        self.valid = False

    def add_warning(self, warning: str) -> None:
        """Add a warning message."""
        self.warnings.append(warning)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {"valid": self.valid, "errors": self.errors, "warnings": self.warnings}


@dataclass
class EncodeResult:
    """Result of an encoding operation."""

    success: bool
    input_file: Path
    output_file: Path
    duration: float = 0.0
    encoding_time: float = 0.0
    input_size: int = 0
    output_size: int = 0
    compression_ratio: float = 0.0
    avg_fps: float = 0.0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def space_saved(self) -> int:
        """Calculate space saved in bytes."""
        return self.input_size - self.output_size

    @property
    def space_saved_mb(self) -> float:
        """Calculate space saved in MB."""
        return self.space_saved / (1024 * 1024)

    @property
    def space_saved_gb(self) -> float:
        """Calculate space saved in GB."""
        return self.space_saved / (1024 * 1024 * 1024)

    def add_error(self, error: str) -> None:
        """Add an error message."""
        self.errors.append(error)
        self.success = False

    def add_warning(self, warning: str) -> None:
        """Add a warning message."""
        self.warnings.append(warning)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "input_file": str(self.input_file),
            "output_file": str(self.output_file),
            "duration": self.duration,
            "encoding_time": self.encoding_time,
            "input_size": self.input_size,
            "output_size": self.output_size,
            "compression_ratio": self.compression_ratio,
            "avg_fps": self.avg_fps,
            "space_saved": self.space_saved,
            "space_saved_mb": self.space_saved_mb,
            "space_saved_gb": self.space_saved_gb,
            "errors": self.errors,
            "warnings": self.warnings,
        }


@dataclass
class MediaInfo:
    """Media file information."""

    path: Path
    codec: str
    duration: float
    width: int
    height: int
    fps: float
    bitrate: int
    size: int
    audio_tracks: int = 0
    subtitle_tracks: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "path": str(self.path),
            "codec": self.codec,
            "duration": self.duration,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "bitrate": self.bitrate,
            "size": self.size,
            "audio_tracks": self.audio_tracks,
            "subtitle_tracks": self.subtitle_tracks,
        }
