"""Settings package facade.

This package was split out of the former ``ouro.core.settings`` module to
keep each concern (schema, normalization, migration, YAML emission, store,
high-level vault integration) in its own file. Every public symbol that used
to live in the old single-file module is re-exported here so existing
``from ouro.core.settings import X`` imports keep working unchanged.
"""

from __future__ import annotations

# Re-export private helpers from sub-modules so the package facade keeps the
# same surface as the former single-file module. The leading underscore signals
# "internal to ouro", not "private to this package", and these re-exports
# are deliberate; suppress reportPrivateUsage at the import-level.
from .high_level import Settings
from .migration import (
    _migrate_from_json_to_yaml,  # pyright: ignore[reportPrivateUsage]  # Re-export
    _migrate_legacy_settings,  # pyright: ignore[reportPrivateUsage]  # Re-export
)
from .normalize import (
    _as_bool,  # pyright: ignore[reportPrivateUsage]  # Re-export
    _as_int,  # pyright: ignore[reportPrivateUsage]  # Re-export
    _deep_merge,  # pyright: ignore[reportPrivateUsage]  # Re-export
    _get_nested,  # pyright: ignore[reportPrivateUsage]  # Re-export
    _is_secret_key,  # pyright: ignore[reportPrivateUsage]  # Re-export
    _set_nested,  # pyright: ignore[reportPrivateUsage]  # Re-export
    _split_key_path,  # pyright: ignore[reportPrivateUsage]  # Re-export
    is_valid_metadata_language,
    metadata_language_for_nfo_locale,
    normalize_metadata_language,
    normalize_nfo_locale,
    normalize_settings,
    normalize_ui_locale,
    redact_settings,
    resolve_nfo_locale,
    validate_settings,
)
from .schema import (
    DEFAULT_METADATA_LANGUAGE,
    DEFAULT_NFO_LOCALE,
    DEFAULT_SETTINGS,
    DEFAULT_UI_LOCALE,
    ENCRYPTED_PLACEHOLDER,
    METADATA_LANGUAGE_RE,
    NFO_LOCALE_TO_METADATA_LANGUAGE,
    SECRET_KEY_PARTS,
    SETTINGS_SCHEMA_VERSION,
    SUPPORTED_NFO_LOCALES,
    SUPPORTED_UI_LOCALES,
)
from .store import SettingsStore
from .yaml_io import (
    _generate_yaml_with_comments,  # pyright: ignore[reportPrivateUsage]  # Re-export
    _yaml_quote,  # pyright: ignore[reportPrivateUsage]  # Re-export
)

__all__ = [
    # Schema / constants
    "SETTINGS_SCHEMA_VERSION",
    "ENCRYPTED_PLACEHOLDER",
    "SUPPORTED_UI_LOCALES",
    "SUPPORTED_NFO_LOCALES",
    "NFO_LOCALE_TO_METADATA_LANGUAGE",
    "DEFAULT_UI_LOCALE",
    "DEFAULT_NFO_LOCALE",
    "DEFAULT_METADATA_LANGUAGE",
    "METADATA_LANGUAGE_RE",
    "SECRET_KEY_PARTS",
    "DEFAULT_SETTINGS",
    # Normalize / validate / locale helpers
    "normalize_settings",
    "validate_settings",
    "redact_settings",
    "normalize_ui_locale",
    "normalize_nfo_locale",
    "resolve_nfo_locale",
    "metadata_language_for_nfo_locale",
    "is_valid_metadata_language",
    "normalize_metadata_language",
    "_deep_merge",
    "_get_nested",
    "_set_nested",
    "_split_key_path",
    "_is_secret_key",
    "_as_bool",
    "_as_int",
    # Migration
    "_migrate_legacy_settings",
    "_migrate_from_json_to_yaml",
    # YAML I/O
    "_yaml_quote",
    "_generate_yaml_with_comments",
    # Store / high-level
    "SettingsStore",
    "Settings",
]
