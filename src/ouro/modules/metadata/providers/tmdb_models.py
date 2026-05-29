"""TMDb API response models and data transformation.

This module defines Pydantic models for TMDb API v3 responses and provides
transformation methods to convert TMDb data into Ouro's unified metadata models.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ouro.core.models.metadata import (
    EpisodeMetadata,
    MetadataCandidate,
    MovieMetadata,
    SeasonMetadata,
)


class TMDbSearchResult(BaseModel):
    """TMDb search result.

    Represents a single search result from TMDb API search endpoint.

    Attributes:
        tmdb_id: TMDb ID (movie or TV series)
        title: Movie title or TV series name
        year: Release year (optional)
        overview: Overview/description (optional)
        poster_path: Poster image path (optional)
        media_type: Type of media (movie or tv)
    """

    tmdb_id: int
    title: str
    year: int | None = None
    overview: str | None = None
    poster_path: str | None = None
    media_type: str = "movie"

    def to_metadata_candidate(
        self,
        kind: str = "movie",
        confidence: float = 0.0,
        reasons: list[str] | None = None,
    ) -> MetadataCandidate:
        """Convert to unified MetadataCandidate.

        Args:
            kind: Media kind (movie, single_episode, season_pack)
            confidence: Confidence score for this match
            reasons: List of reasons for confidence score

        Returns:
            MetadataCandidate with TMDb data
        """
        base_url = "https://www.themoviedb.org"
        if self.media_type == "tv" or kind in {"single_episode", "season_pack"}:
            external_url = f"{base_url}/tv/{self.tmdb_id}"
        else:
            external_url = f"{base_url}/movie/{self.tmdb_id}"

        return MetadataCandidate(
            provider_name="tmdb",
            provider_id=str(self.tmdb_id),
            kind=kind,
            title=self.title,
            year=str(self.year) if self.year else None,
            overview=self.overview,
            external_url=external_url,
            confidence=confidence,
            reasons=reasons or [],
        )


class TMDbGenre(BaseModel):
    """TMDb genre.

    Attributes:
        id: Genre ID
        name: Genre name
    """

    id: int
    name: str


class TMDbProductionCompany(BaseModel):
    """TMDb production company.

    Attributes:
        id: Company ID
        name: Company name
        logo_path: Logo image path (optional)
        origin_country: Country code (optional)
    """

    id: int
    name: str
    logo_path: str | None = None
    origin_country: str | None = None


class TMDbCastMember(BaseModel):
    """TMDb cast member.

    Attributes:
        id: Person ID
        name: Actor name
        character: Character name
        order: Billing order
        profile_path: Profile image path (optional)
    """

    id: int
    name: str
    character: str
    order: int
    profile_path: str | None = None


class TMDbCrewMember(BaseModel):
    """TMDb crew member.

    Attributes:
        id: Person ID
        name: Crew member name
        job: Job title (e.g., Director, Writer)
        department: Department (e.g., Directing, Writing)
        profile_path: Profile image path (optional)
    """

    id: int
    name: str
    job: str
    department: str
    profile_path: str | None = None


class TMDbMovie(BaseModel):
    """TMDb movie details.

    Represents detailed movie information from TMDb API.

    Attributes:
        id: TMDb movie ID
        title: Movie title
        original_title: Original title in original language
        overview: Movie overview/description (optional)
        release_date: Release date in YYYY-MM-DD format (optional)
        runtime: Runtime in minutes (optional)
        genres: List of genres (default: empty list)
        production_companies: List of production companies (default: empty list)
        vote_average: Average rating (optional)
        vote_count: Number of votes (optional)
        poster_path: Poster image path (optional)
        backdrop_path: Backdrop image path (optional)
        budget: Budget in USD (optional)
        revenue: Revenue in USD (optional)
        imdb_id: IMDb ID (optional)
        tagline: Movie tagline (optional)
        status: Release status (optional)
        production_countries: List of production country codes (default: empty list)
        spoken_languages: List of spoken language codes (default: empty list)
    """

    id: int
    title: str
    original_title: str | None = None
    overview: str | None = None
    release_date: str | None = None
    runtime: int | None = None
    genres: list[TMDbGenre] = Field(default_factory=list)
    production_companies: list[TMDbProductionCompany] = Field(default_factory=list)
    vote_average: float | None = None
    vote_count: int | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    budget: int | None = None
    revenue: int | None = None
    imdb_id: str | None = None
    tagline: str | None = None
    status: str | None = None
    production_countries: list[dict[str, str]] = Field(default_factory=list)
    spoken_languages: list[dict[str, str]] = Field(default_factory=list)

    @property
    def release_year(self) -> str | None:
        if self.release_date and len(self.release_date) >= 4:
            return self.release_date[:4]
        return None

    @property
    def poster_url(self) -> str | None:
        if self.poster_path:
            return f"https://image.tmdb.org/t/p/w500{self.poster_path}"
        return None

    @property
    def genre_names(self) -> list[str]:
        return [genre.name for genre in self.genres]

    @property
    def country_codes(self) -> list[str]:
        return [
            country.get("iso_3166_1", "")
            for country in self.production_countries
            if country.get("iso_3166_1")
        ]

    @property
    def language_names(self) -> list[str]:
        names: list[str] = []
        for language in self.spoken_languages:
            name = (
                language.get("english_name")
                or language.get("name")
                or language.get("iso_639_1", "")
            )
            if name:
                names.append(name)
        return names

    def to_movie_metadata(
        self,
        cast: list[str] | None = None,
        crew: list[str] | None = None,
    ) -> MovieMetadata:
        """Convert to unified MovieMetadata.

        Args:
            cast: List of cast member names
            crew: List of crew member names with roles

        Returns:
            MovieMetadata with TMDb movie data
        """
        return MovieMetadata(
            provider_name="tmdb",
            provider_id=str(self.id),
            imdb_id=self.imdb_id,
            external_url=f"https://www.themoviedb.org/movie/{self.id}",
            title=self.title,
            year=self.release_year,
            overview=self.overview,
            genres=self.genre_names,
            runtime_minutes=self.runtime,
            original_title=self.original_title,
            release_date=self.release_date,
            countries=self.country_codes,
            spoken_languages=self.language_names,
            vote_average=self.vote_average,
            poster_url=self.poster_url,
            cast=cast or [],
            crew=crew or [],
        )


class TMDbTVSeries(BaseModel):
    """TMDb TV series details.

    Represents detailed TV series information from TMDb API.

    Attributes:
        id: TMDb series ID
        name: Series name
        original_name: Original name in original language
        overview: Series overview/description (optional)
        first_air_date: First air date in YYYY-MM-DD format (optional)
        last_air_date: Last air date in YYYY-MM-DD format (optional)
        genres: List of genres (default: empty list)
        production_companies: List of production companies (default: empty list)
        vote_average: Average rating (optional)
        vote_count: Number of votes (optional)
        poster_path: Poster image path (optional)
        backdrop_path: Backdrop image path (optional)
        status: Series status (optional)
        type: Series type (optional)
        number_of_seasons: Number of seasons (optional)
        number_of_episodes: Number of episodes (optional)
        origin_country: List of origin country codes (default: empty list)
        spoken_languages: List of spoken language codes (default: empty list)
        created_by: List of creators (default: empty list)
    """

    id: int
    name: str
    original_name: str | None = None
    overview: str | None = None
    first_air_date: str | None = None
    last_air_date: str | None = None
    genres: list[TMDbGenre] = Field(default_factory=list)
    production_companies: list[TMDbProductionCompany] = Field(default_factory=list)
    vote_average: float | None = None
    vote_count: int | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    status: str | None = None
    type: str | None = None
    number_of_seasons: int | None = None
    number_of_episodes: int | None = None
    origin_country: list[str] = Field(default_factory=list)
    spoken_languages: list[str] = Field(default_factory=list)
    created_by: list[dict[str, Any]] = Field(default_factory=list)

    def to_season_metadata(
        self,
        season_number: int,
        season_overview: str | None = None,
        season_air_date: str | None = None,
        season_poster_path: str | None = None,
        cast: list[str] | None = None,
        crew: list[str] | None = None,
    ) -> SeasonMetadata:
        """Convert to unified SeasonMetadata.

        Args:
            season_number: Season number for this metadata
            season_overview: Season-specific overview (optional)
            season_air_date: Season air date (optional)
            season_poster_path: Season-specific poster path (optional)
            cast: List of cast member names
            crew: List of crew member names with roles

        Returns:
            SeasonMetadata with TMDb series data
        """
        # Extract year from first_air_date
        series_year = None
        if self.first_air_date and len(self.first_air_date) >= 4:
            series_year = self.first_air_date[:4]

        # Build poster URL (prefer season poster, fallback to series poster)
        poster_url = None
        if season_poster_path:
            poster_url = f"https://image.tmdb.org/t/p/w500{season_poster_path}"
        elif self.poster_path:
            poster_url = f"https://image.tmdb.org/t/p/w500{self.poster_path}"

        # Extract genre names
        genre_names = [g.name for g in self.genres]

        return SeasonMetadata(
            provider_name="tmdb",
            provider_id=str(self.id),
            imdb_id=None,
            external_url=f"https://www.themoviedb.org/tv/{self.id}",
            series_title=self.name,
            series_year=series_year,
            season_number=season_number,
            overview=season_overview or self.overview,
            episode_summaries=[],
            series_original_title=self.original_name,
            first_air_date=self.first_air_date,
            genres=genre_names,
            countries=self.origin_country,
            spoken_languages=self.spoken_languages,
            vote_average=self.vote_average,
            poster_url=poster_url,
            air_date=season_air_date,
            series_provider_id=str(self.id),
            series_url=f"https://www.themoviedb.org/tv/{self.id}",
            season_url=f"https://www.themoviedb.org/tv/{self.id}/season/{season_number}",
            cast=cast or [],
            crew=crew or [],
        )


class TMDbEpisode(BaseModel):
    """TMDb episode details.

    Represents detailed episode information from TMDb API.

    Attributes:
        id: TMDb episode ID
        name: Episode name
        episode_number: Episode number within season
        season_number: Season number
        overview: Episode overview/description (optional)
        air_date: Air date in YYYY-MM-DD format (optional)
        runtime: Runtime in minutes (optional)
        vote_average: Average rating (optional)
        vote_count: Number of votes (optional)
        still_path: Still image path (optional)
    """

    id: int
    name: str
    episode_number: int
    season_number: int
    overview: str | None = None
    air_date: str | None = None
    runtime: int | None = None
    vote_average: float | None = None
    vote_count: int | None = None
    still_path: str | None = None

    def to_episode_metadata(
        self,
        series: TMDbTVSeries,
        imdb_id: str | None = None,
        cast: list[str] | None = None,
        crew: list[str] | None = None,
    ) -> EpisodeMetadata:
        """Convert to unified EpisodeMetadata.

        Args:
            series: Parent TV series details
            imdb_id: IMDb ID for this episode (optional)
            cast: List of cast member names
            crew: List of crew member names with roles

        Returns:
            EpisodeMetadata with TMDb episode data
        """
        # Extract year from series first_air_date
        series_year = None
        if series.first_air_date and len(series.first_air_date) >= 4:
            series_year = series.first_air_date[:4]

        # Build poster and still URLs
        poster_url = None
        if series.poster_path:
            poster_url = f"https://image.tmdb.org/t/p/w500{series.poster_path}"

        still_url = None
        if self.still_path:
            still_url = f"https://image.tmdb.org/t/p/w500{self.still_path}"

        # Extract genre names
        genre_names = [g.name for g in series.genres]

        series_url = f"https://www.themoviedb.org/tv/{series.id}"
        episode_url = f"{series_url}/season/{self.season_number}/episode/{self.episode_number}"

        return EpisodeMetadata(
            provider_name="tmdb",
            provider_id=str(self.id),
            imdb_id=imdb_id,
            external_url=series_url,
            series_title=series.name,
            series_year=series_year,
            season_number=self.season_number,
            episode_number=self.episode_number,
            episode_title=self.name,
            overview=self.overview,
            air_date=self.air_date,
            runtime_minutes=self.runtime,
            series_original_title=series.original_name,
            first_air_date=series.first_air_date,
            genres=genre_names,
            countries=series.origin_country,
            spoken_languages=series.spoken_languages,
            vote_average=self.vote_average or series.vote_average,
            poster_url=poster_url,
            still_url=still_url,
            series_provider_id=str(series.id),
            series_url=series_url,
            episode_url=episode_url,
            cast=cast or [],
            crew=crew or [],
        )


class TMDbImage(BaseModel):
    """TMDb image (poster, backdrop, still, etc.).

    Attributes:
        file_path: Image file path
        width: Image width in pixels
        height: Image height in pixels
        aspect_ratio: Image aspect ratio
        vote_average: Average rating (optional)
        vote_count: Number of votes (optional)
        iso_639_1: Language code (optional)
    """

    file_path: str
    width: int
    height: int
    aspect_ratio: float
    vote_average: float | None = None
    vote_count: int | None = None
    iso_639_1: str | None = None

    def to_poster_dict(self, name: str) -> dict[str, str | float]:
        """Convert to poster dictionary format.

        Args:
            name: Intelligent name for this poster

        Returns:
            Dictionary with poster information
        """
        return {
            "url": f"https://image.tmdb.org/t/p/w500{self.file_path}",
            "url_original": f"https://image.tmdb.org/t/p/original{self.file_path}",
            "size": f"{self.width}x{self.height}",
            "language": self.iso_639_1 or "en",
            "name": name,
            "aspect_ratio": self.aspect_ratio,
        }
