"""Audio extraction and conversion using FFmpeg."""

from __future__ import annotations

import re
import subprocess  # nosec B404
from pathlib import Path

from loguru import logger

from framekit.core.path_validation import PathValidationError, validate_file_path
from framekit.core.subprocess_safe import MissingToolError, SafeSubprocessError, run_safe
from framekit.core.tools import ToolRegistry
from framekit.modules.extract.models import (
    AudioExtractionOptions,
    AudioFormat,
    AudioTrack,
    ExtractionResult,
)


class AudioExtractor:
    """Extracts and converts audio tracks from video files.

    Handles:
    - Audio extraction using FFmpeg
    - Format conversion between audio formats (AAC, MP3, FLAC, Opus, etc.)
    - Bitrate control for lossy formats
    - Audio normalization using loudnorm filter
    - Language and codec filtering
    - Multi-channel audio support
    - Secure subprocess execution (no shell=True)
    - Path validation and sanitization
    """

    # Codec to format mapping
    CODEC_FORMAT_MAP = {
        "aac": AudioFormat.AAC,
        "mp3": AudioFormat.MP3,
        "flac": AudioFormat.FLAC,
        "alac": AudioFormat.ALAC,
        "pcm": AudioFormat.WAV,
        "opus": AudioFormat.OPUS,
        "vorbis": AudioFormat.VORBIS,
        "ac3": AudioFormat.AC3,
        "eac3": AudioFormat.EAC3,
        "e-ac-3": AudioFormat.EAC3,
        "dts": AudioFormat.DTS,
        "dts-hd": AudioFormat.DTS_HD,
        "dts-ma": AudioFormat.DTS_HD,
        "truehd": AudioFormat.TRUEHD,
    }

    # Format to FFmpeg codec mapping
    FORMAT_CODEC_MAP = {
        AudioFormat.AAC: "aac",
        AudioFormat.MP3: "libmp3lame",
        AudioFormat.FLAC: "flac",
        AudioFormat.ALAC: "alac",
        AudioFormat.WAV: "pcm_s16le",
        AudioFormat.OPUS: "libopus",
        AudioFormat.VORBIS: "libvorbis",
        AudioFormat.AC3: "ac3",
        AudioFormat.EAC3: "eac3",
        AudioFormat.DTS: "dts",
    }

    # Lossless formats
    LOSSLESS_FORMATS = {
        AudioFormat.FLAC,
        AudioFormat.ALAC,
        AudioFormat.WAV,
    }

    # Default bitrates for lossy formats (in kbps)
    DEFAULT_BITRATES = {
        AudioFormat.AAC: "192k",
        AudioFormat.MP3: "192k",
        AudioFormat.OPUS: "128k",
        AudioFormat.VORBIS: "192k",
        AudioFormat.AC3: "640k",
        AudioFormat.EAC3: "768k",
    }

    def __init__(self, registry: ToolRegistry) -> None:
        """Initialize audio extractor.

        Args:
            registry: Tool registry for FFmpeg resolution
        """
        self.registry = registry

    def detect_audio_format(self, codec: str) -> AudioFormat:
        """Detect audio format from codec name.

        Args:
            codec: Codec name (e.g., 'aac', 'mp3', 'ac3')

        Returns:
            Detected audio format
        """
        codec_lower = codec.lower()
        return self.CODEC_FORMAT_MAP.get(codec_lower, AudioFormat.AAC)

    def can_convert_format(
        self,
        source_format: AudioFormat,
        target_format: AudioFormat,
    ) -> bool:
        """Check if format conversion is supported.

        Args:
            source_format: Source audio format
            target_format: Target audio format

        Returns:
            True if conversion is supported
        """
        # Same format doesn't need conversion
        if source_format == target_format:
            return False

        # All conversions are technically supported by FFmpeg
        return True

    def is_lossless_format(self, format: AudioFormat) -> bool:
        """Check if format is lossless.

        Args:
            format: Audio format to check

        Returns:
            True if format is lossless
        """
        return format in self.LOSSLESS_FORMATS

    def get_default_bitrate(self, format: AudioFormat) -> str | None:
        """Get default bitrate for a format.

        Args:
            format: Audio format

        Returns:
            Default bitrate string (e.g., '192k') or None for lossless
        """
        return self.DEFAULT_BITRATES.get(format)

    def validate_bitrate(self, bitrate: str) -> str:
        """Validate bitrate format.

        Args:
            bitrate: Bitrate string (e.g., '192k', '320k')

        Returns:
            Validated bitrate string

        Raises:
            ValueError: If bitrate format is invalid
        """
        # Match pattern like '128k', '192k', '320k'
        pattern = r"^(\d+)k$"
        match = re.match(pattern, bitrate)

        if not match:
            raise ValueError(f"Invalid bitrate format: {bitrate}. Expected format: '192k'")

        # Check reasonable range (32k to 640k for most formats)
        value = int(match.group(1))
        if value < 32 or value > 640:
            raise ValueError(f"Invalid bitrate format: {bitrate}. Range: 32k-640k")

        return bitrate

    def build_extraction_command(
        self,
        video_path: Path,
        track: AudioTrack,
        output_path: Path,
        options: AudioExtractionOptions,
    ) -> list[str]:
        """Build FFmpeg command for audio extraction.

        Security: Uses list-form arguments (no shell=True) and validates all paths.

        Args:
            video_path: Path to input video
            track: Audio track to extract
            output_path: Path to output audio file
            options: Extraction options

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
            "-i",
            str(video_path),  # Input file
            "-map",
            f"0:a:{track.track_id}",  # Select audio track
        ]

        # Determine if we need conversion. ``_source_format`` is kept for
        # debug traceability (visible in tracebacks) but not referenced again.
        _source_format = self.detect_audio_format(track.codec)
        target_format = options.output_format

        if target_format == AudioFormat.ORIGINAL:
            # Copy mode - no conversion
            cmd.extend(["-c:a", "copy"])
        else:
            # Conversion mode
            codec = self.FORMAT_CODEC_MAP.get(target_format, "aac")
            cmd.extend(["-c:a", codec])

            # Add bitrate for lossy formats
            if not self.is_lossless_format(target_format):
                bitrate = options.bitrate
                if not bitrate:
                    bitrate = self.get_default_bitrate(target_format)

                if bitrate:
                    # Validate bitrate for security
                    bitrate = self.validate_bitrate(bitrate)
                    cmd.extend(["-b:a", bitrate])

        # Add output file
        cmd.append(str(output_path))

        return cmd

    def build_normalization_command(
        self,
        input_path: Path,
        output_path: Path,
        target_lufs: float,
        measured_input_i: float | None = None,
    ) -> list[str]:
        """Build FFmpeg command for audio normalization.

        Uses two-pass loudnorm filter for best results.

        Args:
            input_path: Path to input audio file
            output_path: Path to output normalized file
            target_lufs: Target LUFS level (e.g., -16.0)
            measured_input_i: Measured input integrated loudness (for second pass)

        Returns:
            Command as list of strings
        """
        # Get FFmpeg path
        ffmpeg = self.registry.resolve_tool_path("ffmpeg")
        if not ffmpeg:
            ffmpeg = "ffmpeg"

        cmd = [
            ffmpeg,
            "-i",
            str(input_path),
        ]

        # Build loudnorm filter
        if measured_input_i is None:
            # First pass - measure
            loudnorm_filter = f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11:print_format=summary"
        else:
            # Second pass - apply with measured values
            loudnorm_filter = (
                f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11:"
                f"measured_I={measured_input_i}:measured_TP=-1.5:measured_LRA=11:measured_thresh=-26.0:linear=true"
            )

        cmd.extend(
            [
                "-af",
                loudnorm_filter,
                str(output_path),
            ]
        )

        return cmd

    def extract_audio(
        self,
        video_path: Path,
        track: AudioTrack,
        output_path: Path,
        options: AudioExtractionOptions,
    ) -> ExtractionResult:
        """Extract audio track from video file.

        Args:
            video_path: Path to source video file
            track: Audio track to extract
            output_path: Path to output audio file
            options: Extraction options

        Returns:
            Extraction result with success status and metadata
        """
        try:
            video_path, output_path = self._validate_extraction_paths(video_path, output_path)
            source_format, needs_conversion = self._resolve_audio_format_state(track, options)
            self._run_extraction(video_path, track, output_path, options)
            normalized = self._maybe_normalize_audio(output_path, options)
            return self._success_result(
                track=track,
                source_file=video_path,
                output_file=output_path,
                format_converted=needs_conversion,
                original_format=source_format.value if needs_conversion else None,
                normalized=normalized,
            )

        except (subprocess.CalledProcessError, SafeSubprocessError, MissingToolError) as exc:
            return self._failure_result(
                track, video_path, output_path, exc, prefix="Extraction failed"
            )
        except Exception as exc:
            return self._failure_result(
                track, video_path, output_path, exc, prefix="Unexpected error"
            )

    def _validate_extraction_paths(self, video_path: Path, output_path: Path) -> tuple[Path, Path]:
        return (
            validate_file_path(video_path, must_exist=True),
            validate_file_path(output_path, must_exist=False),
        )

    def _resolve_audio_format_state(
        self,
        track: AudioTrack,
        options: AudioExtractionOptions,
    ) -> tuple[AudioFormat, bool]:
        source_format = self.detect_audio_format(track.codec)
        target_format = options.output_format
        if target_format == AudioFormat.ORIGINAL:
            target_format = source_format
        return source_format, self.can_convert_format(source_format, target_format)

    def _run_extraction(
        self,
        video_path: Path,
        track: AudioTrack,
        output_path: Path,
        options: AudioExtractionOptions,
    ) -> None:
        extract_cmd = self.build_extraction_command(
            video_path=video_path,
            track=track,
            output_path=output_path,
            options=options,
        )
        logger.debug(f"Extracting audio: {' '.join(extract_cmd)}")
        _result = run_safe(
            extract_cmd,
            timeout=3600,
            check=True,
            capture_output=True,
            log_label="ffmpeg audio extract",
        )

    def _maybe_normalize_audio(self, output_path: Path, options: AudioExtractionOptions) -> bool:
        if not options.normalize or not output_path.exists():
            return False
        return self._normalize_audio_file(output_path, options)

    def _normalize_audio_file(self, output_path: Path, options: AudioExtractionOptions) -> bool:
        try:
            logger.info(
                f"Applying audio normalization (target: {options.normalize_target_lufs} LUFS)"
            )
            temp_output = output_path.with_suffix(output_path.suffix + ".tmp")
            measured_i = self._measure_input_loudness(output_path, temp_output, options)
            if measured_i is None:
                logger.warning("Could not measure input loudness, skipping normalization")
                if temp_output.exists():
                    temp_output.unlink()
                return False
            self._apply_normalization(output_path, temp_output, options, measured_i)
            temp_output.replace(output_path)
            logger.info("Audio normalization applied successfully")
            return True
        except (subprocess.CalledProcessError, SafeSubprocessError) as exc:
            stderr = getattr(exc, "stderr", "") or getattr(exc, "stdout", "") or str(exc)
            logger.warning(f"Normalization failed: {stderr}")
            return False
        except Exception as exc:
            logger.warning(f"Normalization error: {exc}")
            return False

    def _measure_input_loudness(
        self,
        output_path: Path,
        temp_output: Path,
        options: AudioExtractionOptions,
    ) -> float | None:
        measure_cmd = self.build_normalization_command(
            input_path=output_path,
            output_path=temp_output,
            target_lufs=options.normalize_target_lufs,
        )
        logger.debug(f"Measuring loudness: {' '.join(measure_cmd)}")
        measure_result = run_safe(
            measure_cmd,
            timeout=3600,
            check=False,
            capture_output=True,
            log_label="ffmpeg loudnorm measure",
        )
        return self._extract_measured_input_i(measure_result.stderr)

    def _extract_measured_input_i(self, stderr_output: str) -> float | None:
        for line in stderr_output.split("\n"):
            if "input_i" not in line.lower():
                continue
            match = re.search(r"input_i[:\s]+(-?\d+\.?\d*)", line)
            if match:
                return float(match.group(1))
        return None

    def _apply_normalization(
        self,
        output_path: Path,
        temp_output: Path,
        options: AudioExtractionOptions,
        measured_i: float,
    ) -> None:
        normalize_cmd = self.build_normalization_command(
            input_path=output_path,
            output_path=temp_output,
            target_lufs=options.normalize_target_lufs,
            measured_input_i=measured_i,
        )
        logger.debug(f"Applying normalization: {' '.join(normalize_cmd)}")
        run_safe(
            normalize_cmd,
            timeout=3600,
            check=True,
            capture_output=True,
            log_label="ffmpeg loudnorm apply",
        )

    def _success_result(
        self,
        *,
        track: AudioTrack,
        source_file: Path,
        output_file: Path,
        format_converted: bool,
        original_format: str | None,
        normalized: bool,
    ) -> ExtractionResult:
        return ExtractionResult(
            track=track,
            source_file=source_file,
            output_file=output_file,
            success=True,
            error=None,
            format_converted=format_converted,
            original_format=original_format,
            normalized=normalized,
        )

    def _failure_result(
        self,
        track: AudioTrack,
        source_file: Path,
        output_file: Path,
        exc: Exception,
        *,
        prefix: str,
    ) -> ExtractionResult:
        stderr = getattr(exc, "stderr", "") or getattr(exc, "stdout", "") or str(exc)
        error_msg = f"{prefix}: {stderr}"
        logger.error(error_msg)
        return ExtractionResult(
            track=track,
            source_file=source_file,
            output_file=output_file,
            success=False,
            error=error_msg,
            format_converted=False,
            original_format=None,
            normalized=False,
        )

    def filter_tracks(
        self,
        tracks: list[AudioTrack],
        options: AudioExtractionOptions,
    ) -> list[AudioTrack]:
        """Filter audio tracks based on extraction options.

        Args:
            tracks: List of audio tracks
            options: Extraction options with filter criteria

        Returns:
            Filtered list of audio tracks
        """
        if options.extract_all:
            return tracks

        filtered = tracks

        # Filter by language
        if options.languages:
            filtered = [t for t in filtered if t.language and t.language in options.languages]

        # Filter out commentary if not included
        if not options.include_commentary:
            filtered = [t for t in filtered if not t.commentary]

        return filtered
