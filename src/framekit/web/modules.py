from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import shlex
import sqlite3
import subprocess  # nosec B404
import sys
import time as _time_module
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from queue import Empty, SimpleQueue
from threading import Event, Lock, Semaphore, Thread
from time import monotonic, sleep
from typing import Any, Literal
from uuid import uuid4

from click.core import Argument, Command, Group, Option, Parameter
from loguru import logger
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

# Job state
_JOBS_LOCK = Lock()
_JOBS: dict[str, ModuleJob] = {}
_JOB_CANCEL_EVENTS: dict[str, Event] = {}
_JOB_PROCESSES: dict[str, Any] = {}
_MAX_JOBS = 200
_DB_LOCK = Lock()

# Claim-based worker: replaces ThreadPoolExecutor.
# _PENDING_SIGNAL is set whenever a new job is enqueued; the dispatcher thread
# wakes up, claims pending jobs up to _MAX_CONCURRENT_JOBS, and spawns one
# daemon thread per claimed job.
_MAX_CONCURRENT_JOBS = 2
_WORKER_SEMAPHORE = Semaphore(_MAX_CONCURRENT_JOBS)
_PENDING_SIGNAL = Event()
_WORKER_INIT_LOCK = Lock()
_WORKER_THREAD: Thread | None = None

_MODULE_SPEC_CACHE: dict[str, Any] | None = None
_MODULE_SPEC_CACHE_LOCK = Lock()
_PRESETS_LOCK = Lock()

# Stable worker identity for this process: written to claimed_by column on claim.
_WORKER_ID: str = f"pid-{os.getpid()}"

# ---------------------------------------------------------------------------
# Embedded watcher subsystem (active only during `framekit serve`)
# ---------------------------------------------------------------------------
# Holds the single WatcherService instance when running in service mode.
# None when no watcher is active (no folders configured, or not in service mode).
_EMBEDDED_WATCHER: Any = None  # WatcherService | None — typed as Any to avoid top-level import
_EMBEDDED_WATCHER_LOCK = Lock()
_EMBEDDED_WATCHER_ERROR: str | None = None

# ---------------------------------------------------------------------------
# Intake rate-limiter state (in-process, resets on restart)
# ---------------------------------------------------------------------------
# Maps source_id → list of monotonic timestamps for recent requests.
_INTAKE_RATE_LOCK = Lock()
_INTAKE_RATE_WINDOWS: dict[str, list[float]] = {}
_INTAKE_RATE_LIMIT = 30   # max requests per 60-second window per source

# Environment injected into every web-launched subprocess so that:
#   NO_COLOR=1           → Rich/Click never emit ANSI escape codes into the captured pipe
#   FRAMEKIT_WEB_JOB=1  → print_module_banner() returns early (no ASCII logo in output)
_WEB_JOB_ENV: dict[str, str] = {"NO_COLOR": "1", "FRAMEKIT_WEB_JOB": "1"}

# Matches all standard ANSI/VT100 escape sequences (SGR colors, cursor movement, erase, etc.).
# Applied as a stripping fallback on captured job output even when NO_COLOR is set,
# because third-party tools (ffmpeg, mkvmerge) or Rich Progress bars on stderr
# may still emit their own sequences regardless of environment variables.
_ANSI_ESCAPE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def _clean_web_job_output(text: str) -> str:
    """Strip ANSI escape sequences from captured subprocess output."""
    return _ANSI_ESCAPE.sub("", text)


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
    # Service-mode metadata (populated by intake/watch; null for web/CLI-origin jobs)
    origin: str | None = None
    category: str | None = None
    priority: int = 0


