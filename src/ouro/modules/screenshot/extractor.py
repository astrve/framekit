"""Screenshot extraction using FFmpeg."""

from __future__ import annotations

import subprocess  # nosec B404
from collections.abc import Callable
from pathlib import Path

from loguru import logger

from ouro.core.path_validation import PathValidationError, validate_file_path
from ouro.core.subprocess_safe import MissingToolError, SafeSubprocessError, run_safe
from ouro.core.tools import ToolRegistry


class ScreenshotExtractor:
    """Extracts screenshots from video files using FFmpeg.

    Handles:
    - Single screenshot extraction at specific timestamp
    - Multiple screenshot extraction with progress reporting
    - Secure subprocess execution (no shell=True)
    - Path validation and sanitization
    - Error handling and graceful degradation
    """

    def __init__(self, registry: ToolRegistry) -> None:
        """Initialize screenshot extractor.

        Args:
            registry: Tool registry for FFmpeg resolution
        """
        self.registry = registry

    def build_ffmpeg_command(
        self,
        video_path: Path,
        output_path: Path,
        timestamp: float,
        width: int | None = None,
        height: int | None = None,
        quality: int = 2,
    ) -> list[str]:
        """Build FFmpeg command for screenshot extraction.

        Security: Uses list-form arguments (no shell=True) and validates all paths.

        Args:
            video_path: Path to input video
            output_path: Path to output screenshot
            timestamp: Timestamp in seconds
            width: Target width (None = original)
            height: Target height (None = original)
            quality: JPEG quality (1=best, 31=worst)

        Returns:
            Command as list of strings

        Raises:
            PathValidationError: If paths are invalid or unsafe
            ValueError: If parameters are invalid
        """
        # Validate paths
        try:
            video_path = validate_file_path(video_path, must_exist=True)
        except (PathValidationError, FileNotFoundError) as exc:
            raise PathValidationError(f"Invalid video path: {exc}") from exc

        try:
            output_path = validate_file_path(output_path, must_exist=False)
        except PathValidationError as exc:
            raise PathValidationError(f"Invalid output path: {exc}") from exc

        # Get FFmpeg path
        ffmpeg = self.registry.resolve_tool_path("ffmpeg")
        if not ffmpeg:
            ffmpeg = "ffmpeg"  # Fallback to PATH

        # Build command (list form for security)
        cmd = [
            ffmpeg,
            "-ss",
            str(timestamp),  # Seek to timestamp
            "-i",
            str(video_path),  # Input file
            "-frames:v",
            "1",  # Extract single frame
            "-q:v",
            str(quality),  # Quality setting
        ]

        # Add scaling if specified
        if width is not None or height is not None:
            if width and height:
                scale_filter = f"scale={width}:{height}"
            elif width:
                scale_filter = f"scale={width}:-1"
            else:
                scale_filter = f"scale=-1:{height}"

            cmd.extend(["-vf", scale_filter])

        # Add output path
        cmd.append(str(output_path))

        return cmd

    @staticmethod
    def _output_created(output_path: Path) -> bool:
        if output_path.exists():
            return True
        logger.warning(f"FFmpeg succeeded but output file not created: {output_path}")
        return False

    @staticmethod
    def _handle_safe_subprocess_error(
        exc: SafeSubprocessError,
        *,
        cmd: list[str],
        timeout: int,
    ) -> bool:
        if exc.returncode is None:
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout) from exc
        logger.warning(f"FFmpeg failed: {exc.stderr or exc}")
        return False

    def _run_ffmpeg_command(self, cmd: list[str], *, timeout: int) -> bool:
        try:
            result = run_safe(
                cmd,
                timeout=timeout,
                check=False,
                capture_output=True,
                log_label="ffmpeg screenshot",
            )
        except MissingToolError:
            logger.warning("FFmpeg not on PATH; cannot extract screenshot")
            return False
        except SafeSubprocessError as exc:
            return self._handle_safe_subprocess_error(exc, cmd=cmd, timeout=timeout)

        if result.returncode != 0:
            logger.warning(f"FFmpeg failed (code {result.returncode}): {result.stderr[:200]}")
            return False
        return True

    def extract_screenshot(
        self,
        video_path: Path,
        output_path: Path,
        timestamp: float,
        width: int | None = None,
        height: int | None = None,
        quality: int = 2,
        timeout: int = 30,
    ) -> bool:
        """Extract a single screenshot from video.

        Args:
            video_path: Path to input video
            output_path: Path to output screenshot
            timestamp: Timestamp in seconds
            width: Target width (None = original)
            height: Target height (None = original)
            quality: JPEG quality (1=best, 31=worst)
            timeout: Timeout in seconds

        Returns:
            True if extraction succeeded, False otherwise
        """
        try:
            cmd = self.build_ffmpeg_command(
                video_path=video_path,
                output_path=output_path,
                timestamp=timestamp,
                width=width,
                height=height,
                quality=quality,
            )
            if not self._run_ffmpeg_command(cmd, timeout=timeout):
                return False
            if not self._output_created(output_path):
                return False

            logger.debug(f"Extracted screenshot at {timestamp}s to {output_path}")
            return True

        except subprocess.TimeoutExpired:
            logger.warning(f"FFmpeg timeout after {timeout}s for {video_path}")
            return False
        except (PathValidationError, ValueError) as exc:
            logger.error(f"Path validation error: {exc}")
            return False
        except (PermissionError, OSError) as exc:
            logger.error(f"File system error: {exc}")
            return False
        except Exception as exc:
            logger.error(f"Unexpected error during screenshot extraction: {exc}")
            return False

    def extract_multiple(
        self,
        video_path: Path,
        timestamps: list[float],
        output_paths: list[Path],
        width: int | None = None,
        height: int | None = None,
        quality: int = 2,
        timeout: int = 30,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[bool]:
        """Extract multiple screenshots from video.

        Args:
            video_path: Path to input video
            timestamps: List of timestamps in seconds
            output_paths: List of output paths (must match timestamps length)
            width: Target width (None = original)
            height: Target height (None = original)
            quality: JPEG quality (1=best, 31=worst)
            timeout: Timeout per screenshot in seconds
            progress_callback: Optional callback(current, total) for progress

        Returns:
            List of success flags (True/False) for each screenshot
        """
        if len(timestamps) != len(output_paths):
            raise ValueError("timestamps and output_paths must have same length")

        results = []
        total = len(timestamps)

        for i, (timestamp, output_path) in enumerate(
            zip(timestamps, output_paths, strict=True), start=1
        ):
            success = self.extract_screenshot(
                video_path=video_path,
                output_path=output_path,
                timestamp=timestamp,
                width=width,
                height=height,
                quality=quality,
                timeout=timeout,
            )

            results.append(success)

            # Report progress
            if progress_callback:
                progress_callback(i, total)

        return results
