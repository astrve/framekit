"""Tests for Trakt models and data transformation."""

from __future__ import annotations

from framekit.core.models.metadata import (
    EpisodeMetadata,
    MetadataCandidate,
    MovieMetadata,
    SeasonMetadata,
)
from framekit.modules.metadata.providers.trakt_models import (
    TraktIds,
    TraktMovie,
    TraktShow,
)


class TestTraktIds:
    """Tests for TraktIds model."""

    def test_basic_ids(self):
        """Test basic IDs parsing."""
        ids = TraktIds(
            trakt=12345,
            slug="test-movie-2024",
            imdb="tt1234567",
            tmdb=98765,
        )

        assert ids.trakt == 12345
        assert ids.slug == "test-movie-2024"
        assert ids.imdb == "tt1234567"
        assert ids.tmdb == 98765

    def test_ids_optional_fields(self):
        """Test IDs with optional fields missing."""
        ids = TraktIds(
            trakt=12345,
            slug="test-movie-2024",
        )

        assert ids.trakt == 12345
        assert ids.slug == "test-movie-2024"
        assert ids.imdb is None
        assert ids.tmdb is None


class TestTraktMovie:
    """Tests for TraktMovie model."""

    def test_basic_movie(self):
        """Test basic movie parsing."""
        movie = TraktMovie(
            title="Test Movie",
            year=2024,
            ids=TraktIds(
                trakt=12345,
                slug="test-movie-2024",
                imdb="tt1234567",
                tmdb=98765,
            ),
            overview="A test movie overview",
            rating=8.5,
            votes=1000,
            genres=["action", "thriller"],
        )

        assert movie.title == "Test Movie"
        assert movie.year == 2024
        assert movie.ids.trakt == 12345
        assert movie.overview == "A test movie overview"
        assert movie.rating == 8.5
        assert movie.votes == 1000
        assert movie.genres == ["action", "thriller"]

    def test_movie_optional_fields(self):
        """Test movie with optional fields missing."""
        movie = TraktMovie(
            title="Test Movie",
            ids=TraktIds(
                trakt=12345,
                slug="test-movie-2024",
            ),
        )

        assert movie.title == "Test Movie"
        assert movie.year is None
        assert movie.overview is None
        assert movie.rating is None
        assert movie.votes is None
        assert movie.genres == []

    def test_movie_to_metadata_candidate(self):
        """Test conversion to MetadataCandidate."""
        movie = TraktMovie(
            title="Test Movie",
            year=2024,
            ids=TraktIds(
                trakt=12345,
                slug="test-movie-2024",
                imdb="tt1234567",
            ),
            overview="A test movie overview",
        )

        candidate = movie.to_metadata_candidate()

        assert isinstance(candidate, MetadataCandidate)
        assert candidate.provider_name == "trakt"
        assert candidate.provider_id == "12345"
        assert candidate.kind == "movie"
        assert candidate.title == "Test Movie"
        assert candidate.year == "2024"
        assert candidate.imdb_id == "tt1234567"
        assert candidate.overview == "A test movie overview"
        assert "trakt.tv" in candidate.external_url

    def test_movie_to_movie_metadata(self):
        """Test conversion to MovieMetadata."""
        movie = TraktMovie(
            title="Test Movie",
            year=2024,
            ids=TraktIds(
                trakt=12345,
                slug="test-movie-2024",
                imdb="tt1234567",
                tmdb=98765,
            ),
            overview="A test movie overview",
            rating=8.5,
            votes=1000,
            genres=["action", "thriller"],
        )

        metadata = movie.to_movie_metadata()

        assert isinstance(metadata, MovieMetadata)
        assert metadata.provider_name == "trakt"
        assert metadata.provider_id == "12345"
        assert metadata.imdb_id == "tt1234567"
        assert metadata.title == "Test Movie"
        assert metadata.year == "2024"
        assert metadata.overview == "A test movie overview"
        assert metadata.genres == ["action", "thriller"]
        assert metadata.vote_average == 8.5
        assert "trakt.tv" in metadata.external_url


