from __future__ import annotations

from pathlib import Path
from typing import Any, cast

try:
    # pymediainfo is an optional dependency. When available, it provides rich media metadata.
    from pymediainfo import MediaInfo  # type: ignore[import]
except ImportError:
    MediaInfo = None  # type: ignore[assignment]

from framekit.core.languages import normalize_language
from framekit.core.models.media import MediaFileInfo, MediaTrack
from framekit.core.subtitles import classify_subtitle_variant


def _to_int(value) -> int | None:
    if value in (None, "", "0"):
        return None
    try:
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return None


def _to_float(value) -> float | None:
    if value in (None, "", "0"):
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _normalize_video_codec(fmt: str | None) -> str | None:
    if not fmt:
        return None

    upper = str(fmt).strip().upper()
    if upper == "AVC":
        return "H264"
    if upper in {"HEVC", "H.265"}:
        return "H265"
    return upper


def _extract_hdr(video_track) -> str | None:
    candidates = [
        getattr(video_track, "hdr_format", None),
        getattr(video_track, "hdr_format_string", None),
        getattr(video_track, "hdr_format_commercial", None),
        getattr(video_track, "hdr_format_compatibility", None),
        getattr(video_track, "hdr_format_profile", None),
        getattr(video_track, "format_profile", None),
        getattr(video_track, "transfer_characteristics", None),
        getattr(video_track, "matrix_coefficients", None),
        getattr(video_track, "color_primaries", None),
        getattr(video_track, "colour_primaries", None),
    ]

    cleaned = [str(value).strip() for value in candidates if str(value or "").strip()]
    return " / ".join(dict.fromkeys(cleaned)) or None


def _extract_video_encoding_settings(video_track) -> str | None:
    candidates = [
        getattr(video_track, "encoded_library_settings", None),
        getattr(video_track, "encoding_settings", None),
    ]

    for value in candidates:
        if value:
            cleaned = str(value).strip()
            if cleaned:
                return cleaned

    return None


def _extract_video_library_name(video_track) -> str | None:
    candidates = [
        getattr(video_track, "encoded_library_name", None),
        getattr(video_track, "writing_library", None),
    ]

    for value in candidates:
        if value:
            cleaned = str(value).strip()
            if cleaned:
                return cleaned

    return None


def _normalize_channels(value) -> str | None:
    if value in (None, "", "0"):
        return None

    try:
        n = int(float(str(value).strip()))
    except ValueError:
        return str(value)

    if n == 1:
        return "1.0"
    if n == 2:
        return "2.0"
    if n == 6:
        return "5.1"
    if n == 8:
        return "7.1"
    return str(n)


def _stream_size_ratio(track) -> float | None:
    candidates = [
        getattr(track, "stream_size_proportion", None),
        getattr(track, "stream_size_proportion_of_this", None),
    ]
    for value in candidates:
        ratio = _to_float(value)
        if ratio is not None:
            return ratio
    return None


def _build_audio_track(track) -> MediaTrack:
    lang, variant = normalize_language(
        getattr(track, "language", None) or getattr(track, "language_ietf", None)
    )

    channels_count = _to_int(getattr(track, "channel_s", None) or getattr(track, "channels", None))

    return MediaTrack(
        id=_to_int(getattr(track, "streamorder", None)) or 0,
        kind="audio",
        codec=str(getattr(track, "format", "") or "").strip().upper(),
        format_name=str(getattr(track, "format", "") or "").strip() or None,
        codec_id=str(getattr(track, "codec_id", "") or "").strip() or None,
        language=lang,
        language_variant=variant,
        title=str(getattr(track, "title", "") or "").strip() or None,
        is_default=str(getattr(track, "default", "") or "").lower() == "yes",
        is_forced=str(getattr(track, "forced", "") or "").lower() == "yes",
        channels=_normalize_channels(channels_count),
        bitrate=_to_int(getattr(track, "bit_rate", None)),
        format_profile=str(getattr(track, "format_profile", "") or "").strip() or None,
        stream_size_bytes=_to_int(getattr(track, "stream_size", None)),
        stream_size_ratio=_stream_size_ratio(track),
        frame_rate=None,
        bit_depth=None,
        extra={"channels_count": str(channels_count) if channels_count is not None else ""},
    )


