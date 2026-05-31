"""Configuration profile management.

Profiles are named snapshots of selected settings that can be
switched quickly. They store overrides (not full copies) so they
stay compact and always layer on top of the base swirrl.yaml.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

from swirrl.core.paths import get_config_dir

PROFILES_DIR_NAME = "profiles"


def get_profiles_dir() -> Path:
    """Return the profiles directory, creating it if needed."""
    profiles_dir = get_config_dir() / PROFILES_DIR_NAME
    profiles_dir.mkdir(parents=True, exist_ok=True)
    return profiles_dir


def list_profiles() -> list[str]:
    """List all available profile names."""
    profiles_dir = get_profiles_dir()
    return sorted(
        p.stem for p in profiles_dir.glob("*.json") if p.is_file() and not p.name.startswith(".")
    )


def load_profile(name: str) -> dict[str, Any]:
    """Load a profile by name.

    Returns:
        Dict of settings overrides for this profile.

    Raises:
        FileNotFoundError: If profile doesn't exist.
    """
    profile_path = get_profiles_dir() / f"{name}.json"
    if not profile_path.exists():
        raise FileNotFoundError(f"Profile not found: {name}")

    data = json.loads(profile_path.read_text(encoding="utf-8"))
    logger.debug(f"Loaded profile: {name}")
    return data


def save_profile(name: str, overrides: dict[str, Any], *, description: str = "") -> Path:
    """Save a profile.

    Args:
        name: Profile name (alphanumeric + hyphens)
        overrides: Settings overrides dict
        description: Human-readable description

    Returns:
        Path to saved profile file.
    """
    import re

    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$", name):
        raise ValueError(
            f"Invalid profile name: {name}. Use alphanumeric characters, hyphens, and underscores."
        )

    profile_path = get_profiles_dir() / f"{name}.json"
    profile_data = {
        "name": name,
        "description": description,
        "overrides": overrides,
    }

    profile_path.write_text(
        json.dumps(profile_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(f"Saved profile: {name} -> {profile_path}")
    return profile_path


def delete_profile(name: str) -> bool:
    """Delete a profile by name.

    Returns:
        True if deleted, False if not found.
    """
    profile_path = get_profiles_dir() / f"{name}.json"
    if not profile_path.exists():
        return False
    profile_path.unlink()
    logger.info(f"Deleted profile: {name}")
    return True


def get_active_profile() -> str | None:
    """Get the currently active profile name, if any."""
    marker = get_profiles_dir() / ".active"
    if marker.exists():
        name = marker.read_text(encoding="utf-8").strip()
        if name and (get_profiles_dir() / f"{name}.json").exists():
            return name
    return None


def set_active_profile(name: str | None) -> None:
    """Set or clear the active profile."""
    marker = get_profiles_dir() / ".active"
    if name is None:
        if marker.exists():
            marker.unlink()
        logger.info("Cleared active profile")
        return

    # Verify profile exists
    if not (get_profiles_dir() / f"{name}.json").exists():
        raise FileNotFoundError(f"Profile not found: {name}")

    marker.write_text(name, encoding="utf-8")
    logger.info(f"Active profile set to: {name}")


def apply_profile_overrides(base_settings: dict[str, Any], profile_name: str) -> dict[str, Any]:
    """Apply profile overrides on top of base settings.

    Returns a new dict (does not mutate base_settings).
    """
    from swirrl.core.settings.normalize import _deep_merge

    profile_data = load_profile(profile_name)
    overrides = profile_data.get("overrides", {})

    if not overrides:
        return base_settings.copy()

    return _deep_merge(base_settings, overrides)
