"""TVDB API response models and data transformation.

This module defines Pydantic models for TVDB API v4 responses and provides
transformation methods to convert TVDB data into Ouro's unified metadata models.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ouro.core.models.metadata import (
    EpisodeMetadata,
    MetadataCandidate,
    SeasonMetadata,
)


class TVDBSearchResult(BaseModel):
    """TVDB search result.

    Represents a single search result from TVDB API search endpoint.

    Attributes:
        tvdb_id: TVDB series ID
        name: Series name
        year: Release year (optional)
        overview: Series overview/description (optional)
        image_url: Poster image URL (optional)
    """

    tvdb_id: str
    name: str
    year: int | None = None
    overview: str | None = None
    image_url: str | None = None

    def to_metadata_candidate(self) -> MetadataCandidate:
        """Convert to unified MetadataCandidate.

        Returns:
            MetadataCandidate with TVDB data
        """
        return MetadataCandidate(
            provider_name="tvdb",
            provider_id=self.tvdb_id,
            kind="tv",
            title=self.name,
            year=str(self.year) if self.year else None,
            overview=self.overview,
            external_url=f"https://thetvdb.com/dereferrer/series/{self.tvdb_id}",
            confidence=0.0,
            reasons=[],
        )


class TVDBSeries(BaseModel):
    """TVDB series details.

    Represents detailed series information from TVDB API.

    Attributes:
        id: TVDB series ID
        name: Series name
        overview: Series overview/description (optional)
        first_aired: First air date in YYYY-MM-DD format (optional)
        status: Series status (e.g., "Continuing", "Ended") (optional)
        genres: List of genre names (default: empty list)
        rating: Average rating (optional)
    """

    id: int
    name: str
    overview: str | None = None
    first_aired: str | None = None
    status: str | None = None
    genres: list[str] = Field(default_factory=list)
    rating: float | None = None

    def to_season_metadata(self, season_number: int) -> SeasonMetadata:
        """Convert to unified SeasonMetadata.

        Args:
            season_number: Season number for this metadata

        Returns:
            SeasonMetadata with TVDB series data
        """
        # Extract year from first_aired date
        series_year = None
        if self.first_aired and len(self.first_aired) >= 4:
            series_year = self.first_aired[:4]

        return SeasonMetadata(
            provider_name="tvdb",
            provider_id=str(self.id),
            imdb_id=None,
            external_url=f"https://thetvdb.com/dereferrer/series/{self.id}",
            series_title=self.name,
            series_year=series_year,
            season_number=season_number,
            overview=self.overview,
            episode_summaries=[],
            series_original_title=None,
            first_air_date=self.first_aired,
            genres=self.genres,
            countries=[],
            spoken_languages=[],
            vote_average=self.rating,
            poster_url=None,
            air_date=None,
            series_provider_id=str(self.id),
            series_url=f"https://thetvdb.com/dereferrer/series/{self.id}",
            season_url=None,
            cast=[],
            crew=[],
        )


class TVDBEpisode(BaseModel):
    """TVDB episode information.

    Represents a single episode from TVDB API.

    Attributes:
        id: TVDB episode ID
        name: Episode name/title
        season_number: Season number
        episode_number: Episode number within season
        overview: Episode overview/description (optional)
        aired: Air date in YYYY-MM-DD format (optional)
    """

    id: int
    name: str
    season_number: int
    episode_number: int
    overview: str | None = None
    aired: str | None = None

    def to_episode_metadata(self, series: TVDBSeries) -> EpisodeMetadata:
        """Convert to unified EpisodeMetadata.

        Args:
            series: Parent series information

        Returns:
            EpisodeMetadata with TVDB episode and series data
        """
        # Extract year from series first_aired date
        series_year = None
        if series.first_aired and len(series.first_aired) >= 4:
            series_year = series.first_aired[:4]

        return EpisodeMetadata(
            provider_name="tvdb",
            provider_id=str(self.id),
            imdb_id=None,
            external_url=f"https://thetvdb.com/dereferrer/episode/{self.id}",
            series_title=series.name,
            series_year=series_year,
            season_number=self.season_number,
            episode_number=self.episode_number,
            episode_title=self.name,
            overview=self.overview,
            air_date=self.aired,
            runtime_minutes=None,
            series_original_title=None,
            first_air_date=series.first_aired,
            genres=series.genres,
            countries=[],
            spoken_languages=[],
            vote_average=series.rating,
            poster_url=None,
            still_url=None,
            series_provider_id=str(series.id),
            series_url=f"https://thetvdb.com/dereferrer/series/{series.id}",
            episode_url=f"https://thetvdb.com/dereferrer/episode/{self.id}",
            cast=[],
            crew=[],
        )


class TVDBArtwork(BaseModel):
    """TVDB artwork information.

    Represents artwork (posters, banners, etc.) from TVDB API.

    Attributes:
        id: Artwork ID
        image: Full image URL
        thumbnail: Thumbnail image URL (optional)
        type: Artwork type (e.g., "poster", "banner", "fanart")
    """

    id: int
    image: str
    thumbnail: str | None = None
    type: str
