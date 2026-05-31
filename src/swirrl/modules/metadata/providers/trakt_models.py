"""Trakt API response models and data transformation.

This module defines Pydantic models for Trakt API v2 responses and provides
transformation methods to convert Trakt data into Swirrl's unified metadata models.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from swirrl.core.models.metadata import (
    EpisodeMetadata,
    MetadataCandidate,
    MovieMetadata,
    SeasonMetadata,
)


class TraktIds(BaseModel):
    """Trakt external IDs.

    Trakt provides multiple external IDs for cross-referencing with other services.

    Attributes:
        trakt: Trakt internal ID
        slug: URL-friendly slug
        imdb: IMDb ID (optional)
        tmdb: TMDb ID (optional)
    """

    trakt: int
    slug: str
    imdb: str | None = None
    tmdb: int | None = None


class TraktMovie(BaseModel):
    """Trakt movie information.

    Represents a movie from Trakt API.

    Attributes:
        title: Movie title
        year: Release year (optional)
        ids: External IDs
        overview: Movie overview/description (optional)
        rating: Average rating 0-10 (optional)
        votes: Number of votes (optional)
        genres: List of genre names (default: empty list)
    """

    title: str
    year: int | None = None
    ids: TraktIds
    overview: str | None = None
    rating: float | None = None
    votes: int | None = None
    genres: list[str] = Field(default_factory=list)

    def to_metadata_candidate(self) -> MetadataCandidate:
        """Convert to unified MetadataCandidate.

        Returns:
            MetadataCandidate with Trakt movie data
        """
        return MetadataCandidate(
            provider_name="trakt",
            provider_id=str(self.ids.trakt),
            kind="movie",
            title=self.title,
            year=str(self.year) if self.year else None,
            imdb_id=self.ids.imdb,
            overview=self.overview,
            external_url=f"https://trakt.tv/movies/{self.ids.slug}",
            confidence=0.0,
            reasons=[],
        )

    def to_movie_metadata(self) -> MovieMetadata:
        """Convert to unified MovieMetadata.

        Returns:
            MovieMetadata with Trakt movie data
        """
        return MovieMetadata(
            provider_name="trakt",
            provider_id=str(self.ids.trakt),
            imdb_id=self.ids.imdb,
            external_url=f"https://trakt.tv/movies/{self.ids.slug}",
            title=self.title,
            year=str(self.year) if self.year else None,
            overview=self.overview,
            genres=self.genres,
            runtime_minutes=None,
            original_title=None,
            release_date=None,
            countries=[],
            spoken_languages=[],
            vote_average=self.rating,
            poster_url=None,
            cast=[],
            crew=[],
        )


class TraktShow(BaseModel):
    """Trakt TV show information.

    Represents a TV show from Trakt API.

    Attributes:
        title: Show title
        year: First air year (optional)
        ids: External IDs
        overview: Show overview/description (optional)
        rating: Average rating 0-10 (optional)
        votes: Number of votes (optional)
        genres: List of genre names (default: empty list)
    """

    title: str
    year: int | None = None
    ids: TraktIds
    overview: str | None = None
    rating: float | None = None
    votes: int | None = None
    genres: list[str] = Field(default_factory=list)

    def to_metadata_candidate(self) -> MetadataCandidate:
        """Convert to unified MetadataCandidate.

        Returns:
            MetadataCandidate with Trakt show data
        """
        return MetadataCandidate(
            provider_name="trakt",
            provider_id=str(self.ids.trakt),
            kind="tv",
            title=self.title,
            year=str(self.year) if self.year else None,
            imdb_id=self.ids.imdb,
            overview=self.overview,
            external_url=f"https://trakt.tv/shows/{self.ids.slug}",
            confidence=0.0,
            reasons=[],
        )

    def to_season_metadata(self, season_number: int) -> SeasonMetadata:
        """Convert to unified SeasonMetadata.

        Args:
            season_number: Season number for this metadata

        Returns:
            SeasonMetadata with Trakt show data
        """
        return SeasonMetadata(
            provider_name="trakt",
            provider_id=str(self.ids.trakt),
            imdb_id=self.ids.imdb,
            external_url=f"https://trakt.tv/shows/{self.ids.slug}/seasons/{season_number}",
            series_title=self.title,
            series_year=str(self.year) if self.year else None,
            season_number=season_number,
            overview=self.overview,
            episode_summaries=[],
            series_original_title=None,
            first_air_date=None,
            genres=self.genres,
            countries=[],
            spoken_languages=[],
            vote_average=self.rating,
            poster_url=None,
            air_date=None,
            series_provider_id=str(self.ids.trakt),
            series_url=f"https://trakt.tv/shows/{self.ids.slug}",
            season_url=f"https://trakt.tv/shows/{self.ids.slug}/seasons/{season_number}",
            cast=[],
            crew=[],
        )

    def to_episode_metadata(
        self,
        season_number: int,
        episode_number: int,
        episode_title: str | None = None,
    ) -> EpisodeMetadata:
        """Convert to unified EpisodeMetadata.

        Args:
            season_number: Season number
            episode_number: Episode number
            episode_title: Episode title (optional)

        Returns:
            EpisodeMetadata with Trakt show data
        """
        return EpisodeMetadata(
            provider_name="trakt",
            provider_id=str(self.ids.trakt),
            imdb_id=self.ids.imdb,
            external_url=f"https://trakt.tv/shows/{self.ids.slug}/seasons/{season_number}/episodes/{episode_number}",
            series_title=self.title,
            series_year=str(self.year) if self.year else None,
            season_number=season_number,
            episode_number=episode_number,
            episode_title=episode_title,
            overview=self.overview,
            air_date=None,
            runtime_minutes=None,
            series_original_title=None,
            first_air_date=None,
            genres=self.genres,
            countries=[],
            spoken_languages=[],
            vote_average=self.rating,
            poster_url=None,
            still_url=None,
            series_provider_id=str(self.ids.trakt),
            series_url=f"https://trakt.tv/shows/{self.ids.slug}",
            episode_url=f"https://trakt.tv/shows/{self.ids.slug}/seasons/{season_number}/episodes/{episode_number}",
            cast=[],
            crew=[],
        )
