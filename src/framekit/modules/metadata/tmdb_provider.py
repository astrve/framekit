from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from loguru import logger

from framekit.core.cache import CacheManager
from framekit.core.exceptions import FramekitMetadataError
from framekit.core.http import HttpAuthError, HttpClient, HttpError
from framekit.core.models.metadata import (
    EpisodeMetadata,
    MetadataCandidate,
    MetadataLookupRequest,
    MovieMetadata,
    SeasonMetadata,
)
from framekit.core.paths import get_intelligent_cache_dir
from framekit.modules.metadata.base import MetadataProvider
from framekit.modules.metadata.health import HealthMonitor
from framekit.modules.metadata.rate_limiter import RateLimit, RateLimiter

TMDB_API_BASE = "https://api.themoviedb.org/3"
TMDB_WEB_BASE = "https://www.themoviedb.org"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"


def _normalize_text(value: str | None) -> str:
    return (value or "").strip().lower()


def _extract_year(date_value: str | None) -> str | None:
    if not date_value:
        return None
    return date_value[:4] if len(date_value) >= 4 else None


def _poster_url(path: str | None) -> str | None:
    if not path:
        return None
    return f"{TMDB_IMAGE_BASE}{path}"


def _names(items: list[dict[str, Any]] | None, *keys: str) -> list[str]:
    results: list[str] = []
    for item in items or []:
        for key in keys:
            value = item.get(key)
            if value:
                results.append(str(value))
                break
    return results


def _cast_names(credits: dict[str, Any] | None, *, limit: int = 8) -> list[str]:
    return _names((credits or {}).get("cast"), "name", "original_name")[:limit]


def _crew_names(credits: dict[str, Any] | None, *, limit: int = 8) -> list[str]:
    wanted = {"Director", "Writer", "Screenplay", "Creator", "Producer"}
    results: list[str] = []
    for item in (credits or {}).get("crew", []):
        name = item.get("name") or item.get("original_name")
        job = item.get("job")
        if not name or job not in wanted:
            continue
        label = f"{job}: {name}"
        if label not in results:
            results.append(label)
        if len(results) >= limit:
            break
    return results


def _series_crew_names(details: dict[str, Any], *, limit: int = 8) -> list[str]:
    results: list[str] = []
    for item in details.get("created_by") or []:
        name = item.get("name") or item.get("original_name")
        if not name:
            continue
        label = f"Creator: {name}"
        if label not in results:
            results.append(label)
    for label in _crew_names(details.get("credits"), limit=limit):
        if label not in results:
            results.append(label)
        if len(results) >= limit:
            break
    return results[:limit]


def _countries(details: dict[str, Any]) -> list[str]:
    countries = _names(details.get("production_countries"), "iso_3166_1", "name")
    if countries:
        return countries
    return [str(value) for value in details.get("origin_country", []) if value]


def _spoken_languages(details: dict[str, Any]) -> list[str]:
    return _names(details.get("spoken_languages"), "english_name", "name", "iso_639_1")


@dataclass(slots=True)
class _TMDbConfig:
    read_access_token: str
    language: str


