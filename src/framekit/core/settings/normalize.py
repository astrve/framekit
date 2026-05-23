from __future__ import annotations

from copy import deepcopy
from typing import Any

from framekit.core.exceptions import SettingsError

from .schema import (
    DEFAULT_METADATA_LANGUAGE,
    DEFAULT_NFO_LOCALE,
    DEFAULT_SETTINGS,
    DEFAULT_UI_LOCALE,
    METADATA_LANGUAGE_RE,
    NFO_LOCALE_TO_METADATA_LANGUAGE,
    SECRET_KEY_PARTS,
    SETTINGS_SCHEMA_VERSION,
    SUPPORTED_NFO_LOCALES,
    SUPPORTED_UI_LOCALES,
)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def normalize_ui_locale(value: str | None) -> str:
    """Normalise ui locale."""
    raw = (value or "").strip().replace("_", "-").lower()
    if not raw:
        return DEFAULT_UI_LOCALE

    short = raw.split("-", 1)[0]
    if short in SUPPORTED_UI_LOCALES:
        return short
    return DEFAULT_UI_LOCALE


def normalize_nfo_locale(value: str | None) -> str:
    """Normalise nfo locale."""
    raw = (value or "").strip().replace("_", "-").lower()
    if not raw:
        return DEFAULT_NFO_LOCALE

    short = raw.split("-", 1)[0]
    if short in SUPPORTED_NFO_LOCALES:
        return short
    return DEFAULT_NFO_LOCALE


def resolve_nfo_locale(value: str | None, *, ui_locale: str | None = None) -> str:
    """Resolve nfo locale."""
    normalized = normalize_nfo_locale(value)
    if normalized != "auto":
        return normalized
    return normalize_ui_locale(ui_locale)


def metadata_language_for_nfo_locale(locale: str | None) -> str:
    """Handle metadata language for nfo locale."""
    normalized = normalize_nfo_locale(locale)
    if normalized == "auto":
        normalized = DEFAULT_UI_LOCALE
    return NFO_LOCALE_TO_METADATA_LANGUAGE.get(normalized, DEFAULT_METADATA_LANGUAGE)


def is_valid_metadata_language(value: str | None) -> bool:
    """Return ``True`` if is valid metadata language."""
    return bool(value and METADATA_LANGUAGE_RE.fullmatch(value.strip()))


def normalize_metadata_language(value: str | None) -> str:
    """Normalise metadata language."""
    raw = (value or "").strip().replace("_", "-")
    return raw if is_valid_metadata_language(raw) else DEFAULT_METADATA_LANGUAGE


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _as_int(value: Any, default: int, *, minimum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None and parsed < minimum:
        return default
    return parsed


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in SECRET_KEY_PARTS)


def redact_settings(value: Any, *, placeholder: str = "********") -> Any:
    """Handle redact settings."""
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _is_secret_key(str(key)) and item is not None and item != "":
                redacted[str(key)] = placeholder
            else:
                redacted[str(key)] = redact_settings(item, placeholder=placeholder)
        return redacted

    if isinstance(value, list):
        return [redact_settings(item, placeholder=placeholder) for item in value]

    return value


def _normalize_general(normalized: dict[str, Any]) -> None:
    general = normalized.setdefault("general", {})
    if not isinstance(general, dict):
        return
    general["locale"] = normalize_ui_locale(str(general.get("locale", DEFAULT_UI_LOCALE)))
    general["default_folder"] = str(general.get("default_folder", "") or "").strip()
    general["report_output_folder"] = str(general.get("report_output_folder", "") or "").strip()


