from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from filelock import BaseFileLock, FileLock

from framekit.core.exceptions import SettingsError
from framekit.core.paths import get_settings_path

SETTINGS_SCHEMA_VERSION = 11
SUPPORTED_UI_LOCALES = frozenset({"en", "fr", "es"})
SUPPORTED_NFO_LOCALES = frozenset({"auto", "en", "fr", "es"})
NFO_LOCALE_TO_METADATA_LANGUAGE = {
    "en": "en-US",
    "fr": "fr-FR",
    "es": "es-ES",
}
DEFAULT_UI_LOCALE = "en"
DEFAULT_NFO_LOCALE = "auto"
DEFAULT_METADATA_LANGUAGE = "en-US"
METADATA_LANGUAGE_RE = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})?$")
# List of key substrings that should be considered sensitive.  Any key
# containing one of these parts (case-insensitive) will be redacted
# when settings are printed or logged.  This list is extended to
# include torrent announce configuration so that announce URLs and
# profiles are masked by default.  Additional entries for
# ``authorization`` and ``bearer`` mirror the diagnostics module to
# avoid exposing HTTP Authorization headers or Bearer tokens via
# settings.  See ``redact_settings()`` for usage.
SECRET_KEY_PARTS = (
    "api_key",
    "apikey",
    "access_token",
    "auth_token",
    # Authorization/Bearer headers should be masked as well
    "authorization",
    "bearer",
    "token",
    "password",
    "secret",
    "client_secret",
    # Torrent announce configuration
    "announce",
    "announce_url",
    "announce_urls",
    "selected_announce",
)

