from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_METADATA_SETTINGS = {
    "provider": "tmdb",
    "interactive_confirmation": True,
    "cache_ttl_hours": 168,
    "language": "en-US",
    "tmdb_read_access_token": "",  # nosec B105
    "tvdb_api_key": "",
    "trakt_client_id": "",
    "trakt_client_secret": "",  # nosec B105
    "trakt_access_token": "",  # nosec B105
}


def mask_secret(value: str) -> str:
    """Handle mask secret."""
    if not value:
        return "-"

    if len(value) <= 4:
        return "********"

    return f"********{value[-4:]}"


def has_wrapping_quotes(value: str) -> bool:
    """Return ``True`` if has wrapping quotes."""
    return len(value) >= 2 and (
        (value.startswith('"') and value.endswith('"'))
        or (value.startswith("'") and value.endswith("'"))
    )


def normalize_secret_input(value: str) -> str:
    """Normalise secret input."""
    value = (value or "").strip()
    if has_wrapping_quotes(value):
        return value[1:-1].strip()
    return value


def looks_like_tmdb_read_access_token(value: str) -> bool:
    """Handle looks like tmdb read access token."""
    raw = normalize_secret_input(value)
    if not raw:
        return False

    # Heuristic: TMDB v4 read access tokens are JWT-shaped (three dot-separated parts).
    return raw.count(".") >= 2 and len(raw) >= 60


@dataclass(slots=True)
class MetadataRuntimeConfig:
    """Configuration for metadata runtime."""

    provider: str
    interactive_confirmation: bool
    cache_ttl_hours: int
    language: str

    tmdb_read_access_token: str
    tvdb_api_key: str
    trakt_client_id: str
    trakt_client_secret: str
    trakt_access_token: str

    has_credentials: bool
    credential_source: str
    auth_mode: str


def _merged_metadata_settings(settings: dict) -> dict:
    return {
        **DEFAULT_METADATA_SETTINGS,
        **(settings.get("metadata") or {}),
    }


def _env_metadata_values(env: Mapping[str, str]) -> dict[str, str]:
    return {
        "tmdb_read_access_token": env.get("FRAMEKIT_TMDB_READ_ACCESS_TOKEN", "").strip(),
        "tvdb_api_key": env.get("FRAMEKIT_TVDB_API_KEY", "").strip(),
        "trakt_client_id": env.get("FRAMEKIT_TRAKT_CLIENT_ID", "").strip(),
        "trakt_client_secret": env.get("FRAMEKIT_TRAKT_CLIENT_SECRET", "").strip(),
        "trakt_access_token": env.get("FRAMEKIT_TRAKT_ACCESS_TOKEN", "").strip(),
        "language": env.get("FRAMEKIT_METADATA_LANGUAGE", "").strip(),
    }


def _file_metadata_values(raw: dict) -> dict[str, str]:
    return {
        "tmdb_read_access_token": str(raw.get("tmdb_read_access_token", "") or "").strip(),
        "tvdb_api_key": str(raw.get("tvdb_api_key", "") or "").strip(),
        "trakt_client_id": str(raw.get("trakt_client_id", "") or "").strip(),
        "trakt_client_secret": str(raw.get("trakt_client_secret", "") or "").strip(),
        "trakt_access_token": str(raw.get("trakt_access_token", "") or "").strip(),
    }


def _resolve_tmdb_secret(value: str) -> str:
    if value != "<encrypted>":  # nosec B105
        return value
    try:
        from framekit.core.settings import Settings

        settings_obj = Settings()
        resolved = settings_obj.get_tmdb_token()
        if resolved:
            return resolved
        from loguru import logger

        logger.warning(
            "TMDB token is encrypted but vault returned empty value. "
            "Run 'fk settings security set-token' to configure the token."
        )
    except Exception as exc:
        from loguru import logger

        logger.error(f"Failed to decrypt TMDB token from vault: {exc}")
        logger.warning(
            "TMDB token decryption failed. Run 'fk settings security set-token' to "
            "reconfigure, or 'fk settings security status' to check vault status."
        )
    return ""  # nosec B105


def _resolve_tvdb_secret(value: str) -> str:
    if value != "<encrypted>":
        return value
    from loguru import logger

    logger.warning(
        "TVDB API key encryption not yet implemented. "
        "Please provide the key directly in framekit.yaml or via FRAMEKIT_TVDB_API_KEY environment variable."
    )
    return ""


def _resolve_file_secrets(values: dict[str, str]) -> dict[str, str]:
    values = dict(values)
    values["tmdb_read_access_token"] = _resolve_tmdb_secret(values["tmdb_read_access_token"])
    values["tvdb_api_key"] = _resolve_tvdb_secret(values["tvdb_api_key"])
    return values


def _credential_source(env_values: dict[str, str], file_values: dict[str, str]) -> str:
    if any(
        env_values[key] for key in ("tmdb_read_access_token", "tvdb_api_key", "trakt_client_id")
    ):
        return "environment"
    if any(
        file_values[key] for key in ("tmdb_read_access_token", "tvdb_api_key", "trakt_client_id")
    ):
        return "settings"
    return "missing"


def _effective_language(
    *, language_override: str | None, env_values: dict[str, str], raw: dict
) -> str:
    return (
        language_override
        or env_values["language"]
        or str(raw.get("language", "en-US")).strip()
        or "en-US"
    )


def resolve_metadata_config(
    settings: dict,
    env: Mapping[str, str] | None = None,
    *,
    language_override: str | None = None,
) -> MetadataRuntimeConfig:
    """Resolve metadata config."""
    if env is None:
        env = os.environ

    raw = _merged_metadata_settings(settings)
    env_values = _env_metadata_values(env)
    file_values = _resolve_file_secrets(_file_metadata_values(raw))

    tmdb_read_access_token = (
        env_values["tmdb_read_access_token"] or file_values["tmdb_read_access_token"]
    )
    tvdb_api_key = env_values["tvdb_api_key"] or file_values["tvdb_api_key"]
    trakt_client_id = env_values["trakt_client_id"] or file_values["trakt_client_id"]
    trakt_client_secret = env_values["trakt_client_secret"] or file_values["trakt_client_secret"]
    trakt_access_token = env_values["trakt_access_token"] or file_values["trakt_access_token"]
    credential_source = _credential_source(env_values, file_values)
    auth_mode = "read_access_token" if tmdb_read_access_token else "missing"

    return MetadataRuntimeConfig(
        provider=str(raw.get("provider", "tmdb")).strip().lower(),
        interactive_confirmation=bool(raw.get("interactive_confirmation", True)),
        cache_ttl_hours=int(raw.get("cache_ttl_hours", 168)),
        language=_effective_language(
            language_override=language_override, env_values=env_values, raw=raw
        ),
        tmdb_read_access_token=tmdb_read_access_token,
        tvdb_api_key=tvdb_api_key,
        trakt_client_id=trakt_client_id,
        trakt_client_secret=trakt_client_secret,
        trakt_access_token=trakt_access_token,
        has_credentials=bool(tmdb_read_access_token or tvdb_api_key or trakt_client_id),
        credential_source=credential_source,
        auth_mode=auth_mode,
    )