class IntakeSource(BaseModel):
    """Configuration for an external intake source (e.g. qBittorrent, custom downloader)."""

    id: str
    name: str
    source_id: str
    enabled: bool = True
    default_preset: str | None = None
    created_at: str


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
        # WAL mode improves concurrent read/write throughput for claim operations.
        conn.execute("PRAGMA journal_mode=WAL")
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
        # Compound index for the claim query: WHERE status='pending' ORDER BY priority DESC, created_at ASC.
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_web_module_jobs_claim
            ON web_module_jobs(status, priority, created_at)
            """
        )
        # Additive migration: add service columns when upgrading from an older DB.
        # ALTER TABLE ADD COLUMN is idempotent when guarded by the existing-column check.
        existing: set[str] = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(web_module_jobs)").fetchall()
        }
        new_cols: list[tuple[str, str]] = [
            ("priority",     "INTEGER DEFAULT 0"),
            ("claimed_by",   "TEXT DEFAULT NULL"),
            ("claimed_at",   "TEXT DEFAULT NULL"),
            ("category",     "TEXT DEFAULT NULL"),
            ("origin",       "TEXT DEFAULT NULL"),
            ("request_hash", "TEXT DEFAULT NULL"),
            ("attempts",     "INTEGER DEFAULT 0"),
        ]
        for col_name, col_def in new_cols:
            if col_name not in existing:
                conn.execute(
                    f"ALTER TABLE web_module_jobs ADD COLUMN {col_name} {col_def}"
                )
        conn.commit()


def _persist_job(job: ModuleJob) -> None:
    payload_json = job.model_dump_json()
    with _DB_LOCK, _db_connect() as conn:
        conn.execute(
            """
            INSERT INTO web_module_jobs(id, created_at, status, payload_json, priority, category, origin)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                created_at=excluded.created_at,
                status=excluded.status,
                payload_json=excluded.payload_json,
                priority=excluded.priority,
                category=excluded.category,
                origin=excluded.origin
            """,
            (job.id, job.created_at, job.status, payload_json, job.priority, job.category, job.origin),
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
            extra_env=_WEB_JOB_ENV,
        )
    except SafeSubprocessError as exc:
        return RunModuleResponse(
            ok=False,
            argv=argv,
            returncode=exc.returncode or 1,
            stdout="",
            stderr=str(exc),
        )

    clean_stdout = _clean_web_job_output(completed.stdout)
    clean_stderr = _clean_web_job_output(completed.stderr)
    parsed_kind, parsed_payload = _parse_json_payload(clean_stdout)

    return RunModuleResponse(
        ok=completed.returncode == 0,
        argv=argv,
        returncode=completed.returncode,
        stdout=clean_stdout,
        stderr=clean_stderr,
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
            extra_env=_WEB_JOB_ENV,
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
                stdout_text = _clean_web_job_output("".join(stdout_buffer))
                stderr_text = _clean_web_job_output("".join(stderr_buffer))
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
                stdout_text = _clean_web_job_output("".join(stdout_buffer))
                stderr_text = _clean_web_job_output("".join(stderr_buffer))
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
                stdout_text = _clean_web_job_output("".join(stdout_buffer))
                stderr_text = _clean_web_job_output("".join(stderr_buffer))
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


# ---------------------------------------------------------------------------
# Claim-based job worker
# ---------------------------------------------------------------------------

def _claim_pending_job_from_db(worker_id: str) -> tuple[str, str] | None:
    """Atomically claim one pending job directly from SQLite.

    Uses BEGIN IMMEDIATE so the SELECT+UPDATE is serialized against any
    concurrent writers — correct for both single-process (S1b) and future
    multi-process (S2) use.

    Returns (job_id, payload_json) of the claimed job, or None when the queue
    is empty.  The returned payload_json is the snapshot *before* the claim
    (status still 'pending' in the blob); callers must apply the running
    transition to the in-memory model themselves.
    """
    db_path = _jobs_db_path()
    with _DB_LOCK:
        # Dedicated connection with autocommit so we can issue BEGIN IMMEDIATE
        # without Python's implicit transaction management interfering.
        conn = sqlite3.connect(str(db_path), timeout=10.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT id, payload_json
                FROM web_module_jobs
                WHERE status = 'pending'
                ORDER BY priority DESC, created_at ASC
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                conn.execute("ROLLBACK")
                return None
            job_id = str(row["id"])
            now = _utc_now()
            conn.execute(
                """
                UPDATE web_module_jobs
                SET status = 'running', claimed_by = ?, claimed_at = ?
                WHERE id = ?
                """,
                (worker_id, now, job_id),
            )
            conn.execute("COMMIT")
            return job_id, str(row["payload_json"])
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            conn.close()


def _claim_pending_job() -> str | None:
    """Claim the highest-priority pending job from SQLite and sync to _JOBS cache.

    Returns job_id of the now-running job, or None when nothing is pending.
    Source of truth for claiming is SQLite; _JOBS is updated as a fast-read cache.
    """
    try:
        result = _claim_pending_job_from_db(_WORKER_ID)
    except Exception as exc:
        logger.warning("DB claim failed: {}", exc)
        return None

    if result is None:
        return None

    job_id, payload_json = result
    try:
        job = ModuleJob.model_validate_json(payload_json)
    except Exception as exc:
        logger.warning("Cannot parse claimed job {}: {}", job_id, exc)
        return None

    # Apply the running transition to the in-memory representation.
    updated = job.model_copy(
        update={
            "status": "running",
            "started_at": _utc_now(),
            "live_stdout": "",
            "live_stderr": "",
        }
    )

    with _JOBS_LOCK:
        # Race guard: a cancel request may have arrived between the DB claim and here.
        # If the in-memory job is already cancelled, sync DB and abort execution.
        existing = _JOBS.get(job_id)
        if existing is not None and existing.status == "cancelled":
            _persist_job(existing)  # reverts DB status to cancelled
            return None
        _JOBS[job_id] = updated
        # Ensure a cancel event exists — required for jobs claimed cross-process (S2).
        if job_id not in _JOB_CANCEL_EVENTS:
            _JOB_CANCEL_EVENTS[job_id] = Event()

    # Persist the running state so that payload_json reflects status=running for recovery.
    _persist_job(updated)
    return job_id


def _execute_job(job_id: str) -> None:
    """Execute a job that has already been claimed (status=running).

    This is the extracted body of the former ``_run()`` closure inside
    ``enqueue_module_job``. It is now a top-level function so the worker
    loop can call it for any job, enabling future cross-process claiming.
    """
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return
        cancel_event = _JOB_CANCEL_EVENTS.get(job_id)
        if cancel_event is None:
            return
        request = job.request

    dispatch_webhook_event(
        "job.started",
        {"module": request.module, "args_text": request.args_text, "job_id": job_id},
    )

    def _on_output(stdout_text: str, stderr_text: str) -> None:
        with _JOBS_LOCK:
            current = _JOBS.get(job_id)
            if current is None:
                return
            upd = current.model_copy(
                update={
                    "live_stdout": _clean_web_job_output(stdout_text),
                    "live_stderr": _clean_web_job_output(stderr_text),
                }
            )
            _JOBS[job_id] = upd
            _persist_job(upd)

    try:
        result = _run_module_command_cancellable(
            request, job_id=job_id, cancel_event=cancel_event, on_output=_on_output
        )
    except Exception as exc:  # nosec B110
        with _JOBS_LOCK:
            current = _JOBS.get(job_id)
            if current is not None:
                upd = current.model_copy(
                    update={
                        "status": "cancelled" if cancel_event.is_set() else "failed",
                        "error": str(exc),
                        "finished_at": _utc_now(),
                    }
                )
                _JOBS[job_id] = upd
                _persist_job(upd)
        dispatch_webhook_event(
            "job.failed",
            {
                "module": request.module,
                "args_text": request.args_text,
                "job_id": job_id,
                "error": str(exc),
            },
        )
        return

    with _JOBS_LOCK:
        current = _JOBS.get(job_id)
        if current is None:
            return
        status: Literal["completed", "failed", "cancelled"]
        if cancel_event.is_set():
            status = "cancelled"
        else:
            status = "completed" if result.ok else "failed"
        upd = current.model_copy(
            update={
                "status": status,
                "live_stdout": result.stdout,
                "live_stderr": result.stderr,
                "result": result,
                "finished_at": _utc_now(),
            }
        )
        _JOBS[job_id] = upd
        _persist_job(upd)

    event_name = "job.completed" if status in {"completed", "cancelled"} else "job.failed"
    dispatch_webhook_event(
        event_name,
        {
            "module": request.module,
            "args_text": request.args_text,
            "job_id": job_id,
            "returncode": result.returncode,
            "ok": result.ok,
        },
    )


def _execute_job_and_release(job_id: str) -> None:
    """Execute a claimed job and release the concurrency semaphore slot."""
    try:
        _execute_job(job_id)
    finally:
        _WORKER_SEMAPHORE.release()
        # Signal the dispatcher so it can pick up the next pending job.
        _PENDING_SIGNAL.set()


def _worker_loop() -> None:
    """Dispatcher: drains pending jobs up to _MAX_CONCURRENT_JOBS concurrently."""
    while True:
        _PENDING_SIGNAL.wait(timeout=5.0)
        _PENDING_SIGNAL.clear()
        # Claim and launch all claimable pending jobs in one pass.
        while True:
            if not _WORKER_SEMAPHORE.acquire(blocking=False):
                # At capacity; a running job will signal when it finishes.
                break
            job_id = _claim_pending_job()
            if job_id is None:
                _WORKER_SEMAPHORE.release()
                break
            t = Thread(
                target=_execute_job_and_release,
                args=(job_id,),
                daemon=True,
                name=f"framekit-job-{job_id[:8]}",
            )
            t.start()


def _ensure_worker_started() -> None:
    """Start the dispatcher thread if it is not already alive."""
    global _WORKER_THREAD
    with _WORKER_INIT_LOCK:
        if _WORKER_THREAD is None or not _WORKER_THREAD.is_alive():
            t = Thread(
                target=_worker_loop,
                daemon=True,
                name="framekit-job-dispatcher",
            )
            t.start()
            _WORKER_THREAD = t


# ---------------------------------------------------------------------------
# Public job queue API
# ---------------------------------------------------------------------------

def enqueue_module_job(
    request: RunModuleRequest,
    *,
    origin: str | None = None,
    category: str | None = None,
    priority: int = 0,
) -> ModuleJob:
    """Queue one module execution and return initial pending job snapshot."""
    job = ModuleJob(
        id=str(uuid4()),
        status="pending",
        created_at=_utc_now(),
        request=request,
        origin=origin,
        category=category,
        priority=priority,
    )
    with _JOBS_LOCK:
        _JOBS[job.id] = job
        _JOB_CANCEL_EVENTS[job.id] = Event()
        _persist_job(job)
        _trim_jobs_if_needed()

    _ensure_worker_started()
    _PENDING_SIGNAL.set()
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


def get_watch_service_status() -> dict[str, Any]:
    """Return running/stopped status by reading the watcher PID file."""
    from framekit.modules.watch.service import read_running_watcher_pid

    pid = read_running_watcher_pid()
    return {
        "status": "running" if pid is not None else "stopped",
        "pid": pid,
    }


def stop_watch_service(timeout_seconds: float = 5.0) -> dict[str, Any]:
    """Signal the running watcher to stop gracefully.

    Returns ``{"stopped": True}`` on success, ``{"stopped": False}`` when no
    running watcher was found or the process did not exit within the timeout.
    """
    from framekit.modules.watch.service import stop_running_watcher

    ok = stop_running_watcher(timeout_seconds=timeout_seconds)
    return {"stopped": ok}


# ---------------------------------------------------------------------------
# Embedded watcher lifecycle (service mode only)
# ---------------------------------------------------------------------------


def _build_watch_config_from_settings() -> Any:
    """Build WatchConfig from current settings. Return None if no enabled folders."""
    from framekit.modules.watch.models import WatchConfig

    store = SettingsStore()
    settings = store.load()
    watch_data = settings.get("watch", {})
    folders_raw = watch_data.get("folders", [])
    if not isinstance(folders_raw, list) or not folders_raw:
        return None
    enabled = [
        f for f in folders_raw if isinstance(f, dict) and f.get("enabled", True)
    ]
    if not enabled:
        return None
    watch_config_data: dict[str, Any] = {
        "enabled": True,
        "folders": folders_raw,
        "notifications": watch_data.get("notifications", {}),
    }
    return WatchConfig.from_dict(watch_config_data)


def start_embedded_watcher() -> None:
    """Start WatcherService embedded in the service process.

    No-ops silently if no watch folders are configured.  Any startup error is
    captured in ``_EMBEDDED_WATCHER_ERROR`` and exposed via
    ``get_embedded_watcher_state()``.
    """
    global _EMBEDDED_WATCHER, _EMBEDDED_WATCHER_ERROR
    with _EMBEDDED_WATCHER_LOCK:
        watcher = _EMBEDDED_WATCHER
        if watcher is not None and watcher.status.running:
            return  # already running — idempotent
        _EMBEDDED_WATCHER_ERROR = None
        try:
            config = _build_watch_config_from_settings()
            if config is None:
                logger.info("Embedded watcher: no folders configured — skipping start.")
                return
            from framekit.modules.watch.service import WatcherService

            watcher = WatcherService(config, embedded=True)
            watcher.start()  # returns immediately in embedded mode
            _EMBEDDED_WATCHER = watcher
            active = len([f for f in config.folders if f.enabled])
            logger.info("Embedded watcher started ({} folder(s)).", active)
        except Exception as exc:
            _EMBEDDED_WATCHER_ERROR = str(exc)
            logger.error("Embedded watcher failed to start: {}", exc)


def stop_embedded_watcher() -> None:
    """Stop the embedded WatcherService if running."""
    global _EMBEDDED_WATCHER
    with _EMBEDDED_WATCHER_LOCK:
        watcher = _EMBEDDED_WATCHER
        if watcher is None:
            return
        try:
            watcher.stop()
            logger.info("Embedded watcher stopped.")
        except Exception as exc:
            logger.warning("Embedded watcher stop raised: {}", exc)
        finally:
            _EMBEDDED_WATCHER = None


def get_embedded_watcher_state() -> dict[str, Any]:
    """Return watcher subsystem state for inclusion in /api/v1/service/status."""
    with _EMBEDDED_WATCHER_LOCK:
        watcher = _EMBEDDED_WATCHER
        err = _EMBEDDED_WATCHER_ERROR
    if watcher is None:
        return {
            "status": "error" if err else "stopped",
            "folders_active": 0,
            "last_error": err,
        }
    status = watcher.get_status()
    return {
        "status": "running" if status.running else "stopped",
        "folders_active": len(status.folders_watched),
        "last_error": err,
    }


def list_runs_from_ledger(limit: int = 50) -> list[dict[str, Any]]:
    """Read run ledger NDJSON, group by run_id, return newest-first list.

    Each entry: {run_id, module, file_count, timestamp, actions: [...]}
    """
    from framekit.core.runs.ledger import get_runs_ledger_path

    path = get_runs_ledger_path()
    if not path.exists():
        return []

    # run_id → list of raw entry dicts
    groups: dict[str, list[dict[str, Any]]] = {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry: dict[str, Any] = json.loads(line)
                except json.JSONDecodeError:
                    continue
                run_id = str(entry.get("run_id", ""))
                if not run_id:
                    continue
                groups.setdefault(run_id, []).append(entry)
    except OSError:
        return []

    runs: list[dict[str, Any]] = []
    for run_id, entries in groups.items():
        timestamps = [str(e.get("timestamp", "")) for e in entries if e.get("timestamp")]
        earliest = min(timestamps) if timestamps else ""
        module = str(entries[0].get("module", "")) if entries else ""
        runs.append({
            "run_id": run_id,
            "module": module,
            "file_count": len(entries),
            "timestamp": earliest,
            "actions": entries,
        })

    runs.sort(key=lambda r: r["timestamp"], reverse=True)
    return runs[:limit]


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


# ---------------------------------------------------------------------------
# Intake API — source management and release submission
# ---------------------------------------------------------------------------

_INTAKE_SOURCES_FILENAME = "intake_sources.json"
_VALID_SOURCE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _intake_sources_path() -> Path:
    return get_config_dir() / _INTAKE_SOURCES_FILENAME


def _load_intake_sources() -> list[IntakeSource]:
    path = _intake_sources_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [IntakeSource(**s) for s in data.get("sources", [])]
    except Exception as exc:
        logger.warning("Failed to load intake sources: {}", exc)
        return []


def _save_intake_sources(sources: list[IntakeSource]) -> None:
    path = _intake_sources_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"sources": [s.model_dump() for s in sources]}, indent=2),
        encoding="utf-8",
    )


def list_intake_sources() -> list[dict[str, Any]]:
    """Return all configured intake sources (tokens not included)."""
    return [s.model_dump() for s in _load_intake_sources()]


def create_intake_source(
    name: str,
    source_id: str,
    *,
    default_preset: str | None = None,
) -> dict[str, Any]:
    """Create a new intake source, generate a vault-stored token, return token once.

    Raises ``ValueError`` if source_id is invalid, already exists, or vault is
    unavailable.  Vault must be available — tokens are never stored in plaintext.
    """
    name = name.strip()
    source_id = source_id.strip()
    if not name:
        raise ValueError("name is required")
    if not _VALID_SOURCE_ID_RE.match(source_id):
        raise ValueError(
            "source_id must be 1–64 characters of [a-zA-Z0-9_-]"
        )
    sources = _load_intake_sources()
    if any(s.source_id == source_id for s in sources):
        raise ValueError(f"source_id '{source_id}' already exists")

    # Vault required — fail closed.
    s = Settings()
    vault = s.get_vault()
    if vault is None:
        raise ValueError(
            "Vault is unavailable. Intake source tokens require vault encryption. "
            "Run 'framekit settings security init' to initialise the vault."
        )

    token = secrets.token_urlsafe(32)
    vault_key = f"intake.{source_id}.token"
    vault.store(vault_key, token)

    source = IntakeSource(
        id=str(uuid4()),
        name=name,
        source_id=source_id,
        enabled=True,
        default_preset=default_preset,
        created_at=_utc_now(),
    )
    sources.append(source)
    _save_intake_sources(sources)

    logger.info("Intake source created: source_id={}", source_id)
    result = source.model_dump()
    result["token"] = token  # shown exactly once — never logged
    return result


def delete_intake_source(source_id: str) -> dict[str, Any]:
    """Remove an intake source and delete its vault token."""
    sources = _load_intake_sources()
    remaining = [s for s in sources if s.source_id != source_id]
    if len(remaining) == len(sources):
        raise ValueError(f"source_id '{source_id}' not found")
    _save_intake_sources(remaining)
    try:
        vault = Settings().get_vault()
        if vault:
            vault.delete(f"intake.{source_id}.token")
    except Exception as exc:
        logger.warning("Could not remove vault token for intake source '{}': {}", source_id, exc)
    logger.info("Intake source deleted: source_id={}", source_id)
    return {"deleted": True, "source_id": source_id}


def verify_intake_token(source_id: str, token: str) -> bool:
    """Constant-time comparison of *token* against vault-stored value.

    Returns ``False`` (never raises) on vault errors — fail closed.
    """
    try:
        vault = Settings().get_vault()
        if vault is None:
            return False
        stored = vault.retrieve(f"intake.{source_id}.token", default=None)
        if not stored:
            return False
        return hmac.compare_digest(str(stored), token)
    except Exception:
        return False


def _intake_allowed_roots() -> list[Path]:
    """Return allowlisted root paths for intake path validation.

    Sources (in order): ``settings.intake.allowed_roots`` list, then the path
    of every enabled watch folder.  When the combined list is empty, all paths
    are allowed (no restriction configured).
    """
    store = SettingsStore()
    settings = store.load()
    roots: list[Path] = []
    for raw in (settings.get("intake") or {}).get("allowed_roots", []):
        try:
            roots.append(Path(raw).resolve())
        except Exception:
            pass
    for folder in list_watch_folders():
        try:
            roots.append(Path(folder["path"]).resolve())
        except Exception:
            pass
    return roots


def _intake_path_allowed(resolved: Path) -> bool:
    """Return True if *resolved* is under at least one allowed root."""
    roots = _intake_allowed_roots()
    if not roots:
        return True  # no restriction configured
    for root in roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            pass
    return False


def _intake_request_hash(source_id: str, resolved_path: str, dedup_key: str | None) -> str:
    raw = f"{source_id}:{resolved_path}:{dedup_key or resolved_path}"
    return hashlib.sha1(raw.encode()).hexdigest()  # nosec B324 — dedup only, not crypto


def _find_job_by_request_hash(req_hash: str) -> str | None:
    """Return job_id of pending/running job with matching request_hash, or None."""
    db_path = _jobs_db_path()
    with _DB_LOCK:
        conn = sqlite3.connect(str(db_path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                """
                SELECT id FROM web_module_jobs
                WHERE request_hash = ? AND status IN ('pending', 'running')
                LIMIT 1
                """,
                (req_hash,),
            ).fetchone()
        finally:
            conn.close()
    return str(row["id"]) if row else None


def _set_job_request_hash(job_id: str, req_hash: str) -> None:
    """Write request_hash to the DB row for an existing job (post-enqueue)."""
    with _DB_LOCK, _db_connect() as conn:
        conn.execute(
            "UPDATE web_module_jobs SET request_hash = ? WHERE id = ?",
            (req_hash, job_id),
        )
        conn.commit()


def _check_intake_rate_limit(source_id: str) -> bool:
    """Return True if source is within 30 req/min limit. Thread-safe."""
    now = _time_module.monotonic()
    cutoff = now - 60.0
    with _INTAKE_RATE_LOCK:
        ts = _INTAKE_RATE_WINDOWS.setdefault(source_id, [])
        # Trim expired entries (list is append-ordered → find first in-window index)
        i = 0
        while i < len(ts) and ts[i] < cutoff:
            i += 1
        del ts[:i]
        if len(ts) >= _INTAKE_RATE_LIMIT:
            return False
        ts.append(now)
        return True


def submit_intake_release(
    source_id: str,
    path: str,
    *,
    preset: str | None = None,
    dedup_key: str | None = None,
) -> dict[str, Any]:
    """Validate *path* and enqueue a pipeline job for the given intake source.

    Returns ``{"job_id": ..., "accepted": bool, "dedup_hit": bool}``.

    Raises ``ValueError`` on rate limit, missing/forbidden path, or unknown source.
    Only enqueues ``pipeline`` — never arbitrary modules.
    """
    sources = _load_intake_sources()
    source = next((s for s in sources if s.source_id == source_id), None)
    if source is None:
        raise ValueError(f"Unknown intake source: '{source_id}'")
    if not source.enabled:
        raise ValueError(f"Intake source '{source_id}' is disabled")

    if not _check_intake_rate_limit(source_id):
        raise ValueError("Rate limit exceeded (30 requests/min per source)")

    # resolve() first so symlinks are expanded before the allowlist check;
    # checking exists() on the resolved path also eliminates a TOCTOU race.
    resolved = Path(path.strip()).resolve()
    if not resolved.exists():
        raise ValueError(f"Path does not exist: {path}")
    if not _intake_path_allowed(resolved):
        raise ValueError(
            f"Path is not under any configured allowed root: {path}. "
            "Add the parent directory to settings.intake.allowed_roots or watch folders."
        )

    req_hash = _intake_request_hash(source_id, str(resolved), dedup_key)
    existing = _find_job_by_request_hash(req_hash)
    if existing:
        return {"job_id": existing, "accepted": False, "dedup_hit": True}

    # Preset resolution: explicit → source default → matching watch folder preset
    resolved_preset: str | None = preset
    if not resolved_preset and source.default_preset:
        resolved_preset = source.default_preset
    if not resolved_preset:
        for folder in list_watch_folders():
            try:
                folder_path = Path(folder["path"]).resolve()
                resolved.relative_to(folder_path)
                fp = folder.get("preset", "default") or "default"
                if fp != "default":
                    resolved_preset = fp
                break
            except ValueError:
                pass

    parts = [shlex.quote(str(resolved))]
    if resolved_preset:
        parts.append(f"--preset {shlex.quote(resolved_preset)}")
    args_text = " ".join(parts)

    request = RunModuleRequest(
        module="pipeline",
        args_text=args_text,
        dry_run=False,
        auto_yes=True,
        confirm_destructive=True,
        timeout_seconds=7200.0,
    )
    job = enqueue_module_job(request, origin=f"intake:{source_id}", category="transform")
    _set_job_request_hash(job.id, req_hash)

    logger.info("Intake release accepted: source={} path={} job={}", source_id, str(resolved), job.id)
    return {"job_id": job.id, "accepted": True, "dedup_hit": False}


_init_db()
_load_jobs_from_db()
