from __future__ import annotations

import json
import subprocess  # nosec B404
from pathlib import Path
from typing import Any

from loguru import logger

from framekit.core.i18n import tr
from framekit.core.languages import normalize_language
from framekit.core.mediainfo import probe_media_file
from framekit.core.models.cleanmkv import MkvFileScan, TrackInfo
from framekit.core.parallel import parallel_scan_files
from framekit.core.performance import profile_time
from framekit.core.subprocess_safe import SafeSubprocessError, run_safe
from framekit.core.subtitles import classify_subtitle_variant, is_audio_description_track
from framekit.core.tools import ToolRegistry
from framekit.modules.renamer.rules import VIDEO_EXTENSIONS


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Run ``mkvmerge -J`` style probe with the project's safe wrapper.

    ``check=False`` because callers inspect ``returncode`` themselves and
    raise a localized error message; we keep the safety guarantees of
    :func:`run_safe` (absolute-path resolution, UTF-8 decoding, mandatory
    timeout, ``shell=False``).
    """
    try:
        return run_safe(
            cmd,
            timeout=60,
            check=False,
            capture_output=True,
            log_label="mkvmerge probe",
        )
    except SafeSubprocessError as exc:
        # A timeout or PATH-resolution failure surfaces as a CompletedProcess
        # with returncode != 0 so existing call sites keep their flow.
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=exc.returncode if exc.returncode is not None else 124,
            stdout="",
            stderr=exc.stderr or str(exc),
        )


def _parse_int(value) -> int | None:
    if value in (None, "", "0"):
        return None
    try:
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return None


def _extract_bitrate(props: dict) -> int | None:
    for key in ("audio_bitrate", "bitrate", "bits_per_second", "bps"):
        parsed = _parse_int(props.get(key))
        if parsed:
            return parsed

    statistics = props.get("track_statistics_tags") or props.get("statistics_tags") or {}
    if isinstance(statistics, dict):
        for key in ("BPS", "BPS-eng"):
            parsed = _parse_int(statistics.get(key))
            if parsed:
                return parsed

    return None


def _format_channels(value: int | None) -> str | None:
    if value is None:
        return None
    mapping = {1: "1.0", 2: "2.0", 3: "2.1", 4: "4.0", 5: "5.0", 6: "5.1", 7: "6.1", 8: "7.1"}
    return mapping.get(value, str(value))


def _parse_track(track: dict) -> TrackInfo | None:
    track_id = _parse_track_id(track.get("id"))
    if track_id is None:
        return None

    track_type = track.get("type")
    if track_type not in {"audio", "subtitles"}:
        return None
    props = track.get("properties", {}) or {}
    return _build_track_info(track_id=track_id, track_type=track_type, track=track, props=props)


def _parse_track_id(raw_track_id: object) -> int | None:
    if raw_track_id is None:
        return None
    try:
        return int(str(raw_track_id))
    except (TypeError, ValueError):
        return None


def _build_track_info(
    *,
    track_id: int,
    track_type: str,
    track: dict,
    props: dict,
) -> TrackInfo:
    parsed_channels_count = _parse_channels_count(props.get("audio_channels"))
    language, language_variant = _parse_track_language(props)
    is_default, is_forced, hearing_impaired = _parse_track_flags(props)
    title = str(props.get("track_name") or "").strip() or None
    subtitle_variant = _parse_subtitle_variant(
        track_type=track_type,
        title=title,
        is_forced=is_forced,
        hearing_impaired=hearing_impaired,
    )
    if track_type == "audio" and is_audio_description_track(
        title, flag_visual_impaired=bool(props.get("flag_visual_impaired"))
    ):
        subtitle_variant = "ad"
    kind = _track_kind(track_type)
    format_name = str(props.get("codec_id") or "").strip() or None
    return TrackInfo(
        track_id=track_id,
        kind=kind,
        codec=str(track.get("codec") or "").strip().upper(),
        language=language,
        language_variant=language_variant,
        subtitle_variant=subtitle_variant,
        title=title,
        is_default=is_default,
        is_forced=is_forced,
        bitrate=_extract_bitrate(props),
        format_name=format_name,
        codec_id=format_name,
        channels=_format_channels(parsed_channels_count),
        channels_count=parsed_channels_count,
        extra=_track_extra(props),
    )


def _track_kind(track_type: str) -> str:
    return "audio" if track_type == "audio" else "subtitle"


def _track_extra(props: dict) -> dict[str, str]:
    return {
        "language_raw": str(props.get("language") or ""),
        "language_ietf": str(props.get("language_ietf") or ""),
    }


def _parse_channels_count(channels_count: object) -> int | None:
    try:
        return int(str(channels_count)) if channels_count is not None else None
    except (TypeError, ValueError):
        return None


def _parse_track_language(props: dict) -> tuple[str | None, str | None]:
    raw_language = props.get("language_ietf") or props.get("language")
    return normalize_language(raw_language)


def _parse_track_flags(props: dict) -> tuple[bool, bool, bool]:
    return (
        bool(props.get("default_track")),
        bool(props.get("forced_track")),
        bool(props.get("flag_hearing_impaired")),
    )


def _parse_subtitle_variant(
    *,
    track_type: str,
    title: str | None,
    is_forced: bool,
    hearing_impaired: bool,
) -> str | None:
    if track_type != "subtitles":
        return None
    return classify_subtitle_variant(
        title,
        forced=is_forced,
        hearing_impaired=hearing_impaired,
    )


def _enrich_tracks_with_mediainfo(scan: MkvFileScan) -> None:
    try:
        info = probe_media_file(scan.path)
    except Exception as e:
        logger.warning(f"Failed to scan file {scan.path}: {e}")
        return

    for track, media_track in zip(scan.audio_tracks, info.audio_tracks, strict=False):
        _enrich_audio_track(track, media_track)

    for track, media_track in zip(scan.subtitle_tracks, info.subtitle_tracks, strict=False):
        _enrich_subtitle_track(track, media_track)


def _enrich_audio_track(track: TrackInfo, media_track: Any) -> None:
    track.codec = track.codec or media_track.codec
    track.format_name = track.format_name or media_track.format_name
    track.codec_id = track.codec_id or media_track.codec_id
    track.channels = media_track.channels or track.channels
    track.bitrate = media_track.bitrate or track.bitrate
    track.stream_size_bytes = media_track.stream_size_bytes or track.stream_size_bytes
    track.stream_size_ratio = media_track.stream_size_ratio or track.stream_size_ratio
    track.bit_depth = media_track.bit_depth or track.bit_depth


def _enrich_subtitle_track(track: TrackInfo, media_track: Any) -> None:
    track.codec = track.codec or media_track.codec
    track.format_name = track.format_name or media_track.format_name
    track.codec_id = track.codec_id or media_track.codec_id
    track.bitrate = media_track.bitrate or track.bitrate
    track.stream_size_bytes = media_track.stream_size_bytes or track.stream_size_bytes
    track.stream_size_ratio = media_track.stream_size_ratio or track.stream_size_ratio


@profile_time("scan_mkv_file")
def scan_mkv_file(path: Path, registry: ToolRegistry) -> MkvFileScan:
    """Handle scan mkv file."""
    mkvmerge_path = registry.resolve_tool_path("mkvmerge")
    if not mkvmerge_path:
        raise RuntimeError(
            tr(
                "tools.required_missing",
                default="{tool} is required but not available.",
                tool="mkvmerge",
            )
        )

    result = _run([str(mkvmerge_path), "-J", str(path)])
    if result.returncode != 0:
        raise RuntimeError(
            tr(
                "cleanmkv.error.scan_failed",
                default="mkvmerge failed on {file}: {message}",
                file=path.name,
                message=result.stderr.strip(),
            )
        )

    payload = json.loads(result.stdout)
    tracks = payload.get("tracks", []) or []

    scan = MkvFileScan(path=path)

    for track in tracks:
        parsed = _parse_track(track)
        if parsed is None:
            continue

        if parsed.kind == "audio":
            scan.audio_tracks.append(parsed)
        elif parsed.kind == "subtitle":
            scan.subtitle_tracks.append(parsed)

    _enrich_tracks_with_mediainfo(scan)
    return scan


@profile_time("scan_folder")
def scan_folder(
    folder: Path,
    registry: ToolRegistry,
    *,
    parallel: bool = True,
    max_workers: int | None = None,
) -> list[MkvFileScan]:
    """Scan all MKV files in a folder.

    Args:
        folder: Folder to scan
        registry: Tool registry
        parallel: Use parallel scanning for multiple files
        max_workers: Maximum number of workers for parallel scanning

    Returns:
        List of MKV file scans
    """
    media_files = sorted(
        file_path
        for file_path in folder.iterdir()
        if file_path.is_file() and file_path.suffix.lower() in VIDEO_EXTENSIONS
    )

    if not media_files:
        return []

    # Use parallel scanning for multiple files
    if parallel and len(media_files) > 1:

        def scan_single(path: Path) -> MkvFileScan:
            return scan_mkv_file(path, registry)

        return parallel_scan_files(
            media_files,
            scan_single,
            max_workers=max_workers,
        )

    # Sequential scanning for single file or when parallel is disabled
    return [scan_mkv_file(file_path, registry) for file_path in media_files]