def _build_subtitle_track(track) -> MediaTrack:
    lang, variant = normalize_language(
        getattr(track, "language", None) or getattr(track, "language_ietf", None)
    )

    title = str(getattr(track, "title", "") or "").strip() or None
    is_forced = str(getattr(track, "forced", "") or "").lower() == "yes"
    hearing_impaired = str(getattr(track, "hearing_impaired", "") or "").lower() == "yes"

    return MediaTrack(
        id=_to_int(getattr(track, "streamorder", None)) or 0,
        kind="subtitle",
        codec=str(getattr(track, "format", "") or "").strip().upper(),
        format_name=str(getattr(track, "format", "") or "").strip() or None,
        codec_id=str(getattr(track, "codec_id", "") or "").strip() or None,
        language=lang,
        language_variant=variant,
        subtitle_variant=classify_subtitle_variant(
            title,
            forced=is_forced,
            hearing_impaired=hearing_impaired,
        ),
        title=title,
        is_default=str(getattr(track, "default", "") or "").lower() == "yes",
        is_forced=is_forced,
        bitrate=_to_int(getattr(track, "bit_rate", None)),
        format_profile=str(getattr(track, "format_profile", "") or "").strip() or None,
        stream_size_bytes=_to_int(getattr(track, "stream_size", None)),
        stream_size_ratio=_stream_size_ratio(track),
        frame_rate=None,
        bit_depth=None,
        extra={},
    )


def probe_media_file(path: str | Path) -> MediaFileInfo:
    file_path = Path(path)
    # When pymediainfo is unavailable, return a minimal MediaFileInfo object with only basic
    # filesystem-derived metadata. This avoids crashing when the optional dependency is missing.
    if MediaInfo is None:
        size = file_path.stat().st_size if file_path.exists() else 0
        # When no media parser is available, return a minimal MediaFileInfo with an empty
        # container string and lists for audio and subtitle tracks. Avoid tuples or None for
        # fields with more specific types to satisfy type checkers like pyright.
        return MediaFileInfo(
            path=file_path,
            container="",
            duration_ms=None,
            size_bytes=size,
            overall_bitrate=None,
            width=None,
            height=None,
            aspect_ratio=None,
            video_codec=None,
            video_profile=None,
            video_encoding_settings=None,
            video_library_name=None,
            video_format_name=None,
            video_codec_id=None,
            video_bitrate=None,
            video_frame_rate=None,
            video_bit_depth=None,
            video_stream_size_bytes=None,
            video_stream_size_ratio=None,
            hdr_format=None,
            audio_tracks=[],
            subtitle_tracks=[],
        )

    media_info = cast(Any, MediaInfo.parse(str(file_path)))
    tracks = cast(list[Any], media_info.tracks)

    general = next((t for t in tracks if t.track_type == "General"), None)
    video = next((t for t in tracks if t.track_type == "Video"), None)

    audio_tracks = [_build_audio_track(t) for t in tracks if t.track_type == "Audio"]
    subtitle_tracks = [_build_subtitle_track(t) for t in tracks if t.track_type == "Text"]

    return MediaFileInfo(
        path=file_path,
        container=str(getattr(general, "format", "") or "").strip().upper(),
        duration_ms=_to_int(getattr(general, "duration", None)),
        size_bytes=_to_int(getattr(general, "file_size", None)) or file_path.stat().st_size,
        overall_bitrate=_to_int(
            getattr(general, "overall_bit_rate", None) or getattr(general, "bit_rate", None)
        ),
        width=_to_int(getattr(video, "width", None)) if video else None,
        height=_to_int(getattr(video, "height", None)) if video else None,
        aspect_ratio=(str(getattr(video, "display_aspect_ratio", "") or "").strip() or None)
        if video
        else None,
        video_codec=_normalize_video_codec(getattr(video, "format", None) if video else None),
        video_profile=str(getattr(video, "format_profile", "") or "").strip() or None
        if video
        else None,
        video_encoding_settings=_extract_video_encoding_settings(video) if video else None,
        video_library_name=_extract_video_library_name(video) if video else None,
        video_format_name=str(getattr(video, "format", "") or "").strip() or None
        if video
        else None,
        video_codec_id=str(getattr(video, "codec_id", "") or "").strip() or None if video else None,
        video_bitrate=_to_int(getattr(video, "bit_rate", None)) if video else None,
        video_frame_rate=_to_float(getattr(video, "frame_rate", None)) if video else None,
        video_bit_depth=_to_int(getattr(video, "bit_depth", None)) if video else None,
        video_stream_size_bytes=_to_int(getattr(video, "stream_size", None)) if video else None,
        video_stream_size_ratio=_stream_size_ratio(video) if video else None,
        hdr_format=_extract_hdr(video) if video else None,
        audio_tracks=audio_tracks,
        subtitle_tracks=subtitle_tracks,
    )
