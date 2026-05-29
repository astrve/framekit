"""Tests for AniList metadata provider."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ouro.core.models.metadata import MetadataLookupRequest
from ouro.modules.metadata.providers.anilist import AniListProvider
from ouro.modules.metadata.rate_limiter import RateLimiter


@pytest.fixture
def mock_http_client():
    """Create a mock HTTP client."""
    client = MagicMock()
    client.request = MagicMock()
    return client


@pytest.fixture
def mock_rate_limiter():
    """Create a mock rate limiter."""
    limiter = MagicMock(spec=RateLimiter)
    limiter.acquire.return_value = True
    return limiter


@pytest.fixture
def anilist_provider(mock_http_client, mock_rate_limiter):
    """Create an AniList provider with mocked dependencies."""
    return AniListProvider(
        http_client=mock_http_client,
        rate_limiter=mock_rate_limiter,
    )


class TestAniListProviderInitialization:
    """Tests for AniList provider initialization."""

    def test_provider_name(self, anilist_provider):
        """Test provider name is correct."""
        assert anilist_provider.name == "anilist"

    def test_default_http_client(self):
        """Test default HTTP client is created."""
        provider = AniListProvider()
        assert provider.http_client is not None

    def test_default_rate_limiter(self):
        """Test default rate limiter is created."""
        provider = AniListProvider()
        assert provider.rate_limiter is not None
        assert provider.rate_limiter.rate_limit.requests == 90
        assert provider.rate_limiter.rate_limit.period == 60  # 90 per minute

    def test_custom_rate_limiter(self, mock_rate_limiter):
        """Test custom rate limiter is used."""
        provider = AniListProvider(rate_limiter=mock_rate_limiter)
        assert provider.rate_limiter is mock_rate_limiter


class TestAniListSearch:
    """Tests for AniList search functionality."""

    def test_search_anime_success(self, anilist_provider, mock_http_client):
        """Test successful anime search."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "Page": {
                    "media": [
                        {
                            "id": 12345,
                            "title": {
                                "romaji": "Test Anime",
                                "english": "Test Anime English",
                                "native": "テストアニメ",
                            },
                            "description": "Test description",
                            "episodes": 24,
                            "coverImage": {
                                "large": "https://example.com/large.jpg",
                                "medium": "https://example.com/medium.jpg",
                            },
                            "genres": ["Action", "Drama"],
                            "averageScore": 85,
                            "startDate": {
                                "year": 2020,
                                "month": 3,
                                "day": 15,
                            },
                        }
                    ]
                }
            }
        }
        mock_http_client.request.return_value = mock_response

        request = MetadataLookupRequest(
            media_kind="tv",
            title="Test Anime",
            year="2020",
        )

        results = anilist_provider.search(request)

        assert len(results) == 1
        assert results[0].provider_name == "anilist"
        assert results[0].provider_id == "12345"
        assert results[0].title == "Test Anime English"
        assert results[0].year == "2020"

    def test_search_with_year_filter(self, anilist_provider, mock_http_client):
        """Test search with year filtering."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "Page": {
                    "media": [
                        {
                            "id": 12345,
                            "title": {"romaji": "Test Anime"},
                            "startDate": {"year": 2020},
                        }
                    ]
                }
            }
        }
        mock_http_client.request.return_value = mock_response

        request = MetadataLookupRequest(
            media_kind="tv",
            title="Test Anime",
            year="2020",
        )

        results = anilist_provider.search(request)

        # Verify GraphQL query includes year filter
        call_args = mock_http_client.request.call_args
        if call_args:
            query_data = call_args[1].get("json_body", {})
            assert "seasonYear" in query_data.get("variables", {})

    def test_search_empty_results(self, anilist_provider, mock_http_client):
        """Test search with no results."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"Page": {"media": []}}}
        mock_http_client.request.return_value = mock_response

        request = MetadataLookupRequest(
            media_kind="tv",
            title="Nonexistent Anime",
            year=None,
        )

        results = anilist_provider.search(request)

        assert len(results) == 0

    def test_search_rate_limiting(self, anilist_provider, mock_rate_limiter):
        """Test rate limiting is applied during search."""
        mock_http_client = anilist_provider.http_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"Page": {"media": []}}}
        mock_http_client.request.return_value = mock_response

        request = MetadataLookupRequest(
            media_kind="tv",
            title="Test Anime",
            year=None,
        )

        anilist_provider.search(request)

        # Verify rate limiter was called
        mock_rate_limiter.acquire.assert_called()


