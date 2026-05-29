"""Tests for Trakt metadata provider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from ouro.core.models.metadata import MetadataLookupRequest
from ouro.modules.metadata.providers.trakt import TraktProvider
from ouro.modules.metadata.rate_limiter import RateLimiter


@pytest.fixture
def mock_http_client():
    """Create a mock HTTP client."""
    client = MagicMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    return client


@pytest.fixture
def mock_rate_limiter():
    """Create a mock rate limiter."""
    limiter = MagicMock(spec=RateLimiter)
    limiter.acquire.return_value = True
    return limiter


@pytest.fixture
def trakt_provider(mock_http_client, mock_rate_limiter):
    """Create a Trakt provider with mocked dependencies."""
    return TraktProvider(
        client_id="test_client_id",
        client_secret="test_client_secret",
        http_client=mock_http_client,
        rate_limiter=mock_rate_limiter,
    )


class TestTraktProviderInitialization:
    """Tests for Trakt provider initialization."""

    def test_provider_name(self, trakt_provider):
        """Test provider name is correct."""
        assert trakt_provider.name == "trakt"

    def test_default_rate_limiter(self):
        """Test default rate limiter is created."""
        provider = TraktProvider(client_id="test_id")
        assert provider.rate_limiter is not None
        assert provider.rate_limiter.rate_limit.requests == 1000
        assert provider.rate_limiter.rate_limit.period == 300  # 5 minutes

    def test_custom_rate_limiter(self, mock_rate_limiter):
        """Test custom rate limiter is used."""
        provider = TraktProvider(
            client_id="test_id",
            rate_limiter=mock_rate_limiter,
        )
        assert provider.rate_limiter is mock_rate_limiter


class TestTraktMovieSearch:
    """Tests for Trakt movie search."""

    def test_search_movies_success(self, trakt_provider, mock_http_client):
        """Test successful movie search."""
        mock_http_client.request.return_value = MagicMock(
            status_code=200,
            json=lambda: [
                {
                    "type": "movie",
                    "score": 1000,
                    "movie": {
                        "title": "Test Movie",
                        "year": 2024,
                        "ids": {
                            "trakt": 12345,
                            "slug": "test-movie-2024",
                            "imdb": "tt1234567",
                            "tmdb": 98765,
                        },
                    },
                }
            ],
        )

        request = MetadataLookupRequest(
            media_kind="movie",
            title="Test Movie",
            year="2024",
        )

        results = trakt_provider.search(request)

        assert len(results) > 0
        assert results[0].provider_name == "trakt"
        assert results[0].title == "Test Movie"
        assert results[0].year == "2024"
        mock_http_client.request.assert_called_once()

    def test_search_movies_with_year_filter(self, trakt_provider, mock_http_client):
        """Test movie search with year filter."""
        mock_http_client.request.return_value = MagicMock(
            status_code=200,
            json=lambda: [
                {
                    "type": "movie",
                    "score": 1000,
                    "movie": {
                        "title": "Test Movie",
                        "year": 2024,
                        "ids": {
                            "trakt": 12345,
                            "slug": "test-movie-2024",
                        },
                    },
                }
            ],
        )

        request = MetadataLookupRequest(
            media_kind="movie",
            title="Test Movie",
            year="2024",
        )

        results = trakt_provider.search(request)

        assert len(results) > 0
        call_args = mock_http_client.request.call_args
        assert "years" in str(call_args) or "2024" in str(call_args)

    def test_search_movies_empty_results(self, trakt_provider, mock_http_client):
        """Test movie search with no results."""
        mock_http_client.request.return_value = MagicMock(
            status_code=200,
            json=list,
        )

        request = MetadataLookupRequest(
            media_kind="movie",
            title="Nonexistent Movie",
            year=None,
        )

        results = trakt_provider.search(request)

        assert len(results) == 0


class TestTraktShowSearch:
    """Tests for Trakt TV show search."""

    def test_search_shows_success(self, trakt_provider, mock_http_client):
        """Test successful TV show search."""
        mock_http_client.request.return_value = MagicMock(
            status_code=200,
            json=lambda: [
                {
                    "type": "show",
                    "score": 1000,
                    "show": {
                        "title": "Test Show",
                        "year": 2024,
                        "ids": {
                            "trakt": 54321,
                            "slug": "test-show-2024",
                            "imdb": "tt7654321",
                        },
                    },
                }
            ],
        )

        request = MetadataLookupRequest(
            media_kind="tv",
            title="Test Show",
            year="2024",
        )

        results = trakt_provider.search(request)

        assert len(results) > 0
        assert results[0].provider_name == "trakt"
        assert results[0].title == "Test Show"
        assert results[0].kind == "tv"


class TestTraktMovieDetails:
    """Tests for Trakt movie details retrieval."""

    def test_fetch_movie_success(self, trakt_provider, mock_http_client):
        """Test successful movie details fetch."""
        from ouro.core.models.metadata import MetadataCandidate

        mock_http_client.request.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "title": "Test Movie",
                "year": 2024,
                "ids": {
                    "trakt": 12345,
                    "slug": "test-movie-2024",
                    "imdb": "tt1234567",
                    "tmdb": 98765,
                },
                "overview": "A test movie overview",
                "rating": 8.5,
                "votes": 1000,
                "genres": ["action", "thriller"],
            },
        )

        candidate = MetadataCandidate(
            provider_name="trakt",
            provider_id="12345",
            kind="movie",
            title="Test Movie",
            year="2024",
        )

        metadata = trakt_provider.fetch_movie(candidate)

        assert metadata.provider_name == "trakt"
        assert metadata.title == "Test Movie"
        assert metadata.year == "2024"
        assert metadata.imdb_id == "tt1234567"
        assert metadata.overview == "A test movie overview"
        assert metadata.genres == ["action", "thriller"]

    def test_fetch_movie_not_found(self, trakt_provider, mock_http_client):
        """Test movie details fetch when not found."""
        from ouro.core.http import HttpStatusError
        from ouro.core.models.metadata import MetadataCandidate

        mock_http_client.request.side_effect = HttpStatusError(
            "Not found",
            url="https://api.trakt.tv/movies/99999",
            status_code=404,
        )

        candidate = MetadataCandidate(
            provider_name="trakt",
            provider_id="99999",
            kind="movie",
            title="Nonexistent Movie",
            year=None,
        )

        with pytest.raises(Exception):
            trakt_provider.fetch_movie(candidate)


class TestTraktEpisodeDetails:
    """Tests for Trakt episode details retrieval."""

    def test_fetch_episode_success(self, trakt_provider, mock_http_client):
        """Test successful episode details fetch."""
        from ouro.core.models.metadata import MetadataCandidate

        # Mock show details and episode details
        mock_http_client.request.side_effect = [
            MagicMock(
                status_code=200,
                json=lambda: {
                    "title": "Test Show",
                    "year": 2024,
                    "ids": {
                        "trakt": 54321,
                        "slug": "test-show-2024",
                        "imdb": "tt7654321",
                    },
                    "overview": "A test show overview",
                    "rating": 9.0,
                    "genres": ["drama", "sci-fi"],
                },
            ),
            MagicMock(
                status_code=200,
                json=lambda: {
                    "title": "Test Episode",
                    "season": 1,
                    "number": 5,
                    "ids": {
                        "trakt": 11111,
                        "slug": "test-episode",
                    },
                    "overview": "Test episode overview",
                },
            ),
        ]

        candidate = MetadataCandidate(
            provider_name="trakt",
            provider_id="54321",
            kind="tv",
            title="Test Show",
            year="2024",
            season_number=1,
            episode_number=5,
        )

        metadata = trakt_provider.fetch_episode(candidate)

        assert metadata.provider_name == "trakt"
        assert metadata.series_title == "Test Show"
        assert metadata.season_number == 1
        assert metadata.episode_number == 5
        assert metadata.episode_title == "Test Episode"


class TestTraktRateLimiting:
    """Tests for Trakt rate limiting."""

    def test_rate_limiter_called(self, trakt_provider, mock_rate_limiter, mock_http_client):
        """Test that rate limiter is called before requests."""
        mock_http_client.request.return_value = MagicMock(
            status_code=200,
            json=list,
        )

        request = MetadataLookupRequest(
            media_kind="movie",
            title="Test",
            year=None,
        )

        trakt_provider.search(request)

        # Rate limiter should be called
        assert mock_rate_limiter.acquire.called or mock_rate_limiter.try_acquire.called

    def test_rate_limit_configuration(self):
        """Test rate limit is configured correctly."""
        provider = TraktProvider(client_id="test_id")

        # Trakt allows 1000 requests per 5 minutes
        assert provider.rate_limiter.rate_limit.requests == 1000
        assert provider.rate_limiter.rate_limit.period == 300


class TestTraktErrorHandling:
    """Tests for Trakt error handling."""

    def test_handle_401_unauthorized(self, trakt_provider, mock_http_client):
        """Test handling of 401 unauthorized error."""
        from ouro.core.http import HttpAuthError

        mock_http_client.request.side_effect = HttpAuthError(
            "Unauthorized",
            url="https://api.trakt.tv/search/movie,show",
        )

        request = MetadataLookupRequest(
            media_kind="movie",
            title="Test",
            year=None,
        )

        with pytest.raises(Exception, match="[Uu]nauthorized|[Aa]uth"):
            trakt_provider.search(request)

    def test_handle_429_rate_limit(self, trakt_provider, mock_http_client):
        """Test handling of 429 rate limit error when rate limiter blocks."""
        # Set rate limiter to deny requests
        trakt_provider.rate_limiter.try_acquire = lambda: False

        request = MetadataLookupRequest(
            media_kind="movie",
            title="Test",
            year=None,
        )

        # The search method catches rate limit errors and returns empty list
        results = trakt_provider.search(request)
        assert results == []


class TestTraktSeasonDetails:
    """Tests for Trakt season details retrieval."""

    def test_fetch_season_success(self, trakt_provider, mock_http_client):
        """Test successful season details fetch."""
        from ouro.core.models.metadata import MetadataCandidate

        mock_http_client.request.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "title": "Test Show",
                "year": 2024,
                "ids": {
                    "trakt": 54321,
                    "slug": "test-show-2024",
                    "imdb": "tt7654321",
                },
                "overview": "A test show overview",
                "rating": 9.0,
                "genres": ["drama", "sci-fi"],
            },
        )

        candidate = MetadataCandidate(
            provider_name="trakt",
            provider_id="54321",
            kind="tv",
            title="Test Show",
            year="2024",
            season_number=1,
        )

        metadata = trakt_provider.fetch_season(candidate)

        assert metadata.provider_name == "trakt"
        assert metadata.series_title == "Test Show"
        assert metadata.season_number == 1
        assert metadata.genres == ["drama", "sci-fi"]
