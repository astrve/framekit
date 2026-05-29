from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ouro.core.models.metadata import (
    EpisodeMetadata,
    MetadataCandidate,
    MetadataLookupRequest,
    MovieMetadata,
    SeasonMetadata,
)


class MetadataProvider(ABC):
    """Metadata provider."""

    name: str

    @abstractmethod
    def search(self, request: MetadataLookupRequest) -> list[MetadataCandidate]:
        """Handle search."""
        raise NotImplementedError

    @abstractmethod
    def fetch_movie(self, candidate: MetadataCandidate) -> MovieMetadata:
        """Handle fetch movie."""
        raise NotImplementedError

    @abstractmethod
    def fetch_episode(self, candidate: MetadataCandidate) -> EpisodeMetadata:
        """Handle fetch episode."""
        raise NotImplementedError

    @abstractmethod
    def fetch_season(self, candidate: MetadataCandidate) -> SeasonMetadata:
        """Handle fetch season."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Optional capability hooks
    # ------------------------------------------------------------------
    # Subclasses MAY override the two methods below. The defaults are
    # deliberate no-ops so callers (notably ``workflow.run_metadata_workflow``)
    # can rely on the calls existing without typing tricks. Providers that do
    # not support manual-ID lookup or poster discovery simply opt out by
    # leaving the default behavior in place.

    def search_by_id(
        self,
        provider_id: str,
        media_kind: str,
    ) -> MetadataCandidate | None:
        """Resolve a candidate from a provider-specific ID.

        Args:
            provider_id: TMDb / TVDb / Trakt / AniList identifier.
            media_kind: ``"movie"``, ``"tv"``, ``"season"`` or ``"episode"``.

        Returns:
            A :class:`MetadataCandidate` if the provider supports ID lookup
            and the ID resolves, otherwise ``None``. The default
            implementation returns ``None`` to indicate the capability is not
            supported by this provider.
        """
        del provider_id, media_kind  # unused in default implementation
        return None

    def fetch_posters(self, candidate: MetadataCandidate) -> list[dict[str, Any]]:
        """Return a list of poster dictionaries for ``candidate``.

        Each dict carries at least ``url`` and ``url_original``. The default
        implementation returns an empty list so callers can fall back to the
        ``poster_url`` already resolved on the metadata payload.

        Args:
            candidate: The selected metadata candidate.

        Returns:
            List of poster dictionaries. Empty when the provider has no
            poster discovery capability.
        """
        del candidate  # unused in default implementation
        return []
