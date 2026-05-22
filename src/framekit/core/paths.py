from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from platformdirs import user_cache_dir, user_config_dir

APP_NAME = "framekit"
APP_AUTHOR = "framekit"

SETTINGS_FILENAME = "framekit.yaml"
LEGACY_SETTINGS_FILENAME = "settings.json"
ENV_CONFIG_PATH = "FRAMEKIT_CONFIG"


def get_config_dir() -> Path:
    """User-level config directory (platformdirs).

    Retained for resources that should remain user-scoped (templates, vault,
    cache locks). The active settings file itself lives next to the project,
    not here — see :func:`get_settings_path`.
    """
    return Path(user_config_dir(APP_NAME, APP_AUTHOR))


def get_cache_dir() -> Path:
    """Return the cache dir."""
    return Path(user_cache_dir(APP_NAME, APP_AUTHOR))


def get_lock_dir() -> Path:
    """Return the lock dir."""
    return get_config_dir() / "locks"


def get_settings_path() -> Path:
    """Return the active ``framekit.yaml`` path.

    Resolution order:

    1. ``FRAMEKIT_CONFIG`` environment variable, when set and non-empty.
    2. ``framekit.yaml`` in the current working directory (created on first
       run if absent).

    The file is intentionally project-local so configuration travels with the
    media workspace. Sensitive tokens should either be stored in the vault
    (``security.enabled: true``) or supplied via environment variables.
    """
    override = os.environ.get(ENV_CONFIG_PATH, "").strip()
    if override:
        return Path(override).expanduser()
    return Path.cwd() / SETTINGS_FILENAME


def get_legacy_settings_path() -> Path:
    """Path to a legacy ``settings.json`` for one-shot migration.

    Looks next to the active YAML so an in-place migration finds the JSON if
    the user keeps both files in the same directory.
    """
    return get_settings_path().with_name(LEGACY_SETTINGS_FILENAME)


def get_presets_dir() -> Path:
    """Get the legacy presets directory in config.

    This is maintained for backward compatibility.
    New code should use get_project_presets_dir() or module-specific functions.
    """
    return get_config_dir() / "presets"


def get_project_presets_dir(base_dir: Path | None = None) -> Path:
    """Get the project-level Presets directory.

    Resolution order:
    1. ``base_dir / Presets`` when *base_dir* is given explicitly and exists.
    2. Package-bundled presets shipped inside ``framekit.presets``.
    3. ``CWD / Presets`` as a final fallback for development / user overrides.
    """
    if base_dir is not None:
        candidate = base_dir / "Presets"
        if candidate.is_dir():
            return candidate

    from framekit.presets import PRESETS_ROOT

    if PRESETS_ROOT.is_dir():
        return PRESETS_ROOT

    root = base_dir if base_dir is not None else Path.cwd()
    return root / "Presets"


def get_cleanmkv_presets_dir(base_dir: Path | None = None) -> Path:
    """Get the CleanMKV presets directory.

    Args:
        base_dir: Base directory to use. If None, uses current working directory.

    Returns:
        Path to Presets/CleanMKV/ directory.
    """
    return get_project_presets_dir(base_dir) / "CleanMKV"


def get_prez_presets_dir(base_dir: Path | None = None) -> Path:
    """Get the Prez presets directory.

    Args:
        base_dir: Base directory to use. If None, uses current working directory.

    Returns:
        Path to Presets/Prez/ directory.
    """
    return get_project_presets_dir(base_dir) / "Prez"


def get_pipeline_presets_dir(base_dir: Path | None = None) -> Path:
    """Get the Pipeline presets directory.

    Args:
        base_dir: Base directory to use. If None, uses current working directory.

    Returns:
        Path to Presets/Pipeline/ directory.
    """
    return get_project_presets_dir(base_dir) / "Pipeline"


def get_templates_dir() -> Path:
    """Return the templates dir."""
    return get_config_dir() / "templates"


def get_nfo_templates_dir() -> Path:
    """Return the nfo templates dir."""
    return get_templates_dir() / "nfo"


def get_metadata_cache_file() -> Path:
    """Return the metadata cache file."""
    return get_cache_dir() / "metadata_cache.json"


def get_metadata_choice_store_file() -> Path:
    """Return the metadata choice store file."""
    return get_cache_dir() / "metadata_choices.json"


def get_intelligent_cache_dir() -> Path:
    """Get the directory for intelligent cache system.

    Returns:
        Path to the cache directory for TMDb, MediaInfo, and release caches.
    """
    return get_cache_dir() / "intelligent"


def get_nfo_template_registry_file() -> Path:
    """Return the nfo template registry file."""
    return get_nfo_templates_dir() / "registry.json"


def get_user_templates_root() -> Path:
    """Return the user templates root."""
    return get_templates_dir()


def get_user_nfo_templates_dir() -> Path:
    """Return the user nfo templates dir."""
    return get_user_templates_root() / "nfo"


def get_project_nfo_templates_dir(base_dir: Path | None = None) -> Path:
    """Return the project nfo templates dir."""
    root = base_dir if base_dir is not None else Path.cwd()
    return root / "Templates" / "NFO"


def get_bundled_nfo_logos_dir() -> Path:
    """Return the directory of logos bundled with the package."""
    return Path(__file__).resolve().parent.parent / "templates" / "logos"


def get_user_nfo_logos_dir() -> Path:
    """Return the user nfo logos dir."""
    return get_user_templates_root() / "logos" / "nfo"


def get_nfo_logo_registry_file() -> Path:
    """Return the nfo logo registry file."""
    return get_user_nfo_logos_dir() / "registry.json"


def get_security_dir() -> Path:
    """Get the directory for security-related files.

    Returns:
        Path to the security directory for encryption keys and vault.
    """
    return get_config_dir() / "security"


def get_vault_path() -> Path:
    """Get the path to the encrypted vault file.

    Returns:
        Path to the vault.enc file.
    """
    return get_security_dir() / "vault.enc"


def get_master_key_path() -> Path:
    """Get the path to the master encryption key file (fallback storage).

    Returns:
        Path to the master.key file.
    """
    return get_security_dir() / "master.key"


class PathResolver:
    """Path resolver."""

    def __init__(self, settings: dict[str, Any]) -> None:
        self.settings = settings

    @staticmethod
    def _coerce_explicit_path(
        explicit_path: str | Path | tuple[str, ...] | list[str] | None,
    ) -> str | None:
        if explicit_path is None:
            return None

        if isinstance(explicit_path, Path):
            return str(explicit_path)

        if isinstance(explicit_path, str):
            cleaned = explicit_path.strip()
            return cleaned or None

        if isinstance(explicit_path, (tuple, list)):  # pyright: ignore[reportUnnecessaryIsInstance]  # Defensive runtime check; click can hand back either type
            cleaned = " ".join(str(part) for part in explicit_path if str(part).strip()).strip()
            return cleaned or None

        cleaned = str(explicit_path).strip()
        return cleaned or None

    def resolve_start_folder(
        self,
        module_name: str,
        explicit_path: str | Path | tuple[str, ...] | list[str] | None = None,
    ) -> Path:
        """Resolve start folder."""
        explicit = self._coerce_explicit_path(explicit_path)
        if explicit:
            return Path(explicit).expanduser().resolve()

        module_settings = self.settings.get("modules", {}).get(module_name, {})
        general_settings = self.settings.get("general", {})

        candidates = [
            module_settings.get("default_folder", ""),
            general_settings.get("default_folder", ""),
            str(Path.cwd()),
        ]

        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return Path(candidate).expanduser().resolve()

        return Path.cwd().resolve()
