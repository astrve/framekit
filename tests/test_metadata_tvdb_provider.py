"""Tests for TVDB metadata provider."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from framekit.core.models.metadata import MetadataCandidate, MetadataLookupRequest
from framekit.modules.metadata.providers.tvdb import TVDBProvider
from framekit.modules.metadata.rate_limiter import RateLimiter


def _mock_response(status_code: int = 200, data: dict | None = None) -> MagicMock:
    """Create a mock HttpResponse."""
    body = json.dumps(data or {}).encode()
    resp = MagicMock()
    resp.status_code = status_code
    resp.body = body
    resp.text = body.decode()
    resp.json.return_value = data or {}
    resp.headers = {}
    return resp


@pytest.fixture
def mock_http_client():
    """Create a mock HTTP client."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_rate_limiter():
    """Create a mock rate limiter."""
    limiter = MagicMock(spec=RateLimiter)
    limiter.try_acquire.return_value = True
    return limiter


@pytest.fixture
def tvdb_provider(mock_http_client, mock_rate_limiter):
    """Create a TVDB provider with mocked dependencies."""
    return TVDBProvider(
        api_key="test_api_key",
        http_client=mock_http_client,
        rate_limiter=mock_rate_limiter,
    )


class TestTVDBProviderInitialization:
    """Tests for TVDB provider initialization."""

    def test_provider_name(self, tvdb_provider):
        """Test provider name is correct."""
        assert tvdb_provider.name == "tvdb"

    def test_default_rate_limiter(self):
        """Test default rate limiter is created."""
        provider = TVDBProvider(api_key="test_key")
        assert provider.rate_limiter is not None
        assert provider.rate_limiter.rate_limit.requests == 1000
        assert provider.rate_limiter.rate_limit.period == 86400

    def test_custom_rate_limiter(self, mock_rate_limiter):
        """Test custom rate limiter is used."""
        provider = TVDBProvider(
            api_key="test_key",
            rate_limiter=mock_rate_limiter,
        )
        assert provider.rate_limiter is mock_rate_limiter


class TestTVDBAuthentication:
    """Tests for TVDB authentication."""

    def test_authenticate_success(self, tvdb_provider, mock_http_client):
        """Test successful authentication."""
        mock_http_client.post.return_value = _mock_response(
            200, {"data": {"token": "test_bearer_token"}}
        )

        tvdb_provider._authenticate()

        assert tvdb_provider.token == "test_bearer_token"
        mock_http_client.post.assert_called_once()
        call_args = mock_http_client.post.call_args
        assert "/login" in call_args[0][0]
        assert call_args[1]["json_body"]["apikey"] == "test_api_key"

    def test_authenticate_failure(self, tvdb_provider, mock_http_client):
        """Test authentication failure raises FramekitMetadataError."""
        from framekit.core.exceptions import FramekitMetadataError
        from framekit.core.http import HttpAuthError

        mock_http_client.post.side_effect = HttpAuthError(
            "Authentication failed",
            url="https://api4.thetvdb.com/v4/login",
            status_code=401,
        )

        with pytest.raises(FramekitMetadataError, match="authentication failed"):
            tvdb_provider._authenticate()

    def test_authenticate_caches_token(self, tvdb_provider, mock_http_client):
        """Test token is cached after authentication."""
        mock_http_client.post.return_value = _mock_response(200, {"data": {"token": "test_token"}})

        tvdb_provider._authenticate()
        first_token = tvdb_provider.token

        # Second call should skip (token already set)
        tvdb_provider._authenticate()
        assert tvdb_provider.token == first_token
        assert mock_http_client.post.call_count == 1


class TestTVDBSearch:
    """Tests for TVDB search functionality."""

    def test_search_series_success(self, tvdb_provider, mock_http_client, mock_rate_limiter):
        """Test successful series search."""
        tvdb_provider.token = "test_token"

        mock_http_client.request.return_value = _mock_response(
            200,
            {
                "data": [
                    {
                        "tvdb_id": "12345",
                        "name": "Test Series",
                        "year": "2020",
                        "overview": "Test overview",
                        "image_url": "https://example.com/image.jpg",
                    }
                ]
            },
        )

        request = MetadataLookupRequest(
            media_kind="tv",
            title="Test Series",
            year="2020",
        )

        results = tvdb_provider.search(request)

        assert len(results) == 1
        assert results[0].provider_name == "tvdb"
        assert results[0].title == "Test Series"
        assert results[0].year == "2020"

    def test_search_authenticates_if_no_token(
        self, tvdb_provider, mock_http_client, mock_rate_limiter
    ):
        """Test search authenticates if no token present."""
        assert tvdb_provider.token is None

        # Mock authentication
        mock_http_client.post.return_value = _mock_response(200, {"data": {"token": "new_token"}})

        # Mock search
        mock_http_client.request.return_value = _mock_response(200, {"data": []})

        request = MetadataLookupRequest(
            media_kind="tv",
            title="Test",
            year=None,
        )

        tvdb_provider.search(request)

        assert tvdb_provider.token == "new_token"
        assert mock_http_client.post.call_count == 1

    def test_search_empty_results(self, tvdb_provider, mock_http_client, mock_rate_limiter):
        """Test search with no results."""
        tvdb_provider.token = "test_token"

        mock_http_client.request.return_value = _mock_response(200, {"data": []})

        request = MetadataLookupRequest(
            media_kind="tv",
            title="Nonexistent Series",
            year=None,
        )

        results = tvdb_provider.search(request)
        assert results == []

    def test_search_respects_rate_limit(self, tvdb_provider, mock_rate_limiter, mock_http_client):
        """Test search respects rate limiting."""
        tvdb_provider.token = "test_token"
        mock_http_client.request.return_value = _mock_response(200, {"data": []})

        request = MetadataLookupRequest(
            media_kind="tv",
            title="Test",
            year=None,
        )

        tvdb_provider.search(request)

        mock_rate_limiter.try_acquire.assert_called_once()


