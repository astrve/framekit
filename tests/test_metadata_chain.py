"""Tests for metadata provider chain with fallback logic."""

from __future__ import annotations

from ouro.core.models.metadata import (
    EpisodeMetadata,
    MetadataCandidate,
    MetadataLookupRequest,
    MovieMetadata,
    SeasonMetadata,
)
from ouro.modules.metadata.base import MetadataProvider
from ouro.modules.metadata.chain import ProviderChain, ProviderResult


class MockProvider(MetadataProvider):
    """Mock provider for testing."""

    def __init__(self, name: str, should_fail: bool = False, results: list | None = None):
        self.name = name
        self.should_fail = should_fail
        self.results = results or []
        self.search_called = False
        self.fetch_movie_called = False
        self.fetch_episode_called = False
        self.fetch_season_called = False

    def search(self, request: MetadataLookupRequest) -> list[MetadataCandidate]:
        """Mock search."""
        self.search_called = True
        if self.should_fail:
            raise Exception(f"{self.name} search failed")
        return self.results

    def fetch_movie(self, candidate: MetadataCandidate) -> MovieMetadata:
        """Mock fetch movie."""
        self.fetch_movie_called = True
        if self.should_fail:
            raise Exception(f"{self.name} fetch_movie failed")
        return MovieMetadata(
            provider_name=self.name,
            provider_id=candidate.provider_id,
            imdb_id=None,
            external_url=None,
            title=candidate.title,
            year=candidate.year,
            overview=None,
        )

    def fetch_episode(self, candidate: MetadataCandidate) -> EpisodeMetadata:
        """Mock fetch episode."""
        self.fetch_episode_called = True
        if self.should_fail:
            raise Exception(f"{self.name} fetch_episode failed")
        return EpisodeMetadata(
            provider_name=self.name,
            provider_id=candidate.provider_id,
            imdb_id=None,
            external_url=None,
            series_title=candidate.title,
            series_year=candidate.year,
            season_number=candidate.season_number,
            episode_number=candidate.episode_number,
            episode_title=None,
            overview=None,
        )

    def fetch_season(self, candidate: MetadataCandidate) -> SeasonMetadata:
        """Mock fetch season."""
        self.fetch_season_called = True
        if self.should_fail:
            raise Exception(f"{self.name} fetch_season failed")
        return SeasonMetadata(
            provider_name=self.name,
            provider_id=candidate.provider_id,
            imdb_id=None,
            external_url=None,
            series_title=candidate.title,
            series_year=candidate.year,
            season_number=candidate.season_number,
            overview=None,
        )


def test_provider_chain_initialization():
    """Test provider chain initialization."""
    provider1 = MockProvider("provider1")
    provider2 = MockProvider("provider2")

    chain = ProviderChain(providers=[provider1, provider2])

    assert len(chain.providers) == 2
    assert chain.providers[0].name == "provider1"
    assert chain.providers[1].name == "provider2"


def test_provider_chain_empty_providers():
    """Test provider chain with empty providers list."""
    chain = ProviderChain(providers=[])

    request = MetadataLookupRequest(
        media_kind="movie",
        title="Test Movie",
        year="2020",
    )

    result = chain.search(request)
    assert result is None


def test_provider_chain_search_success_first_provider():
    """Test successful search with first provider."""
    candidate = MetadataCandidate(
        provider_name="provider1",
        provider_id="123",
        kind="movie",
        title="Test Movie",
        year="2020",
        confidence=0.95,
    )

    provider1 = MockProvider("provider1", results=[candidate])
    provider2 = MockProvider("provider2")

    chain = ProviderChain(providers=[provider1, provider2])

    request = MetadataLookupRequest(
        media_kind="movie",
        title="Test Movie",
        year="2020",
    )

    result = chain.search(request)

    assert result is not None
    assert result.provider_name == "provider1"
    assert result.title == "Test Movie"
    assert provider1.search_called
    assert not provider2.search_called  # Should not try second provider


def test_provider_chain_fallback_on_failure():
    """Test fallback to second provider when first fails."""
    candidate = MetadataCandidate(
        provider_name="provider2",
        provider_id="456",
        kind="movie",
        title="Test Movie",
        year="2020",
        confidence=0.90,
    )

    provider1 = MockProvider("provider1", should_fail=True)
    provider2 = MockProvider("provider2", results=[candidate])

    chain = ProviderChain(providers=[provider1, provider2])

    request = MetadataLookupRequest(
        media_kind="movie",
        title="Test Movie",
        year="2020",
    )

    result = chain.search(request)

    assert result is not None
    assert result.provider_name == "provider2"
    assert provider1.search_called
    assert provider2.search_called


