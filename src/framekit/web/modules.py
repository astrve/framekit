from __future__ import annotations

import json
import shlex
import sqlite3
import subprocess  # nosec B404
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from queue import Empty, SimpleQueue
from threading import Event, Lock, Thread
from time import monotonic, sleep
from typing import Any, Literal
from uuid import uuid4

from click.core import Argument, Command, Group, Option, Parameter
from pydantic import BaseModel, Field, field_validator

from framekit.commands.main import cli as framekit_cli
from framekit.core.webhooks import dispatch_webhook_event
from framekit.core.banners import BannerRegistry
from framekit.core.paths import (
    get_cache_dir,
    get_cleanmkv_presets_dir,
    get_config_dir,
    get_pipeline_presets_dir,
    get_prez_presets_dir,
    get_settings_path,
)
from framekit.core.settings import SettingsStore, redact_settings
from framekit.core.settings.high_level import Settings
from framekit.core.subprocess_safe import SafeSubprocessError, popen_safe, run_safe
from framekit.modules.upload.service import UploadService


@dataclass(frozen=True)
class ModuleSpec:
    """Static metadata for one CLI module exposed in web runner."""

    name: str
    description: str
    destructive: bool
    supports_dry_run: bool


MODULE_SPECS: tuple[ModuleSpec, ...] = (
    ModuleSpec("about", "Show version/license information.", False, False),
    ModuleSpec("init", "Create starter config.", True, False),
    ModuleSpec("setup", "Run guided setup.", True, False),
    ModuleSpec("language", "Manage locale preferences.", True, False),
    ModuleSpec("settings", "View/edit local settings.", True, False),
    ModuleSpec("config", "Explain/validate module config.", False, False),
    ModuleSpec("alias", "Manage command aliases.", True, False),
    ModuleSpec("doctor", "Run environment diagnostics.", False, False),
    ModuleSpec("logs", "Inspect structured logs.", False, False),
    ModuleSpec("rollback", "Rollback tracked file operations.", True, False),
    ModuleSpec("examples", "Show command examples.", False, False),
    ModuleSpec("rename-parent", "Rename parent folder from metadata.", True, False),
    ModuleSpec("validate", "Run release checks.", False, False),
    ModuleSpec("profile", "Manage settings profiles.", True, False),
    ModuleSpec("inspect", "Inspect release folder.", False, False),
    ModuleSpec("browse", "Browse release folders.", False, False),
    ModuleSpec("sort", "Sort release folders.", True, True),
    ModuleSpec("extract", "Extract streams from media.", True, True),
    ModuleSpec("screenshot", "Capture screenshots.", True, True),
    ModuleSpec("encode", "Encode video with presets.", True, True),
    ModuleSpec("watch", "Watch folders and trigger workflows.", True, False),
    ModuleSpec("seedbox", "Seedbox transfer helpers.", True, False),
    ModuleSpec("renamer", "Normalize file/folder naming.", True, True),
    ModuleSpec("cleanmkv", "Clean/remux MKV tracks.", True, True),
    ModuleSpec("metadata", "Resolve metadata providers.", True, False),
    ModuleSpec("nfo", "Generate NFO files.", True, True),
    ModuleSpec("torrent", "Create torrent files.", True, True),
    ModuleSpec("prez", "Generate presentation files.", True, True),
    ModuleSpec("upload", "Upload release to tracker APIs.", True, False),
    ModuleSpec("pipeline", "Run full workflow pipeline.", True, True),
    ModuleSpec("batch", "Batch process releases.", True, True),
)

MODULE_INDEX = {spec.name: spec for spec in MODULE_SPECS}
_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="framekit-web-jobs")
_JOBS_LOCK = Lock()
_JOBS: dict[str, ModuleJob] = {}
_JOB_CANCEL_EVENTS: dict[str, Event] = {}
_JOB_PROCESSES: dict[str, Any] = {}
_MAX_JOBS = 200
_DB_LOCK = Lock()
_MODULE_SPEC_CACHE: dict[str, Any] | None = None
_MODULE_SPEC_CACHE_LOCK = Lock()
_PRESETS_LOCK = Lock()


class RunModuleRequest(BaseModel):
    """Request payload for generic Framekit module execution."""

    module: str
    args_text: str = ""
    dry_run: bool = True
    auto_yes: bool = False
    confirm_destructive: bool = False
    timeout_seconds: float = Field(default=1800.0, ge=1.0, le=7200.0)

    @field_validator("module")
    @classmethod
    def _validate_module(cls, value: str) -> str:
        normalized = value.strip()
        if normalized not in MODULE_INDEX:
            raise ValueError(f"Unsupported module: {value}")
        return normalized


class RunModuleResponse(BaseModel):
    """Normalized command execution response payload."""

    ok: bool
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str
    parsed_kind: str | None = None
    parsed_payload: dict[str, Any] | list[Any] | None = None


class ModulePreset(BaseModel):
    """Preset values for web workbench command form."""

    id: str
    label: str
    module: str
    args_text: str
    dry_run: bool
    auto_yes: bool
    confirm_destructive: bool


class ModuleJob(BaseModel):
    """Lifecycle snapshot for one queued module execution."""

    id: str
    status: Literal["pending", "running", "completed", "failed", "cancelled"]
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    request: RunModuleRequest
    live_stdout: str = ""
    live_stderr: str = ""
    result: RunModuleResponse | None = None
    error: str | None = None


