from __future__ import annotations

from pathlib import Path
from typing import Any

from platformdirs import user_cache_dir, user_config_dir

APP_NAME = "framekit"
APP_AUTHOR = "framekit"


def get_config_dir() -> Path:
    return Path(user_config_dir(APP_NAME, APP_AUTHOR))


def get_cache_dir() -> Path:
    return Path(user_cache_dir(APP_NAME, APP_AUTHOR))


def get_lock_dir() -> Path:
    return get_config_dir() / "locks"


def get_settings_path() -> Path:
    return get_config_dir() / "settings.json"


def get_presets_dir() -> Path:
    return get_config_dir() / "presets"


def get_templates_dir() -> Path:
    return get_config_dir() / "templates"


def get_nfo_templates_dir() -> Path:
    return get_templates_dir() / "nfo"


def get_metadata_cache_file() -> Path:
    return get_cache_dir() / "metadata_cache.json"


def get_metadata_choice_store_file() -> Path:
    return get_cache_dir() / "metadata_choices.json"


def get_nfo_template_registry_file() -> Path:
    return get_nfo_templates_dir() / "registry.json"


def get_user_templates_root() -> Path:
    return get_templates_dir()


def get_user_nfo_templates_dir() -> Path:
    return get_user_templates_root() / "nfo"


def get_project_nfo_templates_dir(base_dir: Path | None = None) -> Path:
    root = base_dir if base_dir is not None else Path.cwd()
    return root / "Templates" / "NFO"


def get_user_nfo_logos_dir() -> Path:
    return get_user_templates_root() / "logos" / "nfo"


def get_nfo_logo_registry_file() -> Path:
    return get_user_nfo_logos_dir() / "registry.json"


class PathResolver:
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

        if isinstance(explicit_path, (tuple, list)):
            cleaned = " ".join(str(part) for part in explicit_path if str(part).strip()).strip()
            return cleaned or None

        cleaned = str(explicit_path).strip()
        return cleaned or None

    def resolve_start_folder(
        self,
        module_name: str,
        explicit_path: str | Path | tuple[str, ...] | list[str] | None = None,
    ) -> Path:
        explicit = self._coerce_explicit_path(explicit_path)
        if explicit:
            return Path(explicit).expanduser().resolve()

        module_settings = self.settings.get("modules", {}).get(module_name, {})
        general_settings = self.settings.get("general", {})

        candidates = [
            module_settings.get("last_folder", ""),
            module_settings.get("default_folder", ""),
            general_settings.get("default_folder", ""),
            str(Path.cwd()),
        ]

        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return Path(candidate).expanduser().resolve()

        return Path.cwd().resolve()