def _normalize_metadata(normalized: dict[str, Any]) -> None:
    metadata = normalized.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        return
    provider = str(metadata.get("provider", "tmdb") or "tmdb").strip().lower()
    metadata["provider"] = provider or "tmdb"
    metadata["interactive_confirmation"] = _as_bool(metadata.get("interactive_confirmation"), True)
    metadata["cache_ttl_hours"] = _as_int(metadata.get("cache_ttl_hours"), 168, minimum=1)
    metadata["language"] = normalize_metadata_language(
        str(metadata.get("language", DEFAULT_METADATA_LANGUAGE))
    )
    metadata["tmdb_read_access_token"] = str(
        metadata.get("tmdb_read_access_token", "") or ""
    ).strip()
    metadata["enabled_by_default"] = _as_bool(metadata.get("enabled_by_default"), True)
    metadata["prompt_missing_token_in_pipeline"] = _as_bool(
        metadata.get("prompt_missing_token_in_pipeline"), True
    )


def _normalize_setup(normalized: dict[str, Any]) -> None:
    setup = normalized.setdefault("setup", {})
    if not isinstance(setup, dict):
        return
    setup["completed"] = _as_bool(setup.get("completed"), False)
    setup["prompt_on_start"] = _as_bool(setup.get("prompt_on_start"), True)


def _normalize_security(normalized: dict[str, Any]) -> None:
    security = normalized.setdefault("security", {})
    if not isinstance(security, dict):
        return
    security["enabled"] = _as_bool(security.get("enabled"), True)
    security["vault_path"] = str(security.get("vault_path", "") or "").strip()
    key_storage = str(security.get("key_storage", "keyring") or "keyring").strip().lower()
    security["key_storage"] = key_storage if key_storage in {"keyring", "file"} else "keyring"
    security["auto_migrate"] = _as_bool(security.get("auto_migrate"), True)
    security["backup_before_changes"] = _as_bool(security.get("backup_before_changes"), True)


def _normalize_cache_type(cache: dict[str, Any], cache_type: str, default_ttl: int) -> None:
    type_config = cache.setdefault(cache_type, {})
    if not isinstance(type_config, dict):
        return
    type_config["enabled"] = _as_bool(type_config.get("enabled"), True)
    type_config["ttl_days"] = _as_int(type_config.get("ttl_days"), default_ttl, minimum=1)
    type_config["max_size_mb"] = _as_int(type_config.get("max_size_mb"), 50, minimum=1)


def _normalize_cache(normalized: dict[str, Any]) -> None:
    cache = normalized.setdefault("cache", {})
    if not isinstance(cache, dict):
        return
    cache["enabled"] = _as_bool(cache.get("enabled"), True)
    cache["directory"] = str(cache.get("directory", "") or "").strip()
    cache["auto_cleanup"] = _as_bool(cache.get("auto_cleanup"), True)
    cache["cleanup_on_startup"] = _as_bool(cache.get("cleanup_on_startup"), True)
    _normalize_cache_type(cache, "tmdb", 7)
    _normalize_cache_type(cache, "mediainfo", 30)
    _normalize_cache_type(cache, "release", 7)


def _normalize_cleanmkv_module(modules: dict[str, Any]) -> None:
    cleanmkv = modules.setdefault("cleanmkv", {})
    if not isinstance(cleanmkv, dict):
        return
    cleanmkv["copy_unchanged_files"] = _as_bool(cleanmkv.get("copy_unchanged_files"), True)
    output_dir_name = str(cleanmkv.get("output_dir_name", "") or "").strip()
    if output_dir_name in {"", "clean"}:
        output_dir_name = "Release/{release}"
    cleanmkv["output_dir_name"] = output_dir_name


def _normalize_renamer_module(modules: dict[str, Any]) -> None:
    renamer = modules.setdefault("renamer", {})
    if not isinstance(renamer, dict):
        return
    renamer["default_folder"] = str(renamer.get("default_folder", "") or "").strip()
    renamer["default_language_tag"] = str(
        renamer.get("default_language_tag", "MULTI.VFF") or ""
    ).strip()
    renamer["profile"] = str(renamer.get("profile", "fr_tracker") or "fr_tracker").strip()
    for key in ("junk_terms",):
        raw = renamer.get(key, [])
        renamer[key] = (
            [str(item).strip() for item in raw if str(item).strip()]
            if isinstance(raw, list)
            else []
        )
    for key in ("language_aliases", "quality_aliases", "source_aliases"):
        raw_map = renamer.get(key, {})
        renamer[key] = (
            {str(k).strip().upper(): str(v).strip() for k, v in raw_map.items() if str(k).strip()}
            if isinstance(raw_map, dict)
            else {}
        )
    renamer["insert_missing_resolution"] = _as_bool(renamer.get("insert_missing_resolution"), True)
    renamer["language_insertion"] = str(
        renamer.get("language_insertion", "after_episode_or_start") or "after_episode_or_start"
    ).strip()