PRESETS: tuple[ModulePreset, ...] = (
    ModulePreset(
        id="doctor-json",
        label="Doctor JSON",
        module="doctor",
        args_text="--json",
        dry_run=False,
        auto_yes=False,
        confirm_destructive=False,
    ),
    ModulePreset(
        id="inspect-release",
        label="Inspect release",
        module="inspect",
        args_text='"C:/Releases/My.Release"',
        dry_run=False,
        auto_yes=False,
        confirm_destructive=False,
    ),
    ModulePreset(
        id="pipeline-preview",
        label="Pipeline preview",
        module="pipeline",
        args_text='"C:/Releases/My.Release" --preview',
        dry_run=False,
        auto_yes=False,
        confirm_destructive=True,
    ),
    ModulePreset(
        id="renamer-dry",
        label="Renamer dry-run",
        module="renamer",
        args_text='"C:/Releases/My.Release"',
        dry_run=True,
        auto_yes=False,
        confirm_destructive=True,
    ),
    ModulePreset(
        id="cleanmkv-dry",
        label="CleanMKV dry-run",
        module="cleanmkv",
        args_text='"C:/Releases/My.Release"',
        dry_run=True,
        auto_yes=False,
        confirm_destructive=True,
    ),
    ModulePreset(
        id="nfo-dry",
        label="NFO dry-run",
        module="nfo",
        args_text='"C:/Releases/My.Release"',
        dry_run=True,
        auto_yes=False,
        confirm_destructive=True,
    ),
    ModulePreset(
        id="torrent-dry",
        label="Torrent dry-run",
        module="torrent",
        args_text='"C:/Releases/My.Release"',
        dry_run=True,
        auto_yes=False,
        confirm_destructive=True,
    ),
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _jobs_db_path() -> Path:
    base = get_cache_dir() / "web"
    base.mkdir(parents=True, exist_ok=True)
    return base / "module_jobs.sqlite3"


def _db_connect() -> sqlite3.Connection:
    connection = sqlite3.connect(_jobs_db_path())
    connection.row_factory = sqlite3.Row
    return connection


def _init_db() -> None:
    with _DB_LOCK, _db_connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS web_module_jobs (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_web_module_jobs_created_at
            ON web_module_jobs(created_at)
            """
        )
        conn.commit()


def _persist_job(job: ModuleJob) -> None:
    payload_json = job.model_dump_json()
    with _DB_LOCK, _db_connect() as conn:
        conn.execute(
            """
            INSERT INTO web_module_jobs(id, created_at, status, payload_json)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                created_at=excluded.created_at,
                status=excluded.status,
                payload_json=excluded.payload_json
            """,
            (job.id, job.created_at, job.status, payload_json),
        )
        conn.commit()


def _delete_persisted_job(job_id: str) -> None:
    with _DB_LOCK, _db_connect() as conn:
        conn.execute("DELETE FROM web_module_jobs WHERE id = ?", (job_id,))
        conn.commit()


def _load_jobs_from_db() -> None:
    with _DB_LOCK, _db_connect() as conn:
        rows = conn.execute(
            """
            SELECT payload_json
            FROM web_module_jobs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (_MAX_JOBS,),
        ).fetchall()

    recovered: dict[str, ModuleJob] = {}
    for row in rows:
        try:
            job = ModuleJob.model_validate_json(row["payload_json"])
        except Exception as exc:  # nosec B110
            logger.warning("Skipping corrupted job row from DB: {}", exc)
            continue

        if job.status in {"pending", "running"}:
            job = job.model_copy(
                update={
                    "status": "failed",
                    "finished_at": _utc_now(),
                    "error": "Interrupted by backend restart.",
                }
            )
        recovered[job.id] = job
        _JOB_CANCEL_EVENTS[job.id] = Event()

    _JOBS.clear()
    _JOBS.update(recovered)
    for job in recovered.values():
        _persist_job(job)


def _trim_jobs_if_needed() -> None:
    if len(_JOBS) <= _MAX_JOBS:
        return
    oldest = sorted(_JOBS.values(), key=lambda job: job.created_at)
    for item in oldest[: len(_JOBS) - _MAX_JOBS]:
        _JOBS.pop(item.id, None)
        _JOB_CANCEL_EVENTS.pop(item.id, None)
        _JOB_PROCESSES.pop(item.id, None)
        _delete_persisted_job(item.id)


def _parse_json_payload(stdout_text: str) -> tuple[str | None, dict[str, Any] | list[Any] | None]:
    parsed_kind: str | None = None
    parsed_payload: dict[str, Any] | list[Any] | None = None
    if stdout_text.strip():
        try:
            parsed = json.loads(stdout_text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, (dict, list)):
            parsed_kind = "json"
            parsed_payload = parsed
    return parsed_kind, parsed_payload


def list_modules() -> list[dict[str, Any]]:
    """Return module catalog exposed by web runner."""
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "destructive": spec.destructive,
            "supports_dry_run": spec.supports_dry_run,
        }
        for spec in MODULE_SPECS
    ]


def list_presets() -> list[dict[str, Any]]:
    """Return preset catalog for web workbench quick-fill."""
    return [preset.model_dump() for preset in PRESETS]


def _type_kind_for_param(param: Parameter) -> str:
    type_name = param.type.__class__.__name__.lower()
    if isinstance(param, Option):
        if getattr(param, "is_bool_flag", False):
            return "bool"
        if getattr(param, "multiple", False):
            if getattr(param.type, "choices", None):
                return "multi-choice"
            return "multi-value"
    if isinstance(param, Argument):
        if getattr(param, "nargs", 1) != 1:
            return "multi-value"
    if "int" in type_name:
        return "int"
    if "float" in type_name:
        return "float"
    if "bool" in type_name:
        return "bool"
    if "choice" in type_name:
        return "choice"
    if "path" in type_name:
        return "path"
    return "string"


def _humanize_name(value: str) -> str:
    text = value.replace("-", " ").replace("_", " ").strip()
    if not text:
        return value
    return " ".join(chunk.capitalize() for chunk in text.split())


def _param_to_spec(param: Parameter) -> dict[str, Any]:
    is_option = isinstance(param, Option)
    kind = _type_kind_for_param(param)
    option = param if is_option else None
    choices: list[str] = []
    if getattr(param.type, "choices", None):
        choices = [str(item) for item in getattr(param.type, "choices")]

    default_value = None
    if param.default is not None and param.default != ():
        default_value = param.default
        if isinstance(default_value, tuple):
            default_value = list(default_value)

    name = param.name or ""
    aliases = []
    if option is not None:
        aliases = [opt for opt in option.opts if opt]

    return {
        "kind": "option" if is_option else "argument",
        "name": name,
        "label": _humanize_name(name),
        "help": getattr(param, "help", None) or "",
        "required": bool(getattr(param, "required", False)),
        "repeatable": bool(getattr(param, "multiple", False) or getattr(param, "nargs", 1) not in (None, 1)),
        "nargs": int(getattr(param, "nargs", 1) or 1),
        "type": kind,
        "choices": choices,
        "default": default_value,
        "aliases": aliases,
        "secondary_aliases": [opt for opt in (option.secondary_opts if option else []) if opt],
        "flag_value": getattr(option, "flag_value", None) if option else None,
        "is_flag": bool(getattr(option, "is_flag", False)) if option else False,
        "is_bool_flag": bool(getattr(option, "is_bool_flag", False)) if option else False,
        "metavar": getattr(param, "make_metavar", lambda: "")() if hasattr(param, "make_metavar") else "",
    }


def _command_to_spec(command_name: str, command_obj: Command) -> dict[str, Any]:
    params = [_param_to_spec(param) for param in command_obj.params]
    return {
        "name": command_name,
        "label": _humanize_name(command_name),
        "help": command_obj.help or command_obj.short_help or "",
        "is_group": isinstance(command_obj, Group),
        "parameters": params,
    }


def _collect_subcommands(group: Group) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for command_name in sorted(group.commands):
        command_obj = group.commands.get(command_name)
        if command_obj is None:
            continue
        command_spec = _command_to_spec(command_name, command_obj)
        if isinstance(command_obj, Group):
            command_spec["subcommands"] = _collect_subcommands(command_obj)
        result.append(command_spec)
    return result


def list_modules_spec() -> dict[str, Any]:
    """Return full CLI spec for web dynamic form rendering."""
    global _MODULE_SPEC_CACHE
    if _MODULE_SPEC_CACHE is not None:
        return _MODULE_SPEC_CACHE
    with _MODULE_SPEC_CACHE_LOCK:
        if _MODULE_SPEC_CACHE is not None:
            return _MODULE_SPEC_CACHE

        destructive_index = {spec.name: spec.destructive for spec in MODULE_SPECS}
        dry_run_index = {spec.name: spec.supports_dry_run for spec in MODULE_SPECS}
        sections: dict[str, str] = {}
        for spec in MODULE_SPECS:
            sections[spec.name] = "module"

        modules: list[dict[str, Any]] = []
        for module_name in sorted(framekit_cli.commands):
            command_obj = framekit_cli.commands.get(module_name)
            if command_obj is None:
                continue
            module_spec = _command_to_spec(module_name, command_obj)
            module_spec["destructive"] = bool(destructive_index.get(module_name, False))
            module_spec["supports_dry_run"] = bool(dry_run_index.get(module_name, False))
            module_spec["group"] = sections.get(module_name, "module")
            if isinstance(command_obj, Group):
                module_spec["subcommands"] = _collect_subcommands(command_obj)
            modules.append(module_spec)

        _MODULE_SPEC_CACHE = {"modules": modules}
        return _MODULE_SPEC_CACHE


def get_settings_summary() -> dict[str, Any]:
    """Return redacted settings + key runtime paths for web setup/settings pages."""
    store = SettingsStore()
    settings = store.load()
    return {
        "settings_path": str(get_settings_path()),
        "config_dir": str(get_config_dir()),
        "cache_dir": str(get_cache_dir()),
        "settings": redact_settings(settings),
    }


