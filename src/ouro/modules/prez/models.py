from __future__ import annotations

from dataclasses import dataclass, field

from ouro.core.models.nfo import ReleaseNfoData


@dataclass(frozen=True, slots=True)
class PrezTrack:
    """Prez track."""

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
class PrezTrackGroup:
    """Group of tracks sharing the same language."""

    language: str
    language_code: str | None
    flag_url: str | None
    tracks: tuple[PrezTrack, ...]


@dataclass(frozen=True, slots=True)
class PrezField:
    """Prez field."""

    key: str
    label: str
    value: str
    url: str | None = None
    wide: bool = False


@dataclass(frozen=True, slots=True)
class PrezData:
    """Prez data."""

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
    audio_track_groups: tuple[PrezTrackGroup, ...] = ()
    subtitle_track_groups: tuple[PrezTrackGroup, ...] = ()
    badges: tuple[str, ...] = field(default_factory=tuple)
    banner_audio: str = ""
    banner_information: str = ""
    banner_metadata: str = ""
    banner_release: str = ""
    banner_subtitles: str = ""
    banner_synopsis: str = ""
    banner_technical: str = ""

    @property
    def has_metadata_section(self) -> bool:
        """Return ``True`` if has metadata section."""
        return bool(self.metadata_fields or self.cast != "-" or self.crew != "-")

    @property
    def has_mediainfo(self) -> bool:
        """Return ``True`` if has mediainfo."""
        return bool(self.mediainfo_text and self.mediainfo_text.strip())
