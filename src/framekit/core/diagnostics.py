from __future__ import annotations

import json
import os
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
    # Torrent announce configuration
    "announce",
    "announce_url",
    "announce_urls",
    "selected_announce",
)


@dataclass(slots=True)
class DiagnosticsState:
    debug: bool = False
    log_file: Path | None = None


_STATE = DiagnosticsState()


def reset_diagnostics() -> DiagnosticsState:
    _STATE.debug = False
    _STATE.log_file = None
    return _STATE


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "debug"}


def default_log_file() -> Path:
    return get_cache_dir() / "logs" / "framekit.log"


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
    """Configure process-wide debug/log behavior."""

    if debug is not None:
        _STATE.debug = bool(debug)

    coerced_log_file = _coerce_log_file(log_file)
    if coerced_log_file is not None:
        _STATE.log_file = coerced_log_file

    if _STATE.debug and _STATE.log_file is None:
        _STATE.log_file = default_log_file()

    if _STATE.log_file is not None:
        _STATE.log_file.parent.mkdir(parents=True, exist_ok=True)

    return _STATE


def configure_from_environment() -> DiagnosticsState:
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
    return _STATE.debug


def get_log_file() -> Path | None:
    return _STATE.log_file


def _is_sensitive_key(key: object) -> bool:
    lowered = str(key).lower()
    return any(part in lowered for part in SECRET_KEY_PARTS)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "********" if _is_sensitive_key(key) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, Path):
        return str(value)
    return value


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    return repr(value)


def log_event(level: str, message: str, **context: Any) -> None:
    log_file = get_log_file()
    if log_file is None:
        return

    entry = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "level": level.upper(),
        "message": message,
        "context": redact(context),
    }

    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, default=_json_default) + "\n")
    except OSError:
        # Logging must never break the workflow.
        return


def log_exception(exc: BaseException, **context: Any) -> None:
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    log_event(
        "ERROR",
        str(exc) or exc.__class__.__name__,
        exception_type=exc.__class__.__name__,
        traceback=tb,
        **context,
    )


def format_traceback(exc: BaseException) -> str:
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


def diagnostics_summary() -> dict[str, str | bool | None]:
    log_file = get_log_file()
    return {
        "debug": is_debug_enabled(),
        "log_file": str(log_file) if log_file is not None else None,
        "debug_env_var": DEBUG_ENV_VAR,
        "log_env_var": LOG_ENV_VAR,
    }


configure_from_environment()
