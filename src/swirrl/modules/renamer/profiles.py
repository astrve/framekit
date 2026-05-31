from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml

from swirrl.core.languages import VALID_LANGUAGE_VARIANTS, normalize_language
from swirrl.core.paths import get_config_dir


@dataclass(frozen=True, slots=True)
class LanguageTagRules:
    """Language tag outcomes for common audio-track combinations."""

    only_default: str = ""
    default_plus_others: str = ""
    default_plus_variants_only: str = ""
    default_plus_variants_and_others: str = ""
    none_default_multi: str = "MULTI"


@dataclass(frozen=True, slots=True)
class LanguageTagProfile:
    """Rules used to infer the language tag from MediaInfo audio tracks."""

    name: str
    default_language: str = ""
    variant_languages: tuple[tuple[str, str | None], ...] = ()
    tags: LanguageTagRules = field(default_factory=LanguageTagRules)


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
        junk_terms=tuple(
            str(item).strip() for item in data.get("junk_terms", []) if str(item).strip()
        ),
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


def _upper_tag(value: Any) -> str:
    return str(value or "").strip().upper()


def _normalize_variant(raw: str) -> str | None:
    key = str(raw or "").strip().lower().replace("_", "-")
    if not key:
        return None
    alias_map = {
        "ca": "canada",
        "can": "canada",
        "canada": "canada",
        "fr": "france",
        "fra": "france",
        "france": "france",
        "us": "us",
        "usa": "us",
        "uk": "uk",
        "gb": "uk",
        "latam": "latam",
        "419": "latam",
        "br": "brazil",
        "brazil": "brazil",
        "pt": "europe",
        "europe": "europe",
    }
    candidate = alias_map.get(key, key)
    return candidate if candidate in VALID_LANGUAGE_VARIANTS else None


def _normalize_language_spec(
    value: Any,
    *,
    default_language: str | None = None,
) -> tuple[str | None, str | None]:
    raw = str(value or "").strip()
    if not raw:
        return None, None

    language, variant = normalize_language(raw)
    if language and variant:
        return language, variant
    if language and language in VALID_LANGUAGE_VARIANTS and default_language:
        return default_language, language
    if language:
        return language, None

    variant_from_raw = _normalize_variant(raw)
    if variant_from_raw and default_language:
        return default_language, variant_from_raw
    return None, None


def _normalize_variant_languages(
    values: Any,
    *,
    default_language: str,
) -> tuple[tuple[str, str | None], ...]:
    if not isinstance(values, list):
        return ()
    normalized: list[tuple[str, str | None]] = []
    seen: set[tuple[str, str | None]] = set()
    for value in values:
        language, variant = _normalize_language_spec(value, default_language=default_language)
        if not language:
            continue
        key = (language, variant)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(key)
    return tuple(normalized)


def _language_tag_rules_from_dict(data: dict[str, Any]) -> LanguageTagRules:
    return LanguageTagRules(
        only_default=_upper_tag(data.get("only_default")),
        default_plus_others=_upper_tag(data.get("default_plus_others")),
        default_plus_variants_only=_upper_tag(data.get("default_plus_variants_only")),
        default_plus_variants_and_others=_upper_tag(data.get("default_plus_variants_and_others")),
        none_default_multi=_upper_tag(data.get("none_default_multi")) or "MULTI",
    )


def _language_profile_from_dict(name: str, data: dict[str, Any]) -> LanguageTagProfile:
    default_language, _variant = _normalize_language_spec(data.get("default_language"))
    default_language = default_language or ""
    variants = _normalize_variant_languages(
        data.get("variant_languages", []), default_language=default_language
    )
    tags = _language_tag_rules_from_dict(dict(data.get("tags", {})))
    return LanguageTagProfile(
        name=name,
        default_language=default_language,
        variant_languages=variants,
        tags=tags,
    )


