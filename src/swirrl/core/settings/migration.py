from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from loguru import logger

from swirrl.core.paths import get_legacy_settings_path

from .normalize import (
    _deep_merge,  # pyright: ignore[reportPrivateUsage]  # Internal helper shared within settings package
)
from .schema import DEFAULT_SETTINGS


def _migrate_legacy_settings(data: dict[str, Any]) -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]  # Re-exported through package __init__
    migrated = deepcopy(data)

    modules = migrated.get("modules", {})
    if isinstance(modules, dict):
        legacy_metadata = modules.pop("metadata", None)
        if isinstance(legacy_metadata, dict):
            migrated.setdefault("metadata", {})
            migrated["metadata"] = _deep_merge(legacy_metadata, migrated["metadata"])

        legacy_setup = modules.pop("setup", None)
        if isinstance(legacy_setup, dict):
            migrated.setdefault("setup", {})
            migrated["setup"] = _deep_merge(legacy_setup, migrated["setup"])

    general = migrated.get("general")
    if isinstance(general, dict):
        for removed_key in ("path_resolution_mode", "export_json_reports", "dry_run_by_default"):
            general.pop(removed_key, None)

    metadata = migrated.get("metadata")
    if isinstance(metadata, dict):
        legacy_api_key = metadata.pop("tmdb_api_key", None)
        if legacy_api_key and not metadata.get("tmdb_read_access_token"):
            logger.warning(
                "Legacy 'metadata.tmdb_api_key' detected but no 'tmdb_read_access_token' is set. "
                "Swirrl requires a v4 read access token; obtain one at "
                "https://www.themoviedb.org/settings/api"
            )

    # Migrate old single-seedbox format → multi-seedbox list
    old_seedbox = migrated.get("seedbox", {})
    if isinstance(old_seedbox, dict) and "default_remote" in old_seedbox:
        old_remote = old_seedbox.get("default_remote", "")
        old_path = old_seedbox.get("remote_path", "/")
        if old_remote:
            migrated["seedbox"] = {
                "default": old_remote,
                "history_enabled": True,
                "seedboxes": [
                    {
                        "name": old_remote,
                        "rclone_remote": old_remote,
                        "remote_base_path": old_path or "/",
                        "bandwidth_limit": "",
                        "disk_check_enabled": True,
                        "min_free_gb": 5,
                        "post_upload_command": "",
                        "category_paths": {},
                    }
                ],
            }
        else:
            migrated["seedbox"] = {"default": "", "history_enabled": True, "seedboxes": []}

    migrated["schema_version"] = DEFAULT_SETTINGS["schema_version"]
    return migrated


def _migrate_from_json_to_yaml() -> dict[str, Any] | None:  # pyright: ignore[reportUnusedFunction]  # Re-exported through package __init__
    """Migrate settings from legacy JSON format to YAML if needed."""
    legacy_path = get_legacy_settings_path()
    if not legacy_path.exists():
        return None

    try:
        raw = legacy_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None
