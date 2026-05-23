from __future__ import annotations

import contextlib
import json
import os
import re
import sys
import threading
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger

from framekit.core.paths import get_cache_dir

LOG_ENV_VAR = "FRAMEKIT_LOG_FILE"
DEBUG_ENV_VAR = "FRAMEKIT_DEBUG"

# List of key substrings that should be considered sensitive in
# diagnostic logs.  Any key containing one of these parts
# (case-insensitive) will be replaced with a placeholder when
# serialising context for the log.  This list mirrors the values
# defined in settings.SECRET_KEY_PARTS and is extended to include
# torrent announce configuration keys.  See `redact()` for usage.
SECRET_KEY_PARTS = (
    "api_key",
    "apikey",
    "access_token",
    "auth_token",
    "authorization",
    "bearer",
    "token",
    "password",
    "secret",
    "client_secret",
    "private_key",
    "session",
    "session_id",
    "cookie",
    "jwt",
    "refresh_token",
    "csrf",
    "csrf_token",
    # Torrent announce configuration
    "announce",
    "announce_url",
    "announce_urls",
    "selected_announce",
)

# Regex patterns for detecting sensitive *values* in log lines.
#
# These are deliberately specific: a naive ``\b[A-Za-z0-9_-]{32,}\b`` matches
# normal paths, hashes, base64 blobs and other long-but-harmless tokens, which
# turned every debug log into noise. We only match shapes that are highly
# unlikely to occur outside a credential.
SECRET_VALUE_PATTERNS = [
    # JWT (three dot-separated base64url segments) — TMDb v4 token shape.
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    # HTTP auth header values.
    re.compile(r"Bearer\s+[A-Za-z0-9_\-\.=]+", re.IGNORECASE),
    re.compile(r"Basic\s+[A-Za-z0-9+/=]+", re.IGNORECASE),
    # PEM-encoded private keys.
    re.compile(
        r"-----BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+)?PRIVATE\s+KEY-----"
        r"[\s\S]*?-----END\s+(?:RSA\s+|EC\s+|OPENSSH\s+)?PRIVATE\s+KEY-----"
    ),
    # AWS / GCP / Slack / GitHub token prefixes.
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    re.compile(r"\bxox[abprs]-[0-9A-Za-z\-]{10,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    # ``password=...``, ``token: ...``, etc.
    re.compile(
        r"(?P<lead>(?:password|passwd|secret|token|api[_-]?key)\s*[:=]\s*)"
        r"['\"]?(?P<value>[^'\"\s,;]+)",
        re.IGNORECASE,
    ),
]


@dataclass(slots=True)
class DiagnosticsState:
    """Diagnostics state."""

    debug: bool = False
    log_file: Path | None = None
    loguru_handler_id: int | None = None
    module_loguru_handler_id: int | None = None
    module_logs_dir: Path | None = None
    module_session_stamp: str = ""
    max_size_mb: int = 100
    max_backups: int = 30
    compress_old_logs: bool = True
    retention_days: int = 5


_STATE = DiagnosticsState()


def _get_logging_config() -> dict[str, Any]:
    """Get logging configuration from settings, with fallback to defaults."""
    try:
        from framekit.core.settings import Settings

        settings = Settings()
        data = settings.load()
        logging_config = data.get("logging", {})
        return {
            "max_size_mb": logging_config.get("max_size_mb", 100),
            "max_backups": logging_config.get("max_backups", 30),
            "compress_old_logs": logging_config.get("compress_old_logs", True),
            "retention_days": logging_config.get("retention_days", 5),
            "cleanup_on_startup": logging_config.get("cleanup_on_startup", True),
        }
    except Exception:
        # If settings can't be loaded, use defaults
        return {
            "max_size_mb": 100,
            "max_backups": 30,
            "compress_old_logs": True,
            "retention_days": 5,
            "cleanup_on_startup": True,
        }


def _cleanup_old_logs(log_dir: Path, retention_days: int, max_backups: int) -> None:
    """Clean up old log files based on retention policy."""
    try:
        if not log_dir.exists():
            return

        log_files = _collect_log_backups(log_dir)
        _remove_files_older_than(log_files, datetime.now(UTC) - timedelta(days=retention_days))
        _enforce_max_backup_count(log_files, max_backups)
    except Exception:  # nosec B110
        # Cleanup failure should not break logging
        pass


def _cleanup_module_logs(log_dir: Path, retention_days: int) -> None:
    """Remove old per-module session logs."""
    try:
        if not log_dir.exists():
            return
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        for candidate in log_dir.glob("*_logs_*.log"):
            try:
                file_time = datetime.fromtimestamp(candidate.stat().st_mtime, UTC)
                if file_time < cutoff:
                    candidate.unlink()
            except Exception:  # nosec B112
                continue
    except Exception:  # nosec B110
        pass


def _collect_log_backups(log_dir: Path) -> list[Path]:
    log_files: list[Path] = []
    for pattern in ("framekit.log.*", "framekit.log.*.gz"):
        log_files.extend(log_dir.glob(pattern))
    log_files.sort(key=lambda path: path.stat().st_mtime)
    return log_files


def _remove_files_older_than(log_files: list[Path], cutoff_time: datetime) -> None:
    for log_file in log_files:
        try:
            file_time = datetime.fromtimestamp(log_file.stat().st_mtime, UTC)
            if file_time < cutoff_time:
                log_file.unlink()
        except Exception:  # nosec B112
            continue


def _enforce_max_backup_count(log_files: list[Path], max_backups: int) -> None:
    remaining_files = [file for file in log_files if file.exists()]
    remaining_files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    for old_file in remaining_files[max_backups:]:
        with contextlib.suppress(Exception):
            old_file.unlink()


def reset_diagnostics() -> DiagnosticsState:
    """Reset diagnostics state and close any open handlers."""
    if _STATE.loguru_handler_id is not None:
        with contextlib.suppress(Exception):
            logger.remove(_STATE.loguru_handler_id)
    if _STATE.module_loguru_handler_id is not None:
        with contextlib.suppress(Exception):
            logger.remove(_STATE.module_loguru_handler_id)

    _STATE.debug = False
    _STATE.log_file = None
    _STATE.loguru_handler_id = None
    _STATE.module_loguru_handler_id = None
    _STATE.module_logs_dir = None
    _STATE.module_session_stamp = ""
    _STATE.max_size_mb = 100
    _STATE.max_backups = 30
    _STATE.compress_old_logs = True
    _STATE.retention_days = 5
    return _STATE


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "debug"}