SETTINGS_PATCH_ALLOWLIST: set[str] = {
    # General
    "general.locale",
    "general.log_level",
    "general.default_folder",
    "general.report_output_folder",
    # Logging
    "logging.max_size_mb",
    "logging.max_backups",
    "logging.compress_old_logs",
    "logging.retention_days",
    "logging.cleanup_on_startup",
    # Tools
    "tools.mkvmerge",
    "tools.ffmpeg",
    "tools.ffprobe",
    "tools.mediainfo",
    # Metadata
    "metadata.provider",
    "metadata.language",
    "metadata.cache_ttl_hours",
    "metadata.interactive_confirmation",
    "metadata.enabled_by_default",
    "metadata.prompt_missing_token_in_pipeline",
    "metadata.anilist_enabled",
    "metadata.anilist_language",
    "metadata.tvdb_language",
    # Upload
    "upload.enabled",
    "upload.auto_upload",
    "upload.max_parallel_uploads",
    "upload.image_host",
    "upload.torrent_client",
    "upload.torrent_client_host",
    "upload.torrent_client_port",
    "upload.torrent_client_category",
    "upload.torrent_client_tag",
    "upload.torrent_client_username",
    # Seedbox
    "seedbox.max_concurrent_uploads",
    "seedbox.history_enabled",
    # Watch
    "watch.enabled",
    "watch.notifications.enabled",
    "watch.notifications.on_watch_started",
    "watch.notifications.on_start",
    "watch.notifications.on_success",
    "watch.notifications.on_error",
    # Setup
    "setup.completed",
    "setup.prompt_on_start",
    # Pipeline
    "modules.pipeline.stop_on_error",
    "modules.pipeline.with_metadata",
    "modules.pipeline.auto_mode",
    "modules.pipeline.upload_on_failure",
    "modules.pipeline.upload_timeout",
    "modules.pipeline.enabled_modules",
    # NFO
    "modules.nfo.locale",
    "modules.nfo.active_template",
    "modules.nfo.with_metadata",
    "modules.nfo.mode",
    # Torrent
    "modules.torrent.private",
    "modules.torrent.piece_length",
    "modules.torrent.prompt_save_announce",
    # Prez
    "modules.prez.locale",
    "modules.prez.format",
    "modules.prez.html_template",
    "modules.prez.bbcode_template",
    "modules.prez.mediainfo_mode",
    "modules.prez.include_mediainfo",
    "modules.prez.with_metadata",
    # CleanMKV
    "modules.cleanmkv.default_preset",
    "modules.cleanmkv.output_dir_name",
    "modules.cleanmkv.copy_unchanged_files",
    # Renamer
    "modules.renamer.default_language_tag",
    "modules.renamer.profile",
    # Screenshot
    "modules.screenshot.target",
    # Encoder
    "modules.encoder.preset",
    "modules.encoder.output_dir_name",
}


def patch_settings_values(changes: dict[str, Any]) -> dict[str, Any]:
    """Patch a restricted set of settings keys and return updated summary."""
    if not changes:
        return get_settings_summary()
    store = SettingsStore()
    for key, value in changes.items():
        if key not in SETTINGS_PATCH_ALLOWLIST:
            raise ValueError(f"Unsupported settings key: {key}")
        store.set(key, value)
    return get_settings_summary()


def read_log_lines(*, lines: int = 200, level: str | None = None) -> list[dict[str, Any]]:
    """Return last N lines from the primary log file as parsed dicts."""
    log_file = get_cache_dir() / "logs" / "framekit.log"
    if not log_file.exists():
        return []
    try:
        raw = log_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    result: list[dict[str, Any]] = []
    level_upper = level.upper() if level else None
    for raw_line in raw.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            entry: dict[str, Any] = json.loads(stripped)
        except json.JSONDecodeError:
            entry = {"message": stripped, "level": "INFO", "time": ""}
        if level_upper and str(entry.get("level", "")).upper() != level_upper:
            continue
        result.append(entry)
    return result[-lines:]


def list_seedboxes_summary() -> list[dict[str, Any]]:
    """Return configured seedboxes summary from settings."""
    store = SettingsStore()
    settings = store.load()
    seedbox_cfg = settings.get("seedbox", {})
    default_name = str(seedbox_cfg.get("default", "") or "").strip()
    seedboxes = seedbox_cfg.get("seedboxes", [])
    result: list[dict[str, Any]] = []
    if not isinstance(seedboxes, list):
        return result
    for item in seedboxes:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "") or "").strip()
        result.append(
            {
                "name": name,
                "rclone_remote": str(item.get("rclone_remote", "") or ""),
                "remote_base_path": str(item.get("remote_base_path", "/") or "/"),
                "max_concurrent_uploads": item.get("max_concurrent_uploads"),
                "bandwidth_limit": str(item.get("bandwidth_limit", "") or ""),
                "is_default": bool(name and name == default_name),
            }
        )
    return result


def get_seedbox_default_by_profile() -> dict[str, str]:
    """Return the Framekit profile → seedbox name mapping from settings."""
    store = SettingsStore()
    settings = store.load()
    raw = settings.get("seedbox", {}).get("default_by_profile", {})
    if not isinstance(raw, dict):
        return {}
    return {
        str(k).strip(): str(v).strip()
        for k, v in raw.items()
        if str(k).strip() and str(v).strip()
    }


def create_seedbox_profile(
    *,
    name: str,
    rclone_remote: str,
    remote_base_path: str,
    max_concurrent_uploads: int | None = None,
    bandwidth_limit: str = "",
    set_default: bool = False,
) -> list[dict[str, Any]]:
    """Create one seedbox profile in settings and return updated summary."""
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("seedbox name is required")
    if ":" in normalized_name:
        raise ValueError("seedbox name must not contain ':'")
    normalized_remote = rclone_remote.strip().rstrip(":")
    if not normalized_remote:
        raise ValueError("rclone_remote is required")
    normalized_base = remote_base_path.strip() or "/"
    if not normalized_base.startswith("/"):
        raise ValueError("remote_base_path must start with '/'")
    if max_concurrent_uploads is not None and (max_concurrent_uploads < 1 or max_concurrent_uploads > 32):
        raise ValueError("max_concurrent_uploads must be between 1 and 32")
    if bandwidth_limit.strip():
        bandwidth_value = bandwidth_limit.strip()
        if not any(ch.isdigit() for ch in bandwidth_value):
            raise ValueError("bandwidth_limit must include a numeric value")
    store = SettingsStore()
    settings = store.load()
    seedbox_cfg = settings.setdefault("seedbox", {})
    seedboxes_raw = seedbox_cfg.get("seedboxes", [])
    seedboxes: list[dict[str, Any]] = list(seedboxes_raw) if isinstance(seedboxes_raw, list) else []
    if any(str(item.get("name", "") or "").strip() == normalized_name for item in seedboxes if isinstance(item, dict)):
        raise ValueError(f"seedbox '{normalized_name}' already exists")
    profile: dict[str, Any] = {
        "name": normalized_name,
        "rclone_remote": normalized_remote,
        "remote_base_path": normalized_base,
    }
    if max_concurrent_uploads is not None:
        profile["max_concurrent_uploads"] = max(1, int(max_concurrent_uploads))
    if bandwidth_limit.strip():
        profile["bandwidth_limit"] = bandwidth_limit.strip()
    seedboxes.append(profile)
    seedbox_cfg["seedboxes"] = seedboxes
    if set_default or not str(seedbox_cfg.get("default", "") or "").strip():
        seedbox_cfg["default"] = normalized_name
    settings["seedbox"] = seedbox_cfg
    store.save(settings)
    return list_seedboxes_summary()


