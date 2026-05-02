from __future__ import annotations

from framekit.core.i18n import tr
from framekit.core.languages import language_display_label, language_short_label
from framekit.core.models.cleanmkv import TrackInfo


def format_channel_layout(channels_count: int | None, channels: str | None = None) -> str | None:
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
    if value is None or value <= 0:
        return None
    if value >= 1_000_000:
        mbps = value / 1_000_000
        return f"{mbps:.1f} Mb/s".replace(".0 Mb/s", " Mb/s")
    return f"{round(value / 1000):d} kb/s"


def _clean_part(value: object) -> str:
    return str(value or "").strip().lower()


def track_reference_key(track: TrackInfo) -> str:
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


def track_reference_label(track: TrackInfo) -> str:
    language = language_short_label(track.language, track.language_variant)
    parts = [language]

    if track.kind == "audio":
        codec = track.codec or track.format_name or track.codec_id
        channels = format_channel_layout(track.channels_count, track.channels)
        bitrate = format_bitrate(track.bitrate)
        for value in (codec, channels, bitrate):
            if value:
                parts.append(str(value))
    else:
        if track.subtitle_variant:
            parts.append(
                tr(
                    f"cleanmkv.subtitle_variant.{track.subtitle_variant}",
                    default=track.subtitle_variant.title(),
                )
            )
        if track.codec or track.codec_id:
            parts.append(track.codec or track.codec_id or "")

    if track.title:
        parts.append(track.title)

    flags: list[str] = []
    if track.is_default:
        flags.append(tr("common.default", default="Default"))
    if track.is_forced:
        flags.append(tr("common.forced", default="Forced"))
    if flags:
        parts.append("/".join(flags))

    return " · ".join(str(part) for part in parts if str(part).strip())


def track_reference_hint(
    track: TrackInfo,
    *,
    available_count: int | None = None,
    total_count: int | None = None,
) -> str:
    long_language = language_display_label(track.language, track.language_variant)
    tag = language_short_label(track.language, track.language_variant)
    details = [f"{long_language} ({tag})"]

    codec = track.codec or track.format_name or track.codec_id
    channels = format_channel_layout(track.channels_count, track.channels)
    bitrate = format_bitrate(track.bitrate)
    for value in (codec, channels, bitrate):
        if value:
            details.append(str(value))

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