def default_log_file() -> Path:
    """Handle default log file."""
    return get_cache_dir() / "logs" / "framekit.log"


def default_module_logs_dir() -> Path:
    """Return user-cache folder for per-module logs."""
    return get_cache_dir() / "logs" / "modules"


def _coerce_log_file(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


def configure_diagnostics(
    *,
    debug: bool | None = None,
    log_file: str | Path | None = None,
) -> DiagnosticsState:
    """Configure process-wide debug/log behavior with rotation support."""
    # Remove previous sinks before reconfiguring
    with contextlib.suppress(ValueError):
        logger.remove()
    _STATE.loguru_handler_id = None
    _STATE.module_loguru_handler_id = None

    _apply_debug_state(debug)
    _configure_stderr_sink()

    coerced_log_file = _coerce_log_file(log_file)
    if coerced_log_file is not None:
        _STATE.log_file = coerced_log_file

    if _STATE.log_file is None:
        _STATE.log_file = default_log_file()

    _STATE.log_file.parent.mkdir(parents=True, exist_ok=True)
    config = _load_logging_settings_to_state()
    if config.get("cleanup_on_startup", True):
        _cleanup_old_logs(_STATE.log_file.parent, _STATE.retention_days, _STATE.max_backups)
    _configure_rotating_file_sink()
    _STATE.module_logs_dir = default_module_logs_dir()
    _STATE.module_session_stamp = datetime.now().strftime("%Y%m%d_%H%M")
    _STATE.module_logs_dir.mkdir(parents=True, exist_ok=True)
    if config.get("cleanup_on_startup", True):
        _cleanup_module_logs(_STATE.module_logs_dir, _STATE.retention_days)
    _configure_module_file_sink()

    return _STATE


def _apply_debug_state(debug: bool | None) -> None:
    if debug is not None:
        _STATE.debug = bool(debug)


def _configure_stderr_sink() -> None:
    if not _STATE.debug:
        return
    logger.add(
        sys.stderr,
        level="DEBUG",
        colorize=True,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> — <level>{message}</level>",
    )


def _load_logging_settings_to_state() -> dict[str, Any]:
    config = _get_logging_config()
    _STATE.max_size_mb = config["max_size_mb"]
    _STATE.max_backups = config["max_backups"]
    _STATE.compress_old_logs = config["compress_old_logs"]
    _STATE.retention_days = config["retention_days"]
    return config


def _sanitize_module_label(value: str | None) -> str:
    normalized = re.sub(r"[^a-z0-9_-]+", "_", str(value or "").strip().lower()).strip("_")
    return normalized or "framekit"


def _module_label_from_record_name(record_name: str) -> str:
    parts = [part for part in record_name.split(".") if part]
    if not parts:
        return "framekit"
    if parts[0] != "framekit":
        return _sanitize_module_label(parts[0])
    if len(parts) == 1:
        return "framekit"
    second = parts[1]
    if second == "__main__":
        return "framekit"
    if second == "core":
        return "framekit" if len(parts) > 2 and parts[2] == "diagnostics" else "core"
    if second == "ui":
        return "ui"
    if second in {"commands", "modules"} and len(parts) > 2:
        third = parts[2]
        if third == "pipeline" or third.startswith("pipeline_"):
            return "pipeline"
        return _sanitize_module_label(third)
    return _sanitize_module_label(second)


def _module_label_from_message(message: str) -> str | None:
    payload = message.strip()
    if not (payload.startswith("{") and payload.endswith("}")):
        return None
    try:
        parsed = json.loads(payload)
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    context = parsed.get("context")
    if not isinstance(context, dict):
        return None
    module_name = context.get("module")
    return _sanitize_module_label(module_name) if isinstance(module_name, str) else None


def _module_log_label(record_name: str, message: str) -> str:
    return _module_label_from_message(message) or _module_label_from_record_name(record_name)


def get_module_log_file(module_name: str) -> Path | None:
    """Return current session log file path for one module."""
    if _STATE.module_logs_dir is None or not _STATE.module_session_stamp:
        return None
    label = _sanitize_module_label(module_name)
    return _STATE.module_logs_dir / f"{label}_logs_{_STATE.module_session_stamp}.log"


class _PerModuleLogSink:
    """Loguru sink writing one file per module and session minute."""

    def __init__(self, log_dir: Path, session_stamp: str) -> None:
        self._log_dir = log_dir
        self._session_stamp = session_stamp
        self._handles: dict[Path, Any] = {}
        self._lock = threading.Lock()

    def __call__(self, message) -> None:
        record = message.record
        module_label = _module_log_label(str(record["name"]), str(record["message"]))
        target = self._log_dir / f"{module_label}_logs_{self._session_stamp}.log"
        timestamp = record["time"].strftime("%Y-%m-%d %H:%M:%S")
        redacted_message = redact(str(record["message"]), redact_values=True)
        line = (
            f"{timestamp} | {record['level'].name:<8} | "
            f"{record['name']}:{record['function']}:{record['line']} - {redacted_message}"
        )
        exception = record["exception"]
        if exception is not None:
            tb = "".join(
                traceback.format_exception(exception.type, exception.value, exception.traceback)
            ).rstrip()
            if tb:
                line = f"{line}\n{redact(tb, redact_values=True)}"

        with self._lock:
            handle = self._handles.get(target)
            if handle is None:
                target.parent.mkdir(parents=True, exist_ok=True)
                handle = target.open("a", encoding="utf-8")
                self._handles[target] = handle
            handle.write(f"{line}\n")
            handle.flush()

    def stop(self) -> None:
        with self._lock:
            for handle in self._handles.values():
                with contextlib.suppress(Exception):
                    handle.close()
            self._handles.clear()


def _configure_rotating_file_sink() -> None:
    try:
        if _STATE.loguru_handler_id is not None:
            logger.remove(_STATE.loguru_handler_id)
        _STATE.loguru_handler_id = logger.add(
            str(_STATE.log_file),
            rotation=f"{_STATE.max_size_mb} MB",
            retention=f"{_STATE.retention_days} days",
            compression="zip" if _STATE.compress_old_logs else None,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level="DEBUG" if _STATE.debug else "INFO",
            enqueue=True,
            backtrace=True,
            diagnose=False,
        )
        logger.info(
            f"Log rotation configured: max_size={_STATE.max_size_mb}MB, "
            f"retention={_STATE.retention_days}days, "
            f"compress={_STATE.compress_old_logs}"
        )
    except Exception as error:
        _STATE.loguru_handler_id = None
        logger.warning(f"Failed to configure log rotation: {error}")


def _configure_module_file_sink() -> None:
    if _STATE.module_logs_dir is None or not _STATE.module_session_stamp:
        return
    try:
        if _STATE.module_loguru_handler_id is not None:
            logger.remove(_STATE.module_loguru_handler_id)
        sink = _PerModuleLogSink(_STATE.module_logs_dir, _STATE.module_session_stamp)
        _STATE.module_loguru_handler_id = logger.add(
            sink,
            format="{message}",
            level="DEBUG" if _STATE.debug else "INFO",
            enqueue=False,
            backtrace=True,
            diagnose=False,
        )
    except Exception as error:
        _STATE.module_loguru_handler_id = None
        logger.warning(f"Failed to configure per-module logs: {error}")


def configure_from_environment() -> DiagnosticsState:
    """Handle configure from environment."""
    env_log_file = os.environ.get(LOG_ENV_VAR)
    env_debug = os.environ.get(DEBUG_ENV_VAR)

    return configure_diagnostics(
        debug=_truthy(env_debug) if env_debug is not None else None,
        log_file=env_log_file,
    )


def configure_from_argv(argv: list[str]) -> DiagnosticsState:
    """Preconfigure diagnostics before Click parses global options."""
    debug: bool | None = True if "--debug" in argv else None
    if "--no-debug" in argv:
        debug = False
    log_file: str | None = None

    for index, arg in enumerate(argv):
        if arg == "--log-file" and index + 1 < len(argv):
            log_file = argv[index + 1]
            break
        if arg.startswith("--log-file="):
            log_file = arg.split("=", 1)[1]
            break

    configure_from_environment()
    return configure_diagnostics(debug=debug, log_file=log_file)


def is_debug_enabled() -> bool:
    """Return ``True`` if is debug enabled."""
    return _STATE.debug


def get_log_file() -> Path | None:
    """Return the log file."""
    return _STATE.log_file


def _is_sensitive_key(key: object) -> bool:
    """Check if a key name indicates sensitive data."""
    lowered = str(key).lower()
    return any(part in lowered for part in SECRET_KEY_PARTS)


def _is_sensitive_value(value: str) -> bool:
    """Check if a string value matches sensitive data patterns."""
    if not isinstance(value, str):  # pyright: ignore[reportUnnecessaryIsInstance]  # Runtime guard for callers that bypass type checking
        return False

    # Skip very short strings (likely not secrets)
    if len(value) < 8:
        return False

    # Check against regex patterns
    for pattern in SECRET_VALUE_PATTERNS:
        if pattern.search(value):
            return True

    return False


def redact(value: Any, redact_values: bool = False) -> Any:
    """Recursively redact sensitive data from nested structures.

    Args:
        value: Value to redact (dict, list, tuple, or primitive)
        redact_values: If True, also redact values matching sensitive patterns

    Returns:
        Redacted copy of the value
    """
    if isinstance(value, dict):
        return _redact_dict(value, redact_values=redact_values)
    if isinstance(value, list):
        return [redact(item, redact_values) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item, redact_values) for item in value)
    if isinstance(value, Path):
        return str(value)
    return _redact_scalar(value, redact_values=redact_values)


