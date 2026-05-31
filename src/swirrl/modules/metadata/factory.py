from __future__ import annotations

from collections.abc import Callable, Mapping

from loguru import logger

from swirrl.modules.metadata.base import MetadataProvider
from swirrl.modules.metadata.chain import ProviderChain
from swirrl.modules.metadata.config import MetadataRuntimeConfig, resolve_metadata_config
from swirrl.modules.metadata.providers.anilist import AniListProvider
from swirrl.modules.metadata.providers.trakt import TraktProvider
from swirrl.modules.metadata.providers.tvdb import TVDBProvider
from swirrl.modules.metadata.tmdb_provider import TMDbProvider

# Provider registry: maps provider name to factory function
_PROVIDER_REGISTRY: dict[str, Callable[[dict, MetadataRuntimeConfig], MetadataProvider]] = {}


def register_provider(
    name: str,
    factory: Callable[[dict, MetadataRuntimeConfig], MetadataProvider] | type[MetadataProvider],
) -> None:
    """Register a metadata provider.

    Args:
        name: Provider name (e.g., "tmdb", "tvdb")
        factory: Factory function or provider class
    """
    if isinstance(factory, type):
        # If it's a class, wrap it in a factory function
        def class_factory(settings: dict, config: MetadataRuntimeConfig) -> MetadataProvider:
            return factory()  # type: ignore

        _PROVIDER_REGISTRY[name] = class_factory
    else:
        _PROVIDER_REGISTRY[name] = factory


def get_available_providers() -> list[str]:
    """Get list of available provider names.

    Returns:
        List of registered provider names
    """
    return list(_PROVIDER_REGISTRY.keys())


def _build_tmdb_provider(settings: dict, config: MetadataRuntimeConfig) -> TMDbProvider:
    """Build TMDb provider.

    Args:
        settings: Full settings dictionary
        config: Resolved metadata configuration

    Returns:
        Configured TMDb provider
    """
    cache_config = settings.get("cache", {})

    return TMDbProvider(
        read_access_token=config.tmdb_read_access_token,
        language=config.language,
        cache_config=cache_config,
    )


def _build_tvdb_provider(settings: dict, config: MetadataRuntimeConfig) -> TVDBProvider:
    """Build TVDB provider.

    Args:
        settings: Full settings dictionary
        config: Resolved metadata configuration

    Returns:
        Configured TVDB provider
    """
    if not config.tvdb_api_key:
        raise ValueError(
            "TVDB API key is missing. Set metadata.tvdb_api_key "
            "in swirrl.yaml or export SWIRRL_TVDB_API_KEY."
        )

    return TVDBProvider(
        api_key=config.tvdb_api_key,
    )


def _build_anilist_provider(settings: dict, config: MetadataRuntimeConfig) -> AniListProvider:
    """Build AniList provider.

    Args:
        settings: Full settings dictionary
        config: Resolved metadata configuration

    Returns:
        Configured AniList provider
    """
    return AniListProvider()


def _build_trakt_provider(settings: dict, config: MetadataRuntimeConfig) -> TraktProvider:
    """Build Trakt provider.

    Args:
        settings: Full settings dictionary
        config: Resolved metadata configuration

    Returns:
        Configured Trakt provider
    """
    if not config.trakt_client_id:
        raise ValueError(
            "Trakt client ID is missing. Set metadata.trakt_client_id "
            "in swirrl.yaml or export SWIRRL_TRAKT_CLIENT_ID."
        )

    return TraktProvider(
        client_id=config.trakt_client_id,
        client_secret=config.trakt_client_secret,
        access_token=config.trakt_access_token,
    )


# Register built-in providers
register_provider("tmdb", _build_tmdb_provider)
register_provider("tvdb", _build_tvdb_provider)
register_provider("anilist", _build_anilist_provider)
register_provider("trakt", _build_trakt_provider)


def build_metadata_provider(
    settings: dict | None = None,
    *,
    provider_name: str | None = None,
    config: MetadataRuntimeConfig | None = None,
    env: Mapping[str, str] | None = None,
) -> MetadataProvider:
    """Build a metadata provider by name.

    Args:
        settings: Settings dictionary
        provider_name: Explicit provider name (overrides config)
        config: Pre-resolved runtime config (avoids re-resolution)
        env: Environment variables for config resolution

    Returns:
        Configured metadata provider

    Raises:
        ValueError: If provider is unknown or not registered
    """
    if config is None:
        config = resolve_metadata_config(settings or {}, env=env)

    name = provider_name or config.provider

    if name not in _PROVIDER_REGISTRY:
        raise ValueError(f"Unknown provider: {name}")

    factory = _PROVIDER_REGISTRY[name]
    return factory(settings or {}, config)


def build_provider_chain(
    settings: dict | None = None,
    *,
    config: MetadataRuntimeConfig | None = None,
    env: Mapping[str, str] | None = None,
) -> ProviderChain:
    """Build a provider chain with fallback support.

    Creates a chain of providers based on configuration. The primary provider
    is tried first, followed by fallback providers in order.

    Args:
        settings: Settings dictionary
        config: Pre-resolved runtime config
        env: Environment variables for config resolution

    Returns:
        Provider chain with configured providers
    """
    if config is None:
        config = resolve_metadata_config(settings or {}, env=env)

    settings = settings or {}
    providers: list[MetadataProvider] = []

    # Build primary provider
    try:
        primary = build_metadata_provider(
            settings,
            provider_name=config.provider,
            config=config,
            env=env,
        )
        providers.append(primary)
        logger.debug(f"Built primary provider: {config.provider}")
    except Exception as e:
        logger.warning(f"Failed to build primary provider {config.provider}: {e}")

    # Build fallback providers
    fallback_providers = settings.get("metadata", {}).get("fallback_providers", [])
    for name in fallback_providers:
        try:
            provider = build_metadata_provider(
                settings,
                provider_name=name,
                config=config,
                env=env,
            )
            providers.append(provider)
            logger.debug(f"Built fallback provider: {name}")
        except Exception as e:
            logger.warning(f"Failed to build fallback provider {name}: {e}")

    return ProviderChain(providers=providers)


def build_provider_chain_for_content(
    settings: dict | None = None,
    *,
    content_type: str | None = None,
    config: MetadataRuntimeConfig | None = None,
    env: Mapping[str, str] | None = None,
) -> ProviderChain:
    """Build a provider chain optimized for a specific content type.

    Uses ``metadata.content_type_hints`` to determine provider order.
    Falls back to the standard chain when no hint matches.

    Args:
        settings: Settings dictionary
        content_type: Content type hint (e.g., "anime", "tv", "movie")
        config: Pre-resolved runtime config
        env: Environment variables for config resolution

    Returns:
        Provider chain ordered by content type preference
    """
    settings = settings or {}
    if config is None:
        config = resolve_metadata_config(settings, env=env)

    hints: dict[str, list[str]] = settings.get("metadata", {}).get("content_type_hints", {})
    preferred_order: list[str] | None = hints.get(content_type) if content_type else None

    if not preferred_order:
        return build_provider_chain(settings, config=config, env=env)

    providers: list[MetadataProvider] = []
    for name in preferred_order:
        try:
            provider = build_metadata_provider(settings, provider_name=name, config=config, env=env)
            providers.append(provider)
        except Exception as e:
            logger.debug(f"Skipping provider {name} for content type {content_type}: {e}")

    if not providers:
        return build_provider_chain(settings, config=config, env=env)

    return ProviderChain(providers=providers)
