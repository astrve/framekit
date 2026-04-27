from __future__ import annotations

from collections.abc import Mapping

from framekit.modules.metadata.config import MetadataRuntimeConfig, resolve_metadata_config
from framekit.modules.metadata.tmdb_provider import TMDbProvider


def build_metadata_provider(
    settings: dict | None = None,
    *,
    config: MetadataRuntimeConfig | None = None,
    env: Mapping[str, str] | None = None,
):
    """Build the configured metadata provider.

    ``config`` lets callers reuse an already-resolved runtime config. This avoids
    resolving settings once with a custom env and then silently rebuilding the
    provider from process env only.
    """

    if config is None:
        config = resolve_metadata_config(settings or {}, env=env)

    if config.provider == "tmdb":
        return TMDbProvider(
            api_key=config.tmdb_api_key,
            read_access_token=config.tmdb_read_access_token,
            language=config.language,
        )

    raise ValueError(f"Unsupported metadata provider: {config.provider}")
