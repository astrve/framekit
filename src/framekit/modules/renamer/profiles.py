from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml

from framekit.core.paths import get_config_dir


@dataclass(frozen=True, slots=True)
class RenamerProfile:
    """Configurable renamer behavior profile."""
    name: str
    default_language_tag: str = "MULTI.VFF"
    language_aliases: dict[str, str] = field(default_factory=dict)
    junk_terms: tuple[str, ...] = ()
    quality_aliases: dict[str, str] = field(default_factory=dict)
    source_aliases: dict[str, str] = field(default_factory=dict)
    insert_missing_resolution: bool = True
    language_insertion: str = "after_episode_or_start"


BUILTIN_PROFILES: dict[str, RenamerProfile] = {
    "fr_tracker": RenamerProfile(
        name="fr_tracker",
        default_language_tag="MULTI.VFF",
        language_aliases={
            "TRUEFRENCH": "VFF",
            "FRENCH": "VFF",
            "VFF": "VFF",
            "VFQ": "VFQ",
            "VOSTFR": "VOSTFR",
        },
        junk_terms=("DUAL", "INTERNAL"),
        quality_aliases={"HD": "auto_resolution"},
        source_aliases={"WEB-DL": "WEB", "WEBDL": "WEB"},
    ),
    "international": RenamerProfile(
        name="international",
        default_language_tag="MULTI",
        language_aliases={
            "TRUEFRENCH": "FR",
            "FRENCH": "FR",
            "ENGLISH": "EN",
            "SPANISH": "ES",
        },
        junk_terms=("DUAL", "INTERNAL"),
        quality_aliases={"HD": "auto_resolution"},
        source_aliases={"WEB-DL": "WEB", "WEBDL": "WEB"},
    ),
    "no_language": RenamerProfile(
        name="no_language",
        default_language_tag="",
        language_aliases={},
        junk_terms=("DUAL", "INTERNAL"),
        quality_aliases={"HD": "auto_resolution"},
        source_aliases={"WEB-DL": "WEB", "WEBDL": "WEB"},
    ),
}


def _profile_from_dict(name: str, data: dict[str, Any]) -> RenamerProfile:
    return RenamerProfile(
        name=name,
        default_language_tag=str(data.get("default_language_tag", "") or ""),
        language_aliases={
            str(key).strip().upper(): str(value).strip()
            for key, value in dict(data.get("language_aliases", {})).items()
        },
        junk_terms=tuple(str(item).strip() for item in data.get("junk_terms", []) if str(item).strip()),
        quality_aliases={
            str(key).strip().upper(): str(value).strip()
            for key, value in dict(data.get("quality_aliases", {})).items()
        },
        source_aliases={
            str(key).strip().upper(): str(value).strip()
            for key, value in dict(data.get("source_aliases", {})).items()
        },
        insert_missing_resolution=bool(data.get("insert_missing_resolution", True)),
        language_insertion=str(data.get("language_insertion", "after_episode_or_start")),
    )


def load_renamer_profile(name: str | None) -> RenamerProfile:
    """Load a built-in or user-defined renamer profile."""
    profile_name = (name or "fr_tracker").strip() or "fr_tracker"
    if profile_name in BUILTIN_PROFILES:
        return BUILTIN_PROFILES[profile_name]

    path = get_config_dir() / "profiles" / "renamer" / f"{profile_name}.yaml"
    if not path.exists() and profile_name == "custom":
        path = get_config_dir() / "profiles" / "renamer" / "custom.yaml"
    if not path.exists():
        return BUILTIN_PROFILES["fr_tracker"]

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return BUILTIN_PROFILES["fr_tracker"]
    return _profile_from_dict(profile_name, data)


def list_renamer_profiles() -> list[RenamerProfile]:
    """Return built-in renamer profiles."""
    return list(BUILTIN_PROFILES.values())
