"""Video extraction and conversion using FFmpeg."""

from __future__ import annotations

import re
import subprocess  # nosec B404
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from loguru import logger

from ouro.core.path_validation import PathValidationError, validate_file_path
from ouro.core.subprocess_safe import (
    MissingToolError,
    SafeSubprocessError,
    popen_safe,
    run_safe,
)
from ouro.core.tools import ToolRegistry
from ouro.modules.extract.models import (
    ExtractionResult,
    VideoCodec,
    VideoExtractionOptions,
    VideoTrack,
)


class VideoExtractor:
    """Extracts and converts video streams from video files.

    Handles:
    - Video stream extraction using FFmpeg
    - Codec conversion (H.264, H.265, VP9, AV1)
    - Resolution adjustment using scale filter
    - Quality control (CRF, bitrate)
    - Secure subprocess execution (no shell=True)
    - Path validation and sanitization
    - Integration with ScreenshotExtractor for frame extraction
    """

    # Codec to VideoCodec mapping
    CODEC_MAP = {
        "h264": VideoCodec.H264,
        "avc": VideoCodec.H264,
        "h265": VideoCodec.H265,
        "hevc": VideoCodec.H265,
        "vp9": VideoCodec.VP9,
        "av1": VideoCodec.AV1,
        "av01": VideoCodec.AV1,
        "mpeg2": VideoCodec.MPEG2,
        "mpeg2video": VideoCodec.MPEG2,
        "mpeg4": VideoCodec.MPEG4,
        "vc1": VideoCodec.VC1,
    }

    # VideoCodec to FFmpeg codec name mapping
    FFMPEG_CODEC_MAP = {
        VideoCodec.H264: "libx264",
        VideoCodec.H265: "libx265",
        VideoCodec.HEVC: "libx265",
        VideoCodec.VP9: "libvpx-vp9",
        VideoCodec.AV1: "libaom-av1",
        VideoCodec.MPEG2: "mpeg2video",
        VideoCodec.MPEG4: "mpeg4",
        VideoCodec.COPY: "copy",
    }

    # Codec to file extension mapping
    EXTENSION_MAP = {
        VideoCodec.H264: ".mp4",
        VideoCodec.H265: ".mp4",
        VideoCodec.HEVC: ".mp4",
        VideoCodec.VP9: ".webm",
        VideoCodec.AV1: ".mp4",
        VideoCodec.MPEG2: ".mpg",
        VideoCodec.MPEG4: ".mp4",
        VideoCodec.COPY: ".mkv",
    }

    # Valid encoding presets
    VALID_PRESETS = {
        "ultrafast",
        "superfast",
        "veryfast",
        "faster",
        "fast",
        "medium",
        "slow",
        "slower",
        "veryslow",
    }

    def __init__(self, registry: ToolRegistry) -> None:
        """Initialize video extractor.

        Args:
            registry: Tool registry for FFmpeg resolution
        """
        self.registry = registry

    def detect_video_codec(self, codec: str) -> VideoCodec:
        """Detect video codec from codec name.

        Args:
            codec: Codec name (e.g., 'h264', 'hevc', 'vp9')

        Returns:
            Detected video codec
        """
        codec_lower = codec.lower()
        return self.CODEC_MAP.get(codec_lower, VideoCodec.UNKNOWN)

    def get_ffmpeg_codec_name(self, codec: VideoCodec) -> str:
        """Get FFmpeg codec name from VideoCodec.

        Args:
            codec: Video codec enum

        Returns:
            FFmpeg codec name
        """
        return self.FFMPEG_CODEC_MAP.get(codec, "copy")

    def get_output_extension(self, codec: VideoCodec) -> str:
        """Get output file extension for codec.

        Args:
            codec: Video codec enum

        Returns:
            File extension including dot (e.g., '.mp4')
        """
        return self.EXTENSION_MAP.get(codec, ".mkv")

    def validate_crf_value(self, crf: int, codec: VideoCodec) -> None:
        """Validate CRF value for codec.

        Args:
            crf: CRF value to validate
            codec: Video codec

        Raises:
            ValueError: If CRF value is invalid
        """
        if not 0 <= crf <= 51:
            raise ValueError(f"CRF must be between 0 and 51, got {crf}")

    def validate_bitrate_value(self, bitrate: str) -> None:
        """Validate bitrate value to prevent injection.

        Args:
            bitrate: Bitrate string (e.g., '5M', '2000k')

        Raises:
            ValueError: If bitrate format is invalid or unsafe
        """
        # Only allow digits followed by optional k/M/G suffix
        if not re.match(r"^\d+[kMG]?$", bitrate):
            raise ValueError(
                f"Invalid bitrate format: {bitrate}. "
                "Must be digits optionally followed by k, M, or G"
            )

    def validate_preset_value(self, preset: str) -> None:
        """Validate encoding preset value.

        Args:
            preset: Encoding preset

        Raises:
            ValueError: If preset is invalid
        """
        if preset not in self.VALID_PRESETS:
            raise ValueError(
                f"Invalid preset: {preset}. Must be one of: {', '.join(sorted(self.VALID_PRESETS))}"
            )

    def build_extraction_command(
        self,
        video_path: Path,
        output_path: Path,
        track: VideoTrack,
        options: VideoExtractionOptions,
    ) -> list[str]:
        """Build FFmpeg command for video extraction.

        Security: Uses list-form arguments (no shell=True) and validates all paths.

        Args:
            video_path: Path to input video
            output_path: Path to output file
            track: Video track information
            options: Extraction options

        Returns:
            Command as list of strings

        Raises:
            PathValidationError: If paths are invalid or unsafe
            ValueError: If parameters are invalid
        """
        video_path, output_path = self._validate_paths(video_path, output_path)
        cmd = self._build_base_command(video_path, track)
        self._append_video_encoding_options(cmd, options)
        cmd.append(str(output_path))
        return cmd

    def _validate_paths(self, video_path: Path, output_path: Path) -> tuple[Path, Path]:
        try:
            valid_video_path = validate_file_path(video_path, must_exist=True)
        except (PathValidationError, FileNotFoundError) as exc:
            raise PathValidationError(f"Invalid video path: {exc}") from exc

        try:
            valid_output_path = validate_file_path(output_path, must_exist=False)
        except PathValidationError as exc:
            raise PathValidationError(f"Invalid output path: {exc}") from exc
        return valid_video_path, valid_output_path

    def _build_base_command(self, video_path: Path, track: VideoTrack) -> list[str]:
        ffmpeg = self.registry.resolve_tool_path("ffmpeg") or "ffmpeg"
        return [
            ffmpeg,
            "-i",
            str(video_path),
            "-map",
            f"0:v:{track.track_id}",
        ]

    def _append_video_encoding_options(
        self,
        cmd: list[str],
        options: VideoExtractionOptions,
    ) -> None:
        if options.output_codec == VideoCodec.COPY:
            cmd.extend(["-c:v", "copy"])
            return

        cmd.extend(["-c:v", self.get_ffmpeg_codec_name(options.output_codec)])
        self._append_quality_options(cmd, options)
        self.validate_preset_value(options.preset)
        cmd.extend(["-preset", options.preset])
        scale_filter = self._build_scale_filter(options)
        if scale_filter:
            cmd.extend(["-vf", scale_filter])

    def _append_quality_options(
        self,
        cmd: list[str],
        options: VideoExtractionOptions,
    ) -> None:
        if options.crf is not None:
            self.validate_crf_value(options.crf, options.output_codec)
            cmd.extend(["-crf", str(options.crf)])
            return
        if options.bitrate is not None:
            self.validate_bitrate_value(options.bitrate)
            cmd.extend(["-b:v", options.bitrate])
            return
        default_crf = options.get_default_crf(options.output_codec)
        cmd.extend(["-crf", str(default_crf)])

    def _build_scale_filter(self, options: VideoExtractionOptions) -> str | None:
        if options.width is None and options.height is None:
            return None
        if options.width and options.height:
            return f"scale={options.width}:{options.height}"
        if options.width:
            return f"scale={options.width}:-1"
        return f"scale=-1:{options.height}"

    def extract_video(
        self,
        video_path: Path,
        output_path: Path,
        track: VideoTrack,
        options: VideoExtractionOptions,
        progress_callback: Callable[[float], None] | None = None,
        expected_duration_seconds: float | None = None,
    ) -> ExtractionResult:
        """Extract video stream from file.

        Args:
            video_path: Path to input video
            output_path: Path to output file
            track: Video track information
            options: Extraction options

        Returns:
            Extraction result with success status and metadata
        """
        try:
            # Build extraction command
            cmd = self.build_extraction_command(video_path, output_path, track, options)

            logger.debug(f"Extracting video with command: {' '.join(cmd)}")

            # Execute FFmpeg via subprocess_safe wrapper:
            # full-path resolution, shell=False, mandatory timeout, UTF-8.
            try:
                result = self._execute_video_command(
                    cmd,
                    progress_callback=progress_callback,
                    expected_duration_seconds=expected_duration_seconds,
                )
            except (MissingToolError, SafeSubprocessError) as exc:
                error_msg = f"FFmpeg failed: {exc}"
                logger.error(error_msg)
                return ExtractionResult(
                    track=track,
                    source_file=video_path,
                    output_file=output_path,
                    success=False,
                    error=error_msg,
                    format_converted=False,
                    original_format=None,
                    normalized=False,
                    codec_converted=False,
                    resolution_changed=False,
                )

            if result.returncode != 0:
                error_msg = f"FFmpeg failed: {result.stderr}"
                logger.error(error_msg)
                return ExtractionResult(
                    track=track,
                    source_file=video_path,
                    output_file=output_path,
                    success=False,
                    error=error_msg,
                    format_converted=False,
                    original_format=None,
                    normalized=False,
                    codec_converted=False,
                    resolution_changed=False,
                )

            # Determine what operations were performed
            codec_converted = options.output_codec != VideoCodec.COPY
            resolution_changed = options.width is not None or options.height is not None

            logger.info(f"Successfully extracted video to {output_path}")

            return ExtractionResult(
                track=track,
                source_file=video_path,
                output_file=output_path,
                success=True,
                error=None,
                format_converted=False,
                original_format=track.codec if codec_converted else None,
                normalized=False,
                codec_converted=codec_converted,
                resolution_changed=resolution_changed,
            )

        except PathValidationError as exc:
            error_msg = f"Path validation failed: {exc}"
            logger.error(error_msg)
            return ExtractionResult(
                track=track,
                source_file=video_path,
                output_file=output_path,
                success=False,
                error=error_msg,
                format_converted=False,
                original_format=None,
                normalized=False,
                codec_converted=False,
                resolution_changed=False,
            )

        except ValueError as exc:
            error_msg = f"Invalid parameter: {exc}"
            logger.error(error_msg)
            return ExtractionResult(
                track=track,
                source_file=video_path,
                output_file=output_path,
                success=False,
                error=error_msg,
                format_converted=False,
                original_format=None,
                normalized=False,
                codec_converted=False,
                resolution_changed=False,
            )

        except Exception as exc:
            error_msg = f"Unexpected error during video extraction: {exc}"
            logger.exception(error_msg)
            return ExtractionResult(
                track=track,
                source_file=video_path,
                output_file=output_path,
                success=False,
                error=error_msg,
                format_converted=False,
                original_format=None,
                normalized=False,
                codec_converted=False,
                resolution_changed=False,
            )

    def _execute_video_command(
        self,
        command: list[str],
        *,
        progress_callback: Callable[[float], None] | None = None,
        expected_duration_seconds: float | None = None,
    ):
        if progress_callback is None:
            return run_safe(
                command,
                timeout=3600,
                check=False,
                capture_output=True,
                log_label="ffmpeg video extract",
            )
        self._run_video_with_progress(
            command,
            progress_callback=progress_callback,
            expected_duration_seconds=expected_duration_seconds,
            timeout=3600.0,
        )

        class _Completed:
            returncode = 0
            stderr = ""

        return _Completed()

    def _run_video_with_progress(
        self,
        command: list[str],
        *,
        progress_callback: Callable[[float], None],
        expected_duration_seconds: float | None,
        timeout: float,
    ) -> None:
        progress_file = tempfile.NamedTemporaryFile(
            suffix=".progress",
            prefix="ouro_extract_video_",
            delete=False,
        )
        progress_path = Path(progress_file.name)
        progress_file.close()
        ffmpeg_command = [*command[:-1], "-nostats", "-progress", str(progress_path), command[-1]]
        process = popen_safe(
            ffmpeg_command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            log_label="ffmpeg video extract",
        )

        started = time.monotonic()
        last_position = 0
        try:
            while process.poll() is None:
                last_position = self._read_progress_file(
                    progress_path=progress_path,
                    last_position=last_position,
                    expected_duration_seconds=expected_duration_seconds,
                    progress_callback=progress_callback,
                )
                if (time.monotonic() - started) > timeout:
                    process.kill()
                    process.wait()
                    raise SafeSubprocessError(
                        f"ffmpeg video extract: timed out after {timeout:.0f}s",
                        tool=str(ffmpeg_command[0]),
                        argv=tuple(ffmpeg_command),
                        returncode=None,
                        stderr="",
                    )
                time.sleep(0.25)

            last_position = self._read_progress_file(
                progress_path=progress_path,
                last_position=last_position,
                expected_duration_seconds=expected_duration_seconds,
                progress_callback=progress_callback,
            )
            stderr_output = ""
            if process.stderr is not None:
                stderr_output = process.stderr.read() or ""
            if process.returncode != 0:
                raise SafeSubprocessError(
                    f"ffmpeg video extract: exited {process.returncode}",
                    tool=str(ffmpeg_command[0]),
                    argv=tuple(ffmpeg_command),
                    returncode=process.returncode,
                    stderr=stderr_output,
                )
        finally:
            try:
                progress_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _read_progress_file(
        self,
        *,
        progress_path: Path,
        last_position: int,
        expected_duration_seconds: float | None,
        progress_callback: Callable[[float], None],
    ) -> int:
        try:
            with progress_path.open(encoding="utf-8", errors="replace") as handle:
                handle.seek(last_position)
                content = handle.read()
                new_position = handle.tell()
        except FileNotFoundError:
            return last_position
        except OSError:
            return last_position

        for line in content.splitlines():
            key, _sep, value = line.partition("=")
            if not value:
                continue
            if key == "out_time_ms":
                try:
                    seconds = max(float(value) / 1_000_000.0, 0.0)
                except ValueError:
                    continue
                self._emit_track_progress(progress_callback, seconds, expected_duration_seconds)
                continue
            if key == "out_time":
                seconds = self._parse_ffmpeg_timestamp(value)
                if seconds is not None:
                    self._emit_track_progress(progress_callback, seconds, expected_duration_seconds)
        return new_position

    def _emit_track_progress(
        self,
        progress_callback: Callable[[float], None],
        seconds: float,
        expected_duration_seconds: float | None,
    ) -> None:
        if not expected_duration_seconds or expected_duration_seconds <= 0:
            return
        percentage = min(max((seconds / expected_duration_seconds) * 100.0, 0.0), 99.5)
        progress_callback(percentage)

    def _parse_ffmpeg_timestamp(self, value: str) -> float | None:
        raw = value.strip()
        if not raw:
            return None
        parts = raw.split(":")
        if len(parts) != 3:
            return None
        try:
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
        except ValueError:
            return None
        return (hours * 3600.0) + (minutes * 60.0) + seconds
