from __future__ import annotations

from dataclasses import dataclass, field

from framekit.core.models.nfo import ReleaseNfoData


@dataclass(frozen=True, slots=True)
class PrezTrack:
    language: str
    language_code: str | None
    flag_url: str | None
    codec: str
    channels: str
    bitrate: str
    variant: str
    format_name: str
    is_default: str
    is_forced: str


@dataclass(frozen=True, slots=True)
class PrezField:
    key: str
    label: str
    value: str
    url: str | None = None
    wide: bool = False


@dataclass(frozen=True, slots=True)
class PrezData:
    release: ReleaseNfoData
    title: str
    original_title: str
    year: str
    heading_title: str
    heading_subtitle: str
    season_label: str
    season_episode: str
    season_episode_range: str
    subtitle_line: str
    poster_url: str
    overview: str
    technical_summary: str
    release_name: str
    team: str
    file_size: str
    files_count: str
    source: str
    resolution: str
    video_codec: str
    video_bitrate: str
    aspect_ratio: str
    hdr: str
    tmdb_id: str
    tmdb_url: str
    imdb_id: str
    rating: str
    cast: str
    crew: str
    mediainfo_text: str | None = None
    info_fields: tuple[PrezField, ...] = ()
    metadata_fields: tuple[PrezField, ...] = ()
    release_fields: tuple[PrezField, ...] = ()
    video_fields: tuple[PrezField, ...] = ()
    audio_tracks: tuple[PrezTrack, ...] = ()
    subtitle_tracks: tuple[PrezTrack, ...] = ()
    badges: tuple[str, ...] = field(default_factory=tuple)

    @property
    def has_metadata_section(self) -> bool:
        return bool(self.metadata_fields or self.cast != "-" or self.crew != "-")

    @property
    def has_mediainfo(self) -> bool:
        return bool(self.mediainfo_text and self.mediainfo_text.strip())
