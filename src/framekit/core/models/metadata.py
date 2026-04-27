from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class MetadataLookupRequest:
    media_kind: str
    title: str | None
    year: str | None
    season_number: int | None = None
    episode_number: int | None = None
    release_title: str | None = None


@dataclass(slots=True)
class MetadataCandidate:
    provider_name: str
    provider_id: str
    kind: str

    title: str
    year: str | None
    season_number: int | None = None
    episode_number: int | None = None

    imdb_id: str | None = None
    external_url: str | None = None
    overview: str | None = None

    confidence: float = 0.0
    reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MovieMetadata:
    provider_name: str
    provider_id: str
    imdb_id: str | None
    external_url: str | None

    title: str
    year: str | None
    overview: str | None
    genres: list[str] = field(default_factory=list)
    runtime_minutes: int | None = None
    original_title: str | None = None
    release_date: str | None = None
    countries: list[str] = field(default_factory=list)
    spoken_languages: list[str] = field(default_factory=list)
    vote_average: float | None = None
    poster_url: str | None = None
    cast: list[str] = field(default_factory=list)
    crew: list[str] = field(default_factory=list)


@dataclass(slots=True)
class EpisodeMetadata:
    provider_name: str
    provider_id: str
    imdb_id: str | None
    external_url: str | None

    series_title: str
    series_year: str | None
    season_number: int | None
    episode_number: int | None

    episode_title: str | None
    overview: str | None
    air_date: str | None = None
    runtime_minutes: int | None = None
    series_original_title: str | None = None
    first_air_date: str | None = None
    genres: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    spoken_languages: list[str] = field(default_factory=list)
    vote_average: float | None = None
    poster_url: str | None = None
    still_url: str | None = None
    series_provider_id: str | None = None
    series_url: str | None = None
    episode_url: str | None = None
    cast: list[str] = field(default_factory=list)
    crew: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SeasonMetadata:
    provider_name: str
    provider_id: str
    imdb_id: str | None
    external_url: str | None

    series_title: str
    series_year: str | None
    season_number: int | None

    overview: str | None
    episode_summaries: list[EpisodeMetadata] = field(default_factory=list)
    series_original_title: str | None = None
    first_air_date: str | None = None
    genres: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    spoken_languages: list[str] = field(default_factory=list)
    vote_average: float | None = None
    poster_url: str | None = None
    air_date: str | None = None
    series_provider_id: str | None = None
    series_url: str | None = None
    season_url: str | None = None
    cast: list[str] = field(default_factory=list)
    crew: list[str] = field(default_factory=list)