def _normalize_nfo_module(modules: dict[str, Any]) -> None:
    nfo = modules.setdefault("nfo", {})
    if not isinstance(nfo, dict):
        return
    nfo["locale"] = normalize_nfo_locale(str(nfo.get("locale", DEFAULT_NFO_LOCALE)))
    nfo["active_template"] = (
        str(nfo.get("active_template", "default") or "default").strip() or "default"
    )
    nfo["with_metadata"] = _as_bool(nfo.get("with_metadata"), True)
    mode_value = str(nfo.get("mode", "global") or "global").strip().lower()
    nfo["mode"] = mode_value if mode_value in {"global", "per_file", "both"} else "global"


def _normalize_torrent_module(modules: dict[str, Any]) -> None:
    torrent = modules.setdefault("torrent", {})
    if not isinstance(torrent, dict):
        return
    legacy_announce = str(torrent.get("announce", "") or "").strip()
    announce_urls = _normalized_announce_urls(torrent.get("announce_urls", []), legacy_announce)
    selected = _resolve_selected_announce(
        torrent.get("selected_announce", ""),
        announce_urls,
    )
    torrent["announce_urls"] = announce_urls
    torrent["selected_announce"] = selected
    torrent["announce"] = selected
    torrent["private"] = _as_bool(torrent.get("private"), True)
    piece_length = str(torrent.get("piece_length", "auto") or "auto").strip()
    torrent["piece_length"] = piece_length or "auto"
    torrent["prompt_save_announce"] = _as_bool(torrent.get("prompt_save_announce"), True)


def _normalized_announce_urls(raw_announces: Any, legacy_announce: str) -> list[str]:
    announce_urls: list[str] = []
    if isinstance(raw_announces, list):
        announce_urls = [str(item).strip() for item in raw_announces if str(item).strip()]
    if legacy_announce and legacy_announce not in announce_urls:
        announce_urls.insert(0, legacy_announce)
    return announce_urls


def _resolve_selected_announce(raw_selected: Any, announce_urls: list[str]) -> str:
    selected = str(raw_selected or "").strip()
    if not selected and announce_urls:
        return announce_urls[0]
    return selected


def _normalize_pipeline_module(modules: dict[str, Any]) -> None:
    pipeline = modules.setdefault("pipeline", {})
    if not isinstance(pipeline, dict):
        return
    pipeline["stop_on_error"] = _as_bool(pipeline.get("stop_on_error"), False)
    pipeline["with_metadata"] = _as_bool(pipeline.get("with_metadata"), True)
    raw_enabled = pipeline.get(
        "enabled_modules", DEFAULT_SETTINGS["modules"]["pipeline"]["enabled_modules"]
    )
    allowed = {"renamer", "cleanmkv", "nfo", "torrent", "prez", "upload"}
    if isinstance(raw_enabled, list):
        enabled = [
            str(item).strip().lower()
            for item in raw_enabled
            if str(item).strip().lower() in allowed
        ]
    else:
        enabled = list(DEFAULT_SETTINGS["modules"]["pipeline"]["enabled_modules"])
    pipeline["enabled_modules"] = enabled or list(
        DEFAULT_SETTINGS["modules"]["pipeline"]["enabled_modules"]
    )


