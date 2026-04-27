from __future__ import annotations

from pathlib import Path

from framekit.core.languages import (
    language_display_label,
    language_short_label,
    subtitle_variant_display_label,
)
from framekit.core.mediainfo import probe_media_file
from framekit.core.models.nfo import EpisodeNfoData, TrackNfoData
from framekit.modules.renamer.detector import (
    get_hdr_canonical,
    get_preferred_resolution,
    get_preferred_video_tag,
    hdr_display_label,
)
from framekit.modules.renamer.rules import (
    VIDEO_EXTENSIONS,
    extract_episode_code,
    extract_episode_title,
    split_team,
)


def _overall_bitrate_kbps(size_bytes: int, duration_ms: int | None) -> int | None:
    if not duration_ms or duration_ms <= 0:
        return None

    seconds = duration_ms / 1000
    bits = size_bytes * 8
    kbps = bits / seconds / 1000
    return int(round(kbps))


def _normalize_overall_bitrate_kbps(value: int | None) -> int | None:
    if value is None:
        return None

    # MediaInfo returns overall bitrate in b/s.
    # We store the episode field in kb/s.
    return int(round(value / 1000))


def _episode_label_from_code(code: str | None) -> str | None:
    if not code:
        return None

    upper = code.upper()
    if "E" in upper:
        return "Season/Episode"

    return "Season"


def _aspect_ratio_display(value: str | None) -> str | None:
    if not value:
        return None

    try:
        ratio = float(str(value).replace(",", "."))
    except ValueError:
        return value

    rounded = round(ratio, 3)

    known = [
        (16 / 9, "16/9"),
        (4 / 3, "4/3"),
        (2.0, "2:1"),
        (21 / 9, "21/9"),
        (2.35, "2.35:1"),
        (2.39, "2.39:1"),
    ]

    for expected, label in known:
        if abs(ratio - expected) < 0.03:
            return f"{rounded:.3f} ({label})"

    return f"{rounded:.3f}"


def _build_video_tracks(info) -> list[TrackNfoData]:
    if not info.video_codec and not info.video_format_name:
        return []

    return [
        TrackNfoData(
            display_id="#1",
            kind="video",
            language_display=None,
            language_short=None,
            format_name=info.video_format_name,
            codec=info.video_codec,
            codec_id=info.video_codec_id,
            channels=None,
            channels_count=None,
            title=None,
            is_default=True,
            is_forced=False,
            subtitle_variant=None,
            bitrate=info.video_bitrate,
            size_bytes=info.video_stream_size_bytes,
            size_percent=info.video_stream_size_ratio,
            bit_depth=info.video_bit_depth,
            frame_rate=info.video_frame_rate,
        )
    ]


def _build_audio_tracks(info) -> list[TrackNfoData]:
    tracks: list[TrackNfoData] = []

    for index, track in enumerate(info.audio_tracks, start=2):
        channels_count = None
        if track.channels:
            try:
                channels_count = int(float(track.channels.split(".")[0]))
            except (ValueError, IndexError):
                channels_count = None

        tracks.append(
            TrackNfoData(
                display_id=f"#{index}",
                kind="audio",
                language_display=language_display_label(track.language, track.language_variant),
                language_short=language_short_label(track.language, track.language_variant),
                format_name=track.format_name,
                codec=track.codec,
                codec_id=track.codec_id,
                channels=track.channels,
                channels_count=channels_count,
                title=track.title,
                is_default=track.is_default,
                is_forced=track.is_forced,
                subtitle_variant=None,
                bitrate=track.bitrate,
                size_bytes=track.stream_size_bytes,
                size_percent=track.stream_size_ratio,
                bit_depth=track.bit_depth,
                frame_rate=track.frame_rate,
            )
        )

    return tracks


