from __future__ import annotations

from framekit.core.models.metadata import (
    EpisodeMetadata,
    MetadataCandidate,
    MetadataLookupRequest,
    MovieMetadata,
    SeasonMetadata,
)
from framekit.core.models.nfo import ReleaseNfoData
from framekit.modules.metadata.base import MetadataProvider
from framekit.modules.metadata.cache import MetadataCache
from framekit.modules.metadata.choices import MetadataChoiceStore
from framekit.modules.metadata.matcher import build_lookup_request, sort_candidates


class MetadataService:
    def __init__(
        self,
        provider: MetadataProvider,
        *,
        cache: MetadataCache | None = None,
        choice_store: MetadataChoiceStore | None = None,
        cache_ttl_hours: int = 168,
    ) -> None:
        self.provider = provider
        self.cache = cache or MetadataCache()
        self.choice_store = choice_store or MetadataChoiceStore()
        self.cache_ttl_hours = cache_ttl_hours

    def build_lookup_request(self, release: ReleaseNfoData) -> MetadataLookupRequest:
        return build_lookup_request(release)

    def get_stored_choice(self, release: ReleaseNfoData) -> MetadataCandidate | None:
        stored = self.choice_store.get(release)
        if not stored:
            return None

        if stored.provider_name != self.provider.name:
            return None

        return MetadataCandidate(
            provider_name=stored.provider_name,
            provider_id=stored.provider_id,
            kind=stored.kind,
            title=stored.title,
            year=stored.year,
            season_number=stored.season_number,
            episode_number=stored.episode_number,
            imdb_id=stored.imdb_id,
            external_url=stored.external_url,
            confidence=1.0,
            reasons=["stored choice"],
        )

    def store_choice(self, release: ReleaseNfoData, candidate: MetadataCandidate) -> None:
        self.choice_store.set(release, candidate)

    def clear_stored_choice(self, release: ReleaseNfoData) -> None:
        self.choice_store.clear(release)

    def _same_candidate(self, left: MetadataCandidate, right: MetadataCandidate) -> bool:
        return (
            left.provider_name == right.provider_name
            and left.provider_id == right.provider_id
            and left.kind == right.kind
            and left.season_number == right.season_number
            and left.episode_number == right.episode_number
        )

    def _merge_stored_choice(
        self,
        stored: MetadataCandidate | None,
        candidates: list[MetadataCandidate],
    ) -> list[MetadataCandidate]:
        if stored is None:
            return candidates

        merged: list[MetadataCandidate] = []
        matched_existing = False

        for candidate in candidates:
            if self._same_candidate(stored, candidate):
                reasons = list(candidate.reasons)
                if "stored choice" not in reasons:
                    reasons.insert(0, "stored choice")

                merged.append(
                    MetadataCandidate(
                        provider_name=candidate.provider_name,
                        provider_id=candidate.provider_id,
                        kind=candidate.kind,
                        title=candidate.title,
                        year=candidate.year,
                        season_number=candidate.season_number,
                        episode_number=candidate.episode_number,
                        imdb_id=candidate.imdb_id or stored.imdb_id,
                        external_url=candidate.external_url or stored.external_url,
                        overview=candidate.overview or stored.overview,
                        confidence=max(candidate.confidence, 1.0),
                        reasons=reasons,
                    )
                )
                matched_existing = True
            else:
                merged.append(candidate)

        if not matched_existing:
            merged.insert(0, stored)

        return merged

    def search(
        self, release: ReleaseNfoData
    ) -> tuple[MetadataLookupRequest, list[MetadataCandidate]]:
        request = self.build_lookup_request(release)
        stored = self.get_stored_choice(release)

        cached = self.cache.get(self.provider.name, request, self.cache_ttl_hours)
        if cached is not None:
            ordered = sort_candidates(cached)
            return request, self._merge_stored_choice(stored, ordered)

        candidates = self.provider.search(request)
        ordered = sort_candidates(candidates)
        self.cache.set(self.provider.name, request, ordered)

        return request, self._merge_stored_choice(stored, ordered)

    def resolve_candidate(
        self,
        candidate: MetadataCandidate,
    ) -> MovieMetadata | EpisodeMetadata | SeasonMetadata:
        if candidate.kind == "movie":
            return self.provider.fetch_movie(candidate)

        if candidate.kind == "single_episode":
            return self.provider.fetch_episode(candidate)

        if candidate.kind == "season_pack":
            return self.provider.fetch_season(candidate)

        raise ValueError(f"Unsupported metadata candidate kind: {candidate.kind}")
