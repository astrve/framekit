from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from filelock import BaseFileLock, FileLock

from ouro.core.exceptions import SettingsError
from ouro.core.paths import get_settings_path

from .migration import (
    _migrate_from_json_to_yaml,  # pyright: ignore[reportPrivateUsage]  # Internal helper used across settings sub-modules
    _migrate_legacy_settings,  # pyright: ignore[reportPrivateUsage]  # Internal helper used across settings sub-modules
)
from .normalize import (
    _deep_merge,  # pyright: ignore[reportPrivateUsage]  # Internal helper used across settings sub-modules
    _get_nested,  # pyright: ignore[reportPrivateUsage]  # Internal helper used across settings sub-modules
    _set_nested,  # pyright: ignore[reportPrivateUsage]  # Internal helper used across settings sub-modules
    normalize_settings,
    validate_settings,
)
from .schema import DEFAULT_SETTINGS
from .yaml_io import (
    _generate_yaml_with_comments,  # pyright: ignore[reportPrivateUsage]  # Internal helper used across settings sub-modules
    update_preserving_comments,
)

MODULE_FILE_TARGETS: dict[str, tuple[str, ...]] = {
    "upload": ("upload",),
    "seedbox": ("seedbox",),
    "batch": ("modules", "batch"),
}


class SettingsStore:
    """Low-level persistence for ``ouro.yaml``.

    Reads/writes the active project YAML, applies schema migrations on the
    fly, and locks the file with ``filelock`` so concurrent ``ouro``
    invocations do not corrupt the document.

    The store has two YAML write paths:

    * **First write** (file does not exist): uses the hand-rolled emitter in
      :mod:`ouro.core.settings.yaml_io` which adds section comments
      throughout the file. The output matches the layout
      shipped in ``ouro.example.yaml`` so a fresh install reads exactly
      like the docs.
    * **Subsequent writes**: uses :func:`update_preserving_comments`, which
      goes through ruamel.yaml in round-trip mode. Any comments the user
      added between sections survive every settings update. Keys with new
      values are replaced in place; the document order is preserved.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or get_settings_path()
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    def _lock(self) -> BaseFileLock:
        return FileLock(str(self.lock_path))

    def ensure_exists(self) -> None:
        """Ensure exists."""
        with self._lock():
            if self.path.exists():
                return

            # Check for legacy JSON settings and migrate
            legacy_data = _migrate_from_json_to_yaml()
            if legacy_data:
                # Migrate from JSON
                migrated = _migrate_legacy_settings(legacy_data)
                normalized = normalize_settings(_deep_merge(DEFAULT_SETTINGS, migrated))
                validate_settings(normalized)
                data_to_write = normalized
            else:
                # Create new YAML with defaults
                data_to_write = DEFAULT_SETTINGS

            self.path.parent.mkdir(parents=True, exist_ok=True)
            yaml_content = _generate_yaml_with_comments(data_to_write)
            self.path.write_text(yaml_content, encoding="utf-8")

    def load(self) -> dict[str, Any]:
        """Handle load."""
        self.ensure_exists()

        with self._lock():
            try:
                raw = self.path.read_text(encoding="utf-8")
                data = yaml.safe_load(raw)
            except yaml.YAMLError as exc:
                raise SettingsError(f"Invalid YAML in settings file: {self.path}") from exc
            except OSError as exc:
                raise SettingsError(f"Cannot read settings file: {self.path}") from exc

        if not isinstance(data, dict):
            raise SettingsError("Settings file must contain a YAML object.")

        migrated = self._merge_module_files(_migrate_legacy_settings(data))
        normalized = normalize_settings(_deep_merge(DEFAULT_SETTINGS, migrated))
        validate_settings(normalized)
        return normalized

    def save(self, data: dict[str, Any]) -> None:
        """Handle save."""
        normalized = normalize_settings(
            _deep_merge(DEFAULT_SETTINGS, _migrate_legacy_settings(data))
        )
        validate_settings(normalized)

        with self._lock():
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                if self.path.exists():
                    # Round-trip via ruamel: keep user comments + key order.
                    update_preserving_comments(self.path, normalized)
                else:
                    # First write: lay down the localised template so the
                    # user discovers the schema with annotated headers.
                    self.path.write_text(
                        _generate_yaml_with_comments(normalized),
                        encoding="utf-8",
                    )
            except OSError as exc:
                raise SettingsError(f"Cannot write settings file: {self.path}") from exc

    def get(self, path: str) -> Any:
        """Handle get."""
        data = self.load()
        return _get_nested(data, path)

    def set(self, path: str, value: Any) -> dict[str, Any]:
        """Handle set."""
        data = self.load()
        _set_nested(data, path, value)
        self.save(data)
        return data

    def reset(self, path: str) -> dict[str, Any]:
        """Handle reset."""
        data = self.load()
        default_value = _get_nested(DEFAULT_SETTINGS, path)
        _set_nested(data, path, deepcopy(default_value))
        self.save(data)
        return data

    def module_config_dir(self) -> Path:
        """Return optional per-module config directory for the active settings file."""
        return self.path.parent / "modules"

    def _merge_module_files(self, data: dict[str, Any]) -> dict[str, Any]:
        modules_dir = self.module_config_dir()
        if not modules_dir.exists():
            return data

        merged = deepcopy(data)
        for module_file in sorted(modules_dir.glob("*.yaml")):
            module_name = module_file.stem
            try:
                loaded = yaml.safe_load(module_file.read_text(encoding="utf-8"))
            except yaml.YAMLError as exc:
                raise SettingsError(f"Invalid YAML in module config: {module_file}") from exc
            except OSError as exc:
                raise SettingsError(f"Cannot read module config: {module_file}") from exc

            if loaded is None:
                loaded = {}
            if not isinstance(loaded, dict):
                raise SettingsError(f"Module config must contain a YAML object: {module_file}")

            target_path = MODULE_FILE_TARGETS.get(module_name, ("modules", module_name))
            current: dict[str, Any] = merged
            for key in target_path[:-1]:
                node = current.setdefault(key, {})
                if not isinstance(node, dict):
                    node = {}
                    current[key] = node
                current = node
            leaf = target_path[-1]
            existing = current.get(leaf, {})
            if not isinstance(existing, dict):
                existing = {}
            current[leaf] = _deep_merge(existing, loaded)
        return merged
