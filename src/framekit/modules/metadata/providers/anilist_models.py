"""AniList API response models and data transformation.

This module defines Pydantic models for AniList GraphQL API responses and provides
transformation methods to convert AniList data into Framekit's unified metadata models.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from framekit.core.models.metadata import (
    EpisodeMetadata,
    MetadataCandidate,
    MovieMetadata,
    SeasonMetadata,
)


class AniListTitle(BaseModel):
    """AniList title variants.

    AniList provides titles in multiple languages/formats.

    Attributes:
        romaji: Romanized Japanese title
        english: English title (optional)
        native: Native Japanese title (optional)
    """

    romaji: str | None = None
    english: str | None = None
    native: str | None = None

    def get_preferred(self, language: str = "en") -> str:
        """Get preferred title based on language.

        Args:
            language: Preferred language code (default: "en")

        Returns:
            Preferred title, falling back through: english -> romaji -> native
        """
        if language == "en" and self.english:
            return self.english
        if self.romaji:
            return self.romaji
        if self.native:
            return self.native
        return "Unknown Title"


class AniListCoverImage(BaseModel):
    """AniList cover image URLs.

    Attributes:
        large: Large cover image URL (optional)
        medium: Medium cover image URL (optional)
    """

    large: str | None = None
    medium: str | None = None


class AniListDate(BaseModel):
    """AniList date representation.

    AniList dates are split into year, month, and day components.

    Attributes:
        year: Year (optional)
        month: Month (optional)
        day: Day (optional)
    """

    year: int | None = None
    month: int | None = None
    day: int | None = None

    def to_iso_format(self) -> str | None:
        """Convert to ISO date format (YYYY-MM-DD).

        Returns:
            ISO formatted date string, or None if no date components
        """
        if self.year is None:
            return None

        if self.month is not None and self.day is not None:
            return f"{self.year:04d}-{self.month:02d}-{self.day:02d}"
        elif self.month is not None:
            return f"{self.year:04d}-{self.month:02d}"
        else:
            return f"{self.year:04d}"


class AniListMedia(BaseModel):
    """AniList media information.

    Represents anime or manga from AniList API.

    Attributes:
        id: AniList media ID
        title: Title variants
        description: Media description with HTML (optional)
        episodes: Number of episodes (optional)
        coverImage: Cover image URLs (optional)
        genres: List of genre names (default: empty list)
        averageScore: Average score 0-100 (optional)
        startDate: Start/air date (optional)
    """

    id: int
    title: AniListTitle
    description: str | None = None
    episodes: int | None = None
    coverImage: AniListCoverImage | None = None
    genres: list[str] = Field(default_factory=list)
    averageScore: int | None = None
    startDate: AniListDate | None = None

    def _clean_description(self, text: str | None) -> str | None:
        """Clean HTML from description.

        Args:
            text: Description text with HTML

        Returns:
            Cleaned text without HTML tags
        """
        if not text:
            return None

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)
        # Clean up extra whitespace
        text = re.sub(r"\s+", " ", text).strip()

        return text if text else None

    def _convert_score(self, score: int | None) -> float | None:
        """Convert AniList score (0-100) to standard rating (0-10).

        Args:
            score: AniList score 0-100

        Returns:
            Converted score 0-10, or None
        """
        if score is None:
            return None
        return score / 10.0

    def to_metadata_candidate(self) -> MetadataCandidate:
        """Convert to unified MetadataCandidate.

        Returns:
            MetadataCandidate with AniList data
        """
        year_str = None
        if self.startDate and self.startDate.year:
            year_str = str(self.startDate.year)

        return MetadataCandidate(
            provider_name="anilist",
            provider_id=str(self.id),
            kind="tv",
            title=self.title.get_preferred("en"),
            year=year_str,
            overview=self._clean_description(self.description),
            external_url=f"https://anilist.co/anime/{self.id}",
            confidence=0.0,
            reasons=[],
        )

    def to_season_metadata(self, season_number: int) -> SeasonMetadata:
        """Convert to unified SeasonMetadata.

        Args:
            season_number: Season number

        Returns:
            SeasonMetadata with AniList data
        """
        year_str = None
        if self.startDate and self.startDate.year:
            year_str = str(self.startDate.year)

        poster_url = None
        if self.coverImage:
            poster_url = self.coverImage.large or self.coverImage.medium

        return SeasonMetadata(
            provider_name="anilist",
            provider_id=str(self.id),
            imdb_id=None,
            external_url=f"https://anilist.co/anime/{self.id}",
            series_title=self.title.get_preferred("en"),
            series_year=year_str,
            season_number=season_number,
            overview=self._clean_description(self.description),
            episode_summaries=[],
            series_original_title=self.title.romaji,
            first_air_date=self.startDate.to_iso_format() if self.startDate else None,
            genres=self.genres,
            countries=[],
            spoken_languages=[],
            vote_average=self._convert_score(self.averageScore),
            poster_url=poster_url,
            air_date=self.startDate.to_iso_format() if self.startDate else None,
            series_provider_id=str(self.id),
            series_url=f"https://anilist.co/anime/{self.id}",
            season_url=f"https://anilist.co/anime/{self.id}",
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
            EpisodeMetadata with AniList data
        """
        year_str = None
        if self.startDate and self.startDate.year:
            year_str = str(self.startDate.year)

        poster_url = None
        if self.coverImage:
            poster_url = self.coverImage.large or self.coverImage.medium

        return EpisodeMetadata(
            provider_name="anilist",
            provider_id=str(self.id),
            imdb_id=None,
            external_url=f"https://anilist.co/anime/{self.id}",
            series_title=self.title.get_preferred("en"),
            series_year=year_str,
            season_number=season_number,
            episode_number=episode_number,
            episode_title=episode_title,
            overview=self._clean_description(self.description),
            air_date=self.startDate.to_iso_format() if self.startDate else None,
            runtime_minutes=None,
            series_original_title=self.title.romaji,
            first_air_date=self.startDate.to_iso_format() if self.startDate else None,
            genres=self.genres,
            countries=[],
            spoken_languages=[],
            vote_average=self._convert_score(self.averageScore),
            poster_url=poster_url,
            still_url=None,
            series_provider_id=str(self.id),
            series_url=f"https://anilist.co/anime/{self.id}",
            episode_url=f"https://anilist.co/anime/{self.id}",
            cast=[],
            crew=[],
        )

    def to_movie_metadata(self) -> MovieMetadata:
        """Convert to unified MovieMetadata.

        Returns:
            MovieMetadata with AniList data
        """
        year_str = None
        if self.startDate and self.startDate.year:
            year_str = str(self.startDate.year)

        poster_url = None
        if self.coverImage:
            poster_url = self.coverImage.large or self.coverImage.medium

        return MovieMetadata(
            provider_name="anilist",
            provider_id=str(self.id),
            imdb_id=None,
            external_url=f"https://anilist.co/anime/{self.id}",
            title=self.title.get_preferred("en"),
            year=year_str,
            overview=self._clean_description(self.description),
            genres=self.genres,
            runtime_minutes=None,
            original_title=self.title.romaji,
            release_date=self.startDate.to_iso_format() if self.startDate else None,
            countries=[],
            spoken_languages=[],
            vote_average=self._convert_score(self.averageScore),
            poster_url=poster_url,
            cast=[],
            crew=[],
        )
