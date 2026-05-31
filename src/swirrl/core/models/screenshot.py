"""Data models for screenshot extraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ScreenshotConfig(BaseModel):
    """Configuration for screenshot extraction.

    Attributes:
        count: Number of screenshots to extract (1-50)
        width: Target width in pixels (None = original, min 320)
        height: Target height in pixels (None = original, min 240)
        quality: JPEG quality for FFmpeg (1=best, 31=worst)
        format: Output format (png or jpg)
        skip_start_seconds: Skip N seconds from video start (legacy, overridden by skip_start_percent)
        skip_end_seconds: Skip N seconds from video end (legacy, overridden by skip_end_percent)
        skip_start_percent: Skip N% from video start (0-100, default 5%)
        skip_end_percent: Skip N% from video end (0-100, default 5%)
        avoid_black_frames: Skip black/dark frames
        black_threshold: Black detection threshold (0.0-1.0)
        min_interval_seconds: Minimum interval between screenshots
    """

    count: int = Field(default=6, ge=1, le=50, description="Number of screenshots to extract")
    width: int | None = Field(default=None, ge=320, description="Target width (None = original)")
    height: int | None = Field(default=None, ge=240, description="Target height (None = original)")
    quality: int = Field(default=2, ge=1, le=31, description="JPEG quality (1=best, 31=worst)")
    format: Literal["png", "jpg"] = Field(default="png", description="Output format")
    skip_start_seconds: int = Field(
        default=60, ge=0, description="Skip N seconds from start (legacy)"
    )
    skip_end_seconds: int = Field(default=120, ge=0, description="Skip N seconds from end (legacy)")
    skip_start_percent: float = Field(
        default=5.0,
        ge=0.0,
        le=100.0,
        description="Skip N% from start (overrides skip_start_seconds)",
    )
    skip_end_percent: float = Field(
        default=5.0, ge=0.0, le=100.0, description="Skip N% from end (overrides skip_end_seconds)"
    )
    avoid_black_frames: bool = Field(default=True, description="Skip black/dark frames")
    black_threshold: float = Field(
        default=0.05, ge=0.0, le=1.0, description="Black detection threshold"
    )
    min_interval_seconds: int = Field(
        default=30, ge=1, description="Minimum interval between screenshots"
    )

    @field_validator("quality")
    @classmethod
    def validate_quality(cls, v: int) -> int:
        """Ensure quality is in valid range for FFmpeg."""
        if not 1 <= v <= 31:
            raise ValueError("quality must be between 1 (best) and 31 (worst)")
        return v


class TimestampConfig(BaseModel):
    """Configuration for timestamp-based screenshot extraction.

    Attributes:
        timestamps: Exact timestamps in seconds to extract
        width: Target width in pixels (None = original, min 320)
        height: Target height in pixels (None = original, min 240)
        quality: JPEG quality for FFmpeg (1=best, 31=worst)
        format: Output format (png or jpg)
    """

    timestamps: list[float] = Field(default_factory=list, description="Exact timestamps in seconds")
    width: int | None = Field(default=None, ge=320)
    height: int | None = Field(default=None, ge=240)
    quality: int = Field(default=2, ge=1, le=31)
    format: Literal["png", "jpg"] = Field(default="png")


@dataclass(slots=True)
class ScreenshotMetadata:
    """Metadata for a single screenshot.

    Attributes:
        timestamp_seconds: Timestamp in video where screenshot was taken
        frame_number: Frame number (if available)
        width: Screenshot width in pixels
        height: Screenshot height in pixels
        file_size_bytes: File size in bytes
        quality_score: Quality score 0.0-1.0 (higher is better)
        is_black_frame: Whether frame was detected as black
        video_source: Path to source video file
    """

    timestamp_seconds: float
    frame_number: int | None
    width: int
    height: int
    file_size_bytes: int
    quality_score: float | None
    is_black_frame: bool
    video_source: Path


@dataclass(slots=True)
class ScreenshotResult:
    """Result of screenshot extraction for a single video.

    Attributes:
        video_path: Path to source video
        output_dir: Directory where screenshots were saved
        screenshots: List of screenshot file paths
        metadata: List of metadata for each screenshot
        skipped_black_frames: Number of black frames skipped
        total_frames_analyzed: Total frames analyzed
        duration_seconds: Video duration in seconds
        success: Whether extraction was successful
        error: Error message if extraction failed
    """

    video_path: Path
    output_dir: Path
    screenshots: list[Path] = field(default_factory=list)
    metadata: list[ScreenshotMetadata] = field(default_factory=list)
    skipped_black_frames: int = 0
    total_frames_analyzed: int = 0
    duration_seconds: float = 0.0
    success: bool = True
    error: str | None = None


@dataclass(slots=True)
class ScreenshotReport:
    """Overall report for screenshot extraction operation.

    Attributes:
        results: List of results for each video
        total_videos: Total number of videos processed
        total_screenshots: Total screenshots extracted
        total_failures: Number of failed extractions
        elapsed_seconds: Total elapsed time
    """

    results: list[ScreenshotResult] = field(default_factory=list)
    total_videos: int = 0
    total_screenshots: int = 0
    total_failures: int = 0
    elapsed_seconds: float = 0.0

    @property
    def success_rate(self) -> float:
        """Calculate success rate as fraction of successful videos.

        Returns:
            Success rate between 0.0 and 1.0
        """
        if self.total_videos == 0:
            return 0.0
        return (self.total_videos - self.total_failures) / self.total_videos