def _normalize_prez_module(modules: dict[str, Any]) -> None:
    prez = modules.setdefault("prez", {})
    if not isinstance(prez, dict):
        return
    prez["locale"] = normalize_nfo_locale(str(prez.get("locale", DEFAULT_NFO_LOCALE)))
    prez["format"] = _normalize_prez_format(prez.get("format", "both"))
    prez["preset"] = str(prez.get("preset", "default") or "default").strip().lower() or "default"
    prez["html_template"] = (
        str(prez.get("html_template", "aurora") or "aurora").strip().lower() or "aurora"
    )
    prez["bbcode_template"] = (
        str(prez.get("bbcode_template", "classic") or "classic").strip().lower() or "classic"
    )
    prez["mediainfo_mode"] = _normalize_mediainfo_mode(prez.get("mediainfo_mode", "none"))
    prez["include_mediainfo"] = _as_bool(prez.get("include_mediainfo"), False)
    prez["with_metadata"] = _as_bool(prez.get("with_metadata"), True)


def _normalize_prez_format(raw_format: Any) -> str:
    format_value = str(raw_format or "both").strip().lower()
    if format_value in {"html", "bbcode", "both", "mediainfo"}:
        return format_value
    return "both"


def _normalize_mediainfo_mode(raw_mode: Any) -> str:
    mode = str(raw_mode or "none").strip().lower()
    if mode in {"none", "spoiler", "only"}:
        return mode
    return "none"


def _normalize_modules(normalized: dict[str, Any]) -> None:
    modules = normalized.setdefault("modules", {})
    if not isinstance(modules, dict):
        return
    _normalize_renamer_module(modules)
    _normalize_cleanmkv_module(modules)
    _normalize_nfo_module(modules)
    _normalize_torrent_module(modules)
    _normalize_pipeline_module(modules)
    _normalize_prez_module(modules)


def _normalize_upload(normalized: dict[str, Any]) -> None:
    upload = normalized.setdefault("upload", {})
    if not isinstance(upload, dict):
        normalized["upload"] = deepcopy(DEFAULT_SETTINGS["upload"])
        return
    upload["enabled"] = _as_bool(upload.get("enabled"), False)
    upload["auto_upload"] = _as_bool(upload.get("auto_upload"), False)
    upload["max_parallel_uploads"] = _as_int(upload.get("max_parallel_uploads"), 3, minimum=1)
    for key in ("trackers", "presets"):
        raw = upload.get(key, [])
        upload[key] = raw if isinstance(raw, list) else []


def _normalize_seedbox(normalized: dict[str, Any]) -> None:
    seedbox = normalized.setdefault("seedbox", {})
    if not isinstance(seedbox, dict):
        normalized["seedbox"] = deepcopy(DEFAULT_SETTINGS["seedbox"])
        return
    seedbox["default"] = str(seedbox.get("default", "") or "").strip()
    seedbox["history_enabled"] = _as_bool(seedbox.get("history_enabled"), True)
    raw_seedboxes = seedbox.get("seedboxes", [])
    seedbox["seedboxes"] = raw_seedboxes if isinstance(raw_seedboxes, list) else []


def _normalize_plugins(normalized: dict[str, Any]) -> None:
    plugins = normalized.setdefault("plugins", {})
    if not isinstance(plugins, dict):
        normalized["plugins"] = {"allowed": []}
        return
    raw_allowed = plugins.get("allowed", [])
    if not isinstance(raw_allowed, list):
        plugins["allowed"] = []
        return
    seen: set[str] = set()
    allowed: list[str] = []
    for item in raw_allowed:
        name = str(item).strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        allowed.append(name)
    plugins["allowed"] = allowed


