from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

try:
    # pymediainfo is an optional dependency. When available, it provides rich media metadata.
    from pymediainfo import MediaInfo  # type: ignore[import]
except ImportError:
    MediaInfo = None  # type: ignore[assignment]

from framekit.core.languages import normalize_language
from framekit.core.models.media import MediaFileInfo, MediaTrack
from framekit.core.subtitles import classify_subtitle_variant

if TYPE_CHECKING:
    from framekit.core.cache.manager import CacheManager


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


def _clean_text(value: Any) -> str | None:
    cleaned = str(value or "").strip()
    return cleaned or None


def _cached_int(data: Mapping[str, Any], key: str) -> int | None:
    value = data.get(key)
    return _to_int(value) if value else None


def _cached_float(data: Mapping[str, Any], key: str) -> float | None:
    value = data.get(key)
    return _to_float(value) if value else None


def _cached_text(data: Mapping[str, Any], key: str) -> str | None:
    return _clean_text(data.get(key))


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


def _track_text(track: Any, *attrs: str) -> str | None:
    for attr in attrs:
        value = _clean_text(getattr(track, attr, None))
        if value:
            return value
    return None


def _track_flag(track: Any, attr: str) -> bool:
    return str(getattr(track, attr, "") or "").lower() == "yes"


def _track_stream_id(track: Any) -> int:
    return _to_int(getattr(track, "streamorder", None)) or 0


def _track_language(track: Any) -> tuple[str | None, str | None]:
    return normalize_language(_track_text(track, "language", "language_ietf"))


def _build_audio_track(track) -> MediaTrack:
    lang, variant = _track_language(track)
    channels_count = _to_int(_track_text(track, "channel_s", "channels"))
    codec_text = _track_text(track, "format") or ""

    return MediaTrack(
        id=_track_stream_id(track),
        kind="audio",
        codec=codec_text.upper(),
        format_name=codec_text or None,
        codec_id=_track_text(track, "codec_id"),
        language=lang,
        language_variant=variant,
        title=_track_text(track, "title"),
        is_default=_track_flag(track, "default"),
        is_forced=_track_flag(track, "forced"),
        channels=_normalize_channels(channels_count),
        bitrate=_to_int(getattr(track, "bit_rate", None)),
        format_profile=_track_text(track, "format_profile"),
        stream_size_bytes=_to_int(getattr(track, "stream_size", None)),
        stream_size_ratio=_stream_size_ratio(track),
        frame_rate=None,
        bit_depth=None,
        extra={"channels_count": str(channels_count) if channels_count is not None else ""},
    )


def _build_subtitle_track(track) -> MediaTrack:
    lang, variant = _track_language(track)
    title = _track_text(track, "title")
    is_forced = _track_flag(track, "forced")
    hearing_impaired = _track_flag(track, "hearing_impaired")
    codec_text = _track_text(track, "format") or ""

    return MediaTrack(
        id=_track_stream_id(track),
        kind="subtitle",
        codec=codec_text.upper(),
        format_name=codec_text or None,
        codec_id=_track_text(track, "codec_id"),
        language=lang,
        language_variant=variant,
        subtitle_variant=classify_subtitle_variant(
            title,
            forced=is_forced,
            hearing_impaired=hearing_impaired,
        ),
        title=title,
        is_default=_track_flag(track, "default"),
        is_forced=is_forced,
        bitrate=_to_int(getattr(track, "bit_rate", None)),
        format_profile=_track_text(track, "format_profile"),
        stream_size_bytes=_to_int(getattr(track, "stream_size", None)),
        stream_size_ratio=_stream_size_ratio(track),
        frame_rate=None,
        bit_depth=None,
        extra={},
    )


def _track_to_cache_dict(track: MediaTrack) -> dict[str, Any]:
    """Serialize a MediaTrack for JSON cache storage."""
    return {
        "id": track.id,
        "kind": track.kind,
        "codec": track.codec,
        "language": track.language,
        "language_variant": track.language_variant,
        "subtitle_variant": track.subtitle_variant,
        "title": track.title,
        "is_default": track.is_default,
        "is_forced": track.is_forced,
        "channels": track.channels,
        "bitrate": track.bitrate,
        "format_profile": track.format_profile,
        "format_name": track.format_name,
        "codec_id": track.codec_id,
        "stream_size_bytes": track.stream_size_bytes,
        "stream_size_ratio": track.stream_size_ratio,
        "frame_rate": track.frame_rate,
        "bit_depth": track.bit_depth,
        "extra": track.extra,
    }