def test_provider_chain_fallback_on_empty_results():
    """Test fallback when first provider returns empty results."""
    candidate = MetadataCandidate(
        provider_name="provider2",
        provider_id="456",
        kind="movie",
        title="Test Movie",
        year="2020",
        confidence=0.90,
    )

    provider1 = MockProvider("provider1", results=[])  # Empty results
    provider2 = MockProvider("provider2", results=[candidate])

    chain = ProviderChain(providers=[provider1, provider2])

    request = MetadataLookupRequest(
        media_kind="movie",
        title="Test Movie",
        year="2020",
    )

    result = chain.search(request)

    assert result is not None
    assert result.provider_name == "provider2"
    assert provider1.search_called
    assert provider2.search_called


def test_provider_chain_all_providers_fail():
    """Test when all providers fail."""
    provider1 = MockProvider("provider1", should_fail=True)
    provider2 = MockProvider("provider2", should_fail=True)

    chain = ProviderChain(providers=[provider1, provider2])

    request = MetadataLookupRequest(
        media_kind="movie",
        title="Test Movie",
        year="2020",
    )

    result = chain.search(request)

    assert result is None
    assert provider1.search_called
    assert provider2.search_called


def test_provider_chain_search_all():
    """Test search_all returns results from all providers."""
    candidate1 = MetadataCandidate(
        provider_name="provider1",
        provider_id="123",
        kind="movie",
        title="Test Movie",
        year="2020",
        confidence=0.95,
    )

    candidate2 = MetadataCandidate(
        provider_name="provider2",
        provider_id="456",
        kind="movie",
        title="Test Movie",
        year="2020",
        confidence=0.90,
    )

    provider1 = MockProvider("provider1", results=[candidate1])
    provider2 = MockProvider("provider2", results=[candidate2])

    chain = ProviderChain(providers=[provider1, provider2])

    request = MetadataLookupRequest(
        media_kind="movie",
        title="Test Movie",
        year="2020",
    )

    results = chain.search_all(request)

    assert len(results) == 2
    assert results[0].provider_name == "provider1"
    assert results[0].metadata is not None
    assert results[0].error is None
    assert results[1].provider_name == "provider2"
    assert results[1].metadata is not None
    assert results[1].error is None


def test_provider_chain_search_all_with_failures():
    """Test search_all includes failures."""
    candidate = MetadataCandidate(
        provider_name="provider2",
        provider_id="456",
        kind="movie",
        title="Test Movie",
        year="2020",
        confidence=0.90,
    )

    provider1 = MockProvider("provider1", should_fail=True)
    provider2 = MockProvider("provider2", results=[candidate])

    chain = ProviderChain(providers=[provider1, provider2])

    request = MetadataLookupRequest(
        media_kind="movie",
        title="Test Movie",
        year="2020",
    )

    results = chain.search_all(request)

    assert len(results) == 2
    assert results[0].provider_name == "provider1"
    assert results[0].metadata is None
    assert results[0].error is not None
    assert results[1].provider_name == "provider2"
    assert results[1].metadata is not None
    assert results[1].error is None


def test_provider_chain_with_language():
    """Test provider chain passes language parameter."""
    candidate = MetadataCandidate(
        provider_name="provider1",
        provider_id="123",
        kind="movie",
        title="Test Movie",
        year="2020",
        confidence=0.95,
    )

    provider1 = MockProvider("provider1", results=[candidate])
    chain = ProviderChain(providers=[provider1])

    request = MetadataLookupRequest(
        media_kind="movie",
        title="Test Movie",
        year="2020",
    )

    result = chain.search(request, language="fr-FR")

    assert result is not None
    assert provider1.search_called


def test_provider_result_dataclass():
    """Test ProviderResult dataclass."""
    candidate = MetadataCandidate(
        provider_name="test",
        provider_id="123",
        kind="movie",
        title="Test",
        year="2020",
    )

    result = ProviderResult(
        provider_name="test",
        metadata=candidate,
        error=None,
        duration_ms=123.45,
    )

    assert result.provider_name == "test"
    assert result.metadata == candidate
    assert result.error is None
    assert result.duration_ms == 123.45