class TestAniListFetchEpisode:
    """Tests for AniList episode fetching."""

    def test_fetch_episode_success(self, anilist_provider, mock_http_client):
        """Test successful episode fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "Media": {
                    "id": 12345,
                    "title": {
                        "romaji": "Test Anime",
                        "english": "Test Anime English",
                    },
                    "description": "Test description",
                    "episodes": 24,
                    "genres": ["Action", "Drama"],
                    "averageScore": 85,
                    "startDate": {
                        "year": 2020,
                        "month": 3,
                        "day": 15,
                    },
                    "coverImage": {
                        "large": "https://example.com/large.jpg",
                    },
                }
            }
        }
        mock_http_client.request.return_value = mock_response

        from ouro.core.models.metadata import MetadataCandidate

        candidate = MetadataCandidate(
            provider_name="anilist",
            provider_id="12345",
            kind="tv",
            title="Test Anime",
            year="2020",
            season_number=1,
            episode_number=5,
        )

        result = anilist_provider.fetch_episode(candidate)

        assert result.provider_name == "anilist"
        assert result.provider_id == "12345"
        assert result.series_title == "Test Anime English"
        assert result.season_number == 1
        assert result.episode_number == 5

    def test_fetch_episode_not_found(self, anilist_provider, mock_http_client):
        """Test episode fetch when media not found."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_http_client.request.return_value = mock_response

        from ouro.core.models.metadata import MetadataCandidate

        candidate = MetadataCandidate(
            provider_name="anilist",
            provider_id="99999",
            kind="tv",
            title="Nonexistent Anime",
            year=None,
            season_number=1,
            episode_number=1,
        )

        with pytest.raises(Exception):
            anilist_provider.fetch_episode(candidate)


class TestAniListFetchSeason:
    """Tests for AniList season fetching."""

    def test_fetch_season_success(self, anilist_provider, mock_http_client):
        """Test successful season fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "Media": {
                    "id": 12345,
                    "title": {
                        "romaji": "Test Anime",
                        "english": "Test Anime English",
                    },
                    "description": "Test description",
                    "episodes": 24,
                    "genres": ["Action", "Drama"],
                    "averageScore": 85,
                    "startDate": {
                        "year": 2020,
                        "month": 3,
                        "day": 15,
                    },
                    "coverImage": {
                        "large": "https://example.com/large.jpg",
                    },
                }
            }
        }
        mock_http_client.request.return_value = mock_response

        from ouro.core.models.metadata import MetadataCandidate

        candidate = MetadataCandidate(
            provider_name="anilist",
            provider_id="12345",
            kind="tv",
            title="Test Anime",
            year="2020",
            season_number=1,
        )

        result = anilist_provider.fetch_season(candidate)

        assert result.provider_name == "anilist"
        assert result.provider_id == "12345"
        assert result.series_title == "Test Anime English"
        assert result.season_number == 1
        assert result.genres == ["Action", "Drama"]


class TestAniListFetchMovie:
    """Tests for AniList movie fetching."""

    def test_fetch_movie_success(self, anilist_provider, mock_http_client):
        """Test successful movie fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "Media": {
                    "id": 12345,
                    "title": {
                        "romaji": "Test Movie",
                        "english": "Test Movie English",
                    },
                    "description": "Test description",
                    "genres": ["Action", "Drama"],
                    "averageScore": 85,
                    "startDate": {
                        "year": 2020,
                        "month": 3,
                        "day": 15,
                    },
                    "coverImage": {
                        "large": "https://example.com/large.jpg",
                    },
                }
            }
        }
        mock_http_client.request.return_value = mock_response

        from ouro.core.models.metadata import MetadataCandidate

        candidate = MetadataCandidate(
            provider_name="anilist",
            provider_id="12345",
            kind="movie",
            title="Test Movie",
            year="2020",
        )

        result = anilist_provider.fetch_movie(candidate)

        assert result.provider_name == "anilist"
        assert result.provider_id == "12345"
        assert result.title == "Test Movie English"
        assert result.year == "2020"
        assert result.genres == ["Action", "Drama"]


class TestAniListGraphQLQueries:
    """Tests for GraphQL query construction."""

    def test_search_query_structure(self, anilist_provider, mock_http_client):
        """Test search query has correct structure."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"Page": {"media": []}}}
        mock_http_client.request.return_value = mock_response

        request = MetadataLookupRequest(
            media_kind="tv",
            title="Test Anime",
            year=None,
        )

        anilist_provider.search(request)

        # Verify GraphQL query structure
        call_args = mock_http_client.request.call_args
        assert call_args[1]["path_or_url"] == "https://graphql.anilist.co"

        query_data = call_args[1]["json_body"]
        assert "query" in query_data
        assert "variables" in query_data
        assert "search" in query_data["variables"]

    def test_details_query_structure(self, anilist_provider, mock_http_client):
        """Test details query has correct structure."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "Media": {
                    "id": 12345,
                    "title": {"romaji": "Test Anime"},
                }
            }
        }
        mock_http_client.request.return_value = mock_response

        from ouro.core.models.metadata import MetadataCandidate

        candidate = MetadataCandidate(
            provider_name="anilist",
            provider_id="12345",
            kind="tv",
            title="Test Anime",
            year=None,
            season_number=1,
        )

        anilist_provider.fetch_season(candidate)

        # Verify GraphQL query structure
        call_args = mock_http_client.request.call_args
        query_data = call_args[1]["json_body"]
        assert "query" in query_data
        assert "variables" in query_data
        assert "id" in query_data["variables"]
        assert query_data["variables"]["id"] == 12345
