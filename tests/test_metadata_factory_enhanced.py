"""Tests for enhanced metadata provider factory."""

from __future__ import annotations

import pytest

from swirrl.modules.metadata.base import MetadataProvider
from swirrl.modules.metadata.chain import ProviderChain
from swirrl.modules.metadata.config import MetadataRuntimeConfig
from swirrl.modules.metadata.factory import (
    build_metadata_provider,
    build_provider_chain,
    get_available_providers,
    register_provider,
)


def test_build_metadata_provider_tmdb():
    """Test building TMDb provider."""
    settings = {
        "metadata": {
            "provider": "tmdb",
            "tmdb_read_access_token": "test_token",
            "language": "en-US",
        }
    }

    provider = build_metadata_provider(settings)

    assert provider is not None
    assert provider.name == "tmdb"


def test_build_metadata_provider_with_config():
    """Test building provider with pre-resolved config."""
    config = MetadataRuntimeConfig(
        provider="tmdb",
        interactive_confirmation=True,
        cache_ttl_hours=168,
        language="en-US",
        tmdb_read_access_token="test_token",
        tvdb_api_key="",
        trakt_client_id="",
        trakt_client_secret="",
        trakt_access_token="",
        has_credentials=True,
        credential_source="settings",
        auth_mode="read_access_token",
    )

    provider = build_metadata_provider(config=config)

    assert provider is not None
    assert provider.name == "tmdb"


def test_build_metadata_provider_unknown():
    """Test building unknown provider raises error."""
    settings = {
        "metadata": {
            "provider": "unknown_provider",
        }
    }

    with pytest.raises(ValueError, match="Unknown provider"):
        build_metadata_provider(settings)


def test_build_metadata_provider_by_name():
    """Test building provider by explicit name."""
    settings = {
        "metadata": {
            "provider": "tmdb",
            "tmdb_read_access_token": "test_token",
        }
    }

    provider = build_metadata_provider(settings, provider_name="tmdb")

    assert provider is not None
    assert provider.name == "tmdb"


def test_build_provider_chain_single_provider():
    """Test building provider chain with single provider."""
    settings = {
        "metadata": {
            "provider": "tmdb",
            "tmdb_read_access_token": "test_token",
        }
    }

    chain = build_provider_chain(settings)

    assert isinstance(chain, ProviderChain)
    assert len(chain.providers) >= 1


def test_build_provider_chain_with_fallbacks():
    """Test building provider chain with fallback providers."""
    settings = {
        "metadata": {
            "provider": "tmdb",
            "fallback_providers": ["tvdb", "anilist"],
            "tmdb_read_access_token": "test_token",
            "tvdb_api_key": "test_key",
        }
    }

    chain = build_provider_chain(settings)

    assert isinstance(chain, ProviderChain)
    # Should have at least primary provider
    assert len(chain.providers) >= 1


def test_build_provider_chain_handles_failures():
    """Test that chain building handles provider initialization failures."""
    settings = {
        "metadata": {
            "provider": "tmdb",
            "fallback_providers": ["invalid_provider"],
            "tmdb_read_access_token": "test_token",
        }
    }

    # Should not raise, just skip invalid providers
    chain = build_provider_chain(settings)

    assert isinstance(chain, ProviderChain)


def test_get_available_providers():
    """Test getting list of available providers."""
    providers = get_available_providers()

    assert isinstance(providers, list)
    assert "tmdb" in providers


def test_register_provider():
    """Test registering a custom provider."""

    class CustomProvider(MetadataProvider):
        name = "custom"

        def search(self, request):
            return []

        def fetch_movie(self, candidate):
            pass

        def fetch_episode(self, candidate):
            pass

        def fetch_season(self, candidate):
            pass

    register_provider("custom", CustomProvider)

    providers = get_available_providers()
    assert "custom" in providers


def test_build_provider_chain_empty_settings():
    """Test building chain with empty settings uses defaults."""
    chain = build_provider_chain({})

    assert isinstance(chain, ProviderChain)


def test_build_provider_chain_with_config():
    """Test building chain with pre-resolved config."""
    config = MetadataRuntimeConfig(
        provider="tmdb",
        interactive_confirmation=True,
        cache_ttl_hours=168,
        language="en-US",
        tmdb_read_access_token="test_token",
        tvdb_api_key="",
        trakt_client_id="",
        trakt_client_secret="",
        trakt_access_token="",
        has_credentials=True,
        credential_source="settings",
        auth_mode="read_access_token",
    )

    chain = build_provider_chain(config=config)

    assert isinstance(chain, ProviderChain)


def test_build_metadata_provider_missing_credentials():
    """Test building provider with missing credentials."""
    settings = {
        "metadata": {
            "provider": "tmdb",
            "tmdb_read_access_token": "",
        }
    }

    # Should still build but may not be functional
    provider = build_metadata_provider(settings)

    assert provider is not None


def test_build_provider_chain_content_type_hints():
    """Test building chain with content type hints."""
    settings = {
        "metadata": {
            "provider": "tmdb",
            "content_type_hints": {
                "anime": ["anilist", "tmdb"],
                "tv": ["tvdb", "tmdb"],
            },
            "tmdb_read_access_token": "test_token",
        }
    }

    chain = build_provider_chain(settings)

    assert isinstance(chain, ProviderChain)


def test_build_metadata_provider_from_env():
    """Test building provider with environment variables."""
    env = {
        "SWIRRL_TMDB_READ_ACCESS_TOKEN": "env_token",
        "SWIRRL_METADATA_LANGUAGE": "fr-FR",
    }

    settings = {
        "metadata": {
            "provider": "tmdb",
        }
    }

    provider = build_metadata_provider(settings, env=env)

    assert provider is not None


def test_build_provider_chain_all_providers_fail():
    """Test chain building when all providers fail to initialize."""
    settings = {
        "metadata": {
            "provider": "invalid1",
            "fallback_providers": ["invalid2", "invalid3"],
        }
    }

    chain = build_provider_chain(settings)

    # Should return empty chain
    assert isinstance(chain, ProviderChain)
    assert len(chain.providers) == 0


def test_provider_factory_caching():
    """Test that provider instances can be reused."""
    settings = {
        "metadata": {
            "provider": "tmdb",
            "tmdb_read_access_token": "test_token",
        }
    }

    provider1 = build_metadata_provider(settings)
    provider2 = build_metadata_provider(settings)

    # Should create new instances (no caching by default)
    assert provider1 is not provider2


def test_build_metadata_provider_language_override():
    """Test building provider with language override."""
    settings = {
        "metadata": {
            "provider": "tmdb",
            "tmdb_read_access_token": "test_token",
            "language": "en-US",
        }
    }

    config = MetadataRuntimeConfig(
        provider="tmdb",
        interactive_confirmation=True,
        cache_ttl_hours=168,
        language="fr-FR",  # Override
        tmdb_read_access_token="test_token",
        tvdb_api_key="",
        trakt_client_id="",
        trakt_client_secret="",
        trakt_access_token="",
        has_credentials=True,
        credential_source="settings",
        auth_mode="read_access_token",
    )

    provider = build_metadata_provider(settings, config=config)

    assert provider is not None