def _build_subtitle_tracks(info, audio_track_count: int) -> list[TrackNfoData]:
    tracks: list[TrackNfoData] = []

    start_index = 2 + audio_track_count
    for offset, track in enumerate(info.subtitle_tracks):
        tracks.append(
            TrackNfoData(
                display_id=f"#{start_index + offset}",
                kind="subtitle",
                language_display=language_display_label(track.language, track.language_variant),
                language_short=language_short_label(track.language, track.language_variant),
                format_name=track.format_name,
                codec=track.codec,
                codec_id=track.codec_id,
                channels=None,
                channels_count=None,
                title=track.title,
                is_default=track.is_default,
                is_forced=track.is_forced,
                subtitle_variant=subtitle_variant_display_label(track.subtitle_variant),
                bitrate=track.bitrate,
                size_bytes=track.stream_size_bytes,
                size_percent=track.stream_size_ratio,
                bit_depth=track.bit_depth,
                frame_rate=track.frame_rate,
            )
        )

    return tracks


def _audio_summary_from_probe(info) -> list[str]:
    results: list[str] = []
    for track in info.audio_tracks:
        lang = language_display_label(track.language, track.language_variant)
        codec = track.codec or "Audio"
        channels = track.channels or ""
        if channels:
            results.append(f"{lang} / {codec}.{channels}")
        else:
            results.append(f"{lang} / {codec}")
    return results


def _subtitle_summary_from_probe(info) -> list[str]:
    results: list[str] = []
    for track in info.subtitle_tracks:
        lang = language_display_label(track.language, track.language_variant)
        if track.subtitle_variant:
            results.append(f"{lang} / {subtitle_variant_display_label(track.subtitle_variant)}")
        else:
            results.append(lang)
    return results


def scan_nfo_folder(folder: Path) -> list[EpisodeNfoData]:
    episodes: list[EpisodeNfoData] = []

    media_files = sorted(
        file_path
        for file_path in folder.iterdir()
        if file_path.is_file() and file_path.suffix.lower() in VIDEO_EXTENSIONS
    )

    for file_path in media_files:
        info = probe_media_file(file_path)
        stem, _team = split_team(file_path.stem)

        hdr_canonical = get_hdr_canonical(info)
        hdr_display = hdr_display_label(hdr_canonical) if hdr_canonical else None

        video_tracks = _build_video_tracks(info)
        audio_tracks = _build_audio_tracks(info)
        subtitle_tracks = _build_subtitle_tracks(info, len(audio_tracks))

        episode_code = extract_episode_code(stem)

        episodes.append(
            EpisodeNfoData(
                file_path=file_path,
                file_name=file_path.name,
                episode_code=episode_code,
                episode_label=_episode_label_from_code(episode_code),
                episode_title=extract_episode_title(stem),
                container=info.container,
                size_bytes=info.size_bytes,
                duration_ms=info.duration_ms,
                overall_bitrate_kbps=_normalize_overall_bitrate_kbps(info.overall_bitrate)
                or _overall_bitrate_kbps(info.size_bytes, info.duration_ms),
                resolution=get_preferred_resolution(info) or None,
                aspect_ratio=info.aspect_ratio,
                aspect_ratio_display=_aspect_ratio_display(info.aspect_ratio),
                video_codec=get_preferred_video_tag(info) or None,
                hdr_display=hdr_display,
                video_format_name=info.video_format_name,
                video_codec_id=info.video_codec_id,
                video_bitrate=info.video_bitrate,
                video_bit_depth=info.video_bit_depth,
                video_frame_rate=info.video_frame_rate,
                video_size_bytes=info.video_stream_size_bytes,
                video_size_percent=info.video_stream_size_ratio,
                video_encoding_library=info.video_library_name,
                video_encoding_settings=info.video_encoding_settings,
                audio_summary=_audio_summary_from_probe(info),
                subtitle_summary=_subtitle_summary_from_probe(info),
                video_tracks=video_tracks,
                audio_tracks=audio_tracks,
                subtitle_tracks=subtitle_tracks,
            )
        )

    return episodes
