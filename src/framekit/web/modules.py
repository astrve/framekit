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

from pydantic import BaseModel, Field, field_validator

from framekit.core.paths import get_cache_dir, get_config_dir, get_settings_path
from framekit.core.settings import SettingsStore, redact_settings
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
        except Exception:  # nosec B110
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
    "general.locale",
    "general.log_level",
    "upload.enabled",
    "upload.auto_upload",
    "upload.max_parallel_uploads",
    "seedbox.max_concurrent_uploads",
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
    normalized_remote = rclone_remote.strip()
    if not normalized_remote:
        raise ValueError("rclone_remote is required")
    normalized_base = remote_base_path.strip() or "/"
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


def set_default_seedbox(name: str) -> list[dict[str, Any]]:
    """Set seedbox default profile and return updated summary."""
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
        except Exception:
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
            text=True,
            encoding="utf-8",
            errors="replace",
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


_init_db()
_load_jobs_from_db()