def remove_seedbox_profile(name: str) -> list[dict[str, Any]]:
    """Remove one seedbox profile and return updated summary."""
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("seedbox name is required")
    store = SettingsStore()
    settings = store.load()
    seedbox_cfg = settings.setdefault("seedbox", {})
    seedboxes_raw = seedbox_cfg.get("seedboxes", [])
    seedboxes: list[dict[str, Any]] = list(seedboxes_raw) if isinstance(seedboxes_raw, list) else []
    filtered = [
        item
        for item in seedboxes
        if not (isinstance(item, dict) and str(item.get("name", "") or "").strip() == normalized_name)
    ]
    if len(filtered) == len(seedboxes):
        raise ValueError(f"seedbox '{normalized_name}' not found")
    seedbox_cfg["seedboxes"] = filtered
    current_default = str(seedbox_cfg.get("default", "") or "").strip()
    if current_default == normalized_name:
        seedbox_cfg["default"] = str(filtered[0].get("name", "") or "").strip() if filtered else ""
    settings["seedbox"] = seedbox_cfg
    store.save(settings)
    return list_seedboxes_summary()


def set_default_seedbox(name: str, *, profile_name: str | None = None) -> list[dict[str, Any]]:
    """Set seedbox as global default (or per-profile when profile_name given)."""
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("seedbox name is required")
    store = SettingsStore()
    settings = store.load()
    seedbox_cfg = settings.setdefault("seedbox", {})
    seedboxes_raw = seedbox_cfg.get("seedboxes", [])
    seedboxes: list[dict[str, Any]] = list(seedboxes_raw) if isinstance(seedboxes_raw, list) else []
    if not any(
        isinstance(item, dict) and str(item.get("name", "") or "").strip() == normalized_name
        for item in seedboxes
    ):
        raise ValueError(f"seedbox '{normalized_name}' not found")
    if profile_name:
        mapping = seedbox_cfg.get("default_by_profile", {})
        if not isinstance(mapping, dict):
            mapping = {}
        mapping[profile_name.strip()] = normalized_name
        seedbox_cfg["default_by_profile"] = mapping
    else:
        seedbox_cfg["default"] = normalized_name
    settings["seedbox"] = seedbox_cfg
    store.save(settings)
    return list_seedboxes_summary()


def list_upload_trackers_summary() -> list[dict[str, Any]]:
    """Return configured upload trackers summary from settings."""
    store = SettingsStore()
    settings = store.load()
    upload_cfg = settings.get("upload", {})
    trackers = upload_cfg.get("trackers", [])
    result: list[dict[str, Any]] = []
    if not isinstance(trackers, list):
        return result
    for item in trackers:
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "name": str(item.get("name", "") or ""),
                "type": str(item.get("type", item.get("engine", "")) or ""),
                "url": str(item.get("url", item.get("base_url", "")) or ""),
                "enabled": bool(item.get("enabled", True)),
            }
        )
    return result


def get_upload_tracker_info(name: str) -> dict[str, Any] | None:
    """Return one tracker details when available."""
    tracker_name = name.strip()
    if not tracker_name:
        return None
    return UploadService.get_tracker_info(tracker_name)


def get_upload_state() -> dict[str, bool]:
    """Return upload module toggles."""
    return {
        "enabled": bool(UploadService.is_upload_enabled()),
        "auto_upload": bool(UploadService.is_auto_upload_enabled()),
    }


def set_upload_state(*, enabled: bool, auto_upload: bool | None = None) -> dict[str, bool]:
    """Persist upload module toggles and return effective state."""
    UploadService.set_upload_enabled(enabled=enabled, auto_upload=auto_upload)
    return get_upload_state()


def list_upload_history(limit: int = 20) -> list[dict[str, Any]]:
    """Return upload history entries."""
    return UploadService.get_upload_history(limit=limit)


def list_seedbox_history(limit: int = 50, seedbox_name: str | None = None) -> list[dict[str, Any]]:
    """Return seedbox transfer history entries from NDJSON store."""
    history_path = get_config_dir() / "seedbox" / "history.ndjson"
    if not history_path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in reversed(history_path.read_text(encoding="utf-8").splitlines()):
        raw = line.strip()
        if not raw:
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        if seedbox_name and str(item.get("seedbox", "")).strip() != seedbox_name:
            continue
        entries.append(item)
        if len(entries) >= limit:
            break
    return entries


def _list_yaml_presets(directory: Path, source: str) -> list[dict[str, Any]]:
    if not directory.exists():
        return []
    result: list[dict[str, Any]] = []
    for file_path in sorted(directory.glob("*.yaml")):
        result.append(
            {
                "name": file_path.stem,
                "path": str(file_path),
                "source": source,
            }
        )
    return result


def _list_template_names(directory: Path) -> list[str]:
    if not directory.exists():
        return []
    names: set[str] = set()
    for file_path in directory.glob("*.jinja2"):
        stem = file_path.stem
        if stem.startswith("_"):
            continue
        parts = stem.rsplit(".", 1)
        names.add(parts[0] if len(parts) == 2 else stem)
    return sorted(names)


def _list_prez_html_template_names(directory: Path) -> list[str]:
    if not directory.exists():
        return []
    names: set[str] = set()
    for file_path in directory.glob("*.jinja2"):
        stem = file_path.stem
        if stem.startswith("_"):
            continue
        parts = stem.rsplit(".", 1)
        names.add(parts[0] if len(parts) == 2 else stem)
    return sorted(names)


def list_pipeline_batch_resources() -> dict[str, Any]:
    """Return pipeline/batch helper resources for zero-typing web forms."""
    settings_obj = Settings()
    announce_urls = settings_obj.get_torrent_announces()
    selected_announce = settings_obj.get_selected_announce()

    announce_labels = _load_announce_labels(SettingsStore().load())
    announces: list[dict[str, Any]] = [
        {
            "value": url,
            "label": announce_labels.get(url, ""),
            "is_selected": bool(selected_announce and url == selected_announce),
        }
        for url in announce_urls
        if url
    ]

    pipeline_presets = _list_yaml_presets(get_pipeline_presets_dir(), "bundled")
    prez_presets = _list_yaml_presets(get_prez_presets_dir(), "bundled")

    nfo_templates_dir = Path(__file__).resolve().parent.parent / "templates" / "nfo"
    prez_bbcode_dir = Path(__file__).resolve().parent.parent / "templates" / "prez" / "bbcode"
    prez_html_dir = Path(__file__).resolve().parent.parent / "templates" / "prez" / "html" / "generated"

    banner_previews: list[dict[str, Any]] = []
    # Banner preview images are served from the banners release archive.
    # URLs are only generated when the archive is confirmed reachable.
    # Return empty list to avoid 404 noise until banners are published.

    return {
        "pipeline_presets": pipeline_presets,
        "prez_presets": prez_presets,
        "announces": announces,
        "selected_announce": selected_announce,
        "nfo_templates": _list_template_names(nfo_templates_dir),
        "prez_templates": {
            "bbcode": _list_template_names(prez_bbcode_dir),
            "html": _list_prez_html_template_names(prez_html_dir),
        },
        "banner_previews": banner_previews,
        "cleanmkv_presets": list_cleanmkv_preset_names(),
        "renamer_profiles": list_renamer_profile_names(),
        "encoder_presets": list_encoder_preset_names(),
    }


def list_cleanmkv_preset_names() -> list[str]:
    """Return available CleanMKV preset names (builtin + user YAML files)."""
    from framekit.modules.cleanmkv.planner import BUILTIN_PRESETS

    names: list[str] = list(BUILTIN_PRESETS.keys())
    user_dir = get_cleanmkv_presets_dir()
    if user_dir.exists():
        for file_path in sorted(user_dir.glob("*.yaml")):
            if file_path.stem not in names:
                names.append(file_path.stem)
    return names


