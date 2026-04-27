from __future__ import annotations

from abc import ABC, abstractmethod

from framekit.core.models.metadata import (
    EpisodeMetadata,
    MetadataCandidate,
    MetadataLookupRequest,
    MovieMetadata,
    SeasonMetadata,
)


class MetadataProvider(ABC):
    name: str

    @abstractmethod
    def search(self, request: MetadataLookupRequest) -> list[MetadataCandidate]:
        raise NotImplementedError

    @abstractmethod
    def fetch_movie(self, candidate: MetadataCandidate) -> MovieMetadata:
        raise NotImplementedError

    @abstractmethod
    def fetch_episode(self, candidate: MetadataCandidate) -> EpisodeMetadata:
        raise NotImplementedError

    @abstractmethod
    def fetch_season(self, candidate: MetadataCandidate) -> SeasonMetadata:
        raise NotImplementedError
