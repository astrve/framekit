"""Validation utilities for the Encoder module."""

import json
import subprocess  # nosec B404
from pathlib import Path

from swirrl.core.subprocess_safe import MissingToolError, SafeSubprocessError, run_safe

from .models import MediaInfo, ValidationResult


class EncoderValidator:
    """Validate encoding operations."""

    def __init__(self, ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe"):
        """Initialize validator.

        Args:
            ffmpeg_path: Path to ffmpeg executable
            ffprobe_path: Path to ffprobe executable
        """
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path

    def check_ffmpeg_available(self) -> ValidationResult:
        """Check if ffmpeg is available.

        Returns:
            ValidationResult indicating if ffmpeg is available
        """
        result = ValidationResult(valid=True)

        try:
            run_safe(
                [self.ffmpeg_path, "-version"],
                timeout=5,
                check=True,
                log_label="ffmpeg version probe",
            )
        except (MissingToolError, SafeSubprocessError):
            result.add_error("ffmpeg not found or not working. Please install ffmpeg.")

        return result

    def check_ffprobe_available(self) -> ValidationResult:
        """Check if ffprobe is available.

        Returns:
            ValidationResult indicating if ffprobe is available
        """
        result = ValidationResult(valid=True)

        try:
            run_safe(
                [self.ffprobe_path, "-version"],
                timeout=5,
                check=True,
                log_label="ffprobe version probe",
            )
        except (MissingToolError, SafeSubprocessError):
            result.add_error("ffprobe not found or not working. Please install ffmpeg.")

        return result

    def validate_input_file(
        self, file_path: Path, expected_codec: str | None = None
    ) -> ValidationResult:
        """Validate input file before encoding.

        Args:
            file_path: Path to input file
            expected_codec: Expected codec (h264 or h265), if None, any codec is accepted

        Returns:
            ValidationResult with validation status
        """
        result = ValidationResult(valid=True)

        # Check file exists
        if not file_path.exists():
            result.add_error(f"Input file not found: {file_path}")
            return result

        # Check file is readable
        if not file_path.is_file():
            result.add_error(f"Input path is not a file: {file_path}")
            return result

        # Get media info
        try:
            media_info = self.get_media_info(file_path)

            # Check codec if specified
            if expected_codec and media_info.codec.lower() not in [
                expected_codec.lower(),
                f"lib{expected_codec.lower()}",
            ]:
                result.add_warning(
                    f"Input codec is {media_info.codec}, expected {expected_codec}. "
                    "Encoding may still work but preset may not be optimal."
                )

            # Check duration
            if media_info.duration <= 0:
                result.add_error("Invalid video duration")

            # Check resolution
            if media_info.width <= 0 or media_info.height <= 0:
                result.add_error("Invalid video resolution")

        except Exception as e:
            result.add_error(f"Failed to analyze input file: {e!s}")

        return result

    def validate_output_file(
        self, file_path: Path, expected_duration: float, tolerance: float = 1.0
    ) -> ValidationResult:
        """Validate output file after encoding.

        Args:
            file_path: Path to output file
            expected_duration: Expected duration in seconds
            tolerance: Tolerance for duration comparison in seconds

        Returns:
            ValidationResult with validation status
        """
        result = ValidationResult(valid=True)

        # Check file exists
        if not file_path.exists():
            result.add_error(f"Output file not found: {file_path}")
            return result

        # Check file size
        if file_path.stat().st_size == 0:
            result.add_error("Output file is empty")
            return result

        # Get media info
        try:
            media_info = self.get_media_info(file_path)

            # Check duration matches
            duration_diff = abs(media_info.duration - expected_duration)
            if duration_diff > tolerance:
                result.add_error(
                    f"Output duration ({media_info.duration:.2f}s) differs from input "
                    f"({expected_duration:.2f}s) by {duration_diff:.2f}s"
                )

            # Check video stream exists
            if media_info.width <= 0 or media_info.height <= 0:
                result.add_error("Output file has no valid video stream")

        except Exception as e:
            result.add_error(f"Failed to validate output file: {e!s}")

        return result

    def _ffprobe_command(self, file_path: Path) -> list[str]:
        return [
            self.ffprobe_path,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(file_path),
        ]

    def _parse_stream_stats(self, streams: list[dict]) -> tuple[dict | None, int, int]:
        video_stream: dict | None = None
        audio_count = 0
        subtitle_count = 0
        for stream in streams:
            codec_type = stream.get("codec_type")
            if codec_type == "video" and video_stream is None:
                video_stream = stream
                continue
            if codec_type == "audio":
                audio_count += 1
                continue
            if codec_type == "subtitle":
                subtitle_count += 1
        return video_stream, audio_count, subtitle_count

    def _parse_fps(self, fps_str: str) -> float:
        if "/" not in fps_str:
            return float(fps_str)
        num, den = map(int, fps_str.split("/"))
        return num / den if den != 0 else 0.0

    def _build_media_info_from_data(self, file_path: Path, data: dict) -> MediaInfo:
        streams = data.get("streams", [])
        if not isinstance(streams, list):
            streams = []
        typed_streams = [stream for stream in streams if isinstance(stream, dict)]
        video_stream, audio_count, subtitle_count = self._parse_stream_stats(typed_streams)
        if video_stream is None:
            raise RuntimeError("No video stream found")

        fmt = data.get("format", {})
        if not isinstance(fmt, dict):
            fmt = {}
        codec = str(video_stream.get("codec_name", "unknown"))
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        fps = self._parse_fps(str(video_stream.get("r_frame_rate", "0/1")))
        duration = float(fmt.get("duration", 0))
        bitrate = int(fmt.get("bit_rate", 0))
        size = int(fmt.get("size", 0))
        return MediaInfo(
            path=file_path,
            codec=codec,
            duration=duration,
            width=width,
            height=height,
            fps=fps,
            bitrate=bitrate,
            size=size,
            audio_tracks=audio_count,
            subtitle_tracks=subtitle_count,
        )

    def get_media_info(self, file_path: Path) -> MediaInfo:
        """Get media information using ffprobe.

        Args:
            file_path: Path to media file

        Returns:
            MediaInfo object

        Raises:
            RuntimeError: If ffprobe fails
        """
        cmd = self._ffprobe_command(file_path)

        try:
            # ``run_safe`` enforces shell=False, absolute-path resolution, and
            # a mandatory timeout; ``check=True`` raises ``SafeSubprocessError``
            # which the broader ``except`` chain below translates into a
            # ``RuntimeError`` for callers.
            completed = run_safe(
                cmd,
                timeout=30,
                check=True,
                capture_output=True,
                log_label="ffprobe media info",
            )

            data = json.loads(completed.stdout)
            if not isinstance(data, dict):
                raise RuntimeError("Invalid ffprobe response structure")
            return self._build_media_info_from_data(file_path, data)

        except MissingToolError as exc:
            raise RuntimeError(f"ffprobe not found: {exc}") from exc
        except SafeSubprocessError as exc:
            raise RuntimeError(f"ffprobe failed: {exc.stderr or exc}") from exc
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"ffprobe failed: {e.stderr}") from e
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("ffprobe timed out") from exc
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse ffprobe output: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to get media info: {e}") from e

    def compare_files(self, input_file: Path, output_file: Path) -> dict:
        """Compare input and output files.

        Args:
            input_file: Path to input file
            output_file: Path to output file

        Returns:
            Dictionary with comparison results
        """
        input_info = self.get_media_info(input_file)
        output_info = self.get_media_info(output_file)

        compression_ratio = (
            (1 - (output_info.size / input_info.size)) * 100 if input_info.size > 0 else 0
        )

        return {
            "input_size": input_info.size,
            "output_size": output_info.size,
            "space_saved": input_info.size - output_info.size,
            "compression_ratio": compression_ratio,
            "input_codec": input_info.codec,
            "output_codec": output_info.codec,
            "duration_match": abs(input_info.duration - output_info.duration) < 1.0,
            "resolution_match": (
                input_info.width == output_info.width and input_info.height == output_info.height
            ),
            "audio_tracks_preserved": input_info.audio_tracks == output_info.audio_tracks,
            "subtitle_tracks_preserved": input_info.subtitle_tracks == output_info.subtitle_tracks,
        }
