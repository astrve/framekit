"""Provider chain for multi-provider metadata lookup with fallback."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

from ouro.core.models.metadata import MetadataCandidate, MetadataLookupRequest

if TYPE_CHECKING:
    from ouro.modules.metadata.base import MetadataProvider


@dataclass
class ProviderResult:
    """Result from a provider search."""

    provider_name: str
    metadata: MetadataCandidate | None
    error: Exception | None
    duration_ms: float


class ProviderChain:
    """Chains multiple metadata providers with fallback logic.

    This class manages multiple metadata providers and implements automatic
    fallback when a provider fails or returns no results. It supports:
    - Sequential provider attempts with first-success strategy
    - Parallel search across all providers
    - Error aggregation and reporting
    - Performance tracking per provider

    Example:
        >>> providers = [tmdb_provider, tvdb_provider]
        >>> chain = ProviderChain(providers=providers)
        >>> result = chain.search(request)
    """

    def __init__(self, providers: list[MetadataProvider]):
        """Initialize provider chain.

        Args:
            providers: Ordered list of metadata providers to try.
                      Providers are attempted in the order provided.
        """
        self.providers = providers

    def search(
        self,
        request: MetadataLookupRequest,
        content_type: str | None = None,
        language: str = "en",
    ) -> MetadataCandidate | None:
        """Search across providers with automatic fallback.

        Tries each provider in sequence until one returns a successful result.
        Returns the first successful match or None if all providers fail.

        Args:
            request: Metadata lookup request with search parameters
            content_type: Optional content type hint for provider selection
            language: Language code for metadata (default: "en")

        Returns:
            First successful metadata candidate or None if all providers fail
        """
        if not self.providers:
            logger.warning("No providers available in chain")
            return None

        for provider in self.providers:
            try:
                logger.debug(f"Trying provider: {provider.name}")
                start_time = time.time()

                candidates = provider.search(request)

                duration_ms = (time.time() - start_time) * 1000
                logger.debug(
                    f"Provider {provider.name} returned {len(candidates)} candidates "
                    f"in {duration_ms:.2f}ms"
                )

                if candidates:
                    # Return first candidate from first successful provider
                    return candidates[0]
                else:
                    logger.debug(f"Provider {provider.name} returned no results")

            except Exception as e:
                logger.warning(f"Provider {provider.name} failed: {e.__class__.__name__}: {e}")
                continue

        logger.warning("All providers failed or returned no results")
        return None

    def search_candidates(
        self,
        request: MetadataLookupRequest,
    ) -> list[MetadataCandidate]:
        """Search providers with fallback, returning full candidate list.

        Tries each provider in sequence. Returns all candidates from the first
        provider that yields results. If no provider succeeds, returns empty list.
        """
        if not self.providers:
            return []

        for provider in self.providers:
            try:
                logger.debug(f"Chain search_candidates: trying {provider.name}")
                start_time = time.time()
                candidates = provider.search(request)
                duration_ms = (time.time() - start_time) * 1000
                logger.debug(
                    f"Provider {provider.name}: {len(candidates)} candidates in {duration_ms:.1f}ms"
                )
                if candidates:
                    return candidates
            except Exception as e:
                logger.warning(f"Provider {provider.name} failed: {e}")
                continue

        return []

    @property
    def primary_provider(self) -> MetadataProvider | None:
        """Return the first provider in the chain (primary)."""
        return self.providers[0] if self.providers else None

    def search_all(
        self,
        request: MetadataLookupRequest,
        content_type: str | None = None,
        language: str = "en",
    ) -> list[ProviderResult]:
        """Search all providers and return all results.

        Unlike search(), this method queries all providers regardless of
        success/failure and returns results from all of them. Useful for
        comparison or manual selection.

        Args:
            request: Metadata lookup request with search parameters
            content_type: Optional content type hint for provider selection
            language: Language code for metadata (default: "en")

        Returns:
            List of ProviderResult objects, one per provider
        """
        results: list[ProviderResult] = []

        for provider in self.providers:
            start_time = time.time()
            metadata: MetadataCandidate | None = None
            error: Exception | None = None

            try:
                logger.debug(f"Querying provider: {provider.name}")
                candidates = provider.search(request)

                if candidates:
                    metadata = candidates[0]
                    logger.debug(f"Provider {provider.name} returned {len(candidates)} candidates")
                else:
                    logger.debug(f"Provider {provider.name} returned no results")

            except Exception as e:
                error = e
                logger.warning(f"Provider {provider.name} failed: {e.__class__.__name__}: {e}")

            duration_ms = (time.time() - start_time) * 1000

            results.append(
                ProviderResult(
                    provider_name=provider.name,
                    metadata=metadata,
                    error=error,
                    duration_ms=duration_ms,
                )
            )

        return results
