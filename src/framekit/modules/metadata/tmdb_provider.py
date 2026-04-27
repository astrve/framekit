from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from framekit.core.exceptions import FramekitMetadataError
from framekit.core.http import HttpAuthError, HttpClient, HttpError
from framekit.core.models.metadata import (
    EpisodeMetadata,
    MetadataCandidate,
    MetadataLookupRequest,
    MovieMetadata,
    SeasonMetadata,
)
from framekit.modules.metadata.base import MetadataProvider

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
    api_key: str
    read_access_token: str
    language: str


class TMDbProvider(MetadataProvider):
    name = "tmdb"

    def __init__(
        self,
        *,
        api_key: str = "",
        read_access_token: str = "",
        language: str = "en-US",
        include_adult: bool = False,
        http_client: HttpClient | None = None,
    ) -> None:
        self.config = _TMDbConfig(
            api_key=api_key.strip(),
            read_access_token=read_access_token.strip(),
            language=language.strip() or "en-US",
        )
        self.include_adult = include_adult
        self.http_client = http_client or HttpClient(base_url=TMDB_API_BASE)

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
            if not self.config.api_key:
                raise ValueError(
                    "TMDb credentials are missing. Set metadata.tmdb_api_key or metadata.tmdb_read_access_token."
                )
            params["api_key"] = self.config.api_key

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
        try:
            payload = self.http_client.get_json(
                path,
                params=self._query_params(params),
                headers=self._headers(),
            )
        except HttpAuthError as exc:
            raise ValueError(
                "TMDb rejected your credentials (401/403). "
                "Check your TMDb read access token with: framekit metadata --status"
            ) from exc
        except HttpError as exc:
            raise FramekitMetadataError(f"TMDb request failed: {exc}") from exc

        if not isinstance(payload, dict):
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

        if (
            request.media_kind == "single_episode"
            and request.season_number
            and request.episode_number
        ):
            confidence += 0.1
            reasons.append("episode lookup context")

        if request.media_kind == "season_pack" and request.season_number:
            confidence += 0.1
            reasons.append("season lookup context")

        return confidence, reasons

    def _movie_web_url(self, movie_id: str) -> str:
        return f"{TMDB_WEB_BASE}/movie/{movie_id}"

    def _tv_web_url(self, tv_id: str) -> str:
        return f"{TMDB_WEB_BASE}/tv/{tv_id}"

    def search(self, request: MetadataLookupRequest) -> list[MetadataCandidate]:
        if request.media_kind == "movie":
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

        if request.media_kind in {"single_episode", "season_pack"}:
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

            candidates: list[MetadataCandidate] = []
            for item in results[:8]:
                confidence, reasons = self._tv_candidate_confidence(item, request)
                candidates.append(
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
            return candidates

        raise ValueError(f"TMDb provider does not support media kind: {request.media_kind}")

    def fetch_movie(self, candidate: MetadataCandidate) -> MovieMetadata:
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
        if candidate.season_number is None or candidate.episode_number is None:
            raise ValueError("TMDb episode fetch requires season_number and episode_number.")

        series_details = self._request_json(
            f"/tv/{candidate.provider_id}", {"append_to_response": "credits"}
        )
        episode_details = self._request_json(
            f"/tv/{candidate.provider_id}/season/{candidate.season_number}/episode/{candidate.episode_number}"
        )
        external_ids = self._request_json(
            f"/tv/{candidate.provider_id}/season/{candidate.season_number}/episode/{candidate.episode_number}/external_ids"
        )

        imdb_id = external_ids.get("imdb_id") or None
        series_url = self._tv_web_url(candidate.provider_id)
        episode_url = (
            f"{series_url}/season/{candidate.season_number}/episode/{candidate.episode_number}"
        )

        return EpisodeMetadata(
            provider_name=self.name,
            provider_id=str(episode_details.get("id") or candidate.provider_id),
            imdb_id=imdb_id,
            external_url=series_url,
            series_title=series_details.get("name") or candidate.title,
            series_year=_extract_year(series_details.get("first_air_date")),
            season_number=candidate.season_number,
            episode_number=candidate.episode_number,
            episode_title=episode_details.get("name") or None,
            overview=episode_details.get("overview") or None,
            air_date=episode_details.get("air_date") or None,
            runtime_minutes=episode_details.get("runtime") or None,
            series_original_title=series_details.get("original_name") or None,
            first_air_date=series_details.get("first_air_date") or None,
            genres=[item["name"] for item in series_details.get("genres", []) if item.get("name")],
            countries=_countries(series_details),
            spoken_languages=_spoken_languages(series_details),
            vote_average=episode_details.get("vote_average")
            or series_details.get("vote_average")
            or None,
            poster_url=_poster_url(series_details.get("poster_path")),
            still_url=_poster_url(episode_details.get("still_path")),
            series_provider_id=candidate.provider_id,
            series_url=series_url,
            episode_url=episode_url,
            cast=_cast_names(series_details.get("credits")),
            crew=_series_crew_names(series_details),
        )

    def fetch_season(self, candidate: MetadataCandidate) -> SeasonMetadata:
        if candidate.season_number is None:
            raise ValueError("TMDb season fetch requires season_number.")

        series_details = self._request_json(
            f"/tv/{candidate.provider_id}", {"append_to_response": "credits"}
        )
        season_details = self._request_json(
            f"/tv/{candidate.provider_id}/season/{candidate.season_number}"
        )
        external_ids = self._request_json(
            f"/tv/{candidate.provider_id}/season/{candidate.season_number}/external_ids"
        )

        imdb_id = external_ids.get("imdb_id") or None
        series_url = self._tv_web_url(candidate.provider_id)
        season_url = f"{series_url}/season/{candidate.season_number}"

        episode_summaries: list[EpisodeMetadata] = []
        for item in season_details.get("episodes", []):
            episode_summaries.append(
                EpisodeMetadata(
                    provider_name=self.name,
                    provider_id=str(item.get("id") or ""),
                    imdb_id=None,
                    external_url=series_url,
                    series_title=series_details.get("name") or candidate.title,
                    series_year=_extract_year(series_details.get("first_air_date")),
                    season_number=candidate.season_number,
                    episode_number=item.get("episode_number"),
                    episode_title=item.get("name") or None,
                    overview=item.get("overview") or None,
                    air_date=item.get("air_date") or None,
                    runtime_minutes=item.get("runtime") or None,
                    series_original_title=series_details.get("original_name") or None,
                    first_air_date=series_details.get("first_air_date") or None,
                    series_provider_id=candidate.provider_id,
                    series_url=series_url,
                    episode_url=(
                        f"{series_url}/season/{candidate.season_number}"
                        f"/episode/{item.get('episode_number')}"
                    ),
                )
            )

        return SeasonMetadata(
            provider_name=self.name,
            provider_id=str(season_details.get("id") or candidate.provider_id),
            imdb_id=imdb_id,
            external_url=series_url,
            series_title=series_details.get("name") or candidate.title,
            series_year=_extract_year(series_details.get("first_air_date")),
            season_number=candidate.season_number,
            overview=season_details.get("overview") or None,
            episode_summaries=episode_summaries,
            series_original_title=series_details.get("original_name") or None,
            first_air_date=series_details.get("first_air_date") or None,
            genres=[item["name"] for item in series_details.get("genres", []) if item.get("name")],
            countries=_countries(series_details),
            spoken_languages=_spoken_languages(series_details),
            vote_average=series_details.get("vote_average") or None,
            poster_url=_poster_url(
                season_details.get("poster_path") or series_details.get("poster_path")
            ),
            air_date=season_details.get("air_date") or None,
            series_provider_id=candidate.provider_id,
            series_url=series_url,
            season_url=season_url,
            cast=_cast_names(series_details.get("credits")),
            crew=_series_crew_names(series_details),
        )