def _track_from_cache(track_data: Any) -> MediaTrack | None:
    if not isinstance(track_data, Mapping):
        return None
    return MediaTrack(**dict(track_data))


def _track_list_from_cache(track_data: Any) -> list[MediaTrack]:
    if not isinstance(track_data, list):
        return []
    return [track for item in track_data if (track := _track_from_cache(item)) is not None]


def _serialize_media_file_info(result: MediaFileInfo) -> dict[str, Any]:
    """Serialize MediaFileInfo for cache manager."""
    return {
        "path": str(result.path),
        "container": result.container,
        "duration_ms": result.duration_ms,
        "size_bytes": result.size_bytes,
        "overall_bitrate": result.overall_bitrate,
        "width": result.width,
        "height": result.height,
        "aspect_ratio": result.aspect_ratio,
        "video_codec": result.video_codec,
        "video_profile": result.video_profile,
        "video_encoding_settings": result.video_encoding_settings,
        "video_library_name": result.video_library_name,
        "video_format_name": result.video_format_name,
        "video_codec_id": result.video_codec_id,
        "video_bitrate": result.video_bitrate,
        "video_frame_rate": result.video_frame_rate,
        "video_bit_depth": result.video_bit_depth,
        "video_stream_size_bytes": result.video_stream_size_bytes,
        "video_stream_size_ratio": result.video_stream_size_ratio,
        "hdr_format": result.hdr_format,
        "audio_tracks": [_track_to_cache_dict(track) for track in result.audio_tracks],
        "subtitle_tracks": [_track_to_cache_dict(track) for track in result.subtitle_tracks],
    }


def _media_file_info_from_cache(cached_data: Mapping[str, Any]) -> MediaFileInfo:
    """Rebuild MediaFileInfo object from cache payload."""
    audio_tracks = _track_list_from_cache(cached_data.get("audio_tracks"))
    subtitle_tracks = _track_list_from_cache(cached_data.get("subtitle_tracks"))
    return MediaFileInfo(
        path=Path(str(cached_data["path"])),
        container=str(cached_data.get("container", "")),
        duration_ms=_cached_int(cached_data, "duration_ms"),
        size_bytes=int(cached_data.get("size_bytes", 0) or 0),
        overall_bitrate=_cached_int(cached_data, "overall_bitrate"),
        width=_cached_int(cached_data, "width"),
        height=_cached_int(cached_data, "height"),
        aspect_ratio=_cached_text(cached_data, "aspect_ratio"),
        video_codec=_cached_text(cached_data, "video_codec"),
        video_profile=_cached_text(cached_data, "video_profile"),
        video_encoding_settings=_cached_text(cached_data, "video_encoding_settings"),
        video_library_name=_cached_text(cached_data, "video_library_name"),
        video_format_name=_cached_text(cached_data, "video_format_name"),
        video_codec_id=_cached_text(cached_data, "video_codec_id"),
        video_bitrate=_cached_int(cached_data, "video_bitrate"),
        video_frame_rate=_cached_float(cached_data, "video_frame_rate"),
        video_bit_depth=_cached_int(cached_data, "video_bit_depth"),
        video_stream_size_bytes=_cached_int(cached_data, "video_stream_size_bytes"),
        video_stream_size_ratio=_cached_float(cached_data, "video_stream_size_ratio"),
        hdr_format=_cached_text(cached_data, "hdr_format"),
        audio_tracks=audio_tracks,
        subtitle_tracks=subtitle_tracks,
    )


def _load_cached_media_info(
    file_path: Path, cache_manager: CacheManager | None
) -> MediaFileInfo | None:
    """Load MediaFileInfo from cache when available and valid."""
    if cache_manager is None or not file_path.exists():
        return None
    mtime = file_path.stat().st_mtime
    cached_data = cache_manager.get_mediainfo(file_path, mtime)
    if cached_data is None:
        return None
    return _media_file_info_from_cache(cached_data)


def _minimal_media_info(file_path: Path) -> MediaFileInfo:
    """Return filesystem-only metadata when pymediainfo is unavailable."""
    size = file_path.stat().st_size if file_path.exists() else 0
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


def _first_track(tracks: list[Any], track_type: str) -> Any | None:
    return next((track for track in tracks if track.track_type == track_type), None)


def _tracks_of_type(tracks: list[Any], track_type: str) -> list[Any]:
    return [track for track in tracks if track.track_type == track_type]


