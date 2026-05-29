"""Trakt metadata provider implementation.

This module implements the Trakt API v2 provider for movies and TV shows.
It handles authentication, rate limiting, and data transformation to Ouro's
unified metadata models.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from ouro.core.exceptions import OuroMetadataError
from ouro.core.http import (
    HttpAuthError,
    HttpClient,
    HttpError,
    HttpRateLimitError,
    HttpStatusError,
)
from ouro.core.models.metadata import (
    EpisodeMetadata,
    MetadataCandidate,
    MetadataLookupRequest,
    MovieMetadata,
    SeasonMetadata,
)
from ouro.modules.metadata.base import MetadataProvider
from ouro.modules.metadata.providers.trakt_models import TraktIds, TraktMovie, TraktShow
from ouro.modules.metadata.rate_limiter import RateLimit, RateLimiter

TRAKT_API_BASE = "https://api.trakt.tv"
TRAKT_API_VERSION = "2"


class TraktProvider(MetadataProvider):
    """Trakt metadata provider for movies and TV shows.

    Implements the MetadataProvider interface for Trakt API v2, providing
    movie and TV show metadata with user ratings and popularity data.
    """

    name = "trakt"

    def __init__(
        self,
        client_id: str,
        client_secret: str | None = None,
        access_token: str | None = None,
        http_client: HttpClient | None = None,
        rate_limiter: RateLimiter | None = None,
    ):
        """Initialize Trakt provider.

        Args:
            client_id: Trakt API client ID (required)
            client_secret: Trakt API client secret (optional, for OAuth2)
            access_token: OAuth2 access token (optional, for user data)
            http_client: Optional HTTP client (creates default if None)
            rate_limiter: Optional rate limiter (creates default if None)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.http_client = http_client or HttpClient()
        self.rate_limiter = rate_limiter or RateLimiter(
            RateLimit(requests=1000, period=300)  # 1000 requests per 5 minutes
        )

    def _make_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        """Make an authenticated request to Trakt API.

        Handles authentication headers, rate limiting, and error handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path
            params: Query parameters (optional)
            json_body: JSON request body (optional)

        Returns:
            Parsed JSON response

        Raises:
            OuroMetadataError: On request failure
            HttpRateLimitError: On rate limit exceeded
        """
        # Apply rate limiting
        if not self.rate_limiter.try_acquire():
            raise HttpRateLimitError(
                "Trakt rate limit exceeded",
                url=f"{TRAKT_API_BASE}{path}",
                status_code=429,
            )

        # Build headers
        headers = {
            "Content-Type": "application/json",
            "trakt-api-version": TRAKT_API_VERSION,
            "trakt-api-key": self.client_id,
        }

        # Add OAuth2 token if available
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        try:
            url = f"{TRAKT_API_BASE}{path}"
            response = self.http_client.request(
                method=method,
                path_or_url=url,
                params=params,
                json_body=json_body,
                headers=headers,
            )
            return response.json()

        except HttpAuthError as e:
            raise OuroMetadataError(f"Trakt authentication failed: {e}") from e
        except HttpRateLimitError:
            raise
        except HttpStatusError as e:
            if e.status_code == 404:
                return None
            raise OuroMetadataError(f"Trakt API error: {e}") from e
        except HttpError as e:
            raise OuroMetadataError(f"Trakt request error: {e}") from e

    def search(self, request: MetadataLookupRequest) -> list[MetadataCandidate]:
        """Search for movies or TV shows on Trakt.

        Args:
            request: Metadata lookup request with search parameters

        Returns:
            List of metadata candidates matching the search
        """
        if not request.title:
            return []

        search_type = self._search_type_for_request(request)

        logger.debug(f"Searching Trakt for {search_type}: {request.title}")

        try:
            data = self._make_request(
                "GET",
                "/search/movie,show",
                params=self._build_search_params(request, search_type),
            )

            if not data:
                return []

            candidates = self._parse_search_candidates(data)

            logger.debug(f"Found {len(candidates)} Trakt candidates")
            return candidates

        except OuroMetadataError:
            raise
        except Exception as e:
            logger.error(f"Trakt search failed: {e}")
            return []

    def _search_type_for_request(self, request: MetadataLookupRequest) -> str:
        return "movie" if request.media_kind == "movie" else "show"

    def _build_search_params(
        self,
        request: MetadataLookupRequest,
        search_type: str,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"query": request.title, "type": search_type}
        if request.year:
            params["years"] = request.year
        return params

    def _parse_search_candidates(self, data: list[dict[str, Any]]) -> list[MetadataCandidate]:
        candidates: list[MetadataCandidate] = []
        for item in data:
            candidate = self._candidate_from_search_item(item)
            if candidate is not None:
                candidates.append(candidate)
        return candidates

    def _candidate_from_search_item(self, item: dict[str, Any]) -> MetadataCandidate | None:
        try:
            item_type = item.get("type")
            if item_type == "movie" and "movie" in item:
                return self._movie_candidate(item["movie"])
            if item_type == "show" and "show" in item:
                return self._show_candidate(item["show"])
            return None
        except Exception as error:
            logger.warning(f"Failed to parse Trakt search result: {error}")
            return None

    def _movie_candidate(self, movie_data: dict[str, Any]) -> MetadataCandidate:
        movie = TraktMovie(
            title=movie_data.get("title", ""),
            year=movie_data.get("year"),
            ids=TraktIds(**movie_data.get("ids", {})),
            overview=movie_data.get("overview"),
            rating=movie_data.get("rating"),
            votes=movie_data.get("votes"),
            genres=movie_data.get("genres", []),
        )
        return movie.to_metadata_candidate()

    def _show_candidate(self, show_data: dict[str, Any]) -> MetadataCandidate:
        show = TraktShow(
            title=show_data.get("title", ""),
            year=show_data.get("year"),
            ids=TraktIds(**show_data.get("ids", {})),
            overview=show_data.get("overview"),
            rating=show_data.get("rating"),
            votes=show_data.get("votes"),
            genres=show_data.get("genres", []),
        )
        return show.to_metadata_candidate()

    def fetch_movie(self, candidate: MetadataCandidate) -> MovieMetadata:
        """Fetch detailed movie information from Trakt.

        Args:
            candidate: Metadata candidate with Trakt movie ID

        Returns:
            Detailed movie metadata

        Raises:
            OuroMetadataError: If fetch fails
        """
        logger.debug(f"Fetching Trakt movie details: {candidate.provider_id}")

        try:
            # Fetch movie details with extended info
            path = f"/movies/{candidate.provider_id}"
            params = {"extended": "full"}

            data = self._make_request("GET", path, params=params)

            if not data:
                raise OuroMetadataError(f"Trakt movie not found: {candidate.provider_id}")

            movie = TraktMovie(
                title=data.get("title", ""),
                year=data.get("year"),
                ids=TraktIds(**data.get("ids", {})),
                overview=data.get("overview"),
                rating=data.get("rating"),
                votes=data.get("votes"),
                genres=data.get("genres", []),
            )

            return movie.to_movie_metadata()

        except OuroMetadataError:
            raise
        except Exception as e:
            raise OuroMetadataError(f"Failed to fetch Trakt movie: {e}") from e

    def fetch_episode(self, candidate: MetadataCandidate) -> EpisodeMetadata:
        """Fetch detailed episode information from Trakt.

        Args:
            candidate: Metadata candidate with Trakt show ID and episode info

        Returns:
            Detailed episode metadata

        Raises:
            OuroMetadataError: If fetch fails
        """
        if candidate.season_number is None or candidate.episode_number is None:
            raise OuroMetadataError("Season and episode numbers required for episode fetch")

        logger.debug(
            f"Fetching Trakt episode: {candidate.provider_id} "
            f"S{candidate.season_number}E{candidate.episode_number}"
        )

        try:
            # First fetch show details
            show_path = f"/shows/{candidate.provider_id}"
            show_params = {"extended": "full"}
            show_data = self._make_request("GET", show_path, params=show_params)

            if not show_data:
                raise OuroMetadataError(f"Trakt show not found: {candidate.provider_id}")

            show = TraktShow(
                title=show_data.get("title", ""),
                year=show_data.get("year"),
                ids=TraktIds(**show_data.get("ids", {})),
                overview=show_data.get("overview"),
                rating=show_data.get("rating"),
                votes=show_data.get("votes"),
                genres=show_data.get("genres", []),
            )

            # Fetch episode details
            episode_path = (
                f"/shows/{candidate.provider_id}/seasons/{candidate.season_number}/"
                f"episodes/{candidate.episode_number}"
            )
            episode_params = {"extended": "full"}
            episode_data = self._make_request("GET", episode_path, params=episode_params)

            episode_title = None
            if episode_data:
                episode_title = episode_data.get("title")

            return show.to_episode_metadata(
                season_number=candidate.season_number,
                episode_number=candidate.episode_number,
                episode_title=episode_title,
            )

        except OuroMetadataError:
            raise
        except Exception as e:
            raise OuroMetadataError(f"Failed to fetch Trakt episode: {e}") from e

    def fetch_season(self, candidate: MetadataCandidate) -> SeasonMetadata:
        """Fetch detailed season information from Trakt.

        Args:
            candidate: Metadata candidate with Trakt show ID and season number

        Returns:
            Detailed season metadata

        Raises:
            OuroMetadataError: If fetch fails
        """
        if candidate.season_number is None:
            raise OuroMetadataError("Season number required for season fetch")

        logger.debug(f"Fetching Trakt season: {candidate.provider_id} S{candidate.season_number}")

        try:
            # Fetch show details
            show_path = f"/shows/{candidate.provider_id}"
            show_params = {"extended": "full"}
            show_data = self._make_request("GET", show_path, params=show_params)

            if not show_data:
                raise OuroMetadataError(f"Trakt show not found: {candidate.provider_id}")

            show = TraktShow(
                title=show_data.get("title", ""),
                year=show_data.get("year"),
                ids=TraktIds(**show_data.get("ids", {})),
                overview=show_data.get("overview"),
                rating=show_data.get("rating"),
                votes=show_data.get("votes"),
                genres=show_data.get("genres", []),
            )

            return show.to_season_metadata(season_number=candidate.season_number)

        except OuroMetadataError:
            raise
        except Exception as e:
            raise OuroMetadataError(f"Failed to fetch Trakt season: {e}") from e
