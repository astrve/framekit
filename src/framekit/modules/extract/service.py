"""Extraction service for orchestrating subtitle, audio, and video extraction."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from loguru import logger

from framekit.core.languages import LANGUAGE_SHORT_MAP, normalize_language
from framekit.core.mediainfo import probe_media_file
from framekit.core.reporting import OperationReport
from framekit.core.tools import ToolRegistry
from framekit.modules.extract.audio_extractor import AudioExtractor
from framekit.modules.extract.models import (
    AudioExtractionOptions,
    AudioFormat,
    AudioTrack,
    ExtractionOptions,
    ExtractionResult,
    SubtitleFormat,
    SubtitleTrack,
    VideoExtractionOptions,
    VideoTrack,
)
from framekit.modules.extract.subtitle_extractor import SubtitleExtractor
from framekit.modules.extract.video_extractor import VideoExtractor


def _normalize_video_extension(extension: object) -> str:
    if isinstance(extension, str) and extension.startswith("."):
        return extension
    return ".mp4"


def _audio_extension_for_track(
    extractor: AudioExtractor,
    track: AudioTrack,
    output_format: AudioFormat,
) -> str:
    if output_format != AudioFormat.ORIGINAL:
        return output_format.value

    source_format = extractor.detect_audio_format(track.codec)
    return {
        AudioFormat.AAC: "aac",
        AudioFormat.MP3: "mp3",
        AudioFormat.FLAC: "flac",
        AudioFormat.ALAC: "m4a",
        AudioFormat.WAV: "wav",
        AudioFormat.OPUS: "opus",
        AudioFormat.VORBIS: "ogg",
        AudioFormat.AC3: "ac3",
        AudioFormat.EAC3: "eac3",
        AudioFormat.DTS: "dts",
        AudioFormat.DTS_HD: "dts",
        AudioFormat.TRUEHD: "thd",
    }.get(source_format, "aac")


def _language_tag(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "UND"
    language, _variant = normalize_language(raw)
    if language:
        short = LANGUAGE_SHORT_MAP.get(language)
        if short:
            return short.upper()
        letters = "".join(ch for ch in language.upper() if ch.isalpha())
        if len(letters) >= 2:
            return letters[:3]
    compact = "".join(ch for ch in raw.upper() if ch.isalpha())
    return compact[:3] if compact else "UND"


def _audio_role(track: AudioTrack) -> str | None:
    title = str(track.title or "").lower()
    if any(
        marker in title
        for marker in (
            "audio description",
            "audio-description",
            "descriptive audio",
            "descriptive",
            "ad ",
            "(ad)",
            "[ad]",
            "visually impaired",
            "blind",
        )
    ):
        return "AD"
    if track.commentary:
        return "COMM"
    return None


def _subtitle_role(track: SubtitleTrack) -> str | None:
    if track.forced:
        return "FORCED"
    if track.hearing_impaired:
        return "SDH"
    title = str(track.title or "").lower()
    if "comment" in title:
        return "COMM"
    return None


def _build_tagged_output_path(
    *,
    output_dir: Path,
    file_stem: str,
    extension: str,
    language: str | None,
    role: str | None,
    collisions: dict[str, int],
) -> Path:
    lang = _language_tag(language)
    tokens = [file_stem, lang]
    if role:
        tokens.append(role.upper())
    base_name = ".".join(tokens)
    collision_count = collisions.get(base_name, 0) + 1
    collisions[base_name] = collision_count
    if collision_count > 1:
        tokens.append(str(collision_count))
    return output_dir / f"{'.'.join(tokens)}.{extension.lstrip('.')}"


def _emit_progress(progress_callback: Callable[..., None] | None, **payload: object) -> None:
    if progress_callback is None:
        return
    progress_callback(**payload)


class ExtractionService:
    """Service for orchestrating media extraction operations.

    Coordinates subtitle, audio, and video extractors to handle:
    - Single file and batch extraction
    - Progress reporting
    - Error handling and recovery
    - Output directory management
    """

    def __init__(self, registry: ToolRegistry) -> None:
        """Initialize extraction service.

        Args:
            registry: Tool registry for FFmpeg/mkvextract resolution
        """
        self.registry = registry

    _FONT_SUBTITLE_MARKERS = (
        "application/x-truetype-font",
        "truetype",
        "opentype",
        "ttf",
        "otf",
        "font",
    )

    _SUBRIP_MARKERS = ("subrip", "srt", "utf-8", "utf8", "s_text/utf8")
    _ASS_MARKERS = ("ass",)
    _SSA_MARKERS = ("ssa",)
    _VTT_MARKERS = ("webvtt", "vtt")
    _PGS_MARKERS = ("pgs", "hdmv_pgs_subtitle", "s_hdmv/pgs")
    _VOBSUB_MARKERS = ("dvd_subtitle", "vobsub")

    def _language_tokens(self, value: str | None) -> set[str]:
        if not value:
            return set()
        raw = value.strip().lower()
        tokens = {raw}
        language, _variant = normalize_language(raw)
        if language:
            tokens.add(language)
            short = LANGUAGE_SHORT_MAP.get(language)
            if short:
                tokens.add(short)
        return tokens

    def _language_matches(self, candidate: str | None, requested: list[str] | None) -> bool:
        if not requested:
            return True
        candidate_tokens = self._language_tokens(candidate)
        if not candidate_tokens:
            return False
        requested_tokens: set[str] = set()
        for item in requested:
            requested_tokens.update(self._language_tokens(item))
        return bool(candidate_tokens & requested_tokens)

    def _subtitle_codec_from_media_track(self, track) -> str:
        values = " ".join(
            filter(
                None,
                [
                    str(getattr(track, "codec", "") or ""),
                    str(getattr(track, "format_name", "") or ""),
                    str(getattr(track, "codec_id", "") or ""),
                ],
            )
        ).lower()
        if any(marker in values for marker in self._SUBRIP_MARKERS):
            return "subrip"
        if any(marker in values for marker in self._ASS_MARKERS):
            return "ass"
        if any(marker in values for marker in self._SSA_MARKERS):
            return "ssa"
        if any(marker in values for marker in self._VTT_MARKERS):
            return "webvtt"
        if any(marker in values for marker in self._PGS_MARKERS):
            return "hdmv_pgs_subtitle"
        if any(marker in values for marker in self._VOBSUB_MARKERS):
            return "dvd_subtitle"
        return str(getattr(track, "codec", "") or "").lower() or "subrip"

    def _is_font_subtitle_track(self, track) -> bool:
        values = " ".join(
            filter(
                None,
                [
                    str(getattr(track, "codec", "") or ""),
                    str(getattr(track, "format_name", "") or ""),
                    str(getattr(track, "codec_id", "") or ""),
                    str(getattr(track, "title", "") or ""),
                ],
            )
        ).lower()
        return any(marker in values for marker in self._FONT_SUBTITLE_MARKERS)

    def extract_subtitles(
        self,
        files: list[Path],
        options: ExtractionOptions,
        progress_callback: Callable[..., None] | None = None,
    ) -> tuple[OperationReport, list[ExtractionResult]]:
        """Extract subtitles from video files.

        Args:
            files: List of video files to process
            options: Extraction options
            progress_callback: Optional progress callback

        Returns:
            Tuple of (operation report, extraction results)
        """
        report = OperationReport(tool="extract")
        results: list[ExtractionResult] = []

        # Create output directory if specified
        if options.output_dir:
            options.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize extractor
        extractor = SubtitleExtractor(self.registry)
        total_files = len(files)
        files_done = 0

        for file_index, file_path in enumerate(files, start=1):
            resolved_path = file_path.resolve()
            if not resolved_path.exists() or resolved_path.is_dir():
                report.add_error(
                    "file_not_found",
                    f"File does not exist or is not a video file: {resolved_path}",
                    file=str(resolved_path),
                )
                continue

            report.processed += 1
            _emit_progress(
                progress_callback,
                phase="analysis",
                current_file=resolved_path.name,
                file_index=file_index,
                total_files=total_files,
                files=0,
            )

            try:
                info = probe_media_file(resolved_path)
                subtitle_tracks: list[SubtitleTrack] = []
                for media_track in info.subtitle_tracks:
                    if self._is_font_subtitle_track(media_track):
                        report.skipped += 1
                        report.add_warning(
                            "font_track_skipped",
                            f"Skipped embedded font track: {resolved_path.name}",
                            file=str(resolved_path),
                            track_id=getattr(media_track, "id", None),
                        )
                        continue
                    language = getattr(media_track, "language", None)
                    if not options.extract_all and not self._language_matches(
                        language, options.languages
                    ):
                        continue
                    variant = str(getattr(media_track, "subtitle_variant", "") or "full").lower()
                    forced = bool(getattr(media_track, "is_forced", False))
                    hearing_impaired = variant in {"sdh", "hi"}
                    if not options.extract_all:
                        if not options.include_forced and forced:
                            continue
                        if not options.include_sdh and hearing_impaired:
                            continue
                    subtitle_tracks.append(
                        SubtitleTrack(
                            track_id=max(int(getattr(media_track, "id", 0) or 0), 0),
                            codec=self._subtitle_codec_from_media_track(media_track),
                            language=language,
                            title=getattr(media_track, "title", None),
                            forced=forced,
                            hearing_impaired=hearing_impaired,
                            default=bool(getattr(media_track, "is_default", False)),
                            variant=variant or "full",
                        )
                    )

                if not subtitle_tracks:
                    report.add_warning(
                        "no_subtitle_tracks",
                        f"No extractable subtitle tracks: {resolved_path.name}",
                        file=str(resolved_path),
                    )
                    files_done += 1
                    _emit_progress(
                        progress_callback,
                        phase="finalization",
                        current_file=resolved_path.name,
                        file_index=file_index,
                        total_files=total_files,
                        files=1,
                        files_done=files_done,
                    )
                    continue

                _emit_progress(
                    progress_callback,
                    phase="selection",
                    current_file=resolved_path.name,
                    file_index=file_index,
                    total_files=total_files,
                    total_tracks=len(subtitle_tracks),
                    files=0,
                )
                collisions: dict[str, int] = {}
                output_dir = options.output_dir or resolved_path.parent
                format_hint = (
                    options.output_format.value
                    if options.output_format != SubtitleFormat.ORIGINAL
                    else None
                )

                for track_index, track in enumerate(subtitle_tracks, start=1):
                    extension = format_hint or extractor.detect_subtitle_format(track.codec).value
                    output_path = _build_tagged_output_path(
                        output_dir=output_dir,
                        file_stem=resolved_path.stem,
                        extension=extension,
                        language=track.language,
                        role=_subtitle_role(track),
                        collisions=collisions,
                    )
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    _emit_progress(
                        progress_callback,
                        phase="extraction",
                        current_file=resolved_path.name,
                        file_index=file_index,
                        total_files=total_files,
                        current_track=track_index,
                        total_tracks=len(subtitle_tracks),
                        track_progress=0.0,
                        files=0,
                    )
                    result = extractor.extract_subtitle(
                        video_path=resolved_path,
                        output_path=output_path,
                        track=track,
                        target_format=options.output_format,
                    )
                    results.append(result)
                    if result.success:
                        report.modified += 1
                        report.add_detail(
                            file=resolved_path.name,
                            action="extract_subtitle",
                            status="success",
                            message=f"Extracted to {result.output_file.name}",
                        )
                    else:
                        report.add_error(
                            "extraction_failed",
                            result.error or "Unknown error",
                            file=str(resolved_path),
                        )
                    _emit_progress(
                        progress_callback,
                        phase="extraction",
                        current_file=resolved_path.name,
                        file_index=file_index,
                        total_files=total_files,
                        current_track=track_index,
                        total_tracks=len(subtitle_tracks),
                        track_progress=100.0,
                        files=0,
                    )

                files_done += 1
                _emit_progress(
                    progress_callback,
                    phase="finalization",
                    current_file=resolved_path.name,
                    file_index=file_index,
                    total_files=total_files,
                    files=1,
                    files_done=files_done,
                )

            except Exception as exc:
                logger.exception(f"Failed to extract subtitle from {resolved_path}")
                report.add_error(
                    "extraction_exception",
                    str(exc),
                    file=str(resolved_path),
                )

        return report, results

    def extract_audio(
        self,
        files: list[Path],
        options: AudioExtractionOptions,
        progress_callback: Callable[..., None] | None = None,
    ) -> tuple[OperationReport, list[ExtractionResult]]:
        """Extract audio from video files.

        Args:
            files: List of video files to process
            options: Audio extraction options
            progress_callback: Optional progress callback

        Returns:
            Tuple of (operation report, extraction results)
        """
        report = OperationReport(tool="extract")
        results: list[ExtractionResult] = []

        # Create output directory if specified
        if options.output_dir:
            options.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize extractor
        extractor = AudioExtractor(self.registry)
        total_files = len(files)
        files_done = 0

        for file_index, file_path in enumerate(files, start=1):
            resolved_path = file_path.resolve()
            if not resolved_path.exists() or resolved_path.is_dir():
                report.add_error(
                    "file_not_found",
                    f"File does not exist or is not a video file: {resolved_path}",
                    file=str(resolved_path),
                )
                continue

            report.processed += 1
            _emit_progress(
                progress_callback,
                phase="analysis",
                current_file=resolved_path.name,
                file_index=file_index,
                total_files=total_files,
                files=0,
            )

            try:
                info = probe_media_file(resolved_path)
                selected_audio_tracks: list[AudioTrack] = []
                for index, media_track in enumerate(info.audio_tracks):
                    language = getattr(media_track, "language", None)
                    title = str(getattr(media_track, "title", "") or "")
                    is_commentary = "commentary" in title.lower()
                    if not options.extract_all:
                        if not self._language_matches(language, options.languages):
                            continue
                        if not options.include_commentary and is_commentary:
                            continue
                    selected_audio_tracks.append(
                        AudioTrack(
                            track_id=index,
                            codec=str(getattr(media_track, "codec", "aac") or "aac").lower(),
                            language=language,
                            title=getattr(media_track, "title", None),
                            channels=None,
                            sample_rate=None,
                            bitrate=getattr(media_track, "bitrate", None),
                            default=bool(getattr(media_track, "is_default", False)),
                            commentary=is_commentary,
                        )
                    )

                if not selected_audio_tracks:
                    report.add_warning(
                        "no_audio_tracks",
                        f"No extractable audio tracks: {resolved_path.name}",
                        file=str(resolved_path),
                    )
                    files_done += 1
                    _emit_progress(
                        progress_callback,
                        phase="finalization",
                        current_file=resolved_path.name,
                        file_index=file_index,
                        total_files=total_files,
                        files=1,
                        files_done=files_done,
                    )
                    continue

                _emit_progress(
                    progress_callback,
                    phase="selection",
                    current_file=resolved_path.name,
                    file_index=file_index,
                    total_files=total_files,
                    total_tracks=len(selected_audio_tracks),
                    files=0,
                )
                collisions: dict[str, int] = {}
                output_dir = options.output_dir or resolved_path.parent
                duration_seconds = None
                if getattr(info, "duration_ms", None):
                    duration_seconds = float(info.duration_ms) / 1000.0

                for track_index, track in enumerate(selected_audio_tracks, start=1):
                    output_suffix = _audio_extension_for_track(
                        extractor,
                        track,
                        options.output_format,
                    )
                    output_path = _build_tagged_output_path(
                        output_dir=output_dir,
                        file_stem=resolved_path.stem,
                        extension=output_suffix,
                        language=track.language,
                        role=_audio_role(track),
                        collisions=collisions,
                    )
                    output_path.parent.mkdir(parents=True, exist_ok=True)

                    def _track_progress(track_progress: float) -> None:
                        _emit_progress(
                            progress_callback,
                            phase="extraction",
                            current_file=resolved_path.name,
                            file_index=file_index,
                            total_files=total_files,
                            current_track=track_index,
                            total_tracks=len(selected_audio_tracks),
                            track_progress=max(0.0, min(track_progress, 100.0)),
                            files=0,
                        )

                    _track_progress(0.0)
                    result = extractor.extract_audio(
                        video_path=resolved_path,
                        track=track,
                        output_path=output_path,
                        options=options,
                        progress_callback=_track_progress,
                        expected_duration_seconds=duration_seconds,
                    )
                    _track_progress(100.0)

                    results.append(result)
                    if result.success:
                        report.modified += 1
                        report.add_detail(
                            file=resolved_path.name,
                            action="extract_audio",
                            status="success",
                            message=f"Extracted to {result.output_file.name}",
                        )
                    else:
                        report.add_error(
                            "extraction_failed",
                            result.error or "Unknown error",
                            file=str(resolved_path),
                        )

                files_done += 1
                _emit_progress(
                    progress_callback,
                    phase="finalization",
                    current_file=resolved_path.name,
                    file_index=file_index,
                    total_files=total_files,
                    files=1,
                    files_done=files_done,
                )

            except Exception as exc:
                logger.exception(f"Failed to extract audio from {resolved_path}")
                report.add_error(
                    "extraction_exception",
                    str(exc),
                    file=str(resolved_path),
                )

        return report, results

    def extract_video(
        self,
        files: list[Path],
        options: VideoExtractionOptions,
        progress_callback: Callable[..., None] | None = None,
    ) -> tuple[OperationReport, list[ExtractionResult]]:
        """Extract video from video files.

        Args:
            files: List of video files to process
            options: Video extraction options
            progress_callback: Optional progress callback

        Returns:
            Tuple of (operation report, extraction results)
        """
        report = OperationReport(tool="extract")
        results: list[ExtractionResult] = []

        # Create output directory if specified
        if options.output_dir:
            options.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize extractor
        extractor = VideoExtractor(self.registry)
        total_files = len(files)
        files_done = 0

        for file_index, file_path in enumerate(files, start=1):
            resolved_path = file_path.resolve()
            if not resolved_path.exists() or resolved_path.is_dir():
                report.add_error(
                    "file_not_found",
                    f"File does not exist or is not a video file: {resolved_path}",
                    file=str(resolved_path),
                )
                continue

            report.processed += 1
            _emit_progress(
                progress_callback,
                phase="analysis",
                current_file=resolved_path.name,
                file_index=file_index,
                total_files=total_files,
                files=0,
            )

            try:
                info = probe_media_file(resolved_path)
                track = VideoTrack(
                    track_id=0,
                    codec=str(info.video_codec or info.video_format_name or "h264").lower(),
                    width=info.width,
                    height=info.height,
                    fps=info.video_frame_rate,
                    bitrate=info.video_bitrate,
                    pixel_format=None,
                    color_space=None,
                    hdr=bool(info.hdr_format),
                )

                _emit_progress(
                    progress_callback,
                    phase="selection",
                    current_file=resolved_path.name,
                    file_index=file_index,
                    total_files=total_files,
                    total_tracks=1,
                    files=0,
                )

                extension = _normalize_video_extension(
                    extractor.get_output_extension(options.output_codec)
                )
                output_path = (
                    options.output_dir / f"{resolved_path.stem}{extension}"
                    if options.output_dir
                    else resolved_path.with_suffix(extension)
                )
                duration_seconds = None
                if getattr(info, "duration_ms", None):
                    duration_seconds = float(info.duration_ms) / 1000.0

                def _track_progress(track_progress: float) -> None:
                    _emit_progress(
                        progress_callback,
                        phase="extraction",
                        current_file=resolved_path.name,
                        file_index=file_index,
                        total_files=total_files,
                        current_track=1,
                        total_tracks=1,
                        track_progress=max(0.0, min(track_progress, 100.0)),
                        files=0,
                    )

                _track_progress(0.0)
                result = extractor.extract_video(
                    video_path=resolved_path,
                    output_path=output_path,
                    track=track,
                    options=options,
                    progress_callback=_track_progress,
                    expected_duration_seconds=duration_seconds,
                )
                _track_progress(100.0)

                results.append(result)

                if result.success:
                    report.modified += 1
                    report.add_detail(
                        file=resolved_path.name,
                        action="extract_video",
                        status="success",
                        message=f"Extracted to {result.output_file.name}",
                    )
                else:
                    report.add_error(
                        "extraction_failed",
                        result.error or "Unknown error",
                        file=str(resolved_path),
                    )

                files_done += 1
                _emit_progress(
                    progress_callback,
                    phase="finalization",
                    current_file=resolved_path.name,
                    file_index=file_index,
                    total_files=total_files,
                    files=1,
                    files_done=files_done,
                )

            except Exception as exc:
                logger.exception(f"Failed to extract video from {resolved_path}")
                report.add_error(
                    "extraction_exception",
                    str(exc),
                    file=str(resolved_path),
                )

        return report, results
