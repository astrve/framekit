from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_METADATA_SETTINGS = {
    "provider": "tmdb",
    "interactive_confirmation": True,
    "cache_ttl_hours": 168,
    "language": "en-US",
    "tmdb_api_key": "",
    "tmdb_read_access_token": "",
}


def mask_secret(value: str) -> str:
    if not value:
        return "-"

    if len(value) <= 4:
        return "********"

    return f"********{value[-4:]}"


def has_wrapping_quotes(value: str) -> bool:
    return len(value) >= 2 and (
        (value.startswith('"') and value.endswith('"'))
        or (value.startswith("'") and value.endswith("'"))
    )


def normalize_secret_input(value: str) -> str:
    value = (value or "").strip()
    if has_wrapping_quotes(value):
        return value[1:-1].strip()
    return value


def looks_like_tmdb_api_key(value: str) -> bool:
    raw = normalize_secret_input(value)
    if not raw:
        return False

    # Heuristic: API keys are usually short-ish and do not look like JWT tokens.
    return (
        "." not in raw and 24 <= len(raw) <= 40 and raw.replace("-", "").replace("_", "").isalnum()
    )


def looks_like_tmdb_read_access_token(value: str) -> bool:
    raw = normalize_secret_input(value)
    if not raw:
        return False

    # Heuristic: read access tokens are long and usually JWT-like.
    return raw.count(".") >= 2 and len(raw) >= 60


@dataclass(slots=True)
class MetadataRuntimeConfig:
    provider: str
    interactive_confirmation: bool
    cache_ttl_hours: int
    language: str

    tmdb_api_key: str
    tmdb_read_access_token: str

    has_credentials: bool
    credential_source: str
    auth_mode: str


def resolve_metadata_config(
    settings: dict,
    env: Mapping[str, str] | None = None,
    *,
    language_override: str | None = None,
) -> MetadataRuntimeConfig:
    if env is None:
        env = os.environ

    raw = {
        **DEFAULT_METADATA_SETTINGS,
        **(settings.get("metadata") or {}),
    }

    env_api_key = env.get("FRAMEKIT_TMDB_API_KEY", "").strip()
    env_read_access_token = env.get("FRAMEKIT_TMDB_READ_ACCESS_TOKEN", "").strip()
    env_language = env.get("FRAMEKIT_METADATA_LANGUAGE", "").strip()

    file_api_key = str(raw.get("tmdb_api_key", "") or "").strip()
    file_read_access_token = str(raw.get("tmdb_read_access_token", "") or "").strip()

    tmdb_api_key = env_api_key or file_api_key
    tmdb_read_access_token = env_read_access_token or file_read_access_token

    if env_read_access_token or env_api_key:
        credential_source = "environment"
    elif file_read_access_token or file_api_key:
        credential_source = "settings"
    else:
        credential_source = "missing"

    if tmdb_read_access_token:
        auth_mode = "read_access_token"
    elif tmdb_api_key:
        auth_mode = "api_key"
    else:
        auth_mode = "missing"

    return MetadataRuntimeConfig(
        provider=str(raw.get("provider", "tmdb")).strip().lower(),
        interactive_confirmation=bool(raw.get("interactive_confirmation", True)),
        cache_ttl_hours=int(raw.get("cache_ttl_hours", 168)),
        language=(
            language_override
            or env_language
            or str(raw.get("language", "en-US")).strip()
            or "en-US"
        ),
        tmdb_api_key=tmdb_api_key,
        tmdb_read_access_token=tmdb_read_access_token,
        has_credentials=bool(tmdb_api_key or tmdb_read_access_token),
        credential_source=credential_source,
        auth_mode=auth_mode,
    )