def _redact_dict(value: dict[Any, Any], *, redact_values: bool) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, item in value.items():
        normalized_key = str(key)
        redacted[normalized_key] = (
            "********" if _is_sensitive_key(key) else redact(item, redact_values=redact_values)
        )
    return redacted


def _redact_scalar(value: Any, *, redact_values: bool) -> Any:
    if redact_values and isinstance(value, str) and _is_sensitive_value(value):
        return "********"
    return value


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    return repr(value)


def log_event(level: str, message: str, **context: Any) -> None:
    """Log an event with automatic rotation support."""
    log_file = get_log_file()
    if log_file is None:
        return

    entry = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "level": level.upper(),
        "message": message,
        "context": redact(context, redact_values=True),  # Security: enable value redaction
    }

    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Use Loguru handler if available
        if _STATE.loguru_handler_id is not None:
            try:
                # Format the log entry as JSON
                log_line = json.dumps(entry, ensure_ascii=False, default=_json_default)

                # Log through Loguru with appropriate level
                log_method = getattr(logger, level.lower(), logger.info)
                log_method(log_line)
                return
            except Exception:  # nosec B110
                # Fall back to direct file write if handler fails
                pass

        # Fallback: direct file write (backward compatibility)
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, default=_json_default) + "\n")
    except OSError:
        # Logging must never break the workflow.
        return


