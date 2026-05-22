"""Frame analysis for screenshot extraction."""

from __future__ import annotations

import json
import re
import subprocess  # nosec B404
from pathlib import Path
from typing import Any

from loguru import logger

from framekit.core.subprocess_safe import MissingToolError, SafeSubprocessError, run_safe
from framekit.core.tools import ToolRegistry


class FrameAnalyzer:
    """Analyzes video frames for quality and content.

    Uses FFmpeg/FFprobe to:
    - Get video duration and metadata
    - Detect black frames
    - Generate evenly distributed timestamps
    - Filter timestamps to avoid black frames
    """

    def __init__(self, registry: ToolRegistry) -> None:
        """Initialize frame analyzer.

        Args:
            registry: Tool registry for FFmpeg/FFprobe resolution
        """
        self.registry = registry

    def get_video_duration(self, video_path: Path) -> float | None:
        """Get video duration in seconds using ffprobe.

        Args:
            video_path: Path to video file

        Returns:
            Duration in seconds, or None if probe fails
        """
        ffprobe = self.registry.resolve_tool_path("ffprobe")
        if not ffprobe:
            logger.warning("ffprobe not available, cannot get video duration")
            return None

        cmd = [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(video_path),
        ]

        try:
            result = run_safe(
                cmd,
                timeout=10,
                check=False,
                capture_output=True,
                log_label="ffprobe duration",
            )

            if result.returncode != 0:
                logger.warning(f"ffprobe failed with code {result.returncode}")
                return None

            data = json.loads(result.stdout)
            duration_str = data.get("format", {}).get("duration")
            if duration_str:
                return float(duration_str)

            return None

        except (MissingToolError, SafeSubprocessError) as exc:
            logger.warning(f"ffprobe failed for {video_path}: {exc}")
            return None
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.warning(f"Failed to parse ffprobe output: {exc}")
            return None

    def get_video_info(self, video_path: Path) -> dict[str, Any] | None:
        """Get complete video information using ffprobe.

        Args:
            video_path: Path to video file

        Returns:
            Dictionary with video info (duration, width, height, codec, fps)
            or None if probe fails
        """
        ffprobe = self.registry.resolve_tool_path("ffprobe")
        if not ffprobe:
            return None

        cmd = [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_name,codec_type,width,height,r_frame_rate",
            "-of",
            "json",
            str(video_path),
        ]

        try:
            result = run_safe(
                cmd,
                timeout=10,
                check=False,
                capture_output=True,
                log_label="ffprobe info",
            )

            if result.returncode != 0:
                return None

            data = json.loads(result.stdout)

            # Find video stream
            video_stream = None
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    video_stream = stream
                    break

            if not video_stream:
                logger.warning(f"No video stream found in {video_path}")
                return None

            # Parse frame rate
            fps_str = video_stream.get("r_frame_rate", "0/1")
            try:
                num, den = map(int, fps_str.split("/"))
                fps = num / den if den != 0 else 0.0
            except (ValueError, ZeroDivisionError):
                fps = 0.0

            return {
                "duration": float(data.get("format", {}).get("duration", 0)),
                "width": int(video_stream.get("width", 0)),
                "height": int(video_stream.get("height", 0)),
                "codec": video_stream.get("codec_name", "unknown"),
                "fps": fps,
            }

        except (
            MissingToolError,
            SafeSubprocessError,
            subprocess.TimeoutExpired,
            json.JSONDecodeError,
            ValueError,
            KeyError,
        ) as exc:
            logger.warning(f"Failed to get video info: {exc}")
            return None

    def generate_timestamps(
        self,
        duration: float,
        count: int,
        skip_start: int = 0,
        skip_end: int = 0,
        skip_start_percent: float | None = None,
        skip_end_percent: float | None = None,
        min_interval: int = 1,
    ) -> list[float]:
        """Generate evenly distributed timestamps with configurable margins.

        Supports both second-based and percentage-based margins to avoid
        irrelevant frames at video start/end (intros, outros, black screens).

        Args:
            duration: Video duration in seconds
            count: Number of timestamps to generate
            skip_start: Seconds to skip from start (legacy, overridden by skip_start_percent)
            skip_end: Seconds to skip from end (legacy, overridden by skip_end_percent)
            skip_start_percent: Percentage of duration to skip from start (0-100)
            skip_end_percent: Percentage of duration to skip from end (0-100)
            min_interval: Minimum interval between timestamps in seconds

        Returns:
            List of timestamps in seconds, evenly distributed within safe zone

        Examples:
            # Skip first 5% and last 5% (default recommended)
            timestamps = generate_timestamps(7200, 6, skip_start_percent=5.0, skip_end_percent=5.0)
            # Result: [360.0, 1728.0, 3096.0, 4464.0, 5832.0, 6840.0]
            # Percentages: [5%, 24%, 43%, 62%, 81%, 95%]
        """
        # Convert percentage margins to seconds if provided
        # Percentage margins take precedence over second-based margins
        if skip_start_percent is not None:
            skip_start = int(duration * (skip_start_percent / 100.0))

        if skip_end_percent is not None:
            skip_end = int(duration * (skip_end_percent / 100.0))

        # Calculate available duration
        available_duration = duration - skip_start - skip_end

        if available_duration <= 0:
            logger.warning("No available duration after skipping start/end")
            return []

        # Calculate maximum possible screenshots with min_interval
        max_possible = int(available_duration / min_interval) + 1

        # Adjust count if it exceeds what's possible
        actual_count = min(count, max_possible)

        if actual_count <= 0:
            return []

        if actual_count == 1:
            # Single screenshot: place in middle of safe zone
            timestamp = skip_start + (available_duration / 2)
            return [round(timestamp, 2)]

        # Calculate interval between screenshots
        interval = available_duration / (actual_count - 1)

        # Ensure interval respects minimum
        if interval < min_interval:
            # Recalculate with enforced minimum interval
            actual_count = int(available_duration / min_interval) + 1
            if actual_count <= 1:
                timestamp = skip_start + (available_duration / 2)
                return [round(timestamp, 2)]
            interval = available_duration / (actual_count - 1)

        # Generate timestamps evenly distributed within safe zone
        timestamps = []
        for i in range(actual_count):
            timestamp = skip_start + (i * interval)
            # Ensure we don't exceed bounds (with small tolerance for floating point)
            max_timestamp = duration - skip_end
            if timestamp > max_timestamp:
                timestamp = max_timestamp
            timestamps.append(round(timestamp, 2))

        return timestamps

    def detect_black_frames(
        self,
        video_path: Path,
        threshold: float = 0.05,
        duration: float = 0.5,
    ) -> list[float]:
        """Detect black frames using FFmpeg blackdetect filter.

        Args:
            video_path: Path to video file
            threshold: Black pixel threshold (0.0-1.0)
            duration: Minimum duration for black detection

        Returns:
            List of timestamps where black frames start
        """
        ffmpeg = self.registry.resolve_tool_path("ffmpeg")
        if not ffmpeg:
            logger.warning("ffmpeg not available, cannot detect black frames")
            return []

        cmd = [
            ffmpeg,
            "-i",
            str(video_path),
            "-vf",
            f"blackdetect=d={duration}:pix_th={threshold}",
            "-f",
            "null",
            "-",
        ]

        try:
            result = run_safe(
                cmd,
                timeout=60,
                check=False,
                capture_output=True,
                log_label="ffmpeg blackdetect",
            )

            if result.returncode not in (0, 1):
                # FFmpeg returns 1 for some non-fatal errors
                logger.warning(f"ffmpeg blackdetect failed with code {result.returncode}")
                return []

            # Parse black frame timestamps from stderr
            black_frames = []
            pattern = r"black_start:(\d+\.?\d*)"

            for match in re.finditer(pattern, result.stderr):
                timestamp = float(match.group(1))
                black_frames.append(timestamp)

            logger.debug(f"Detected {len(black_frames)} black frames in {video_path}")
            return black_frames

        except (MissingToolError, SafeSubprocessError) as exc:
            logger.warning(f"ffmpeg blackdetect failed for {video_path}: {exc}")
            return []
        except (ValueError, AttributeError) as exc:
            logger.warning(f"Failed to parse blackdetect output: {exc}")
            return []

    def filter_black_frames(
        self,
        timestamps: list[float],
        black_frames: list[float],
        tolerance: float = 2.0,
    ) -> list[float]:
        """Filter timestamps to remove those near black frames.

        Args:
            timestamps: List of candidate timestamps
            black_frames: List of black frame timestamps
            tolerance: Tolerance in seconds (remove if within this range)

        Returns:
            Filtered list of timestamps
        """
        if not black_frames:
            return timestamps

        filtered = []
        for ts in timestamps:
            # Check if timestamp is too close to any black frame
            is_near_black = any(abs(ts - black_ts) <= tolerance for black_ts in black_frames)

            if not is_near_black:
                filtered.append(ts)

        return filtered