DEFAULT_SETTINGS: dict[str, Any] = {
    "schema_version": SETTINGS_SCHEMA_VERSION,
    "general": {
        "locale": DEFAULT_UI_LOCALE,
        "default_folder": "",
        "path_resolution_mode": "module_last_then_module_default_then_global_then_cwd",
        "export_json_reports": False,
        "report_output_folder": "",
        "dry_run_by_default": False,
    },
    "tools": {
        "mkvmerge": "",
        "mediainfo": "",
    },
    "setup": {
        "completed": False,
        "prompt_on_start": True,
    },
    "metadata": {
        "provider": "tmdb",
        "interactive_confirmation": True,
        "cache_ttl_hours": 168,
        "language": DEFAULT_METADATA_LANGUAGE,
        "tmdb_api_key": "",
        "tmdb_read_access_token": "",
        "enabled_by_default": True,
    },
    "modules": {
        "renamer": {
            "default_folder": "",
            "last_folder": "",
            "default_language_tag": "MULTI.VFF",
        },
        "cleanmkv": {
            "default_folder": "",
            "last_folder": "",
            "output_dir_name": "Release/{release}",
            "default_preset": "multi",
            "copy_unchanged_files": True,
        },
        "nfo": {
            "default_folder": "",
            "last_folder": "",
            "active_template": "default",
            "locale": DEFAULT_NFO_LOCALE,
            "logo_path": "",
            "active_logo": "",
            "with_metadata": True,
            "mode": "global",
        },
        "torrent": {
            "default_folder": "",
            "last_folder": "",
            "announce": "",
            "announce_urls": [],
            "selected_announce": "",
            "private": True,
            "piece_length": "auto",
        },
        "prez": {
            "default_folder": "",
            "last_folder": "",
            "locale": DEFAULT_NFO_LOCALE,
            "format": "both",
            "preset": "default",
            "html_template": "aurora",
            "bbcode_template": "classic",
            "mediainfo_mode": "none",
            "include_mediainfo": False,
            "with_metadata": True,
        },
        "pipeline": {
            "default_folder": "",
            "last_folder": "",
            "stop_on_error": True,
            "enabled_modules": ["renamer", "cleanmkv", "nfo", "torrent", "prez"],
            "with_metadata": True,
        },
        "encoder": {
            "default_folder": "",
            "last_folder": "",
            "output_dir_name": "encoded",
        },
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def normalize_ui_locale(value: str | None) -> str:
    raw = (value or "").strip().replace("_", "-").lower()
    if not raw:
        return DEFAULT_UI_LOCALE

    short = raw.split("-", 1)[0]
    if short in SUPPORTED_UI_LOCALES:
        return short
    return DEFAULT_UI_LOCALE


def normalize_nfo_locale(value: str | None) -> str:
    raw = (value or "").strip().replace("_", "-").lower()
    if not raw:
        return DEFAULT_NFO_LOCALE

    short = raw.split("-", 1)[0]
    if short in SUPPORTED_NFO_LOCALES:
        return short
    return DEFAULT_NFO_LOCALE


def resolve_nfo_locale(value: str | None, *, ui_locale: str | None = None) -> str:
    normalized = normalize_nfo_locale(value)
    if normalized != "auto":
        return normalized
    return normalize_ui_locale(ui_locale)


def metadata_language_for_nfo_locale(locale: str | None) -> str:
    normalized = normalize_nfo_locale(locale)
    if normalized == "auto":
        normalized = DEFAULT_UI_LOCALE
    return NFO_LOCALE_TO_METADATA_LANGUAGE.get(normalized, DEFAULT_METADATA_LANGUAGE)


def is_valid_metadata_language(value: str | None) -> bool:
    return bool(value and METADATA_LANGUAGE_RE.fullmatch(value.strip()))


def normalize_metadata_language(value: str | None) -> str:
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


def normalize_settings(data: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(data)

    normalized["schema_version"] = SETTINGS_SCHEMA_VERSION

    general = normalized.setdefault("general", {})
    if isinstance(general, dict):
        general["locale"] = normalize_ui_locale(str(general.get("locale", DEFAULT_UI_LOCALE)))
        general["export_json_reports"] = _as_bool(general.get("export_json_reports"), False)
        general["dry_run_by_default"] = _as_bool(general.get("dry_run_by_default"), False)

    metadata = normalized.setdefault("metadata", {})
    if isinstance(metadata, dict):
        provider = str(metadata.get("provider", "tmdb") or "tmdb").strip().lower()
        metadata["provider"] = provider or "tmdb"
        metadata["interactive_confirmation"] = _as_bool(
            metadata.get("interactive_confirmation"),
            True,
        )
        metadata["cache_ttl_hours"] = _as_int(
            metadata.get("cache_ttl_hours"),
            168,
            minimum=1,
        )
        metadata["language"] = normalize_metadata_language(
            str(metadata.get("language", DEFAULT_METADATA_LANGUAGE))
        )
        metadata["tmdb_api_key"] = str(metadata.get("tmdb_api_key", "") or "").strip()
        metadata["tmdb_read_access_token"] = str(
            metadata.get("tmdb_read_access_token", "") or ""
        ).strip()
        metadata["enabled_by_default"] = _as_bool(metadata.get("enabled_by_default"), True)

    setup = normalized.setdefault("setup", {})
    if isinstance(setup, dict):
        setup["completed"] = _as_bool(setup.get("completed"), False)
        setup["prompt_on_start"] = _as_bool(setup.get("prompt_on_start"), True)

    modules = normalized.setdefault("modules", {})
    if isinstance(modules, dict):
        cleanmkv = modules.setdefault("cleanmkv", {})
        if isinstance(cleanmkv, dict):
            cleanmkv["copy_unchanged_files"] = _as_bool(
                cleanmkv.get("copy_unchanged_files"),
                True,
            )
            output_dir_name = str(cleanmkv.get("output_dir_name", "") or "").strip()
            if output_dir_name in {"", "clean"}:
                output_dir_name = "Release/{release}"
            cleanmkv["output_dir_name"] = output_dir_name

        nfo = modules.setdefault("nfo", {})
        if isinstance(nfo, dict):
            nfo["locale"] = normalize_nfo_locale(str(nfo.get("locale", DEFAULT_NFO_LOCALE)))
            nfo["active_template"] = (
                str(nfo.get("active_template", "default") or "default").strip() or "default"
            )
            nfo["with_metadata"] = _as_bool(nfo.get("with_metadata"), True)
            mode_value = str(nfo.get("mode", "global") or "global").strip().lower()
            nfo["mode"] = mode_value if mode_value in {"global", "per_file", "both"} else "global"

        torrent = modules.setdefault("torrent", {})
        if isinstance(torrent, dict):
            legacy_announce = str(torrent.get("announce", "") or "").strip()
            raw_announces = torrent.get("announce_urls", [])
            announce_urls: list[str] = []
            if isinstance(raw_announces, list):
                announce_urls = [str(item).strip() for item in raw_announces if str(item).strip()]
            if legacy_announce and legacy_announce not in announce_urls:
                announce_urls.insert(0, legacy_announce)
            selected = str(torrent.get("selected_announce", "") or "").strip()
            if not selected and announce_urls:
                selected = announce_urls[0]
            torrent["announce_urls"] = announce_urls
            torrent["selected_announce"] = selected
            torrent["announce"] = selected
            torrent["private"] = _as_bool(torrent.get("private"), True)
            piece_length = str(torrent.get("piece_length", "auto") or "auto").strip()
            torrent["piece_length"] = piece_length or "auto"

        pipeline = modules.setdefault("pipeline", {})
        if isinstance(pipeline, dict):
            pipeline["stop_on_error"] = _as_bool(pipeline.get("stop_on_error"), True)
            pipeline["with_metadata"] = _as_bool(pipeline.get("with_metadata"), True)
            raw_enabled = pipeline.get(
                "enabled_modules", DEFAULT_SETTINGS["modules"]["pipeline"]["enabled_modules"]
            )
            allowed = {"renamer", "cleanmkv", "nfo", "torrent", "prez"}
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

        prez = modules.setdefault("prez", {})
        if isinstance(prez, dict):
            prez["locale"] = normalize_nfo_locale(str(prez.get("locale", DEFAULT_NFO_LOCALE)))
            prez["format"] = str(prez.get("format", "both") or "both").strip().lower()
            if prez["format"] not in {"html", "bbcode", "both", "mediainfo"}:
                prez["format"] = "both"
            prez["preset"] = (
                str(prez.get("preset", "default") or "default").strip().lower() or "default"
            )
            prez["html_template"] = (
                str(prez.get("html_template", "aurora") or "aurora").strip().lower() or "aurora"
            )
            prez["bbcode_template"] = (
                str(prez.get("bbcode_template", "classic") or "classic").strip().lower()
                or "classic"
            )
            prez["mediainfo_mode"] = (
                str(prez.get("mediainfo_mode", "none") or "none").strip().lower()
            )
            if prez["mediainfo_mode"] not in {"none", "spoiler", "only"}:
                prez["mediainfo_mode"] = "none"
            prez["include_mediainfo"] = _as_bool(prez.get("include_mediainfo"), False)
            prez["with_metadata"] = _as_bool(prez.get("with_metadata"), True)

    return normalized


def validate_settings(data: dict[str, Any]) -> None:
    general = data.get("general", {})
    if not isinstance(general, dict):
        raise SettingsError("settings.general must be an object.")
    if general.get("locale") not in SUPPORTED_UI_LOCALES:
        raise SettingsError(f"Unsupported UI locale: {general.get('locale')}")

    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        raise SettingsError("settings.metadata must be an object.")
    if metadata.get("provider") != "tmdb":
        raise SettingsError(f"Unsupported metadata provider: {metadata.get('provider')}")
    if not is_valid_metadata_language(str(metadata.get("language", ""))):
        raise SettingsError(f"Invalid metadata language: {metadata.get('language')}")

    modules = data.get("modules", {})
    if not isinstance(modules, dict):
        raise SettingsError("settings.modules must be an object.")
    nfo = modules.get("nfo", {})
    if not isinstance(nfo, dict):
        raise SettingsError("settings.modules.nfo must be an object.")
    if nfo.get("locale") not in SUPPORTED_NFO_LOCALES:
        raise SettingsError(f"Unsupported NFO locale: {nfo.get('locale')}")

    prez = modules.get("prez", {})
    if not isinstance(prez, dict):
        raise SettingsError("settings.modules.prez must be an object.")
    if prez.get("locale") not in SUPPORTED_NFO_LOCALES:
        raise SettingsError(f"Unsupported Prez locale: {prez.get('locale')}")


def _split_key_path(path: str) -> list[str]:
    if not path or not path.strip():
        raise SettingsError("Settings path cannot be empty.")
    return [part for part in path.strip().split(".") if part]


def _get_nested(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in _split_key_path(path):
        if not isinstance(current, dict) or part not in current:
            raise SettingsError(f"Unknown settings key: {path}")
        current = current[part]
    return current


def _set_nested(data: dict[str, Any], path: str, value: Any) -> None:
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


def _migrate_legacy_settings(data: dict[str, Any]) -> dict[str, Any]:
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

    migrated["schema_version"] = DEFAULT_SETTINGS["schema_version"]
    return migrated


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or get_settings_path()
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    def _lock(self) -> BaseFileLock:
        return FileLock(str(self.lock_path))

    def ensure_exists(self) -> None:
        with self._lock():
            if self.path.exists():
                return

            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(DEFAULT_SETTINGS, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    def load(self) -> dict[str, Any]:
        self.ensure_exists()

        with self._lock():
            try:
                raw = self.path.read_text(encoding="utf-8")
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise SettingsError(f"Invalid JSON in settings file: {self.path}") from exc
            except OSError as exc:
                raise SettingsError(f"Cannot read settings file: {self.path}") from exc

        if not isinstance(data, dict):
            raise SettingsError("Settings file must contain a JSON object.")

        migrated = _migrate_legacy_settings(data)
        normalized = normalize_settings(_deep_merge(DEFAULT_SETTINGS, migrated))
        validate_settings(normalized)
        return normalized

    def save(self, data: dict[str, Any]) -> None:
        normalized = normalize_settings(
            _deep_merge(DEFAULT_SETTINGS, _migrate_legacy_settings(data))
        )
        validate_settings(normalized)

        with self._lock():
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_text(
                    json.dumps(normalized, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
            except OSError as exc:
                raise SettingsError(f"Cannot write settings file: {self.path}") from exc

    def get(self, path: str) -> Any:
        data = self.load()
        return _get_nested(data, path)

    def set(self, path: str, value: Any) -> dict[str, Any]:
        data = self.load()
        _set_nested(data, path, value)
        self.save(data)
        return data

    def reset(self, path: str) -> dict[str, Any]:
        data = self.load()
        default_value = _get_nested(DEFAULT_SETTINGS, path)
        _set_nested(data, path, deepcopy(default_value))
        self.save(data)
        return data
