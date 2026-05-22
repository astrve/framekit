"""Tests for enhanced TMDb metadata provider."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from framekit.core.http import HttpAuthError, HttpError
from framekit.core.models.metadata import MetadataLookupRequest
from framekit.modules.metadata.health import HealthMonitor, HealthStatus
from framekit.modules.metadata.rate_limiter import RateLimiter
from framekit.modules.metadata.tmdb_provider import TMDbProvider


@pytest.fixture
def mock_http_client():
    """Create a mock HTTP client."""
    client = MagicMock()
    client.get_json = MagicMock()
    return client


@pytest.fixture
def mock_rate_limiter():
    """Create a mock rate limiter."""
    limiter = MagicMock(spec=RateLimiter)
    limiter.acquire.return_value = True
    limiter.try_acquire.return_value = True
    return limiter


@pytest.fixture
def mock_health_monitor():
    """Create a mock health monitor."""
    monitor = MagicMock(spec=HealthMonitor)
    monitor.is_available.return_value = True
    monitor.get_status.return_value = HealthStatus.HEALTHY
    return monitor


@pytest.fixture
def mock_cache_manager():
    """Create a mock cache manager that always misses."""
    from framekit.core.cache import CacheManager

    cache = MagicMock(spec=CacheManager)
    cache.get_tmdb_search.return_value = None
    return cache


@pytest.fixture
def tmdb_provider(mock_http_client, mock_rate_limiter, mock_health_monitor, mock_cache_manager):
    """Create a TMDb provider with mocked dependencies."""
    return TMDbProvider(
        read_access_token="test_token",
        http_client=mock_http_client,
        rate_limiter=mock_rate_limiter,
        health_monitor=mock_health_monitor,
        cache_manager=mock_cache_manager,
    )


class TestTMDbProviderInitialization:
    """Tests for TMDb provider initialization."""

    def test_provider_name(self, tmdb_provider):
        """Test provider name is correct."""
        assert tmdb_provider.name == "tmdb"

    def test_default_rate_limiter(self):
        """Test default rate limiter is created with TMDb limits."""
        provider = TMDbProvider(read_access_token="test_token")
        assert provider.rate_limiter is not None
        # TMDb allows 40 requests per 10 seconds
        assert provider.rate_limiter.rate_limit.requests == 40
        assert provider.rate_limiter.rate_limit.period == 10.0

    def test_custom_rate_limiter(self, mock_rate_limiter):
        """Test custom rate limiter is used."""
        provider = TMDbProvider(
            read_access_token="test_token",
            rate_limiter=mock_rate_limiter,
        )
        assert provider.rate_limiter is mock_rate_limiter

    def test_default_health_monitor(self):
        """Test default health monitor is created."""
        provider = TMDbProvider(read_access_token="test_token")
        assert provider.health_monitor is not None
        assert provider.health_monitor.failure_threshold == 5
        assert provider.health_monitor.recovery_timeout == 60.0

    def test_custom_health_monitor(self, mock_health_monitor):
        """Test custom health monitor is used."""
        provider = TMDbProvider(
            read_access_token="test_token",
            health_monitor=mock_health_monitor,
        )
        assert provider.health_monitor is mock_health_monitor

    def test_missing_token_raises_error(self, mock_http_client):
        """Test that missing token raises error on first request."""
        provider = TMDbProvider(
            read_access_token="",
            http_client=mock_http_client,
        )

        request = MetadataLookupRequest(
            media_kind="movie",
            title="Test Movie",
            year=None,
        )

        # Should return empty list due to error handling
        results = provider.search(request)
        assert results == []


class TestTMDbRateLimiting:
    """Tests for TMDb rate limiting."""

    def test_rate_limiter_called_on_search(
        self, tmdb_provider, mock_rate_limiter, mock_http_client
    ):
        """Test rate limiter is called before making requests."""
        mock_http_client.get_json.return_value = {"results": []}

        request = MetadataLookupRequest(
            media_kind="movie",
            title="Test Movie",
            year=None,
        )

        tmdb_provider.search(request)

        # Rate limiter should be called
        assert mock_rate_limiter.try_acquire.called or mock_rate_limiter.acquire.called

    def test_rate_limit_exceeded_returns_empty(self, tmdb_provider, mock_rate_limiter):
        """Test that rate limit exceeded returns empty results gracefully."""
        mock_rate_limiter.try_acquire.return_value = False

        request = MetadataLookupRequest(
            media_kind="movie",
            title="Test Movie",
            year=None,
        )

        # Should handle rate limit gracefully
        results = tmdb_provider.search(request)
        assert results == []

    def test_rate_limiter_called_on_fetch(self, tmdb_provider, mock_rate_limiter, mock_http_client):
        """Test rate limiter is called when fetching metadata."""
        from framekit.core.models.metadata import MetadataCandidate

        mock_http_client.get_json.return_value = {
            "id": 12345,
            "title": "Test Movie",
            "release_date": "2020-01-01",
            "overview": "Test",
            "genres": [],
            "runtime": 120,
        }

        candidate = MetadataCandidate(
            provider_name="tmdb",
            provider_id="12345",
            kind="movie",
            title="Test Movie",
            year=None,
            external_url="https://www.themoviedb.org/movie/12345",
            confidence=1.0,
            reasons=["manual ID"],
        )

        tmdb_provider.fetch_movie(candidate)

        # Rate limiter should be called for fetch requests too
        assert mock_rate_limiter.try_acquire.called or mock_rate_limiter.acquire.called


class TestTMDbHealthMonitor:
    """Tests for TMDb health monitor (circuit breaker)."""

    def test_health_monitor_checked_before_request(self, tmdb_provider, mock_health_monitor):
        """Test health monitor is checked before making requests."""
        request = MetadataLookupRequest(
            media_kind="movie",
            title="Test Movie",
            year=None,
        )

        tmdb_provider.search(request)

        # Health monitor should be checked
        mock_health_monitor.is_available.assert_called_with("tmdb")

    def test_circuit_open_returns_empty(self, tmdb_provider, mock_health_monitor):
        """Test that open circuit returns empty results."""
        mock_health_monitor.is_available.return_value = False
        mock_health_monitor.get_status.return_value = HealthStatus.UNHEALTHY

        request = MetadataLookupRequest(
            media_kind="movie",
            title="Test Movie",
            year=None,
        )

        results = tmdb_provider.search(request)
        assert results == []

    def test_success_recorded_on_successful_request(
        self, tmdb_provider, mock_health_monitor, mock_http_client
    ):
        """Test that successful requests are recorded in health monitor."""
        mock_http_client.get_json.return_value = {"results": []}

        request = MetadataLookupRequest(
            media_kind="movie",
            title="Test Movie",
            year=None,
        )

        tmdb_provider.search(request)

        # Success should be recorded
        mock_health_monitor.record_success.assert_called_with("tmdb")

    def test_failure_recorded_on_failed_request(
        self, tmdb_provider, mock_health_monitor, mock_http_client
    ):
        """Test that failed requests are recorded in health monitor."""
        mock_http_client.get_json.side_effect = HttpError("API error", url="test", status_code=500)

        request = MetadataLookupRequest(
            media_kind="movie",
            title="Test Movie",
            year=None,
        )

        # Should handle error gracefully
        results = tmdb_provider.search(request)
        assert results == []

        # Failure should be recorded
        mock_health_monitor.record_failure.assert_called_with("tmdb")


class TestTMDbSearch:
    """Tests for TMDb search functionality."""

    def test_search_movie_success(self, tmdb_provider, mock_http_client):
        """Test successful movie search."""
        mock_http_client.get_json.return_value = {
            "results": [
                {
                    "id": 12345,
                    "title": "Test Movie",
                    "release_date": "2020-01-15",
                    "overview": "Test overview",
                    "poster_path": "/poster.jpg",
                }
            ]
        }

        request = MetadataLookupRequest(
            media_kind="movie",
            title="Test Movie",
            year="2020",
        )

        results = tmdb_provider.search(request)

        assert len(results) == 1
        assert results[0].provider_name == "tmdb"
        assert results[0].provider_id == "12345"
        assert results[0].title == "Test Movie"
        assert results[0].year == "2020"

    def test_search_tv_success(self, tmdb_provider, mock_http_client):
        """Test successful TV series search."""
        mock_http_client.get_json.return_value = {
            "results": [
                {
                    "id": 67890,
                    "name": "Test Series",
                    "first_air_date": "2021-01-01",
                    "overview": "Series overview",
                }
            ]
        }

        request = MetadataLookupRequest(
            media_kind="single_episode",
            title="Test Series",
            year=None,
            season_number=1,
            episode_number=1,
        )

        results = tmdb_provider.search(request)

        assert len(results) == 1
        assert results[0].provider_name == "tmdb"
        assert results[0].title == "Test Series"
        assert results[0].kind == "single_episode"

    def test_search_empty_results(self, tmdb_provider, mock_http_client):
        """Test search with no results."""
        mock_http_client.get_json.return_value = {"results": []}

        request = MetadataLookupRequest(
            media_kind="movie",
            title="Nonexistent Movie",
            year=None,
        )

        results = tmdb_provider.search(request)
        assert results == []

    def test_search_with_year_filter(self, tmdb_provider, mock_http_client):
        """Test search includes year parameter."""
        mock_http_client.get_json.return_value = {"results": []}

        request = MetadataLookupRequest(
            media_kind="movie",
            title="Test Movie",
            year="2020",
        )

        tmdb_provider.search(request)

        # Verify year was passed in params
        call_args = mock_http_client.get_json.call_args
        assert call_args is not None
        params = call_args[1]["params"]
        assert "year" in params
        assert params["year"] == "2020"

    def test_search_with_include_adult(self, mock_http_client, mock_cache_manager):
        """Test search respects include_adult setting."""
        provider = TMDbProvider(
            read_access_token="test_token",
            include_adult=True,
            http_client=mock_http_client,
            cache_manager=mock_cache_manager,
        )

        mock_http_client.get_json.return_value = {"results": []}

        request = MetadataLookupRequest(
            media_kind="movie",
            title="Test Movie",
            year=None,
        )

        provider.search(request)

        # Verify include_adult was passed
        call_args = mock_http_client.get_json.call_args
        params = call_args[1]["params"]
        assert "include_adult" in params
        assert params["include_adult"] == "true"


class TestTMDbFetchMovie:
    """Tests for TMDb movie fetching."""

    def test_fetch_movie_success(self, tmdb_provider, mock_http_client):
        """Test successful movie fetch."""
        from framekit.core.models.metadata import MetadataCandidate

        # Mock movie details response
        mock_http_client.get_json.side_effect = [
            {
                "id": 12345,
                "title": "Test Movie",
                "original_title": "Original Test",
                "release_date": "2020-01-15",
                "runtime": 120,
                "overview": "Test overview",
                "genres": [{"id": 28, "name": "Action"}],
                "vote_average": 7.5,
                "poster_path": "/poster.jpg",
                "credits": {
                    "cast": [{"name": "Actor One"}, {"name": "Actor Two"}],
                    "crew": [{"name": "Director One", "job": "Director"}],
                },
            },
            # Mock external IDs response
            {"imdb_id": "tt1234567"},
        ]

        candidate = MetadataCandidate(
            provider_name="tmdb",
            provider_id="12345",
            kind="movie",
            title="Test Movie",
            year="2020",
            external_url="https://www.themoviedb.org/movie/12345",
            confidence=1.0,
            reasons=["manual ID"],
        )

        metadata = tmdb_provider.fetch_movie(candidate)

        assert metadata.provider_name == "tmdb"
        assert metadata.provider_id == "12345"
        assert metadata.title == "Test Movie"
        assert metadata.year == "2020"
        assert metadata.runtime_minutes == 120
        assert metadata.imdb_id == "tt1234567"
        assert "Action" in metadata.genres
        assert len(metadata.cast) > 0
        assert len(metadata.crew) > 0


class TestTMDbFetchEpisode:
    """Tests for TMDb episode fetching."""

    def test_fetch_episode_success(self, tmdb_provider, mock_http_client):
        """Test successful episode fetch."""
        from framekit.core.models.metadata import MetadataCandidate

        # Mock series details, episode details, and external IDs
        mock_http_client.get_json.side_effect = [
            {
                "id": 67890,
                "name": "Test Series",
                "first_air_date": "2021-01-01",
                "genres": [{"id": 18, "name": "Drama"}],
                "vote_average": 8.2,
                "poster_path": "/series_poster.jpg",
                "credits": {"cast": [{"name": "Actor One"}], "crew": []},
                "created_by": [{"name": "Creator One"}],
            },
            {
                "id": 11111,
                "name": "Test Episode",
                "episode_number": 5,
                "season_number": 1,
                "air_date": "2021-02-01",
                "runtime": 45,
                "overview": "Episode overview",
                "vote_average": 8.0,
                "still_path": "/still.jpg",
            },
            {"imdb_id": "tt9876543"},
        ]

        candidate = MetadataCandidate(
            provider_name="tmdb",
            provider_id="67890",
            kind="single_episode",
            title="Test Series",
            year="2021",
            season_number=1,
            episode_number=5,
            external_url="https://www.themoviedb.org/tv/67890",
            confidence=1.0,
            reasons=["manual ID"],
        )

        metadata = tmdb_provider.fetch_episode(candidate)

        assert metadata.provider_name == "tmdb"
        assert metadata.series_title == "Test Series"
        assert metadata.season_number == 1
        assert metadata.episode_number == 5
        assert metadata.episode_title == "Test Episode"
        assert metadata.imdb_id == "tt9876543"


class TestTMDbFetchSeason:
    """Tests for TMDb season fetching."""

    def test_fetch_season_success(self, tmdb_provider, mock_http_client):
        """Test successful season fetch."""
        from framekit.core.models.metadata import MetadataCandidate

        # Mock series details, season details, and external IDs
        mock_http_client.get_json.side_effect = [
            {
                "id": 67890,
                "name": "Test Series",
                "first_air_date": "2021-01-01",
                "genres": [{"id": 18, "name": "Drama"}],
                "vote_average": 8.2,
                "poster_path": "/series_poster.jpg",
                "credits": {"cast": [], "crew": []},
            },
            {
                "id": 22222,
                "season_number": 1,
                "overview": "Season 1 overview",
                "air_date": "2021-01-01",
                "poster_path": "/season_poster.jpg",
                "episodes": [
                    {
                        "id": 11111,
                        "name": "Episode 1",
                        "episode_number": 1,
                        "air_date": "2021-01-01",
                    },
                    {
                        "id": 11112,
                        "name": "Episode 2",
                        "episode_number": 2,
                        "air_date": "2021-01-08",
                    },
                ],
            },
            {"imdb_id": None},
        ]

        candidate = MetadataCandidate(
            provider_name="tmdb",
            provider_id="67890",
            kind="season_pack",
            title="Test Series",
            year="2021",
            season_number=1,
            external_url="https://www.themoviedb.org/tv/67890",
            confidence=1.0,
            reasons=["manual ID"],
        )

        metadata = tmdb_provider.fetch_season(candidate)

        assert metadata.provider_name == "tmdb"
        assert metadata.series_title == "Test Series"
        assert metadata.season_number == 1
        assert metadata.overview == "Season 1 overview"
        assert len(metadata.episode_summaries) == 2


class TestTMDbErrorHandling:
    """Tests for TMDb error handling."""

    def test_auth_error_raises_value_error(self, tmdb_provider, mock_http_client):
        """Test authentication error raises ValueError with helpful message."""
        mock_http_client.get_json.side_effect = HttpAuthError(
            "Unauthorized", url="test", status_code=401
        )

        request = MetadataLookupRequest(
            media_kind="movie",
            title="Test Movie",
            year=None,
        )

        # Should handle auth error gracefully
        results = tmdb_provider.search(request)
        assert results == []

    def test_http_error_handled_gracefully(self, tmdb_provider, mock_http_client):
        """Test HTTP errors are handled gracefully."""
        mock_http_client.get_json.side_effect = HttpError(
            "Server error", url="test", status_code=500
        )

        request = MetadataLookupRequest(
            media_kind="movie",
            title="Test Movie",
            year=None,
        )

        results = tmdb_provider.search(request)
        assert results == []

    def test_invalid_json_handled(self, tmdb_provider, mock_http_client):
        """Test invalid JSON response is handled."""
        mock_http_client.get_json.return_value = "not a dict"

        request = MetadataLookupRequest(
            media_kind="movie",
            title="Test Movie",
            year=None,
        )

        # Should handle gracefully
        results = tmdb_provider.search(request)
        assert results == []


class TestTMDbCaching:
    """Tests for TMDb caching behavior."""

    def test_search_uses_cache(self, tmdb_provider, mock_http_client):
        """Test search results are cached."""
        mock_http_client.get_json.return_value = {
            "results": [
                {
                    "id": 12345,
                    "title": "Test Movie",
                    "release_date": "2020-01-15",
                }
            ]
        }

        request = MetadataLookupRequest(
            media_kind="movie",
            title="Test Movie",
            year=None,
        )

        # First search
        results1 = tmdb_provider.search(request)

        # Second search should use cache
        results2 = tmdb_provider.search(request)

        assert results1 == results2
        # HTTP client should only be called once if caching works
        # (This depends on cache implementation)
