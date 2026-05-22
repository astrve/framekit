"""AniList metadata provider implementation.

This module implements the AniList GraphQL API provider for anime/manga metadata.
It handles GraphQL queries, rate limiting, and data transformation to Framekit's
unified metadata models.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from framekit.core.exceptions import FramekitMetadataError
from framekit.core.http import HttpClient, HttpError, HttpRateLimitError, HttpStatusError
from framekit.core.models.metadata import (
    EpisodeMetadata,
    MetadataCandidate,
    MetadataLookupRequest,
    MovieMetadata,
    SeasonMetadata,
)
from framekit.modules.metadata.base import MetadataProvider
from framekit.modules.metadata.providers.anilist_models import AniListMedia
from framekit.modules.metadata.rate_limiter import RateLimit, RateLimiter

ANILIST_GRAPHQL_URL = "https://graphql.anilist.co"


class AniListProvider(MetadataProvider):
    """AniList metadata provider for anime/manga.

    Implements the MetadataProvider interface for AniList GraphQL API,
    providing anime and manga metadata without authentication.
    """

    name = "anilist"

    def __init__(
        self,
        http_client: HttpClient | None = None,
        rate_limiter: RateLimiter | None = None,
    ):
        """Initialize AniList provider.

        Args:
            http_client: Optional HTTP client (creates default if None)
            rate_limiter: Optional rate limiter (creates default if None)
        """
        self.http_client = http_client or HttpClient()
        self.rate_limiter = rate_limiter or RateLimiter(
            RateLimit(requests=90, period=60)  # 90 requests per minute
        )

    def _make_graphql_request(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        """Make a GraphQL request to AniList API.

        Args:
            query: GraphQL query string
            variables: Query variables

        Returns:
            Response data dictionary

        Raises:
            FramekitMetadataError: If request fails
        """
        # Apply rate limiting
        if not self.rate_limiter.acquire(timeout=30.0):
            raise FramekitMetadataError("AniList rate limit exceeded")

        try:
            response = self.http_client.request(
                method="POST",
                path_or_url=ANILIST_GRAPHQL_URL,
                json_body={
                    "query": query,
                    "variables": variables,
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )

            data = response.json()

            # Check for GraphQL errors
            if "errors" in data:
                error_messages = [err.get("message", "Unknown error") for err in data["errors"]]
                raise FramekitMetadataError(f"AniList GraphQL errors: {', '.join(error_messages)}")

            return data

        except HttpRateLimitError as e:
            raise FramekitMetadataError(f"AniList rate limit error: {e}") from e
        except HttpStatusError as e:
            raise FramekitMetadataError(f"AniList API error: {e}") from e
        except HttpError as e:
            raise FramekitMetadataError(f"AniList request error: {e}") from e

    def search(self, request: MetadataLookupRequest) -> list[MetadataCandidate]:
        """Search for anime/manga.

        Args:
            request: Metadata lookup request

        Returns:
            List of metadata candidates
        """
        if not request.title:
            return []

        # Build GraphQL query
        query = """
        query SearchMedia($search: String, $seasonYear: Int, $type: MediaType) {
            Page(page: 1, perPage: 10) {
                media(search: $search, seasonYear: $seasonYear, type: $type, sort: SEARCH_MATCH) {
                    id
                    title {
                        romaji
                        english
                        native
                    }
                    description
                    episodes
                    coverImage {
                        large
                        medium
                    }
                    genres
                    averageScore
                    startDate {
                        year
                        month
                        day
                    }
                }
            }
        }
        """

        # Determine media type
        media_type = "ANIME"  # AniList primarily focuses on anime

        # Build variables
        variables: dict[str, Any] = {
            "search": request.title,
            "type": media_type,
        }

        # Add year filter if provided
        if request.year:
            try:
                variables["seasonYear"] = int(request.year)
            except (ValueError, TypeError):
                logger.warning(f"Invalid year format: {request.year}")

        logger.debug(f"Searching AniList for: {request.title}")

        try:
            data = self._make_graphql_request(query, variables)

            # Parse results
            media_list = data.get("data", {}).get("Page", {}).get("media", [])

            candidates = []
            for media_data in media_list:
                try:
                    media = AniListMedia(**media_data)
                    candidate = media.to_metadata_candidate()
                    candidates.append(candidate)
                except Exception as e:
                    logger.warning(f"Failed to parse AniList media: {e}")
                    continue

            logger.debug(f"Found {len(candidates)} AniList results")
            return candidates

        except FramekitMetadataError:
            raise
        except Exception as e:
            raise FramekitMetadataError(f"AniList search failed: {e}") from e

    def fetch_movie(self, candidate: MetadataCandidate) -> MovieMetadata:
        """Fetch movie metadata.

        Args:
            candidate: Metadata candidate

        Returns:
            Movie metadata

        Raises:
            FramekitMetadataError: If fetch fails
        """
        media = self._fetch_media_details(candidate.provider_id)
        return media.to_movie_metadata()

    def fetch_episode(self, candidate: MetadataCandidate) -> EpisodeMetadata:
        """Fetch episode metadata.

        Args:
            candidate: Metadata candidate

        Returns:
            Episode metadata

        Raises:
            FramekitMetadataError: If fetch fails
        """
        media = self._fetch_media_details(candidate.provider_id)

        # AniList doesn't provide per-episode metadata in the same way as TVDB
        # We use the series metadata and episode number from the candidate
        episode_title = None
        if candidate.episode_number:
            episode_title = f"Episode {candidate.episode_number}"

        return media.to_episode_metadata(
            season_number=candidate.season_number or 1,
            episode_number=candidate.episode_number or 1,
            episode_title=episode_title,
        )

    def fetch_season(self, candidate: MetadataCandidate) -> SeasonMetadata:
        """Fetch season metadata.

        Args:
            candidate: Metadata candidate

        Returns:
            Season metadata

        Raises:
            FramekitMetadataError: If fetch fails
        """
        media = self._fetch_media_details(candidate.provider_id)
        return media.to_season_metadata(season_number=candidate.season_number or 1)

    def _fetch_media_details(self, media_id: str) -> AniListMedia:
        """Fetch detailed media information.

        Args:
            media_id: AniList media ID

        Returns:
            AniList media object

        Raises:
            FramekitMetadataError: If fetch fails
        """
        query = """
        query GetMedia($id: Int) {
            Media(id: $id) {
                id
                title {
                    romaji
                    english
                    native
                }
                description
                episodes
                coverImage {
                    large
                    medium
                }
                genres
                averageScore
                startDate {
                    year
                    month
                    day
                }
            }
        }
        """

        try:
            media_id_int = int(media_id)
        except (ValueError, TypeError) as e:
            raise FramekitMetadataError(f"Invalid AniList media ID: {media_id}") from e

        variables = {"id": media_id_int}

        logger.debug(f"Fetching AniList media details: {media_id}")

        try:
            data = self._make_graphql_request(query, variables)

            media_data = data.get("data", {}).get("Media")
            if not media_data:
                raise FramekitMetadataError(f"AniList media not found: {media_id}")

            return AniListMedia(**media_data)

        except FramekitMetadataError:
            raise
        except Exception as e:
            raise FramekitMetadataError(f"Failed to fetch AniList media {media_id}: {e}") from e
