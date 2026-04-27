from __future__ import annotations

import json
import subprocess
from pathlib import Path

from framekit.core.i18n import tr
from framekit.core.languages import normalize_language
from framekit.core.mediainfo import probe_media_file
from framekit.core.models.cleanmkv import MkvFileScan, TrackInfo
from framekit.core.subtitles import classify_subtitle_variant
from framekit.core.tools import ToolRegistry
from framekit.modules.renamer.rules import VIDEO_EXTENSIONS


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
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
    raw_track_id = track.get("id")
    if raw_track_id is None:
        return None

    track_id = int(raw_track_id)
    track_type = track.get("type")
    props = track.get("properties", {}) or {}

    if track_type not in {"audio", "subtitles"}:
        return None

    raw_language = props.get("language_ietf") or props.get("language")
    language, language_variant = normalize_language(raw_language)

    title = str(props.get("track_name") or "").strip() or None

    is_default = bool(props.get("default_track"))
    is_forced = bool(props.get("forced_track"))
    hearing_impaired = bool(props.get("flag_hearing_impaired"))

    subtitle_variant = None
    if track_type == "subtitles":
        subtitle_variant = classify_subtitle_variant(
            title,
            forced=is_forced,
            hearing_impaired=hearing_impaired,
        )

    channels_count = props.get("audio_channels")
    try:
        parsed_channels_count = int(channels_count) if channels_count is not None else None
    except (TypeError, ValueError):
        parsed_channels_count = None

    return TrackInfo(
        track_id=int(track_id),
        kind="audio" if track_type == "audio" else "subtitle",
        codec=str(track.get("codec") or "").strip().upper(),
        language=language,
        language_variant=language_variant,
        subtitle_variant=subtitle_variant,
        title=title,
        is_default=is_default,
        is_forced=is_forced,
        bitrate=_extract_bitrate(props),
        format_name=str(props.get("codec_id") or "").strip() or None,
        codec_id=str(props.get("codec_id") or "").strip() or None,
        channels=_format_channels(parsed_channels_count),
        channels_count=parsed_channels_count,
        extra={
            "language_raw": str(props.get("language") or ""),
            "language_ietf": str(props.get("language_ietf") or ""),
        },
    )


def _enrich_tracks_with_mediainfo(scan: MkvFileScan) -> None:
    try:
        info = probe_media_file(scan.path)
    except Exception:
        return

    for track, media_track in zip(scan.audio_tracks, info.audio_tracks, strict=False):
        track.codec = track.codec or media_track.codec
        track.format_name = track.format_name or media_track.format_name
        track.codec_id = track.codec_id or media_track.codec_id
        track.channels = media_track.channels or track.channels
        track.bitrate = media_track.bitrate or track.bitrate
        track.stream_size_bytes = media_track.stream_size_bytes or track.stream_size_bytes
        track.stream_size_ratio = media_track.stream_size_ratio or track.stream_size_ratio
        track.bit_depth = media_track.bit_depth or track.bit_depth

    for track, media_track in zip(scan.subtitle_tracks, info.subtitle_tracks, strict=False):
        track.codec = track.codec or media_track.codec
        track.format_name = track.format_name or media_track.format_name
        track.codec_id = track.codec_id or media_track.codec_id
        track.bitrate = media_track.bitrate or track.bitrate
        track.stream_size_bytes = media_track.stream_size_bytes or track.stream_size_bytes
        track.stream_size_ratio = media_track.stream_size_ratio or track.stream_size_ratio


def scan_mkv_file(path: Path, registry: ToolRegistry) -> MkvFileScan:
    mkvmerge_path = registry.resolve_tool_path("mkvmerge")
    if not mkvmerge_path:
        raise RuntimeError(
            tr(
                "tools.mkvmerge_not_found",
                default="mkvmerge not found. Configure it or add it to PATH.",
            )
        )

    result = _run([mkvmerge_path, "-J", str(path)])
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


def scan_folder(folder: Path, registry: ToolRegistry) -> list[MkvFileScan]:
    results: list[MkvFileScan] = []

    media_files = sorted(
        file_path
        for file_path in folder.iterdir()
        if file_path.is_file() and file_path.suffix.lower() in VIDEO_EXTENSIONS
    )

    for file_path in media_files:
        results.append(scan_mkv_file(file_path, registry))

    return results