def list_renamer_profile_names() -> list[str]:
    """Return available Renamer profile names (builtin + user YAML files)."""
    from framekit.modules.renamer.profiles import BUILTIN_PROFILES
    from framekit.core.paths import get_config_dir

    names: list[str] = list(BUILTIN_PROFILES.keys())
    user_dir = get_config_dir() / "profiles" / "renamer"
    if user_dir.exists():
        for file_path in sorted(user_dir.glob("*.yaml")):
            if file_path.stem not in names:
                names.append(file_path.stem)
    return names


def list_encoder_preset_names() -> list[str]:
    """Return unique encoder preset names (module auto-detects codec direction)."""
    from framekit.modules.encoder.presets import PresetLoader

    loader = PresetLoader()  # uses project presets dir, not config dir
    presets = loader.list_presets()
    seen: set[str] = set()
    for names in presets.values():
        seen.update(names)
    return sorted(seen)


def get_vault_status_info() -> dict[str, Any]:
    """Return secure vault status."""
    try:
        return Settings().get_vault_status()
    except Exception as exc:
        return {"enabled": False, "error": str(exc)}


def get_tmdb_token_value() -> dict[str, Any]:
    """Return TMDB token (decrypted) and whether it is set."""
    try:
        token = Settings().get_tmdb_token()
        return {"token": token, "is_set": bool(token)}
    except Exception as exc:
        return {"token": "", "is_set": False, "error": str(exc)}


def set_tmdb_token_value(token: str) -> dict[str, Any]:
    """Store TMDB token (encrypted if vault available)."""
    Settings().set_tmdb_token(token.strip())
    return get_tmdb_token_value()


def _load_announce_labels(settings_raw: dict[str, Any]) -> dict[str, str]:
    modules_cfg = settings_raw.get("modules", {})
    if not isinstance(modules_cfg, dict):
        return {}
    torrent_cfg = modules_cfg.get("torrent", {})
    if not isinstance(torrent_cfg, dict):
        return {}
    raw_labels = torrent_cfg.get("announce_labels", {})
    if not isinstance(raw_labels, dict):
        return {}
    return {k: str(v) for k, v in raw_labels.items()}


def list_torrent_announces_info() -> dict[str, Any]:
    """Return all announce URLs (decrypted), their labels, and which is selected."""
    settings_obj = Settings()
    urls = settings_obj.get_torrent_announces()
    selected = settings_obj.get_selected_announce()
    announce_labels = _load_announce_labels(SettingsStore().load())
    announces = [
        {
            "value": url,
            "label": announce_labels.get(url, ""),
            "is_selected": bool(selected and url == selected),
        }
        for url in urls
    ]
    return {"announces": announces, "selected_announce": selected}


def add_torrent_announce_url(url: str) -> dict[str, Any]:
    """Append one announce URL to the vault-backed list."""
    url = url.strip()
    if not url:
        raise ValueError("announce URL is required")
    settings_obj = Settings()
    current = settings_obj.get_torrent_announces()
    if url in current:
        raise ValueError("announce URL already exists")
    settings_obj.set_torrent_announces([*current, url])
    return list_torrent_announces_info()


def remove_torrent_announce_url(index: int) -> dict[str, Any]:
    """Remove announce URL by index."""
    settings_obj = Settings()
    current = settings_obj.get_torrent_announces()
    if index < 0 or index >= len(current):
        raise ValueError(f"index {index} out of range (0–{len(current) - 1})")
    updated = [url for i, url in enumerate(current) if i != index]
    settings_obj.set_torrent_announces(updated)
    return list_torrent_announces_info()


def select_torrent_announce_url(url: str) -> dict[str, Any]:
    """Set the selected announce URL."""
    Settings().set_selected_announce(url.strip())
    return list_torrent_announces_info()


def rename_torrent_announce_label(index: int, label: str) -> dict[str, Any]:
    """Set or clear the display label for an announce URL by index."""
    settings_obj = Settings()
    urls = settings_obj.get_torrent_announces()
    if index < 0 or index >= len(urls):
        raise ValueError(f"index {index} out of range (0–{len(urls) - 1})")
    url = urls[index]
    store = SettingsStore()
    settings_raw = store.load()
    modules_cfg = settings_raw.setdefault("modules", {})
    if not isinstance(modules_cfg, dict):
        modules_cfg = {}
        settings_raw["modules"] = modules_cfg
    torrent_cfg = modules_cfg.setdefault("torrent", {})
    if not isinstance(torrent_cfg, dict):
        torrent_cfg = {}
        modules_cfg["torrent"] = torrent_cfg
    announce_labels: dict[str, str] = {}
    raw = torrent_cfg.get("announce_labels", {})
    if isinstance(raw, dict):
        announce_labels = {k: str(v) for k, v in raw.items()}
    label = label.strip()
    if label:
        announce_labels[url] = label
    else:
        announce_labels.pop(url, None)
    torrent_cfg["announce_labels"] = announce_labels
    store.save(settings_raw)
    return list_torrent_announces_info()


_VALID_TOKEN_PROVIDERS = {"tmdb", "tvdb", "anilist", "trakt"}


def get_provider_token_value(provider: str) -> dict[str, Any]:
    """Return a metadata provider API token and whether it is set."""
    if provider not in _VALID_TOKEN_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}")
    try:
        s = Settings()
        if provider == "tmdb":
            token = s.get_tmdb_token()
            vault = s.get_vault()
            return {"provider": "tmdb", "token": token, "is_set": bool(token), "encrypted": bool(vault)}
        vault = s.get_vault()
        if vault:
            token = str(vault.retrieve(f"metadata_token_{provider}", default="") or "")
            return {"provider": provider, "token": token, "is_set": bool(token), "encrypted": True}
        data = s.load()
        token = str(((data.get("metadata") or {}).get("tokens") or {}).get(provider, "") or "")
        return {"provider": provider, "token": token, "is_set": bool(token), "encrypted": False}
    except Exception as exc:
        return {"provider": provider, "token": "", "is_set": False, "encrypted": False, "error": str(exc)}


def set_provider_token_value(provider: str, token: str) -> dict[str, Any]:
    """Store a metadata provider API token (vault-encrypted when available)."""
    if provider not in _VALID_TOKEN_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}")
    token = token.strip()
    if provider == "tmdb":
        Settings().set_tmdb_token(token)
        return get_provider_token_value("tmdb")
    s = Settings()
    vault = s.get_vault()
    if vault:
        vault.store(f"metadata_token_{provider}", token)
    else:
        data = s.load()
        data.setdefault("metadata", {}).setdefault("tokens", {})[provider] = token
        s.save(data)
    return get_provider_token_value(provider)


_VALID_PRESET_KINDS: frozenset[str] = frozenset({"pipeline", "prez", "cleanmkv"})
_VALID_IMAGE_HOSTS = {"imgbb", "imgbox", "ptpimg", "freeimage"}


def _safe_preset_filename(name: str) -> str:
    import re
    cleaned = re.sub(r"[^\w\-.]", "_", name.strip())
    return cleaned or "preset"


def get_image_host_key(host: str) -> dict[str, Any]:
    """Return API key for an image host (decrypted from vault when available)."""
    if host not in _VALID_IMAGE_HOSTS:
        raise ValueError(f"Unsupported image host: {host}")
    s = Settings()
    vault = s.get_vault()
    if vault:
        key = str(vault.retrieve(f"imghost_key_{host}", default="") or "")
        return {"host": host, "key": key, "is_set": bool(key), "encrypted": True}
    data = s.load()
    key = str(((data.get("upload") or {}).get("image_host_keys") or {}).get(host, "") or "")
    return {"host": host, "key": key, "is_set": bool(key), "encrypted": False}


