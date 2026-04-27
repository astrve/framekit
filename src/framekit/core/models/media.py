from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class MediaTrack:
    id: int
    kind: str
    codec: str
    language: str | None = None
    language_variant: str | None = None
    subtitle_variant: str | None = None
    title: str | None = None
    is_default: bool = False
    is_forced: bool = False
    channels: str | None = None
    bitrate: int | None = None
    format_profile: str | None = None

    format_name: str | None = None
    codec_id: str | None = None
    stream_size_bytes: int | None = None
    stream_size_ratio: float | None = None
    frame_rate: float | None = None
    bit_depth: int | None = None

    extra: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class MediaFileInfo:
    path: Path
    container: str
    duration_ms: int | None
    size_bytes: int
    overall_bitrate: int | None
    width: int | None
    height: int | None
    aspect_ratio: str | None

    video_codec: str | None
    video_profile: str | None
    video_encoding_settings: str | None
    video_library_name: str | None

    video_format_name: str | None
    video_codec_id: str | None
    video_bitrate: int | None
    video_frame_rate: float | None
    video_bit_depth: int | None
    video_stream_size_bytes: int | None
    video_stream_size_ratio: float | None

    hdr_format: str | None

    audio_tracks: list[MediaTrack] = field(default_factory=list)
    subtitle_tracks: list[MediaTrack] = field(default_factory=list)