def _normalize_aliases(normalized: dict[str, Any]) -> None:
    aliases = normalized.setdefault("aliases", {})
    if not isinstance(aliases, dict):
        return
    aliases["enabled"] = _as_bool(aliases.get("enabled"), True)
    aliases["max_chain_depth"] = _as_int(aliases.get("max_chain_depth"), 5, minimum=1)
    raw_removed = aliases.get("removed", [])
    if isinstance(raw_removed, list):
        removed = sorted({str(item).strip() for item in raw_removed if str(item).strip()})
    else:
        removed = []
    aliases["removed"] = removed
    aliases.setdefault("user", {})
    aliases.setdefault("builtin", {})
    for alias_type in ["user", "builtin"]:
        alias_dict = aliases.get(alias_type, {})
        if not isinstance(alias_dict, dict):
            aliases[alias_type] = {}
            continue
        for name, definition in list(alias_dict.items()):
            if name in removed:
                del alias_dict[name]
                continue
            if isinstance(definition, dict):
                definition.setdefault("command", "")
                definition.setdefault("description", "")
                definition["enabled"] = _as_bool(definition.get("enabled"), True)
                continue
            del alias_dict[name]


def normalize_settings(data: dict[str, Any]) -> dict[str, Any]:
    """Normalise settings."""
    normalized = deepcopy(data)

    normalized["schema_version"] = SETTINGS_SCHEMA_VERSION

    _normalize_general(normalized)
    _normalize_metadata(normalized)
    _normalize_setup(normalized)
    _normalize_security(normalized)
    _normalize_cache(normalized)
    _normalize_modules(normalized)
    _normalize_upload(normalized)
    _normalize_seedbox(normalized)
    _normalize_plugins(normalized)
    _normalize_aliases(normalized)

    return normalized


def validate_settings(data: dict[str, Any]) -> None:
    """Validate settings."""
    general = _expect_dict(data.get("general", {}), "settings.general")
    _validate_general(general)

    metadata = _expect_dict(data.get("metadata", {}), "settings.metadata")
    _validate_metadata(metadata)

    modules = _expect_dict(data.get("modules", {}), "settings.modules")
    _validate_modules(modules)


def _expect_dict(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SettingsError(f"{path} must be an object.")
    return value


def _validate_general(general: dict[str, Any]) -> None:
    if general.get("locale") not in SUPPORTED_UI_LOCALES:
        raise SettingsError(f"Unsupported UI locale: {general.get('locale')}")


def _validate_metadata(metadata: dict[str, Any]) -> None:
    if metadata.get("provider") != "tmdb":
        raise SettingsError(f"Unsupported metadata provider: {metadata.get('provider')}")
    if not is_valid_metadata_language(str(metadata.get("language", ""))):
        raise SettingsError(f"Invalid metadata language: {metadata.get('language')}")


def _validate_modules(modules: dict[str, Any]) -> None:
    nfo = _expect_dict(modules.get("nfo", {}), "settings.modules.nfo")
    if nfo.get("locale") not in SUPPORTED_NFO_LOCALES:
        raise SettingsError(f"Unsupported NFO locale: {nfo.get('locale')}")

    prez = _expect_dict(modules.get("prez", {}), "settings.modules.prez")
    if prez.get("locale") not in SUPPORTED_NFO_LOCALES:
        raise SettingsError(f"Unsupported Prez locale: {prez.get('locale')}")


def _split_key_path(path: str) -> list[str]:
    if not path or not path.strip():
        raise SettingsError("Settings path cannot be empty.")
    return [part for part in path.strip().split(".") if part]


def _get_nested(data: dict[str, Any], path: str) -> Any:  # pyright: ignore[reportUnusedFunction]  # Re-exported through package __init__
    current: Any = data
    for part in _split_key_path(path):
        if not isinstance(current, dict) or part not in current:
            raise SettingsError(f"Unknown settings key: {path}")
        current = current[part]
    return current


def _set_nested(data: dict[str, Any], path: str, value: Any) -> None:  # pyright: ignore[reportUnusedFunction]  # Re-exported through package __init__
    parts = _split_key_path(path)
    current: Any = data

    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            raise SettingsError(f"Unknown settings key: {path}")
        current = current[part]

    last = parts[-1]
    if not isinstance(current, dict) or last not in current:
        raise SettingsError(f"Unknown settings key: {path}")

    current[last] = value