def set_image_host_key(host: str, key: str) -> dict[str, Any]:
    """Store API key for an image host (vault-encrypted when available)."""
    if host not in _VALID_IMAGE_HOSTS:
        raise ValueError(f"Unsupported image host: {host}")
    key = key.strip()
    s = Settings()
    vault = s.get_vault()
    if vault:
        vault.store(f"imghost_key_{host}", key)
    else:
        data = s.load()
        data.setdefault("upload", {}).setdefault("image_host_keys", {})[host] = key
        s.save(data)
    return get_image_host_key(host)


def get_torrent_client_password() -> dict[str, Any]:
    """Return torrent client password status without revealing the value."""
    s = Settings()
    vault = s.get_vault()
    if vault:
        pwd = vault.retrieve("upload_torrent_client_password", default="")
        return {"is_set": bool(pwd), "encrypted": True}
    data = s.load()
    pwd = str((data.get("upload") or {}).get("torrent_client_password", "") or "")
    return {"is_set": bool(pwd), "encrypted": False}


def set_torrent_client_password(password: str) -> dict[str, Any]:
    """Store torrent client password (vault-encrypted when available)."""
    password = password.strip()
    s = Settings()
    vault = s.get_vault()
    if vault:
        vault.store("upload_torrent_client_password", password)
        data = s.load()
        if "upload" in data and "torrent_client_password" in data["upload"]:
            del data["upload"]["torrent_client_password"]
            s.save(data)
    else:
        data = s.load()
        data.setdefault("upload", {})["torrent_client_password"] = password
        s.save(data)
    return get_torrent_client_password()


def _preset_dir_for_kind(kind: str) -> Path:
    if kind == "pipeline":
        return get_pipeline_presets_dir()
    if kind == "cleanmkv":
        return get_cleanmkv_presets_dir()
    if kind == "prez":
        return get_prez_presets_dir()
    raise ValueError(f"Invalid preset kind: {kind}")


def create_yaml_preset(kind: str, name: str, content: str) -> dict[str, Any]:
    """Write a new YAML preset file for pipeline, prez, or cleanmkv."""
    if kind not in _VALID_PRESET_KINDS:
        raise ValueError(f"Invalid preset kind: {kind}")
    with _PRESETS_LOCK:
        preset_dir = _preset_dir_for_kind(kind)
        preset_dir.mkdir(parents=True, exist_ok=True)
        safe_name = _safe_preset_filename(name)
        if not safe_name:
            raise ValueError("Preset name is required")
        file_path = preset_dir / f"{safe_name}.yaml"
        if not str(file_path.resolve()).startswith(str(preset_dir.resolve())):
            raise ValueError("Invalid preset name")
        if file_path.exists():
            raise ValueError(f"Preset '{safe_name}' already exists")
        try:
            import yaml as _yaml
            _yaml.safe_load(content)
        except Exception as exc:
            raise ValueError(f"Invalid YAML: {exc}") from exc
        try:
            file_path.write_text(content, encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"Could not write preset: {exc}") from exc
    return {"name": safe_name, "path": str(file_path), "source": "user", "kind": kind}


def delete_yaml_preset(kind: str, name: str) -> dict[str, Any]:
    """Delete a YAML preset file for pipeline, prez, or cleanmkv."""
    if kind not in _VALID_PRESET_KINDS:
        raise ValueError(f"Invalid preset kind: {kind}")
    with _PRESETS_LOCK:
        preset_dir = _preset_dir_for_kind(kind)
        safe_name = _safe_preset_filename(name)
        file_path = preset_dir / f"{safe_name}.yaml"
        if not str(file_path.resolve()).startswith(str(preset_dir.resolve())):
            raise ValueError("Invalid preset name")
        if not file_path.exists():
            raise ValueError(f"Preset '{safe_name}' not found")
        try:
            file_path.unlink()
        except FileNotFoundError:
            raise ValueError(f"Preset '{safe_name}' not found")
        except OSError as exc:
            raise ValueError(f"Could not delete preset: {exc}") from exc
    return {"name": safe_name, "deleted": True, "kind": kind}


def delete_all_yaml_presets(kind: str) -> dict[str, Any]:
    """Delete all user YAML preset files for a given kind (pipeline, prez, or cleanmkv)."""
    if kind not in _VALID_PRESET_KINDS:
        raise ValueError(f"Invalid preset kind: {kind}")
    with _PRESETS_LOCK:
        preset_dir = _preset_dir_for_kind(kind)
        deleted: list[str] = []
        if preset_dir.exists():
            for file_path in sorted(preset_dir.glob("*.yaml")):
                try:
                    file_path.unlink()
                    deleted.append(file_path.stem)
                except OSError:
                    pass
    return {"kind": kind, "deleted": deleted, "count": len(deleted)}


def list_settings_profiles() -> dict[str, Any]:
    """Return all settings profiles and the currently active one."""
    from framekit.core.settings.profiles import get_active_profile, list_profiles, load_profile

    active = get_active_profile()
    result: list[dict[str, Any]] = []
    for name in list_profiles():
        try:
            data = load_profile(name)
            desc = str(data.get("description", "") or "")
            overrides = data.get("overrides", {})
        except Exception:
            desc = ""
            overrides = {}
        result.append({"name": name, "description": desc, "active": name == active, "overrides": overrides})
    return {"profiles": result, "active": active}


def activate_settings_profile(name: str) -> dict[str, Any]:
    """Set the active settings profile and apply its overrides."""
    from framekit.core.settings.profiles import get_active_profile, load_profile, set_active_profile

    name = name.strip()
    if not name:
        raise ValueError("profile name is required")
    data = load_profile(name)
    overrides: dict[str, Any] = data.get("overrides", {}) or {}
    store = SettingsStore()
    settings = store.load()
    for key, value in overrides.items():
        parts = key.split(".")
        node: Any = settings
        for part in parts[:-1]:
            if isinstance(node, dict):
                node = node.setdefault(part, {})
        if isinstance(node, dict):
            node[parts[-1]] = value
    store.save(settings)
    set_active_profile(name)
    return list_settings_profiles()


def deactivate_settings_profile() -> dict[str, Any]:
    """Clear the active settings profile."""
    from framekit.core.settings.profiles import set_active_profile

    set_active_profile(None)
    return list_settings_profiles()


