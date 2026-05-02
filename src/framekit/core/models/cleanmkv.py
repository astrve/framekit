from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CleanPreset:
    name: str
    keep_audio_filters: tuple[str, ...]
    default_audio_filter: str | None
    keep_subtitle_filters: tuple[str, ...]
    keep_subtitle_variants: tuple[str, ...]
    default_subtitle_filter: str | None
    default_subtitle_variant: str | None

    keep_audio_track_refs: tuple[str, ...] = ()
    default_audio_track_ref: str | None = None
    keep_subtitle_track_refs: tuple[str, ...] = ()
    default_subtitle_track_ref: str | None = None

    # When True, the absence of a default audio/subtitle reference means
    # "the user explicitly chose no default" rather than "the preset does not
    # care". The planner will then refuse to fall back to the source file's
    # is_default flag — fixing a long-standing bug where some files ended up
    # with a random default subtitle track even though the user picked None.
    audio_default_explicit: bool = False
    subtitle_default_explicit: bool = False


@dataclass(slots=True)
class TrackInfo:
    track_id: int
    kind: str
    codec: str
    language: str | None
    language_variant: str | None
    subtitle_variant: str | None
    title: str | None
    is_default: bool
    is_forced: bool

    bitrate: int | None = None
    format_name: str | None = None
    codec_id: str | None = None
    channels: str | None = None
    channels_count: int | None = None
    stream_size_bytes: int | None = None
    stream_size_ratio: float | None = None
    bit_depth: int | None = None
    frame_rate: float | None = None

    extra: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class MkvFileScan:
    path: Path
    audio_tracks: list[TrackInfo] = field(default_factory=list)
    subtitle_tracks: list[TrackInfo] = field(default_factory=list)


@dataclass(slots=True)
class RemuxPlan:
    source: Path
    target: Path
    keep_audio_track_ids: list[int]
    keep_subtitle_track_ids: list[int]
    default_audio_track_id: int | None
    default_subtitle_track_id: int | None
    copy_only: bool