class TMDbProvider(MetadataProvider):
    """TMDb metadata provider with rate limiting and health monitoring.

    Implements the MetadataProvider interface for TMDb API v3, providing
    movie and TV series metadata with authentication, rate limiting, and
    circuit breaker pattern for resilience.
    """

    name = "tmdb"

    def __init__(
        self,
        *,
        read_access_token: str = "",
        language: str = "en-US",
        include_adult: bool = False,
        http_client: HttpClient | None = None,
        cache_manager: CacheManager | None = None,
        cache_config: dict[str, Any] | None = None,
        rate_limiter: RateLimiter | None = None,
        health_monitor: HealthMonitor | None = None,
    ) -> None:
        """Initialize TMDb provider.

        Args:
            read_access_token: TMDb API read access token (v4 auth)
            language: Language for metadata (default: en-US)
            include_adult: Include adult content in searches (default: False)
            http_client: Optional HTTP client (creates default if None)
            cache_manager: Optional cache manager (creates default if None)
            cache_config: Optional cache configuration
            rate_limiter: Optional rate limiter (creates default if None)
            health_monitor: Optional health monitor (creates default if None)
        """
        self.config = _TMDbConfig(
            read_access_token=read_access_token.strip(),
            language=language.strip() or "en-US",
        )
        self.include_adult = include_adult
        self.http_client = http_client or HttpClient(base_url=TMDB_API_BASE)

        # Initialize cache manager
        if cache_manager is not None:
            self.cache = cache_manager
        else:
            cache_dir = get_intelligent_cache_dir()
            self.cache = CacheManager(cache_dir, config=cache_config)

        # Initialize rate limiter (TMDb allows 40 requests per 10 seconds)
        self.rate_limiter = rate_limiter or RateLimiter(RateLimit(requests=40, period=10.0))

        # Initialize health monitor (circuit breaker)
        self.health_monitor = health_monitor or HealthMonitor(
            failure_threshold=5,
            recovery_timeout=60.0,
        )

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
        }
        if self.config.read_access_token:
            headers["Authorization"] = f"Bearer {self.config.read_access_token}"
        return headers

    def _query_params(
        self, extra: dict[str, str | int | bool | None] | None = None
    ) -> dict[str, str]:
        params: dict[str, str] = {
            "language": self.config.language,
        }

        if not self.config.read_access_token:
            raise ValueError(
                "TMDb credentials are missing. Set metadata.tmdb_read_access_token "
                "in framekit.yaml or export FRAMEKIT_TMDB_READ_ACCESS_TOKEN."
            )

        if extra:
            for key, value in extra.items():
                if value is None or value == "":
                    continue
                if isinstance(value, bool):
                    params[key] = "true" if value else "false"
                else:
                    params[key] = str(value)

        return params

    def _request_json(
        self, path: str, params: dict[str, str | int | bool | None] | None = None
    ) -> dict[str, Any]:
        """Make an authenticated request to TMDb API with rate limiting and health monitoring.

        Args:
            path: API endpoint path
            params: Query parameters

        Returns:
            Parsed JSON response

        Raises:
            ValueError: On authentication failure
            FramekitMetadataError: On request failure
        """
        # Check if provider is available (circuit breaker)
        if not self.health_monitor.is_available(self.name):
            logger.warning("TMDb provider circuit is open, skipping request")
            raise FramekitMetadataError("TMDb provider is temporarily unavailable")

        # Acquire rate limit token
        if not self.rate_limiter.try_acquire():
            logger.warning("TMDb rate limit exceeded, request throttled")
            self.health_monitor.record_failure(self.name)
            raise FramekitMetadataError("TMDb rate limit exceeded")

        try:
            payload = self.http_client.get_json(
                path,
                params=self._query_params(params),
                headers=self._headers(),
            )

            # Record successful request
            self.health_monitor.record_success(self.name)

        except HttpAuthError as exc:
            self.health_monitor.record_failure(self.name)
            raise ValueError(
                "TMDb rejected your credentials (401/403). "
                "Check your TMDb read access token with: framekit metadata --status"
            ) from exc
        except HttpError as exc:
            self.health_monitor.record_failure(self.name)
            raise FramekitMetadataError(f"TMDb request failed: {exc}") from exc

        if not isinstance(payload, dict):
            self.health_monitor.record_failure(self.name)
            raise FramekitMetadataError("TMDb returned an unexpected non-object JSON payload.")

        return payload

    def _movie_candidate_confidence(
        self, result: dict, request: MetadataLookupRequest
    ) -> tuple[float, list[str]]:
        confidence = 0.0
        reasons: list[str] = []

        request_title = _normalize_text(request.title)
        candidate_title = _normalize_text(result.get("title"))

        if request_title and candidate_title == request_title:
            confidence += 0.7
            reasons.append("exact title")
        elif request_title and request_title in candidate_title:
            confidence += 0.45
            reasons.append("partial title")

        request_year = request.year
        candidate_year = _extract_year(result.get("release_date"))

        if request_year and candidate_year == request_year:
            confidence += 0.25
            reasons.append("year match")

        return confidence, reasons

    def _tv_candidate_confidence(
        self, result: dict, request: MetadataLookupRequest
    ) -> tuple[float, list[str]]:
        confidence = 0.0
        reasons: list[str] = []

        request_title = _normalize_text(request.title)
        candidate_title = _normalize_text(result.get("name"))

        if request_title and candidate_title == request_title:
            confidence += 0.7
            reasons.append("exact series title")
        elif request_title and request_title in candidate_title:
            confidence += 0.45
            reasons.append("partial series title")

        request_year = request.year
        candidate_year = _extract_year(result.get("first_air_date"))

        if request_year and candidate_year == request_year:
            confidence += 0.2
            reasons.append("year match")
        confidence, reasons = self._apply_tv_context_bonus(request, confidence, reasons)

        return confidence, reasons

    @staticmethod
    def _apply_tv_context_bonus(
        request: MetadataLookupRequest, confidence: float, reasons: list[str]
    ) -> tuple[float, list[str]]:
        if (
            request.media_kind == "single_episode"
            and request.season_number
            and request.episode_number
        ):
            return confidence + 0.1, [*reasons, "episode lookup context"]
        if request.media_kind == "season_pack" and request.season_number:
            return confidence + 0.1, [*reasons, "season lookup context"]
        return confidence, reasons

    def _movie_web_url(self, movie_id: str) -> str:
        return f"{TMDB_WEB_BASE}/movie/{movie_id}"

    def _tv_web_url(self, tv_id: str) -> str:
        return f"{TMDB_WEB_BASE}/tv/{tv_id}"

    def search_by_id(self, provider_id: str, media_kind: str) -> MetadataCandidate | None:
        """Create a candidate directly from a TMDB ID.

        Args:
            provider_id: The TMDB ID. Named ``provider_id`` to match the base
                ``MetadataProvider.search_by_id`` signature so the override
                stays Liskov-compatible.
            media_kind: The media kind (``"movie"``, ``"single_episode"``,
                ``"season_pack"``).

        Returns:
            MetadataCandidate or None if not found.
        """
        tmdb_id = provider_id  # local alias for readability against TMDb URLs
        try:
            if media_kind == "movie":
                details = self._request_json(f"/movie/{tmdb_id}")
                return MetadataCandidate(
                    provider_name=self.name,
                    provider_id=tmdb_id,
                    kind="movie",
                    title=details.get("title") or "",
                    year=_extract_year(details.get("release_date")),
                    imdb_id=None,
                    external_url=self._movie_web_url(tmdb_id),
                    overview=details.get("overview") or None,
                    confidence=1.0,
                    reasons=["manual ID"],
                )
            if media_kind in {"single_episode", "season_pack"}:
                details = self._request_json(f"/tv/{tmdb_id}")
                return MetadataCandidate(
                    provider_name=self.name,
                    provider_id=tmdb_id,
                    kind=media_kind,
                    title=details.get("name") or "",
                    year=_extract_year(details.get("first_air_date")),
                    imdb_id=None,
                    external_url=self._tv_web_url(tmdb_id),
                    overview=details.get("overview") or None,
                    confidence=1.0,
                    reasons=["manual ID"],
                )
        except Exception:
            return None

        return None

    def search(self, request: MetadataLookupRequest) -> list[MetadataCandidate]:
        """Search for movies or TV series on TMDb.

        Args:
            request: Metadata lookup request with search parameters

        Returns:
            List of metadata candidates matching the search
        """
        # Try to get from cache first
        query = request.title or ""
        cached = self.cache.get_tmdb_search(
            query=query,
            media_kind=request.media_kind,
            language=self.config.language,
        )
        if cached is not None:
            # Reconstruct MetadataCandidate objects from cached data
            return [MetadataCandidate(**item) for item in cached]

        logger.debug(f"Searching TMDb for: {request.title}")

        try:
            if request.media_kind == "movie":
                candidates = self._search_movie_candidates(request)
                self._cache_search_results(
                    query=query, media_kind=request.media_kind, candidates=candidates
                )
                logger.debug(f"Found {len(candidates)} TMDb movie candidates")
                return candidates

            if request.media_kind in {"single_episode", "season_pack"}:
                tv_candidates = self._search_tv_candidates(request)
                self._cache_search_results(
                    query=query,
                    media_kind=request.media_kind,
                    candidates=tv_candidates,
                )
                logger.debug(f"Found {len(tv_candidates)} TMDb TV candidates")
                return tv_candidates

            raise ValueError(f"TMDb provider does not support media kind: {request.media_kind}")

        except FramekitMetadataError as e:
            logger.warning(f"TMDb search failed: {e}")
            return []
        except Exception as e:
            logger.error(f"TMDb search error: {e}")
            return []

    def _search_movie_candidates(self, request: MetadataLookupRequest) -> list[MetadataCandidate]:
        payload = self._request_json(
            "/search/movie",
            {
                "query": request.title,
                "year": request.year,
                "include_adult": self.include_adult,
                "page": 1,
            },
        )
        results = payload.get("results", [])
        candidates: list[MetadataCandidate] = []
        for item in results[:8]:
            confidence, reasons = self._movie_candidate_confidence(item, request)
            candidates.append(
                MetadataCandidate(
                    provider_name=self.name,
                    provider_id=str(item["id"]),
                    kind="movie",
                    title=item.get("title") or "",
                    year=_extract_year(item.get("release_date")),
                    imdb_id=None,
                    external_url=self._movie_web_url(str(item["id"])),
                    overview=item.get("overview") or None,
                    confidence=confidence,
                    reasons=reasons,
                )
            )
        return candidates

    def _search_tv_candidates(self, request: MetadataLookupRequest) -> list[MetadataCandidate]:
        payload = self._request_json(
            "/search/tv",
            {
                "query": request.title,
                "first_air_date_year": request.year,
                "include_adult": self.include_adult,
                "page": 1,
            },
        )
        results = payload.get("results", [])
        tv_candidates: list[MetadataCandidate] = []
        for item in results[:8]:
            confidence, reasons = self._tv_candidate_confidence(item, request)
            tv_candidates.append(
                MetadataCandidate(
                    provider_name=self.name,
                    provider_id=str(item["id"]),
                    kind=request.media_kind,
                    title=item.get("name") or "",
                    year=_extract_year(item.get("first_air_date")),
                    season_number=request.season_number,
                    episode_number=request.episode_number,
                    imdb_id=None,
                    external_url=self._tv_web_url(str(item["id"])),
                    overview=item.get("overview") or None,
                    confidence=confidence,
                    reasons=reasons,
                )
            )
        return tv_candidates

    def _cache_search_results(
        self,
        *,
        query: str,
        media_kind: str,
        candidates: list[MetadataCandidate],
    ) -> None:
        from dataclasses import asdict

        self.cache.set_tmdb_search(
            query=query,
            media_kind=media_kind,
            results=[asdict(candidate) for candidate in candidates],
            language=self.config.language,
        )

    def _intelligent_poster_name(self, poster: dict[str, Any], index: int, is_first: bool) -> str:
        """Generate an intelligent name for a poster based on its metadata.

        Args:
            poster: Poster metadata from TMDb API
            index: 1-based index of the poster
            is_first: Whether this is the first/primary poster

        Returns:
            Intelligent poster name
        """
        file_path = poster.get("file_path", "")
        aspect_ratio = poster.get("aspect_ratio", 0.0)

        # Check if it's the primary/default poster
        if is_first:
            return "Poster (Default)"

        # Check for season number in file path (e.g., /season/2/poster.jpg)
        import re

        season_match = re.search(r"/season[/_-]?(\d+)", file_path, re.IGNORECASE)
        if season_match:
            season_num = season_match.group(1)
            return f"Poster Season {season_num}"

        # Check for horizontal/landscape orientation (aspect ratio > 1.5)
        if aspect_ratio > 1.5:
            return "Poster Horizontal"

        # Check for year in file path
        year_match = re.search(r"(19\d{2}|20\d{2})", file_path)
        if year_match:
            year = year_match.group(1)
            return f"Poster {year}"

        # Fallback to numbered poster
        return f"Poster #{index}"

    def fetch_posters(self, candidate: MetadataCandidate) -> list[dict[str, str]]:
        """Fetch available poster images for a candidate.

        Returns a list of poster dictionaries with 'url' and 'size' keys.
        """
        # Try to get from cache first
        media_kind = "movie" if candidate.kind == "movie" else "tv"
        cached = self.cache.get_tmdb_posters(candidate.provider_id, media_kind)
        if cached is not None:
            return cached

        if candidate.kind == "movie":
            images = self._request_json(f"/movie/{candidate.provider_id}/images")
        elif candidate.kind in {"single_episode", "season_pack"}:
            images = self._request_json(f"/tv/{candidate.provider_id}/images")
        else:
            raise ValueError(
                f"TMDb provider does not support fetching posters for kind: {candidate.kind}"
            )

        posters: list[dict[str, str]] = []
        for idx, poster in enumerate(images.get("posters", []), start=1):
            file_path = poster.get("file_path")
            if not file_path:
                continue

            # Generate intelligent poster name
            is_first = idx == 1
            poster_name = self._intelligent_poster_name(poster, idx, is_first)

            # Add the w500 version (standard size)
            posters.append(
                {
                    "url": f"https://image.tmdb.org/t/p/w500{file_path}",
                    "url_original": f"https://image.tmdb.org/t/p/original{file_path}",
                    "size": f"{poster.get('width', 0)}x{poster.get('height', 0)}",
                    "language": poster.get("iso_639_1") or "en",
                    "name": poster_name,
                    "aspect_ratio": poster.get("aspect_ratio", 0.0),
                }
            )

        # Cache the posters
        self.cache.set_tmdb_posters(candidate.provider_id, media_kind, posters)

        return posters

    def fetch_movie(self, candidate: MetadataCandidate) -> MovieMetadata:
        """Handle fetch movie."""
        details = self._request_json(
            f"/movie/{candidate.provider_id}", {"append_to_response": "credits"}
        )
        external_ids = self._request_json(f"/movie/{candidate.provider_id}/external_ids")

        imdb_id = external_ids.get("imdb_id") or None
        external_url = self._movie_web_url(candidate.provider_id)

        return MovieMetadata(
            provider_name=self.name,
            provider_id=candidate.provider_id,
            imdb_id=imdb_id,
            external_url=external_url,
            title=details.get("title") or candidate.title,
            year=_extract_year(details.get("release_date")),
            overview=details.get("overview") or None,
            genres=[item["name"] for item in details.get("genres", []) if item.get("name")],
            runtime_minutes=details.get("runtime") or None,
            original_title=details.get("original_title") or None,
            release_date=details.get("release_date") or None,
            countries=_countries(details),
            spoken_languages=_spoken_languages(details),
            vote_average=details.get("vote_average") or None,
            poster_url=_poster_url(details.get("poster_path")),
            cast=_cast_names(details.get("credits")),
            crew=_crew_names(details.get("credits")),
        )

    def fetch_episode(self, candidate: MetadataCandidate) -> EpisodeMetadata:
        """Handle fetch episode."""
        season_number, episode_number = self._require_episode_numbers(candidate)
        series_details, episode_details, external_ids = self._fetch_episode_payload(
            candidate.provider_id,
            season_number,
            episode_number,
        )
        return self._build_episode_metadata(
            candidate=candidate,
            season_number=season_number,
            episode_number=episode_number,
            series_details=series_details,
            episode_details=episode_details,
            external_ids=external_ids,
        )

    def _require_episode_numbers(self, candidate: MetadataCandidate) -> tuple[int, int]:
        if candidate.season_number is None or candidate.episode_number is None:
            raise ValueError("TMDb episode fetch requires season_number and episode_number.")
        return candidate.season_number, candidate.episode_number

    def _build_episode_metadata(
        self,
        *,
        candidate: MetadataCandidate,
        season_number: int,
        episode_number: int,
        series_details: dict[str, Any],
        episode_details: dict[str, Any],
        external_ids: dict[str, Any],
    ) -> EpisodeMetadata:
        imdb_id = _coalesce(external_ids.get("imdb_id"), None)
        series_url = self._tv_web_url(candidate.provider_id)
        episode_url = f"{series_url}/season/{season_number}/episode/{episode_number}"
        return EpisodeMetadata(
            provider_name=self.name,
            provider_id=str(_coalesce(episode_details.get("id"), candidate.provider_id)),
            imdb_id=imdb_id,
            external_url=series_url,
            series_title=_coalesce(series_details.get("name"), candidate.title),
            series_year=_extract_year(series_details.get("first_air_date")),
            season_number=season_number,
            episode_number=episode_number,
            episode_title=_coalesce(episode_details.get("name"), None),
            overview=_coalesce(episode_details.get("overview"), None),
            air_date=_coalesce(episode_details.get("air_date"), None),
            runtime_minutes=_coalesce(episode_details.get("runtime"), None),
            series_original_title=_coalesce(series_details.get("original_name"), None),
            first_air_date=_coalesce(series_details.get("first_air_date"), None),
            genres=[item["name"] for item in series_details.get("genres", []) if item.get("name")],
            countries=_countries(series_details),
            spoken_languages=_spoken_languages(series_details),
            vote_average=_coalesce(
                episode_details.get("vote_average"),
                series_details.get("vote_average"),
                None,
            ),
            poster_url=_poster_url(series_details.get("poster_path")),
            still_url=_poster_url(episode_details.get("still_path")),
            series_provider_id=candidate.provider_id,
            series_url=series_url,
            episode_url=episode_url,
            cast=_cast_names(series_details.get("credits")),
            crew=_series_crew_names(series_details),
        )

    def _fetch_episode_payload(
        self,
        provider_id: str,
        season_number: int,
        episode_number: int,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        series_details = self._request_json(f"/tv/{provider_id}", {"append_to_response": "credits"})
        episode_base = f"/tv/{provider_id}/season/{season_number}/episode/{episode_number}"
        episode_details = self._request_json(episode_base)
        external_ids = self._request_json(f"{episode_base}/external_ids")
        return series_details, episode_details, external_ids

    def _fetch_season_payload(
        self, candidate: MetadataCandidate, season_number: int
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        series_details = self._request_json(
            f"/tv/{candidate.provider_id}", {"append_to_response": "credits"}
        )
        season_details = self._request_json(f"/tv/{candidate.provider_id}/season/{season_number}")
        external_ids = self._request_json(
            f"/tv/{candidate.provider_id}/season/{season_number}/external_ids"
        )
        return series_details, season_details, external_ids

    def _build_season_episode_summaries(
        self,
        *,
        candidate: MetadataCandidate,
        season_number: int,
        series_details: dict[str, Any],
        season_details: dict[str, Any],
        series_url: str,
    ) -> list[EpisodeMetadata]:
        return [
            self._build_episode_summary(
                candidate=candidate,
                season_number=season_number,
                series_details=series_details,
                series_url=series_url,
                episode_payload=item,
            )
            for item in season_details.get("episodes", [])
        ]

    def _build_episode_summary(
        self,
        *,
        candidate: MetadataCandidate,
        season_number: int,
        series_details: dict[str, Any],
        series_url: str,
        episode_payload: dict[str, Any],
    ) -> EpisodeMetadata:
        episode_number = episode_payload.get("episode_number")
        return EpisodeMetadata(
            provider_name=self.name,
            provider_id=str(episode_payload.get("id") or ""),
            imdb_id=None,
            external_url=series_url,
            series_title=series_details.get("name") or candidate.title,
            series_year=_extract_year(series_details.get("first_air_date")),
            season_number=season_number,
            episode_number=episode_number,
            episode_title=episode_payload.get("name") or None,
            overview=episode_payload.get("overview") or None,
            air_date=episode_payload.get("air_date") or None,
            runtime_minutes=episode_payload.get("runtime") or None,
            series_original_title=series_details.get("original_name") or None,
            first_air_date=series_details.get("first_air_date") or None,
            series_provider_id=candidate.provider_id,
            series_url=series_url,
            episode_url=f"{series_url}/season/{season_number}/episode/{episode_number}",
        )

    def fetch_season(self, candidate: MetadataCandidate) -> SeasonMetadata:
        """Handle fetch season."""
        season_number = self._require_season_number(candidate)
        series_details, season_details, external_ids = self._fetch_season_payload(
            candidate, season_number
        )
        episode_summaries = self._build_season_episode_summaries(
            candidate=candidate,
            season_number=season_number,
            series_details=series_details,
            season_details=season_details,
            series_url=self._tv_web_url(candidate.provider_id),
        )
        return self._build_season_metadata(
            candidate=candidate,
            season_number=season_number,
            series_details=series_details,
            season_details=season_details,
            external_ids=external_ids,
            episode_summaries=episode_summaries,
        )

    def _require_season_number(self, candidate: MetadataCandidate) -> int:
        if candidate.season_number is None:
            raise ValueError("TMDb season fetch requires season_number.")
        return candidate.season_number

    def _build_season_metadata(
        self,
        *,
        candidate: MetadataCandidate,
        season_number: int,
        series_details: dict[str, Any],
        season_details: dict[str, Any],
        external_ids: dict[str, Any],
        episode_summaries: list[EpisodeMetadata],
    ) -> SeasonMetadata:
        imdb_id = _coalesce(external_ids.get("imdb_id"), None)
        series_url = self._tv_web_url(candidate.provider_id)
        season_url = f"{series_url}/season/{season_number}"
        return SeasonMetadata(
            provider_name=self.name,
            provider_id=str(_coalesce(season_details.get("id"), candidate.provider_id)),
            imdb_id=imdb_id,
            external_url=series_url,
            series_title=_coalesce(series_details.get("name"), candidate.title),
            series_year=_extract_year(series_details.get("first_air_date")),
            season_number=season_number,
            overview=_coalesce(season_details.get("overview"), None),
            episode_summaries=episode_summaries,
            series_original_title=_coalesce(series_details.get("original_name"), None),
            first_air_date=_coalesce(series_details.get("first_air_date"), None),
            genres=[item["name"] for item in series_details.get("genres", []) if item.get("name")],
            countries=_countries(series_details),
            spoken_languages=_spoken_languages(series_details),
            vote_average=_coalesce(series_details.get("vote_average"), None),
            poster_url=_poster_url(
                _coalesce(season_details.get("poster_path"), series_details.get("poster_path"))
            ),
            air_date=_coalesce(season_details.get("air_date"), None),
            series_provider_id=candidate.provider_id,
            series_url=series_url,
            season_url=season_url,
            cast=_cast_names(series_details.get("credits")),
            crew=_series_crew_names(series_details),
        )


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None