def create_settings_profile(
    name: str,
    description: str = "",
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create or overwrite a settings profile and return updated list."""
    from framekit.core.settings.profiles import save_profile

    name = name.strip()
    if not name:
        raise ValueError("profile name is required")
    save_profile(name, overrides or {}, description=description)
    return list_settings_profiles()


def delete_settings_profile(name: str) -> dict[str, Any]:
    """Delete a settings profile and return updated list."""
    from framekit.core.settings.profiles import delete_profile

    name = name.strip()
    if not name:
        raise ValueError("profile name is required")
    deleted = delete_profile(name)
    if not deleted:
        raise ValueError(f"profile not found: {name}")
    return list_settings_profiles()


def _get_alias_manager() -> Any:
    from framekit.core.aliases import AliasManager
    from framekit.core.settings import SettingsStore as _Store

    return AliasManager(_Store(get_settings_path()))


def _alias_to_dict(alias: Any, kind: str) -> dict[str, Any]:
    return {
        "name": alias.name,
        "command": alias.command,
        "description": alias.description,
        "enabled": alias.enabled,
        "kind": kind,
    }


def list_aliases_summary() -> list[dict[str, Any]]:
    """Return all aliases (user + builtin) sorted by name."""
    mgr = _get_alias_manager()
    result = []
    for name, alias in sorted(mgr.list_aliases(user_only=True).items()):
        result.append(_alias_to_dict(alias, "user"))
    for name, alias in sorted(mgr.list_aliases(builtin_only=True).items()):
        result.append(_alias_to_dict(alias, "builtin"))
    return result


def add_alias_entry(
    name: str, command: str, description: str = "", enabled: bool = True
) -> list[dict[str, Any]]:
    """Create a new user alias and return updated list."""
    from framekit.core.aliases import AliasError

    try:
        _get_alias_manager().add_alias(
            name=name, command=command, description=description, enabled=enabled
        )
    except AliasError as exc:
        raise ValueError(str(exc)) from exc
    return list_aliases_summary()


def remove_alias_entry(name: str) -> list[dict[str, Any]]:
    """Delete a user alias and return updated list."""
    from framekit.core.aliases import AliasError

    try:
        _get_alias_manager().remove_alias(name)
    except AliasError as exc:
        raise ValueError(str(exc)) from exc
    return list_aliases_summary()


def enable_alias_entry(name: str) -> list[dict[str, Any]]:
    """Enable an alias and return updated list."""
    from framekit.core.aliases import AliasError

    try:
        _get_alias_manager().enable_alias(name)
    except AliasError as exc:
        raise ValueError(str(exc)) from exc
    return list_aliases_summary()


def disable_alias_entry(name: str) -> list[dict[str, Any]]:
    """Disable an alias and return updated list."""
    from framekit.core.aliases import AliasError

    try:
        _get_alias_manager().disable_alias(name)
    except AliasError as exc:
        raise ValueError(str(exc)) from exc
    return list_aliases_summary()


def check_tools() -> dict[str, Any]:
    """Check each configured external tool via shutil.which and return status."""
    import shutil

    store = SettingsStore()
    settings = store.load()
    tools_cfg = settings.get("tools", {})

    tool_names = {
        "mkvmerge": tools_cfg.get("mkvmerge") or "mkvmerge",
        "ffmpeg": tools_cfg.get("ffmpeg") or "ffmpeg",
        "ffprobe": tools_cfg.get("ffprobe") or "ffprobe",
        "mediainfo": tools_cfg.get("mediainfo") or "mediainfo",
    }

    results = []
    for name, binary in tool_names.items():
        resolved = shutil.which(binary)
        results.append({
            "name": name,
            "binary": binary,
            "ok": resolved is not None,
            "path": resolved or "",
        })
    return {"tools": results}


def list_watch_folders() -> list[dict[str, Any]]:
    """Return the configured watch folders list."""
    store = SettingsStore()
    settings = store.load()
    folders_raw = settings.get("watch", {}).get("folders", [])
    if not isinstance(folders_raw, list):
        return []
    result = []
    for item in folders_raw:
        if isinstance(item, dict):
            result.append({
                "path": str(item.get("path", "") or ""),
                "preset": str(item.get("preset", "default") or "default"),
                "enabled": bool(item.get("enabled", True)),
            })
        elif isinstance(item, str) and item.strip():
            result.append({"path": item.strip(), "preset": "default", "enabled": True})
    return result


def add_watch_folder(path: str, preset: str = "default") -> list[dict[str, Any]]:
    """Append a watch folder and return updated list."""
    normalized = path.strip()
    if not normalized:
        raise ValueError("path is required")
    store = SettingsStore()
    settings = store.load()
    watch_cfg = settings.setdefault("watch", {})
    folders_raw = watch_cfg.get("folders", [])
    folders: list[Any] = list(folders_raw) if isinstance(folders_raw, list) else []
    for item in folders:
        item_path = str(item.get("path", "") if isinstance(item, dict) else item).strip()
        if item_path == normalized:
            raise ValueError(f"folder '{normalized}' already registered")
    folders.append({"path": normalized, "preset": (preset or "default").strip(), "enabled": True})
    watch_cfg["folders"] = folders
    settings["watch"] = watch_cfg
    store.save(settings)
    return list_watch_folders()


def remove_watch_folder(index: int) -> list[dict[str, Any]]:
    """Remove a watch folder by index and return updated list."""
    store = SettingsStore()
    settings = store.load()
    watch_cfg = settings.setdefault("watch", {})
    folders_raw = watch_cfg.get("folders", [])
    folders: list[Any] = list(folders_raw) if isinstance(folders_raw, list) else []
    if index < 0 or index >= len(folders):
        raise ValueError(f"index {index} out of range")
    folders.pop(index)
    watch_cfg["folders"] = folders
    settings["watch"] = watch_cfg
    store.save(settings)
    return list_watch_folders()


def run_module_command(request: RunModuleRequest) -> RunModuleResponse:
    """Execute requested Framekit module through CLI subprocess."""
    spec = MODULE_INDEX[request.module]

    if spec.destructive and not request.confirm_destructive:
        raise ValueError(
            f"Module '{request.module}' flagged destructive. Set confirm_destructive=true."
        )

    user_args = shlex.split(request.args_text) if request.args_text.strip() else []
    argv: list[str] = [sys.executable, "-m", "framekit", request.module, *user_args]

    if request.dry_run and spec.supports_dry_run and "--dry-run" not in argv:
        argv.append("--dry-run")
    if request.auto_yes and "--yes" not in argv and "-y" not in argv:
        argv.append("--yes")

    try:
        completed = run_safe(
            argv,
            timeout=request.timeout_seconds,
            check=False,
            capture_output=True,
        )
    except SafeSubprocessError as exc:
        return RunModuleResponse(
            ok=False,
            argv=argv,
            returncode=exc.returncode or 1,
            stdout="",
            stderr=str(exc),
        )

    parsed_kind, parsed_payload = _parse_json_payload(completed.stdout)

    return RunModuleResponse(
        ok=completed.returncode == 0,
        argv=argv,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        parsed_kind=parsed_kind,
        parsed_payload=parsed_payload,
    )


def _build_module_argv(request: RunModuleRequest) -> list[str]:
    spec = MODULE_INDEX[request.module]
    if spec.destructive and not request.confirm_destructive:
        raise ValueError(
            f"Module '{request.module}' flagged destructive. Set confirm_destructive=true."
        )

    user_args = shlex.split(request.args_text) if request.args_text.strip() else []
    argv: list[str] = [sys.executable, "-m", "framekit", request.module, *user_args]
    if request.dry_run and spec.supports_dry_run and "--dry-run" not in argv:
        argv.append("--dry-run")
    if request.auto_yes and "--yes" not in argv and "-y" not in argv:
        argv.append("--yes")
    return argv


def _run_module_command_cancellable(
    request: RunModuleRequest,
    *,
    job_id: str,
    cancel_event: Event,
    on_output: Callable[[str, str], None] | None = None,
) -> RunModuleResponse:
    argv = _build_module_argv(request)
    process: Any = None
    stdout_buffer: list[str] = []
    stderr_buffer: list[str] = []
    output_queue: SimpleQueue[tuple[str, str]] = SimpleQueue()
    stop_readers = Event()

    def _reader(stream_name: str, stream_obj: Any) -> None:
        if stream_obj is None:
            return
        try:
            while not stop_readers.is_set():
                chunk = stream_obj.readline()
                if not chunk:
                    break
                output_queue.put((stream_name, chunk))
        except Exception as exc:
            logger.warning("Job output reader error ({}): {}", stream_name, exc)
            return

    def _drain_queue() -> bool:
        changed = False
        while True:
            try:
                stream_name, chunk = output_queue.get_nowait()
            except Empty:
                break
            if stream_name == "stdout":
                stdout_buffer.append(chunk)
            else:
                stderr_buffer.append(chunk)
            changed = True
        if changed and on_output is not None:
            on_output("".join(stdout_buffer), "".join(stderr_buffer))
        return changed

    try:
        process = popen_safe(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
        )
        with _JOBS_LOCK:
            _JOB_PROCESSES[job_id] = process
        stdout_thread = Thread(
            target=_reader,
            args=("stdout", process.stdout),
            daemon=True,
            name=f"framekit-web-{job_id}-stdout",
        )
        stderr_thread = Thread(
            target=_reader,
            args=("stderr", process.stderr),
            daemon=True,
            name=f"framekit-web-{job_id}-stderr",
        )
        stdout_thread.start()
        stderr_thread.start()

        started = monotonic()
        while True:
            _drain_queue()
            if cancel_event.is_set():
                process.terminate()
                try:
                    process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                stop_readers.set()
                stdout_thread.join(timeout=2.0)
                stderr_thread.join(timeout=2.0)
                _drain_queue()
                stdout_text = "".join(stdout_buffer)
                stderr_text = "".join(stderr_buffer)
                return RunModuleResponse(
                    ok=False,
                    argv=argv,
                    returncode=130,
                    stdout=stdout_text or "",
                    stderr=(stderr_text or "") + "\nCancelled by user.",
                )

            if monotonic() - started > request.timeout_seconds:
                process.terminate()
                try:
                    process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                stop_readers.set()
                stdout_thread.join(timeout=2.0)
                stderr_thread.join(timeout=2.0)
                _drain_queue()
                stdout_text = "".join(stdout_buffer)
                stderr_text = "".join(stderr_buffer)
                return RunModuleResponse(
                    ok=False,
                    argv=argv,
                    returncode=124,
                    stdout=stdout_text or "",
                    stderr=(stderr_text or "") + f"\nTimed out after {request.timeout_seconds}s.",
                )

            if process.poll() is not None:
                stop_readers.set()
                stdout_thread.join(timeout=2.0)
                stderr_thread.join(timeout=2.0)
                _drain_queue()
                stdout_text = "".join(stdout_buffer)
                stderr_text = "".join(stderr_buffer)
                parsed_kind, parsed_payload = _parse_json_payload(stdout_text)

                return RunModuleResponse(
                    ok=(process.returncode or 0) == 0,
                    argv=argv,
                    returncode=process.returncode or 0,
                    stdout=stdout_text,
                    stderr=stderr_text,
                    parsed_kind=parsed_kind,
                    parsed_payload=parsed_payload,
                )

            sleep(0.2)
    except SafeSubprocessError as exc:
        return RunModuleResponse(
            ok=False,
            argv=argv,
            returncode=exc.returncode or 1,
            stdout="",
            stderr=str(exc),
        )
    finally:
        with _JOBS_LOCK:
            _JOB_PROCESSES.pop(job_id, None)


def enqueue_module_job(request: RunModuleRequest) -> ModuleJob:
    """Queue one module execution and return initial pending job snapshot."""
    job = ModuleJob(
        id=str(uuid4()),
        status="pending",
        created_at=_utc_now(),
        request=request,
    )
    with _JOBS_LOCK:
        _JOBS[job.id] = job
        _JOB_CANCEL_EVENTS[job.id] = Event()
        _persist_job(job)
        _trim_jobs_if_needed()

    def _run() -> None:
        with _JOBS_LOCK:
            current = _JOBS[job.id]
            updated = current.model_copy(
                update={"status": "running", "started_at": _utc_now(), "live_stdout": "", "live_stderr": ""}
            )
            _JOBS[job.id] = updated
            _persist_job(updated)
            cancel_event = _JOB_CANCEL_EVENTS[job.id]

        dispatch_webhook_event(
            "job.started",
            {"module": request.module, "args_text": request.args_text, "job_id": job.id},
        )

        def _on_output(stdout_text: str, stderr_text: str) -> None:
            with _JOBS_LOCK:
                current = _JOBS.get(job.id)
                if current is None:
                    return
                updated = current.model_copy(
                    update={
                        "live_stdout": stdout_text,
                        "live_stderr": stderr_text,
                    }
                )
                _JOBS[job.id] = updated
                _persist_job(updated)

        try:
            result = _run_module_command_cancellable(
                request, job_id=job.id, cancel_event=cancel_event, on_output=_on_output
            )
        except Exception as exc:  # nosec B110
            with _JOBS_LOCK:
                current = _JOBS[job.id]
                updated = current.model_copy(
                    update={
                        "status": "cancelled" if cancel_event.is_set() else "failed",
                        "error": str(exc),
                        "finished_at": _utc_now(),
                    }
                )
                _JOBS[job.id] = updated
                _persist_job(updated)
            dispatch_webhook_event(
                "job.failed",
                {"module": request.module, "args_text": request.args_text, "job_id": job.id, "error": str(exc)},
            )
            return

        with _JOBS_LOCK:
            current = _JOBS[job.id]
            status: Literal["completed", "failed", "cancelled"]
            if cancel_event.is_set():
                status = "cancelled"
            else:
                status = "completed" if result.ok else "failed"
            updated = current.model_copy(
                update={
                    "status": status,
                    "live_stdout": result.stdout,
                    "live_stderr": result.stderr,
                    "result": result,
                    "finished_at": _utc_now(),
                }
            )
            _JOBS[job.id] = updated
            _persist_job(updated)

        event_name = "job.completed" if status in {"completed", "cancelled"} else "job.failed"
        dispatch_webhook_event(
            event_name,
            {
                "module": request.module,
                "args_text": request.args_text,
                "job_id": job.id,
                "returncode": result.returncode,
                "ok": result.ok,
            },
        )

    _EXECUTOR.submit(_run)
    return job


def get_module_job(job_id: str) -> ModuleJob | None:
    """Return one job snapshot by id, or ``None`` when missing."""
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        return job.model_copy(deep=True) if job else None


def list_module_jobs(limit: int = 20) -> list[ModuleJob]:
    """Return newest jobs first, bounded by ``limit``."""
    with _JOBS_LOCK:
        jobs = sorted(_JOBS.values(), key=lambda item: item.created_at, reverse=True)
        return [job.model_copy(deep=True) for job in jobs[:limit]]


def cancel_module_job(job_id: str) -> ModuleJob | None:
    """Request cancellation for one running/pending job and return snapshot."""
    process: Any = None
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return None
        if job.status in {"completed", "failed", "cancelled"}:
            return job.model_copy(deep=True)

        cancel_event = _JOB_CANCEL_EVENTS.get(job_id)
        if cancel_event:
            cancel_event.set()
        process = _JOB_PROCESSES.get(job_id)
        if job.status == "pending":
            updated = job.model_copy(
                update={
                    "status": "cancelled",
                    "finished_at": _utc_now(),
                    "error": "Cancelled by user.",
                }
            )
            _JOBS[job_id] = updated
            _persist_job(updated)
            return updated.model_copy(deep=True)

    if process is not None:
        process.terminate()
    current = get_module_job(job_id)
    return current


def rerun_module_job(job_id: str) -> ModuleJob | None:
    """Queue a new job with request copied from existing job id."""
    source = get_module_job(job_id)
    if source is None:
        return None
    return enqueue_module_job(source.request)


def clear_module_jobs() -> int:
    """Delete all terminal jobs (completed/failed/cancelled) from memory and SQLite."""
    to_delete: list[str] = []
    with _JOBS_LOCK:
        for job_id, job in list(_JOBS.items()):
            if job.status in {"completed", "failed", "cancelled"}:
                to_delete.append(job_id)
        for job_id in to_delete:
            _JOBS.pop(job_id, None)
            _JOB_CANCEL_EVENTS.pop(job_id, None)
            _JOB_PROCESSES.pop(job_id, None)
    for job_id in to_delete:
        _delete_persisted_job(job_id)
    return len(to_delete)


_init_db()
_load_jobs_from_db()
