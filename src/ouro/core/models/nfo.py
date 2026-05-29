from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class TrackNfoData:
    """Track nfo data."""

    display_id: str
    kind: str
    language_display: str | None
    language_short: str | None
    format_name: str | None
    codec: str | None
    codec_id: str | None
    channels: str | None
    channels_count: int | None
    title: str | None
    is_default: bool
    is_forced: bool
    subtitle_variant: str | None
    bitrate: int | None
    size_bytes: int | None
    size_percent: float | None
    bit_depth: int | None
    frame_rate: float | None


@dataclass(slots=True)
class EpisodeNfoData:
    """Episode nfo data."""

    file_path: Path
    file_name: str
    episode_code: str | None
    episode_label: str | None
    episode_title: str | None
    container: str
    size_bytes: int
    duration_ms: int | None
    overall_bitrate_kbps: int | None
    resolution: str | None
    aspect_ratio: str | None
    aspect_ratio_display: str | None
    video_codec: str | None
    hdr_display: str | None

    video_format_name: str | None = None
    video_codec_id: str | None = None
    video_bitrate: int | None = None
    video_bit_depth: int | None = None
    video_frame_rate: float | None = None
    video_size_bytes: int | None = None
    video_size_percent: float | None = None
    video_encoding_library: str | None = None
    video_encoding_settings: str | None = None

    audio_summary: list[str] = field(default_factory=list)
    subtitle_summary: list[str] = field(default_factory=list)

    video_tracks: list[TrackNfoData] = field(default_factory=list)
    audio_tracks: list[TrackNfoData] = field(default_factory=list)
    subtitle_tracks: list[TrackNfoData] = field(default_factory=list)

    @property
    def text_tracks(self) -> list[TrackNfoData]:
        """Handle text tracks."""
        return self.subtitle_tracks

    @property
    def text(self) -> list[TrackNfoData]:
        """Handle text."""
        return self.subtitle_tracks

    @property
    def video(self) -> TrackNfoData | None:
        """Handle video."""
        return self.video_tracks[0] if self.video_tracks else None

    @property
    def audio(self) -> list[TrackNfoData]:
        """Handle audio."""
        return self.audio_tracks

    @property
    def subtitles(self) -> str:
        """Handle subtitles."""
        return ", ".join(self.subtitle_summary or [])

    @property
    def code(self) -> str | None:
        """Handle code."""
        return self.episode_code

    @property
    def aspect(self) -> str | None:
        """Handle aspect."""
        return self.aspect_ratio_display

    @property
    def size(self) -> int:
        """Handle size."""
        return self.size_bytes

    @property
    def duration(self) -> int | None:
        """Handle duration."""
        return self.duration_ms

    @property
    def hdr(self) -> str | None:
        """Handle hdr."""
        return self.hdr_display

    @property
    def display_title(self) -> str:
        """Handle display title."""
        return self.episode_title or ""

    @property
    def overall_bitrate(self) -> int | None:
        """Handle overall bitrate."""
        return self.overall_bitrate_kbps


@dataclass(slots=True)
class ReleaseNfoData:
    """Release nfo data."""

    media_kind: str
    release_title: str
    title_display: str | None
    series_title: str | None
    year: str | None
    source: str | None
    resolution: str | None
    video_tag: str | None
    audio_tag: str | None
    language_tag: str | None
    audio_languages_display: str | None
    subtitle_summary_lines: list[str] = field(default_factory=list)
    subtitle_summary_by_episode: list[str] = field(default_factory=list)
    hdr_display: str | None = None
    team: str | None = None
    total_size_bytes: int = 0
    total_duration_ms: int | None = None
    episodes: list[EpisodeNfoData] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        """Handle full name."""
        return self.release_title

    @property
    def title(self) -> str | None:
        """Backward-compatible title accessor used by metadata/prez paths."""
        if self.media_kind == "movie":
            return self.title_display or self.release_title
        return self.series_title or self.title_display or self.release_title

    @property
    def total_size(self) -> int:
        """Handle total size."""
        return self.total_size_bytes

    @property
    def total_duration(self) -> int | None:
        """Handle total duration."""
        return self.total_duration_ms

    @property
    def audio_languages(self) -> str | None:
        """Handle audio languages."""
        return self.audio_languages_display

    @property
    def series(self) -> str | None:
        """Handle series."""
        return self.series_title

    @property
    def season(self) -> str | None:
        """Handle season."""
        if self.media_kind not in {"single_episode", "season_pack", "special_pack"}:
            return None

        for episode in self.episodes:
            code = (episode.episode_code or "").upper()
            if code.startswith("S") and len(code) >= 3:
                return code[:3]
        return None

    @property
    def episode_completeness(self) -> str:
        """Handle episode completeness."""
        from ouro.core.release_inspection import completeness_label

        return completeness_label(self)

    @property
    def missing_episode_codes(self) -> tuple[str, ...]:
        """Handle missing episode codes."""
        from ouro.core.release_inspection import missing_episode_codes

        return missing_episode_codes(self)