def log_exception(exc: BaseException, **context: Any) -> None:
    """Handle log exception."""
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    log_event(
        "ERROR",
        str(exc) or exc.__class__.__name__,
        exception_type=exc.__class__.__name__,
        traceback=tb,
        **context,
    )


def format_traceback(exc: BaseException) -> str:
    """Format traceback."""
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


def cleanup_old_logs() -> dict[str, Any]:
    """Manually trigger cleanup of old log files.

    Returns:
        Dictionary with cleanup statistics.
    """
    log_file = get_log_file()
    if log_file is None:
        return {"status": "no_log_file", "removed": 0}

    log_dir = log_file.parent
    if not log_dir.exists():
        return {"status": "no_log_dir", "removed": 0}

    # Count files before cleanup
    before_count = len(list(log_dir.glob("framekit.log.*")))
    before_count += len(list(log_dir.glob("framekit.log.*.gz")))

    # Perform cleanup
    _cleanup_old_logs(log_dir, _STATE.retention_days, _STATE.max_backups)

    # Count files after cleanup
    after_count = len(list(log_dir.glob("framekit.log.*")))
    after_count += len(list(log_dir.glob("framekit.log.*.gz")))

    removed = before_count - after_count

    log_event(
        "INFO",
        "Manual log cleanup completed",
        removed_files=removed,
        retention_days=_STATE.retention_days,
        max_backups=_STATE.max_backups,
    )

    return {
        "status": "success",
        "removed": removed,
        "remaining": after_count,
        "retention_days": _STATE.retention_days,
        "max_backups": _STATE.max_backups,
    }


