from __future__ import annotations

from framekit.core.i18n import tr
from framekit.core.languages import language_display_label, language_short_label
from framekit.core.models.cleanmkv import TrackInfo

CODEC_PRIORITY: dict[str, int] = {
    "truehd": 100,
    "dts-ma": 90,
    "dts-hd": 90,
    "eac3": 70,
    "e-ac-3": 70,
    "dts": 60,
    "ac3": 50,
    "ac-3": 50,
    "aac": 40,
}


def ad_codec_score(codec: str | None) -> int:
    """Return quality score for an audio codec. Higher = better. Used to pick the best AD track."""
    return CODEC_PRIORITY.get((codec or "").strip().lower(), 0)


def format_channel_layout(channels_count: int | None, channels: str | None = None) -> str | None:
    """Format channel layout."""
    if channels and channels.strip() and channels.strip() not in {"0", "0.0"}:
        return channels.strip()
    if channels_count is None:
        return None
    mapping = {
        1: "1.0",
        2: "2.0",
        3: "2.1",
        4: "4.0",
        5: "5.0",
        6: "5.1",
        7: "6.1",
        8: "7.1",
    }
    return mapping.get(channels_count, str(channels_count))


def format_bitrate(value: int | None) -> str | None:
    """Format bitrate."""
    if value is None or value <= 0:
        return None
    if value >= 1_000_000:
        mbps = value / 1_000_000
        return f"{mbps:.1f} Mb/s".replace(".0 Mb/s", " Mb/s")
    return f"{round(value / 1000):d} kb/s"


def _clean_part(value: object) -> str:
    return str(value or "").strip().lower()


def track_reference_key(track: TrackInfo) -> str:
    """Handle track reference key."""
    if track.kind == "subtitle":
        parts = [
            track.kind,
            _clean_part(track.language),
            _clean_part(track.language_variant),
            _clean_part(track.subtitle_variant),
            _clean_part(track.codec),
            _clean_part(track.codec_id),
            str(bool(track.is_forced)),
        ]
        return "|".join(parts)

    parts = [
        track.kind,
        _clean_part(track.language),
        _clean_part(track.language_variant),
        _clean_part(track.subtitle_variant),
        _clean_part(track.codec),
        _clean_part(track.codec_id),
        _clean_part(format_channel_layout(track.channels_count, track.channels)),
        _clean_part(track.title),
    ]
    return "|".join(parts)


def track_display_grouping_key(track: TrackInfo) -> str:
    """Create a grouping key for interactive display mode.

    For audio tracks: groups by language and role/variant (e.g., AD vs normal),
    but NOT by codec - allowing same-language tracks with different codecs
    to be displayed together.

    For subtitle tracks: uses the same logic as track_reference_key to maintain
    current behavior.
    """
    if track.kind == "subtitle":
        # Subtitles: keep existing behavior (group by everything including codec)
        parts = [
            track.kind,
            _clean_part(track.language),
            _clean_part(track.language_variant),
            _clean_part(track.subtitle_variant),
            _clean_part(track.codec),
            _clean_part(track.codec_id),
            str(bool(track.is_forced)),
        ]
        return "|".join(parts)

    # Audio: group by language and role/variant, but NOT codec
    # This allows AAC, AC3, DTS, etc. of the same language to be grouped together
    # BUT keeps AD (audio description) separate from normal tracks
    parts = [
        track.kind,
        _clean_part(track.language),
        _clean_part(track.language_variant),
        _clean_part(track.subtitle_variant),  # Used for audio roles like AD
        # Deliberately omit codec and codec_id here
        _clean_part(format_channel_layout(track.channels_count, track.channels)),
        _clean_part(track.title),
    ]
    return "|".join(parts)


def track_reference_label(track: TrackInfo) -> str:
    """Handle track reference label."""
    language = language_short_label(track.language, track.language_variant)
    parts = [language]

    if track.kind == "audio":
        parts.extend(_audio_track_display_parts(track))
    else:
        parts.extend(_subtitle_track_display_parts(track))

    if track.title:
        parts.append(track.title)

    flags = _track_flags(track)
    if flags:
        parts.append("/".join(flags))

    return " · ".join(str(part) for part in parts if str(part).strip())