def _video_fields(video: Any) -> dict[str, Any]:
    if video is None:
        return {
            "width": None,
            "height": None,
            "aspect_ratio": None,
            "video_codec": None,
            "video_profile": None,
            "video_encoding_settings": None,
            "video_library_name": None,
            "video_format_name": None,
            "video_codec_id": None,
            "video_bitrate": None,
            "video_frame_rate": None,
            "video_bit_depth": None,
            "video_stream_size_bytes": None,
            "video_stream_size_ratio": None,
            "hdr_format": None,
        }

    return {
        "width": _to_int(getattr(video, "width", None)),
        "height": _to_int(getattr(video, "height", None)),
        "aspect_ratio": _clean_text(getattr(video, "display_aspect_ratio", None)),
        "video_codec": _normalize_video_codec(getattr(video, "format", None)),
        "video_profile": _clean_text(getattr(video, "format_profile", None)),
        "video_encoding_settings": _extract_video_encoding_settings(video),
        "video_library_name": _extract_video_library_name(video),
        "video_format_name": _clean_text(getattr(video, "format", None)),
        "video_codec_id": _clean_text(getattr(video, "codec_id", None)),
        "video_bitrate": _to_int(getattr(video, "bit_rate", None)),
        "video_frame_rate": _to_float(getattr(video, "frame_rate", None)),
        "video_bit_depth": _to_int(getattr(video, "bit_depth", None)),
        "video_stream_size_bytes": _to_int(getattr(video, "stream_size", None)),
        "video_stream_size_ratio": _stream_size_ratio(video),
        "hdr_format": _extract_hdr(video),
    }


def _base_media_info_fields(file_path: Path, general: Any) -> dict[str, Any]:
    return {
        "path": file_path,
        "container": str(getattr(general, "format", "") or "").strip().upper(),
        "duration_ms": _to_int(getattr(general, "duration", None)),
        "size_bytes": _to_int(getattr(general, "file_size", None)) or file_path.stat().st_size,
        "overall_bitrate": _to_int(
            getattr(general, "overall_bit_rate", None) or getattr(general, "bit_rate", None)
        ),
    }


def _probe_with_pymediainfo(file_path: Path) -> MediaFileInfo:
    """Probe media file with pymediainfo and build MediaFileInfo."""
    if MediaInfo is None:  # pragma: no cover - guarded by caller
        raise RuntimeError("pymediainfo is not available")
    try:
        media_info = cast(Any, MediaInfo.parse(str(file_path)))
    except Exception as exc:
        from framekit.ui.console import print_warning

        print_warning(
            f"MediaInfo could not open '{file_path.name}': {exc}. Using minimal fallback."
        )
        return _minimal_media_info(file_path)
    tracks = cast(list[Any], media_info.tracks)

    general = _first_track(tracks, "General")
    video = _first_track(tracks, "Video")
    audio_tracks = [_build_audio_track(track) for track in _tracks_of_type(tracks, "Audio")]
    subtitle_tracks = [_build_subtitle_track(track) for track in _tracks_of_type(tracks, "Text")]

    fields: dict[str, Any] = {}
    fields.update(_base_media_info_fields(file_path, general))
    fields.update(_video_fields(video))
    fields["audio_tracks"] = audio_tracks
    fields["subtitle_tracks"] = subtitle_tracks
    return MediaFileInfo(**fields)


def _cache_media_file_info(
    file_path: Path,
    cache_manager: CacheManager | None,
    result: MediaFileInfo,
) -> None:
    """Cache MediaFileInfo when cache manager and source file are available."""
    if cache_manager is None or not file_path.exists():
        return
    mtime = file_path.stat().st_mtime
    cache_manager.set_mediainfo(file_path, mtime, _serialize_media_file_info(result))


def probe_media_file(
    path: str | Path,
    cache_manager: CacheManager | None = None,
) -> MediaFileInfo:
    """Probe media file and return metadata.

    Args:
        path: Path to media file
        cache_manager: Optional cache manager for caching results

    Returns:
        MediaFileInfo with parsed metadata
    """
    file_path = Path(path)

    cached_result = _load_cached_media_info(file_path, cache_manager)
    if cached_result is not None:
        return cached_result

    if MediaInfo is None:
        return _minimal_media_info(file_path)

    result = _probe_with_pymediainfo(file_path)
    _cache_media_file_info(file_path, cache_manager, result)
    return result