def get_log_rotation_status() -> dict[str, Any]:
    """Get current log rotation configuration and status.

    Returns:
        Dictionary with rotation status information.
    """
    log_file = get_log_file()
    if log_file is None:
        return {"enabled": False}

    status: dict[str, Any] = {
        "enabled": _STATE.loguru_handler_id is not None,
        "log_file": str(log_file),
        "max_size_mb": _STATE.max_size_mb,
        "max_backups": _STATE.max_backups,
        "compress_old_logs": _STATE.compress_old_logs,
        "retention_days": _STATE.retention_days,
    }

    # Add file statistics if log file exists
    if log_file.exists():
        stat = log_file.stat()
        status["current_size_mb"] = round(stat.st_size / (1024 * 1024), 2)
        status["current_size_percent"] = round(
            (stat.st_size / (1024 * 1024)) / _STATE.max_size_mb * 100, 1
        )

    # Count backup files
    if log_file.parent.exists():
        backup_count = len(list(log_file.parent.glob("framekit.log.*")))
        backup_count += len(list(log_file.parent.glob("framekit.log.*.gz")))
        status["backup_files"] = backup_count

    return status


def diagnostics_summary() -> dict[str, Any]:
    """Get diagnostics configuration summary."""
    log_file = get_log_file()
    summary: dict[str, Any] = {
        "debug": is_debug_enabled(),
        "log_file": str(log_file) if log_file is not None else None,
        "debug_env_var": DEBUG_ENV_VAR,
        "log_env_var": LOG_ENV_VAR,
    }

    # Add rotation info if enabled
    if _STATE.loguru_handler_id is not None:
        summary["rotation_enabled"] = True
        summary["max_size_mb"] = _STATE.max_size_mb
        summary["max_backups"] = _STATE.max_backups

    return summary


# Note: ``configure_from_environment()`` is NOT called at import time. Importing
# this module must not create log files or read env vars — callers (the CLI
# entry point in ``framekit/__main__.py``) invoke it explicitly once the
# command line has been parsed.
