"""Subtitle extraction and conversion using FFmpeg and mkvextract."""

from __future__ import annotations

import subprocess  # nosec B404
import tempfile
from pathlib import Path

from loguru import logger

from ouro.core.path_validation import PathValidationError, validate_file_path
from ouro.core.subprocess_safe import MissingToolError, SafeSubprocessError, run_safe
from ouro.core.tools import ToolRegistry
from ouro.modules.extract.models import (
    ExtractionOptions,
    ExtractionResult,
    SubtitleFormat,
    SubtitleTrack,
)


class SubtitleExtractor:
    """Extracts and converts subtitle tracks from video files.

    Handles:
    - Subtitle extraction using mkvextract (preferred) or FFmpeg (fallback)
    - Format conversion between text-based formats (SRT, ASS, VTT, SSA)
    - Language filtering and variant detection
    - Secure subprocess execution (no shell=True)
    - Path validation and sanitization
    """

    # Codec to format mapping
    CODEC_FORMAT_MAP = {
        "subrip": SubtitleFormat.SRT,
        "srt": SubtitleFormat.SRT,
        "ass": SubtitleFormat.ASS,
        "ssa": SubtitleFormat.SSA,
        "webvtt": SubtitleFormat.VTT,
        "vtt": SubtitleFormat.VTT,
        "hdmv_pgs_subtitle": SubtitleFormat.PGS,
        "dvd_subtitle": SubtitleFormat.VOBSUB,
        "dvdsub": SubtitleFormat.VOBSUB,
    }

    # Text-based formats that can be converted
    TEXT_FORMATS = {
        SubtitleFormat.SRT,
        SubtitleFormat.ASS,
        SubtitleFormat.SSA,
        SubtitleFormat.VTT,
    }

    def __init__(self, registry: ToolRegistry) -> None:
        """Initialize subtitle extractor.

        Args:
            registry: Tool registry for FFmpeg/mkvextract resolution
        """
        self.registry = registry

    def detect_subtitle_format(self, codec: str) -> SubtitleFormat:
        """Detect subtitle format from codec name.

        Args:
            codec: Codec name (e.g., 'subrip', 'ass', 'hdmv_pgs_subtitle')

        Returns:
            Detected subtitle format
        """
        codec_lower = codec.lower()
        return self.CODEC_FORMAT_MAP.get(codec_lower, SubtitleFormat.SRT)

    def can_convert_format(
        self,
        source_format: SubtitleFormat,
        target_format: SubtitleFormat,
    ) -> bool:
        """Check if format conversion is supported.

        Args:
            source_format: Source subtitle format
            target_format: Target subtitle format

        Returns:
            True if conversion is supported
        """
        # Same format doesn't need conversion
        if source_format == target_format:
            return False

        # Only text-based formats can be converted
        return source_format in self.TEXT_FORMATS and target_format in self.TEXT_FORMATS

    def build_extraction_command(
        self,
        video_path: Path,
        output_path: Path,
        track: SubtitleTrack,
        use_mkvextract: bool = False,
    ) -> list[str]:
        """Build command for subtitle extraction.

        Security: Uses list-form arguments (no shell=True) and validates all paths.

        Args:
            video_path: Path to input video
            output_path: Path to output subtitle file
            track: Subtitle track to extract
            use_mkvextract: Whether to use mkvextract (True) or FFmpeg (False)

        Returns:
            Command as list of strings

        Raises:
            PathValidationError: If paths are invalid or unsafe
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

        if use_mkvextract:
            # Use mkvextract for MKV files
            mkvextract = self.registry.resolve_tool_path("mkvextract")
            if not mkvextract:
                mkvextract = "mkvextract"  # Fallback to PATH

            # mkvextract syntax: mkvextract tracks input.mkv track_id:output.srt
            cmd = [
                mkvextract,
                "tracks",
                str(video_path),
                f"{track.track_id}:{output_path!s}",
            ]
        else:
            # Use FFmpeg for all formats
            ffmpeg = self.registry.resolve_tool_path("ffmpeg")
            if not ffmpeg:
                ffmpeg = "ffmpeg"  # Fallback to PATH

            # FFmpeg syntax: ffmpeg -i input.mkv -map 0:s:N -c:s copy output.srt
            cmd = [
                ffmpeg,
                "-i",
                str(video_path),
                "-map",
                f"0:{track.track_id}",
                "-c:s",
                "copy",
                str(output_path),
                "-y",  # Overwrite output file
            ]

        return cmd

    def build_conversion_command(
        self,
        input_path: Path,
        output_path: Path,
        target_format: SubtitleFormat,
    ) -> list[str]:
        """Build command for subtitle format conversion.

        Args:
            input_path: Path to input subtitle file
            output_path: Path to output subtitle file
            target_format: Target subtitle format

        Returns:
            Command as list of strings

        Raises:
            PathValidationError: If paths are invalid
        """
        # Validate paths
        try:
            input_path = validate_file_path(input_path, must_exist=True)
        except (PathValidationError, FileNotFoundError) as exc:
            raise PathValidationError(f"Invalid input path: {exc}") from exc

        try:
            output_path = validate_file_path(output_path, must_exist=False)
        except PathValidationError as exc:
            raise PathValidationError(f"Invalid output path: {exc}") from exc

        # Use FFmpeg for format conversion
        ffmpeg = self.registry.resolve_tool_path("ffmpeg")
        if not ffmpeg:
            ffmpeg = "ffmpeg"

        cmd = [
            ffmpeg,
            "-i",
            str(input_path),
            str(output_path),
            "-y",  # Overwrite output file
        ]

        return cmd

    def extract_subtitle(
        self,
        video_path: Path,
        output_path: Path,
        track: SubtitleTrack,
        target_format: SubtitleFormat | None = None,
        use_mkvextract: bool = False,
    ) -> ExtractionResult:
        """Extract a single subtitle track.

        Args:
            video_path: Path to source video file
            output_path: Path to output subtitle file
            track: Subtitle track to extract
            target_format: Target format (None = keep original)
            use_mkvextract: Whether to use mkvextract

        Returns:
            Extraction result with success status and details
        """
        try:
            # Detect source format
            source_format = self.detect_subtitle_format(track.codec)

            # Determine if conversion is needed
            needs_conversion = (
                target_format is not None
                and target_format != SubtitleFormat.ORIGINAL
                and self.can_convert_format(source_format, target_format)
            )

            # Extract subtitle
            if needs_conversion:
                # Extract to temporary file first
                with tempfile.NamedTemporaryFile(
                    suffix=f".{source_format.value}",
                    delete=False,
                ) as tmp_file:
                    temp_path = Path(tmp_file.name)

                try:
                    # Extract to temp file
                    extract_cmd = self.build_extraction_command(
                        video_path=video_path,
                        output_path=temp_path,
                        track=track,
                        use_mkvextract=use_mkvextract,
                    )

                    logger.debug(f"Extracting subtitle: {' '.join(extract_cmd)}")
                    run_safe(
                        extract_cmd,
                        timeout=600,
                        check=True,
                        capture_output=True,
                        log_label="ffmpeg/mkvextract subtitle extract",
                    )

                    # Convert format (target_format is guaranteed non-None here)
                    assert target_format is not None  # nosec B101
                    convert_cmd = self.build_conversion_command(
                        input_path=temp_path,
                        output_path=output_path,
                        target_format=target_format,
                    )

                    logger.debug(f"Converting format: {' '.join(convert_cmd)}")
                    run_safe(
                        convert_cmd,
                        timeout=300,
                        check=True,
                        capture_output=True,
                        log_label="ffmpeg subtitle convert",
                    )

                    return ExtractionResult(
                        track=track,
                        source_file=video_path,
                        output_file=output_path,
                        success=True,
                        error=None,
                        format_converted=True,
                        original_format=source_format.value,
                        normalized=False,
                    )
                finally:
                    # Clean up temp file
                    if temp_path.exists():
                        temp_path.unlink()
            else:
                # Direct extraction without conversion
                extract_cmd = self.build_extraction_command(
                    video_path=video_path,
                    output_path=output_path,
                    track=track,
                    use_mkvextract=use_mkvextract,
                )

                logger.debug(f"Extracting subtitle: {' '.join(extract_cmd)}")
                run_safe(
                    extract_cmd,
                    timeout=600,
                    check=True,
                    capture_output=True,
                    log_label="ffmpeg/mkvextract subtitle extract direct",
                )

                return ExtractionResult(
                    track=track,
                    source_file=video_path,
                    output_file=output_path,
                    success=True,
                    error=None,
                    format_converted=False,
                    original_format=None,
                    normalized=False,
                )

        except (subprocess.CalledProcessError, SafeSubprocessError, MissingToolError) as exc:
            stderr = getattr(exc, "stderr", "") or getattr(exc, "stdout", "") or str(exc)
            error_msg = f"Extraction failed: {stderr}"
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
            error_msg = f"Unexpected error: {exc}"
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

    def filter_tracks(
        self,
        tracks: list[SubtitleTrack],
        options: ExtractionOptions,
    ) -> list[SubtitleTrack]:
        """Filter subtitle tracks based on extraction options.

        Args:
            tracks: List of subtitle tracks
            options: Extraction options with filter criteria

        Returns:
            Filtered list of tracks
        """
        # If extract_all is True, return all tracks
        if options.extract_all:
            return tracks

        filtered = []

        for track in tracks:
            # Filter by language
            if options.languages is not None:
                if track.language not in options.languages:
                    continue

            # Filter by forced flag
            if not options.include_forced and track.forced:
                continue

            # Filter by SDH/hearing impaired flag
            if not options.include_sdh and track.hearing_impaired:
                continue

            filtered.append(track)

        return filtered

    def generate_output_filename(
        self,
        video_path: Path,
        track: SubtitleTrack,
        options: ExtractionOptions,
    ) -> Path:
        """Generate output filename for extracted subtitle.

        Args:
            video_path: Source video file path
            track: Subtitle track
            options: Extraction options with output pattern

        Returns:
            Generated output file path
        """
        # Get output directory
        if options.output_dir:
            output_dir = options.output_dir
        else:
            output_dir = video_path.parent

        # Get basename without extension
        basename = video_path.stem

        # Determine format extension
        if options.output_format == SubtitleFormat.ORIGINAL:
            format_ext = self.detect_subtitle_format(track.codec).value
        else:
            format_ext = options.output_format.value

        # Build filename from pattern
        filename = options.output_pattern.format(
            basename=basename,
            language=track.language or "unknown",
            variant=track.variant,
            format=format_ext,
        )

        return output_dir / filename

    def extract_subtitles(
        self,
        video_path: Path,
        tracks: list[SubtitleTrack],
        options: ExtractionOptions,
    ) -> list[ExtractionResult]:
        """Extract multiple subtitle tracks.

        Args:
            video_path: Source video file path
            tracks: List of subtitle tracks to extract
            options: Extraction options

        Returns:
            List of extraction results
        """
        # Filter tracks based on options
        filtered_tracks = self.filter_tracks(tracks, options)

        results = []

        for track in filtered_tracks:
            # Generate output filename
            output_path = self.generate_output_filename(
                video_path=video_path,
                track=track,
                options=options,
            )

            # Create output directory if needed
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Determine if we should use mkvextract
            use_mkvextract = (
                video_path.suffix.lower() == ".mkv"
                and self.registry.resolve_tool_path("mkvextract") is not None
            )

            # Extract subtitle
            result = self.extract_subtitle(
                video_path=video_path,
                output_path=output_path,
                track=track,
                target_format=options.output_format,
                use_mkvextract=use_mkvextract,
            )

            results.append(result)

        return results