class TestTVDBFetchDetails:
    """Tests for TVDB fetch details functionality."""

    def test_fetch_season_success(self, tvdb_provider, mock_http_client, mock_rate_limiter):
        """Test successful season fetch."""
        tvdb_provider.token = "test_token"

        mock_http_client.request.side_effect = [
            # Series details
            _mock_response(
                200,
                {
                    "data": {
                        "id": 12345,
                        "name": "Test Series",
                        "overview": "Series overview",
                        "firstAired": "2020-01-01",
                        "genres": [{"name": "Drama"}],
                    }
                },
            ),
            # Episodes
            _mock_response(
                200,
                {
                    "data": {
                        "episodes": [
                            {
                                "id": 1,
                                "name": "Episode 1",
                                "seasonNumber": 1,
                                "number": 1,
                                "overview": "Ep 1 overview",
                                "aired": "2020-01-01",
                            }
                        ]
                    }
                },
            ),
        ]

        candidate = MetadataCandidate(
            provider_name="tvdb",
            provider_id="12345",
            kind="tv",
            title="Test Series",
            year="2020",
            season_number=1,
            confidence=0.9,
            reasons=["test"],
        )

        metadata = tvdb_provider.fetch_season(candidate)

        assert metadata is not None
        assert metadata.series_title == "Test Series"
        assert metadata.season_number == 1
        assert len(metadata.episode_summaries) == 1

    def test_fetch_episode_success(self, tvdb_provider, mock_http_client, mock_rate_limiter):
        """Test successful episode fetch."""
        tvdb_provider.token = "test_token"

        mock_http_client.request.side_effect = [
            # Series details
            _mock_response(
                200,
                {
                    "data": {
                        "id": 12345,
                        "name": "Test Series",
                        "firstAired": "2020-01-01",
                    }
                },
            ),
            # Episodes
            _mock_response(
                200,
                {
                    "data": {
                        "episodes": [
                            {
                                "id": 1,
                                "name": "Test Episode",
                                "seasonNumber": 1,
                                "number": 5,
                                "overview": "Episode overview",
                                "aired": "2020-02-01",
                            }
                        ]
                    }
                },
            ),
        ]

        candidate = MetadataCandidate(
            provider_name="tvdb",
            provider_id="12345",
            kind="tv",
            title="Test Series",
            year="2020",
            season_number=1,
            episode_number=5,
            confidence=0.9,
            reasons=["test"],
        )

        metadata = tvdb_provider.fetch_episode(candidate)

        assert metadata is not None
        assert metadata.series_title == "Test Series"
        assert metadata.episode_number == 5
        assert metadata.episode_title == "Test Episode"


class TestTVDBErrorHandling:
    """Tests for TVDB error handling."""

    def test_handle_401_reauthenticate(self, tvdb_provider, mock_http_client, mock_rate_limiter):
        """Test 401 error triggers re-authentication."""
        from framekit.core.http import HttpAuthError

        tvdb_provider.token = "expired_token"

        # First call raises 401, second succeeds after re-auth
        mock_http_client.request.side_effect = [
            HttpAuthError(
                "Unauthorized", url="https://api4.thetvdb.com/v4/search", status_code=401
            ),
            _mock_response(200, {"data": []}),
        ]

        # Re-auth post returns new token
        mock_http_client.post.return_value = _mock_response(200, {"data": {"token": "new_token"}})

        request = MetadataLookupRequest(
            media_kind="tv",
            title="Test",
            year=None,
        )

        tvdb_provider.search(request)

        assert tvdb_provider.token == "new_token"
        assert mock_http_client.post.call_count == 1

    def test_handle_rate_limit_exceeded(self, tvdb_provider, mock_rate_limiter, mock_http_client):
        """Test rate limit exceeded returns empty results."""
        tvdb_provider.token = "test_token"
        mock_rate_limiter.try_acquire.return_value = False

        request = MetadataLookupRequest(
            media_kind="tv",
            title="Test",
            year=None,
        )

        # search() catches the HttpRateLimitError internally and returns []
        results = tvdb_provider.search(request)
        assert results == []

    def test_handle_404_not_found(self, tvdb_provider, mock_http_client, mock_rate_limiter):
        """Test fetch_season raises on 404."""
        from framekit.core.exceptions import FramekitMetadataError
        from framekit.core.http import HttpError

        tvdb_provider.token = "test_token"

        mock_http_client.request.side_effect = HttpError(
            "Not Found",
            url="https://api4.thetvdb.com/v4/series/99999/extended",
            status_code=404,
        )

        candidate = MetadataCandidate(
            provider_name="tvdb",
            provider_id="99999",
            kind="tv",
            title="Nonexistent",
            year=None,
            season_number=1,
            confidence=0.5,
            reasons=["test"],
        )

        with pytest.raises(FramekitMetadataError):
            tvdb_provider.fetch_season(candidate)