BUILTIN_LANGUAGE_TAG_PROFILES: dict[str, LanguageTagProfile] = {
    "fr_tracker": LanguageTagProfile(
        name="fr_tracker",
        default_language="french",
        variant_languages=(("french", "canada"),),
        tags=LanguageTagRules(
            only_default="VFF",
            default_plus_others="MULTI.VFF",
            default_plus_variants_only="VF2",
            default_plus_variants_and_others="MULTI.VF2",
            none_default_multi="MULTI",
        ),
    ),
    "en": LanguageTagProfile(
        name="en",
        default_language="english",
        tags=LanguageTagRules(
            only_default="EN",
            default_plus_others="MULTI.EN",
            default_plus_variants_only="EN",
            default_plus_variants_and_others="MULTI.EN",
            none_default_multi="MULTI",
        ),
    ),
    "en_us": LanguageTagProfile(
        name="en_us",
        default_language="english",
        variant_languages=(("english", "us"), ("english", "uk")),
        tags=LanguageTagRules(
            only_default="EN",
            default_plus_others="MULTI.EN",
            default_plus_variants_only="EN.US",
            default_plus_variants_and_others="MULTI.EN.US",
            none_default_multi="MULTI",
        ),
    ),
    "es": LanguageTagProfile(
        name="es",
        default_language="spanish",
        tags=LanguageTagRules(
            only_default="ES",
            default_plus_others="MULTI.ES",
            default_plus_variants_only="ES",
            default_plus_variants_and_others="MULTI.ES",
            none_default_multi="MULTI",
        ),
    ),
    "de": LanguageTagProfile(
        name="de",
        default_language="german",
        tags=LanguageTagRules(
            only_default="DE",
            default_plus_others="MULTI.DE",
            default_plus_variants_only="DE",
            default_plus_variants_and_others="MULTI.DE",
            none_default_multi="MULTI",
        ),
    ),
    "it": LanguageTagProfile(
        name="it",
        default_language="italian",
        tags=LanguageTagRules(
            only_default="IT",
            default_plus_others="MULTI.IT",
            default_plus_variants_only="IT",
            default_plus_variants_and_others="MULTI.IT",
            none_default_multi="MULTI",
        ),
    ),
    "international": LanguageTagProfile(
        name="international",
        default_language="english",
        tags=LanguageTagRules(
            only_default="EN",
            default_plus_others="MULTI",
            default_plus_variants_only="EN",
            default_plus_variants_and_others="MULTI",
            none_default_multi="MULTI",
        ),
    ),
    "no_language": LanguageTagProfile(
        name="no_language",
        default_language="",
        tags=LanguageTagRules(
            only_default="",
            default_plus_others="MULTI",
            default_plus_variants_only="",
            default_plus_variants_and_others="MULTI",
            none_default_multi="MULTI",
        ),
    ),
}


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


def _user_language_profiles_from_settings(settings: dict[str, Any]) -> dict[str, LanguageTagProfile]:
    renamer = (settings.get("modules") or {}).get("renamer", {})
    language_profiles_cfg = renamer.get("language_profiles", {})
    if not isinstance(language_profiles_cfg, dict):
        return {}
    profiles_blob = language_profiles_cfg.get("profiles", {})
    if not isinstance(profiles_blob, dict):
        return {}
    profiles: dict[str, LanguageTagProfile] = {}
    for profile_name, raw_data in profiles_blob.items():
        if not isinstance(raw_data, dict):
            continue
        name = str(profile_name or "").strip()
        if not name:
            continue
        profiles[name] = _language_profile_from_dict(name, raw_data)
    return profiles


def resolve_language_tag_profile(
    settings: dict[str, Any],
    *,
    profile_name: str | None = None,
) -> LanguageTagProfile:
    """Resolve active language-tag profile from settings/user override."""
    renamer = (settings.get("modules") or {}).get("renamer", {})
    cfg = renamer.get("language_profiles", {})
    active_name = profile_name
    if not active_name:
        if isinstance(cfg, dict):
            active_name = str(cfg.get("active", "") or "").strip()
        if not active_name:
            active_name = str(renamer.get("profile", "fr_tracker") or "fr_tracker").strip()
    active_name = active_name or "fr_tracker"

    user_profiles = _user_language_profiles_from_settings(settings)
    if active_name in user_profiles:
        return user_profiles[active_name]
    return BUILTIN_LANGUAGE_TAG_PROFILES.get(active_name, BUILTIN_LANGUAGE_TAG_PROFILES["fr_tracker"])


def language_tags_for_profile(profile: LanguageTagProfile) -> set[str]:
    """Return all non-empty tags configured by a language profile."""
    return {
        _upper_tag(profile.tags.only_default),
        _upper_tag(profile.tags.default_plus_others),
        _upper_tag(profile.tags.default_plus_variants_only),
        _upper_tag(profile.tags.default_plus_variants_and_others),
        _upper_tag(profile.tags.none_default_multi),
    } - {""}


def _unique_audio_languages(
    audio_languages: list[tuple[str | None, str | None]],
) -> list[tuple[str, str | None]]:
    unique: list[tuple[str, str | None]] = []
    seen: set[tuple[str, str | None]] = set()
    for language, variant in audio_languages:
        if not language:
            continue
        key = (language, variant)
        if key in seen:
            continue
        seen.add(key)
        unique.append(key)
    return unique


def infer_language_tag(
    profile: LanguageTagProfile,
    audio_languages: list[tuple[str | None, str | None]],
) -> str:
    """Infer release language tag from normalized audio track languages."""
    unique_languages = _unique_audio_languages(audio_languages)
    if not unique_languages:
        return ""

    default_lang = profile.default_language
    if not default_lang:
        if len(unique_languages) > 1:
            return _upper_tag(profile.tags.none_default_multi)
        return _upper_tag(profile.tags.only_default)

    variants = set(profile.variant_languages)
    has_default = any(language == default_lang for language, _variant in unique_languages)
    has_variant = any((language, variant) in variants for language, variant in unique_languages)
    has_other = any(
        language != default_lang and (language, variant) not in variants
        for language, variant in unique_languages
    )

    if has_default and has_variant and has_other:
        return _upper_tag(profile.tags.default_plus_variants_and_others)
    if has_default and has_variant and not has_other:
        return _upper_tag(profile.tags.default_plus_variants_only)
    if has_default and has_other:
        return _upper_tag(profile.tags.default_plus_others)
    if has_default:
        return _upper_tag(profile.tags.only_default)
    if len(unique_languages) > 1:
        return _upper_tag(profile.tags.none_default_multi)
    return ""
