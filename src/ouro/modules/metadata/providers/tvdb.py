"""TVDB metadata provider implementation.

This module implements the TVDB API v4 provider for TV series metadata.
It handles authentication, rate limiting, and data transformation to Ouro's
unified metadata models.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from ouro.core.exceptions import OuroMetadataError
from ouro.core.http import HttpAuthError, HttpClient, HttpError, HttpRateLimitError
from ouro.core.models.metadata import (
    EpisodeMetadata,
    MetadataCandidate,
    MetadataLookupRequest,
    MovieMetadata,
    SeasonMetadata,
)
from ouro.modules.metadata.base import MetadataProvider
from ouro.modules.metadata.providers.tvdb_models import (
    TVDBEpisode,
    TVDBSearchResult,
    TVDBSeries,
)
from ouro.modules.metadata.rate_limiter import RateLimit, RateLimiter

TVDB_API_BASE = "https://api4.thetvdb.com/v4"


class TVDBProvider(MetadataProvider):
    """TVDB metadata provider for TV series.

    Implements the MetadataProvider interface for TVDB API v4, providing
    TV series and episode metadata with authentication and rate limiting.
    """

    name = "tvdb"

    def __init__(
        self,
        api_key: str,
        http_client: HttpClient | None = None,
        rate_limiter: RateLimiter | None = None,
    ):
        """Initialize TVDB provider.

        Args:
            api_key: TVDB API key for authentication
            http_client: Optional HTTP client (creates default if None)
            rate_limiter: Optional rate limiter (creates default if None)
        """
        self.api_key = api_key
        self.http_client = http_client or HttpClient(base_url=TVDB_API_BASE)
        self.rate_limiter = rate_limiter or RateLimiter(
            RateLimit(requests=1000, period=86400)  # 1000 requests per day
        )
        self.token: str | None = None

    def _authenticate(self) -> None:
        """Authenticate with TVDB API and obtain bearer token.

        The token is cached and reused for subsequent requests until it expires.
        TVDB tokens are valid for 24 hours.

        Raises:
            OuroMetadataError: If authentication fails
        """
        # Skip if already authenticated
        if self.token:
            return

        logger.debug("Authenticating with TVDB API")

        try:
            response = self.http_client.post(
                "/login",
                json_body={"apikey": self.api_key},
            )

            data = response.json()
            self.token = data.get("data", {}).get("token")

            if not self.token:
                raise OuroMetadataError("TVDB authentication failed: no token in response")

            logger.debug("TVDB authentication successful")

        except HttpAuthError as e:
            raise OuroMetadataError(f"TVDB authentication failed: {e}") from e
        except HttpError as e:
            raise OuroMetadataError(f"TVDB authentication error: {e}") from e

    def _make_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        retry_auth: bool = True,
    ) -> Any:
        """Make an authenticated request to TVDB API.

        Handles authentication, rate limiting, and token refresh on 401 errors.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path
            params: Query parameters
            retry_auth: Whether to retry with new token on 401

        Returns:
            Parsed JSON response

        Raises:
            OuroMetadataError: On request failure
            HttpRateLimitError: On rate limit exceeded
        """
        # Ensure we're authenticated
        if not self.token:
            self._authenticate()

        # Acquire rate limit token
        if not self.rate_limiter.try_acquire():
            raise HttpRateLimitError(
                "TVDB rate limit exceeded",
                url=f"{TVDB_API_BASE}{path}",
                status_code=429,
            )

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }

        try:
            response = self.http_client.request(
                method,
                path,
                params=params,
                headers=headers,
            )
            return response.json()

        except HttpAuthError as e:
            # Token expired, try to re-authenticate once
            if retry_auth:
                logger.debug("TVDB token expired, re-authenticating")
                self.token = None
                self._authenticate()
                return self._make_request(method, path, params, retry_auth=False)
            raise OuroMetadataError(f"TVDB authentication failed: {e}") from e

        except HttpRateLimitError:
            raise

        except HttpError as e:
            raise OuroMetadataError(f"TVDB API request failed: {e}") from e

    def search(self, request: MetadataLookupRequest) -> list[MetadataCandidate]:
        """Search for TV series on TVDB.

        Args:
            request: Metadata lookup request with search parameters

        Returns:
            List of metadata candidates matching the search
        """
        if not request.title:
            return []

        logger.debug(f"Searching TVDB for: {request.title}")

        try:
            params = {
                "query": request.title,
                "type": "series",
            }

            if request.year:
                params["year"] = request.year

            data = self._make_request("GET", "/search", params=params)

            results = data.get("data", [])
            candidates: list[MetadataCandidate] = []

            for item in results:
                try:
                    search_result = TVDBSearchResult(
                        tvdb_id=str(item.get("tvdb_id", item.get("id", ""))),
                        name=item.get("name", ""),
                        year=item.get("year"),
                        overview=item.get("overview"),
                        image_url=item.get("image_url", item.get("image")),
                    )
                    candidates.append(search_result.to_metadata_candidate())
                except Exception as e:
                    logger.warning(f"Failed to parse TVDB search result: {e}")
                    continue

            logger.debug(f"Found {len(candidates)} TVDB candidates")
            return candidates

        except HttpRateLimitError:
            logger.warning("TVDB rate limit exceeded")
            return []
        except Exception as e:
            logger.error(f"TVDB search failed: {e}")
            return []

    def fetch_movie(self, candidate: MetadataCandidate) -> MovieMetadata:
        """Fetch movie metadata (not supported by TVDB).

        Args:
            candidate: Metadata candidate

        Raises:
            OuroMetadataError: TVDB does not support movies
        """
        raise OuroMetadataError("TVDB does not support movie metadata")

    def fetch_episode(self, candidate: MetadataCandidate) -> EpisodeMetadata:
        """Fetch episode metadata from TVDB.

        Args:
            candidate: Metadata candidate with series ID and episode info

        Returns:
            Episode metadata

        Raises:
            OuroMetadataError: On fetch failure
        """
        series_id, season_num, episode_num = self._resolve_episode_lookup(candidate)
        if season_num is None or episode_num is None:
            raise OuroMetadataError("Season and episode numbers required for episode fetch")

        logger.debug(f"Fetching TVDB episode: {series_id} S{season_num}E{episode_num}")

        try:
            series = self._fetch_series(series_id)
            episode = self._fetch_episode_from_season(series_id, season_num, episode_num)
            return episode.to_episode_metadata(series)

        except HttpRateLimitError:
            raise
        except OuroMetadataError:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch TVDB episode: {e}")
            raise OuroMetadataError(f"Failed to fetch TVDB episode: {e}") from e

    def _resolve_episode_lookup(
        self,
        candidate: MetadataCandidate,
    ) -> tuple[str, int | None, int | None]:
        return candidate.provider_id, candidate.season_number, candidate.episode_number

    def _fetch_series(self, series_id: str) -> TVDBSeries:
        series_data = self._make_request("GET", f"/series/{series_id}/extended")
        return self._series_from_response(series_id, series_data.get("data", {}))

    def _series_from_response(self, series_id: str, series_info: dict[str, Any]) -> TVDBSeries:
        return TVDBSeries(
            id=int(series_id),
            name=series_info.get("name", ""),
            overview=series_info.get("overview"),
            first_aired=series_info.get("firstAired"),
            status=series_info.get("status", {}).get("name")
            if isinstance(series_info.get("status"), dict)
            else series_info.get("status"),
            genres=[
                genre.get("name", genre) if isinstance(genre, dict) else str(genre)
                for genre in series_info.get("genres", [])
            ],
            rating=series_info.get("score"),
        )

    def _fetch_episode_from_season(
        self,
        series_id: str,
        season_num: int,
        episode_num: int,
    ) -> TVDBEpisode:
        episodes_data = self._make_request(
            "GET",
            f"/series/{series_id}/episodes/default",
            params={"season": season_num},
        )
        episodes_list = episodes_data.get("data", {}).get("episodes", [])
        match = self._find_episode_data(episodes_list, season_num, episode_num)
        if match is None:
            raise OuroMetadataError(
                f"Episode S{season_num}E{episode_num} not found for series {series_id}"
            )
        return self._episode_from_data(match, season_num, episode_num)

    def _find_episode_data(
        self,
        episodes_list: list[dict[str, Any]],
        season_num: int,
        episode_num: int,
    ) -> dict[str, Any] | None:
        for episode_data in episodes_list:
            if (
                episode_data.get("seasonNumber") == season_num
                and episode_data.get("number") == episode_num
            ):
                return episode_data
        return None

    def _episode_from_data(
        self,
        episode_data: dict[str, Any],
        season_num: int,
        episode_num: int,
    ) -> TVDBEpisode:
        return TVDBEpisode(
            id=episode_data.get("id", 0),
            name=episode_data.get("name", ""),
            season_number=episode_data.get("seasonNumber", season_num),
            episode_number=episode_data.get("number", episode_num),
            overview=episode_data.get("overview"),
            aired=episode_data.get("aired"),
        )

    def fetch_season(self, candidate: MetadataCandidate) -> SeasonMetadata:
        """Fetch season metadata from TVDB.

        Args:
            candidate: Metadata candidate with series ID and season number

        Returns:
            Season metadata with episode summaries

        Raises:
            OuroMetadataError: On fetch failure
        """
        series_id = candidate.provider_id
        season_num = candidate.season_number

        if not season_num:
            raise OuroMetadataError("Season number required for season fetch")

        logger.debug(f"Fetching TVDB season: {series_id} S{season_num}")

        try:
            # Fetch series details
            series_data = self._make_request("GET", f"/series/{series_id}/extended")
            series_info = series_data.get("data", {})

            series = TVDBSeries(
                id=int(series_id),
                name=series_info.get("name", ""),
                overview=series_info.get("overview"),
                first_aired=series_info.get("firstAired"),
                status=series_info.get("status", {}).get("name")
                if isinstance(series_info.get("status"), dict)
                else series_info.get("status"),
                genres=[
                    g.get("name", g) if isinstance(g, dict) else str(g)
                    for g in series_info.get("genres", [])
                ],
                rating=series_info.get("score"),
            )

            # Fetch episodes for the season
            episodes_data = self._make_request(
                "GET",
                f"/series/{series_id}/episodes/default",
                params={"season": season_num},
            )

            episodes_list = episodes_data.get("data", {}).get("episodes", [])

            # Convert to season metadata
            season_metadata = series.to_season_metadata(season_num)

            # Add episode summaries
            for ep_data in episodes_list:
                try:
                    episode = TVDBEpisode(
                        id=ep_data.get("id", 0),
                        name=ep_data.get("name", ""),
                        season_number=ep_data.get("seasonNumber", season_num),
                        episode_number=ep_data.get("number", 0),
                        overview=ep_data.get("overview"),
                        aired=ep_data.get("aired"),
                    )
                    season_metadata.episode_summaries.append(episode.to_episode_metadata(series))
                except Exception as e:
                    logger.warning(f"Failed to parse TVDB episode: {e}")
                    continue

            logger.debug(
                f"Fetched {len(season_metadata.episode_summaries)} episodes for season {season_num}"
            )
            return season_metadata

        except HttpRateLimitError:
            raise
        except OuroMetadataError:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch TVDB season: {e}")
            raise OuroMetadataError(f"Failed to fetch TVDB season: {e}") from e