class TestTraktShow:
    """Tests for TraktShow model."""

    def test_basic_show(self):
        """Test basic show parsing."""
        show = TraktShow(
            title="Test Show",
            year=2024,
            ids=TraktIds(
                trakt=54321,
                slug="test-show-2024",
                imdb="tt7654321",
                tmdb=56789,
            ),
            overview="A test show overview",
            rating=9.0,
            votes=5000,
            genres=["drama", "sci-fi"],
        )

        assert show.title == "Test Show"
        assert show.year == 2024
        assert show.ids.trakt == 54321
        assert show.overview == "A test show overview"
        assert show.rating == 9.0
        assert show.votes == 5000
        assert show.genres == ["drama", "sci-fi"]

    def test_show_optional_fields(self):
        """Test show with optional fields missing."""
        show = TraktShow(
            title="Test Show",
            ids=TraktIds(
                trakt=54321,
                slug="test-show-2024",
            ),
        )

        assert show.title == "Test Show"
        assert show.year is None
        assert show.overview is None
        assert show.rating is None
        assert show.votes is None
        assert show.genres == []

    def test_show_to_metadata_candidate(self):
        """Test conversion to MetadataCandidate."""
        show = TraktShow(
            title="Test Show",
            year=2024,
            ids=TraktIds(
                trakt=54321,
                slug="test-show-2024",
                imdb="tt7654321",
            ),
            overview="A test show overview",
        )

        candidate = show.to_metadata_candidate()

        assert isinstance(candidate, MetadataCandidate)
        assert candidate.provider_name == "trakt"
        assert candidate.provider_id == "54321"
        assert candidate.kind == "tv"
        assert candidate.title == "Test Show"
        assert candidate.year == "2024"
        assert candidate.imdb_id == "tt7654321"
        assert candidate.overview == "A test show overview"
        assert "trakt.tv" in candidate.external_url

    def test_show_to_season_metadata(self):
        """Test conversion to SeasonMetadata."""
        show = TraktShow(
            title="Test Show",
            year=2024,
            ids=TraktIds(
                trakt=54321,
                slug="test-show-2024",
                imdb="tt7654321",
            ),
            overview="A test show overview",
            rating=9.0,
            genres=["drama", "sci-fi"],
        )

        metadata = show.to_season_metadata(season_number=1)

        assert isinstance(metadata, SeasonMetadata)
        assert metadata.provider_name == "trakt"
        assert metadata.provider_id == "54321"
        assert metadata.imdb_id == "tt7654321"
        assert metadata.series_title == "Test Show"
        assert metadata.series_year == "2024"
        assert metadata.season_number == 1
        assert metadata.overview == "A test show overview"
        assert metadata.genres == ["drama", "sci-fi"]
        assert metadata.vote_average == 9.0
        assert "trakt.tv" in metadata.external_url

    def test_show_to_episode_metadata(self):
        """Test conversion to EpisodeMetadata."""
        show = TraktShow(
            title="Test Show",
            year=2024,
            ids=TraktIds(
                trakt=54321,
                slug="test-show-2024",
                imdb="tt7654321",
            ),
            overview="A test show overview",
            rating=9.0,
            genres=["drama", "sci-fi"],
        )

        metadata = show.to_episode_metadata(
            season_number=1,
            episode_number=5,
            episode_title="Test Episode",
        )

        assert isinstance(metadata, EpisodeMetadata)
        assert metadata.provider_name == "trakt"
        assert metadata.provider_id == "54321"
        assert metadata.imdb_id == "tt7654321"
        assert metadata.series_title == "Test Show"
        assert metadata.series_year == "2024"
        assert metadata.season_number == 1
        assert metadata.episode_number == 5
        assert metadata.episode_title == "Test Episode"
        assert metadata.overview == "A test show overview"
        assert metadata.genres == ["drama", "sci-fi"]
        assert metadata.vote_average == 9.0
        assert "trakt.tv" in metadata.external_url


# Made with Bob