def track_grouped_label(
    tracks: list[TrackInfo],
    *,
    available_count: int | None = None,
    total_count: int | None = None,
) -> str:
    """Create a label for a group of tracks (e.g., same language, different codecs).

    Shows all available codecs in the group.

    For multi-grouped tracks (multiple codecs), optionally shows file availability.
    """
    if not tracks:
        return ""

    # Use the first track as the base
    track = tracks[0]
    language = language_short_label(track.language, track.language_variant)
    parts = [language]

    if track.kind == "audio":
        parts.extend(_grouped_audio_parts(tracks))
    else:
        parts.extend(_subtitle_track_display_parts(track))

    if track.title:
        parts.append(track.title)

    flags = _track_flags(track)
    if flags:
        parts.append("/".join(flags))

    label = " · ".join(str(part) for part in parts if str(part).strip())

    # Add file count for multi-grouped tracks (multiple codecs)
    if len(tracks) > 1 and available_count is not None and total_count is not None:
        file_count_info = tr(
            "cleanmkv.track.available_in",
            default="available in {count}/{total} files",
            count=available_count,
            total=total_count,
        )
        label = f"{label} ({file_count_info})"

    return label


def _audio_track_display_parts(track: TrackInfo) -> list[str]:
    codec = track.codec or track.format_name or track.codec_id
    channels = format_channel_layout(track.channels_count, track.channels)
    bitrate = format_bitrate(track.bitrate)
    return [str(value) for value in (codec, channels, bitrate) if value]


def _subtitle_track_display_parts(track: TrackInfo) -> list[str]:
    parts: list[str] = []
    if track.subtitle_variant:
        parts.append(
            tr(
                f"cleanmkv.subtitle_variant.{track.subtitle_variant}",
                default=track.subtitle_variant.title(),
            )
        )
    if track.codec or track.codec_id:
        parts.append(track.codec or track.codec_id or "")
    return parts


def _track_flags(track: TrackInfo) -> list[str]:
    flags: list[str] = []
    if track.is_default:
        flags.append(tr("common.default", default="Default"))
    if track.is_forced:
        flags.append(tr("common.forced", default="Forced"))
    return flags


def _grouped_audio_parts(tracks: list[TrackInfo]) -> list[str]:
    first_track = tracks[0]
    parts: list[str] = []
    codecs = _unique_codecs(tracks)
    if codecs:
        parts.append("/".join(codecs))
    channels = format_channel_layout(first_track.channels_count, first_track.channels)
    if channels:
        parts.append(channels)
    bitrate_span = _grouped_bitrate_span(tracks)
    if bitrate_span:
        parts.append(bitrate_span)
    return parts


def _unique_codecs(tracks: list[TrackInfo]) -> list[str]:
    codecs: list[str] = []
    for track in tracks:
        codec = track.codec or track.format_name or track.codec_id
        if codec and codec not in codecs:
            codecs.append(codec)
    return codecs


def _grouped_bitrate_span(tracks: list[TrackInfo]) -> str | None:
    bitrates = [
        bitrate for track in tracks if (bitrate := format_bitrate(track.bitrate)) is not None
    ]
    if not bitrates:
        return None
    unique_bitrates = list(dict.fromkeys(bitrates))
    if len(unique_bitrates) == 1:
        return unique_bitrates[0]
    return f"{unique_bitrates[0]}-{unique_bitrates[-1]}"


def track_reference_hint(
    track: TrackInfo,
    *,
    available_count: int | None = None,
    total_count: int | None = None,
) -> str:
    """Handle track reference hint."""
    long_language = language_display_label(track.language, track.language_variant)
    tag = language_short_label(track.language, track.language_variant)
    details = [f"{long_language} ({tag})"]

    codec = track.codec or track.format_name or track.codec_id
    channels = format_channel_layout(track.channels_count, track.channels)
    bitrate = format_bitrate(track.bitrate)
    details.extend(str(value) for value in (codec, channels, bitrate) if value)

    if track.kind == "subtitle" and track.subtitle_variant:
        details.append(
            tr(
                f"cleanmkv.subtitle_variant.{track.subtitle_variant}",
                default=track.subtitle_variant.title(),
            )
        )

    if available_count is not None and total_count is not None:
        return tr(
            "cleanmkv.track.available_in",
            default="available in {count}/{total} files",
            count=available_count,
            total=total_count,
        )

    return " · ".join(details)
