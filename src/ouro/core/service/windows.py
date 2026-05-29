"""Windows service / scheduled-task management for Ouro.

Provides helpers for installing, uninstalling, starting, stopping, and
querying the Ouro service on Windows.

Two install modes:
    nssm  — preferred; handles log redirection, log rotation, restart-on-failure.
    sc    — built-in fallback; no log redirection.

One additional mode:
    task  — schtasks ONLOGON; typically does not require admin rights for
            current-user tasks, though group policy or an elevated shell
            can still prevent task creation.

None of the public functions raise on unexpected output — they return
(ok: bool, message: str) so the CLI layer can decide how to handle errors.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Generator

_SERVICE_NAME = "Ouro"
_DISPLAY_NAME = "Ouro Web Service"
_DESCRIPTION = "Ouro release-workflow web service and file watcher."
_TASK_NAME = "Ouro"

# NSSM log-rotation threshold: 50 MB
_LOG_ROTATE_BYTES = 52_428_800


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run(args: list[str], timeout: float = 15.0) -> tuple[bool, str]:
    """Run a subprocess and return (success, combined_output).

    Never raises; returns (False, error_text) on failure.
    """
    try:
        result = subprocess.run(  # nosec B603
            args,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
        )
        combined = (result.stdout + result.stderr).strip()
        return result.returncode == 0, combined
    except FileNotFoundError:
        return False, f"Executable not found: {args[0]}"
    except subprocess.TimeoutExpired:
        return False, f"Command timed out after {timeout}s: {args[0]}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _windows_only() -> tuple[bool, str] | None:
    """Return an error tuple when not on Windows, or None when on Windows."""
    if sys.platform != "win32":
        return False, "Windows service management is only supported on Windows."
    return None


def _find_nssm() -> str | None:
    """Return the path to nssm.exe, or None if not installed."""
    return shutil.which("nssm")


def _python_exe() -> str:
    """Return the absolute path to the current Python interpreter."""
    return sys.executable


# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------


def install_nssm(
    nssm: str,
    python_exe: str,
    host: str,
    port: int,
    log_out: str,
    log_err: str,
) -> tuple[bool, str]:
    """Install the Ouro Windows service via NSSM.

    Configures auto-start, log redirection, log rotation, and
    restart-on-failure (3 restart attempts, 60 s delay).

    Args:
        nssm:       Path to nssm.exe.
        python_exe: Path to the Python interpreter.
        host:       Bind host for `ouro serve`.
        port:       Bind port for `ouro serve`.
        log_out:    Absolute path for stdout log file.
        log_err:    Absolute path for stderr log file.

    Returns:
        (True, "Installed successfully.") on success.
        (False, error_detail) on failure.
    """
    steps: list[tuple[str, list[str]]] = [
        (
            "install service",
            [nssm, "install", _SERVICE_NAME, python_exe,
             "-m", "ouro", "serve", "--host", host, "--port", str(port)],
        ),
        (
            "set display name",
            [nssm, "set", _SERVICE_NAME, "DisplayName", _DISPLAY_NAME],
        ),
        (
            "set description",
            [nssm, "set", _SERVICE_NAME, "Description", _DESCRIPTION],
        ),
        (
            "set auto-start",
            [nssm, "set", _SERVICE_NAME, "Start", "SERVICE_AUTO_START"],
        ),
        (
            "set stdout log",
            [nssm, "set", _SERVICE_NAME, "AppStdout", log_out],
        ),
        (
            "set stderr log",
            [nssm, "set", _SERVICE_NAME, "AppStderr", log_err],
        ),
        (
            "enable log rotation",
            [nssm, "set", _SERVICE_NAME, "AppRotateFiles", "1"],
        ),
        (
            "enable online rotation",
            [nssm, "set", _SERVICE_NAME, "AppRotateOnline", "1"],
        ),
        (
            "set rotation threshold",
            [nssm, "set", _SERVICE_NAME, "AppRotateBytes", str(_LOG_ROTATE_BYTES)],
        ),
        (
            "configure restart delay",
            [nssm, "set", _SERVICE_NAME, "AppThrottle", "60000"],
        ),
        (
            "configure exit action (restart)",
            [nssm, "set", _SERVICE_NAME, "AppExit", "Default", "Restart"],
        ),
    ]

    for step_name, cmd in steps:
        ok, out = _run(cmd)
        if not ok:
            return False, f"NSSM step '{step_name}' failed: {out}"

    return True, f"Service '{_SERVICE_NAME}' installed (NSSM). Run: sc start {_SERVICE_NAME}"


def install_sc(python_exe: str, host: str, port: int) -> tuple[bool, str]:
    """Install the Ouro Windows service via sc.exe (no log redirection).

    Args:
        python_exe: Path to the Python interpreter.
        host:       Bind host.
        port:       Bind port.

    Returns:
        (True, message) on success, (False, error) on failure.
    """
    guard = _windows_only()
    if guard is not None:
        return guard

    binpath = f'"{python_exe}" -m ouro serve --host {host} --port {port}'
    ok, out = _run([
        "sc", "create", _SERVICE_NAME,
        f"binpath= {binpath}",
        "start= auto",
        f"DisplayName= {_DISPLAY_NAME}",
    ])
    if not ok:
        return False, f"sc create failed: {out}"

    # Set description (ignore failure — cosmetic)
    _run(["sc", "description", _SERVICE_NAME, _DESCRIPTION])

    # Configure restart on failure: restart after 60 s for first 3 failures
    _run([
        "sc", "failure", _SERVICE_NAME,
        "reset= 3600",
        "actions= restart/60000/restart/60000/restart/60000",
    ])

    return True, f"Service '{_SERVICE_NAME}' installed (sc.exe). Run: sc start {_SERVICE_NAME}"


def _build_task_tr(bat_path: Path) -> str:
    """Build the /TR value for schtasks, wrapping bat_path for cmd.exe.

    Uses the CMD.EXE double-outer-quote convention when the path contains
    spaces so that Task Scheduler correctly passes the quoted path to cmd.
    """
    bat_str = str(bat_path)
    if " " in bat_str:
        return f'cmd.exe /c ""{bat_str}""'
    return f'cmd.exe /c "{bat_str}"'


def _write_task_bat(
    bat_path: Path,
    python_exe: str,
    host: str,
    port: int,
    log_out: str,
    log_err: str,
) -> None:
    """Write the batch-file wrapper used by the scheduled task.

    Redirects stdout and stderr to the service log files so that
    ``ouro service logs`` works in task mode.
    """
    line = (
        f'"{python_exe}" -m ouro serve --host {host} --port {port}'
        f' >> "{log_out}" 2>> "{log_err}"'
    )
    content = "@echo off\r\n" + line + "\r\n"
    bat_path.write_bytes(content.encode("utf-8"))


def install_task(
    python_exe: str,
    host: str,
    port: int,
    service_dir: Path | None = None,
) -> tuple[bool, str]:
    """Install a scheduled task that starts Ouro at user log-on.

    Creates a batch-file wrapper in ``service_dir`` that redirects stdout
    and stderr to log files, then registers a schtasks ONLOGON trigger.

    This mode is intended for current-user installs. It typically does not
    require admin rights, but group policy or running from an elevated shell
    can still prevent task creation.

    Note: ``/RL HIGHEST`` is intentionally omitted. Registering a task at
    the HIGHEST run-level requires elevation and contradicts the purpose of
    this mode. Use ``--mode=sc`` or ``--mode=nssm`` for system-level install.

    Args:
        python_exe:  Path to the Python interpreter.
        host:        Bind host.
        port:        Bind port.
        service_dir: Directory for the bat wrapper and log files.
                     Auto-discovered when None.

    Returns:
        (True, message) on success, (False, error) on failure.
    """
    guard = _windows_only()
    if guard is not None:
        return guard

    if service_dir is None:
        from ouro.core.paths import get_service_dir  # lazy to avoid circular
        service_dir = get_service_dir()

    service_dir.mkdir(parents=True, exist_ok=True)
    log_out = str(service_dir / "service.out.log")
    log_err = str(service_dir / "service.err.log")
    bat_path = service_dir / "ouro-serve.bat"

    _write_task_bat(bat_path, python_exe, host, port, log_out, log_err)

    tr_value = _build_task_tr(bat_path)
    ok, out = _run([
        "schtasks", "/Create",
        "/TN", _TASK_NAME,
        "/TR", tr_value,
        "/SC", "ONLOGON",
        "/F",
    ])
    if not ok:
        return False, _task_error_message(out)

    return True, (
        f"Scheduled task '{_TASK_NAME}' created (ONLOGON). "
        "Ouro will start automatically at next log-on. "
        f"To start now: schtasks /Run /TN {_TASK_NAME}\n"
        f"Logs: {log_out}"
    )


def _task_error_message(raw_output: str) -> str:
    """Translate raw schtasks error output into actionable CLI guidance."""
    low = raw_output.lower()
    # "Access denied" appears in English, French ("Accès refusé"),
    # and other locales; also catch replacement-character variants
    # produced by errors='replace' decoding of OEM codepage bytes.
    access_denied_patterns = (
        "access denied",
        "access is denied",
        "accès refusé",               # French (correct UTF-8)
        "acc�s refus�",     # French (errors='replace' mojibake)
        "zugriff verweigert",         # German
        "acceso denegado",            # Spanish
    )
    if any(p in low for p in access_denied_patterns):
        return (
            "schtasks /Create failed: Access denied.\n\n"
            "The scheduled task mode (--mode=task) normally does NOT require\n"
            "admin rights, but this error can occur when:\n\n"
            "  1. The terminal is already running as Administrator and Windows\n"
            "     refuses to create a per-user task from an elevated shell.\n"
            "     Fix: open a normal (non-elevated) terminal and retry.\n\n"
            "  2. Group Policy blocks task creation for this user account.\n"
            "     Fix: contact your system administrator, or use --mode=sc\n"
            "     (requires admin) or --mode=nssm (requires nssm + admin).\n\n"
            f"Raw output: {raw_output}"
        )
    return f"schtasks /Create failed: {raw_output}"


# ---------------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------------


def uninstall_nssm(nssm: str) -> tuple[bool, str]:
    """Remove the NSSM-managed Ouro service."""
    # Stop first (ignore errors — service may already be stopped)
    _run([nssm, "stop", _SERVICE_NAME, "confirm"])
    ok, out = _run([nssm, "remove", _SERVICE_NAME, "confirm"])
    if not ok:
        return False, f"NSSM remove failed: {out}"
    return True, f"Service '{_SERVICE_NAME}' removed (NSSM)."


def uninstall_sc() -> tuple[bool, str]:
    """Remove the sc.exe-managed Ouro service."""
    guard = _windows_only()
    if guard is not None:
        return guard

    # Stop first
    _run(["sc", "stop", _SERVICE_NAME])
    ok, out = _run(["sc", "delete", _SERVICE_NAME])
    if not ok:
        return False, f"sc delete failed: {out}"
    return True, f"Service '{_SERVICE_NAME}' removed (sc.exe)."


def uninstall_task() -> tuple[bool, str]:
    """Remove the scheduled task for Ouro."""
    guard = _windows_only()
    if guard is not None:
        return guard

    ok, out = _run(["schtasks", "/Delete", "/TN", _TASK_NAME, "/F"])
    if not ok:
        return False, f"schtasks /Delete failed: {out}"
    return True, f"Scheduled task '{_TASK_NAME}' removed."


# ---------------------------------------------------------------------------
# Start / stop
# ---------------------------------------------------------------------------


def start_service_sc() -> tuple[bool, str]:
    """Start the Ouro Windows service via sc.exe."""
    guard = _windows_only()
    if guard is not None:
        return guard

    ok, out = _run(["sc", "start", _SERVICE_NAME])
    if not ok:
        return False, f"sc start failed: {out}"
    return True, f"Service '{_SERVICE_NAME}' start requested."


def stop_service_sc() -> tuple[bool, str]:
    """Stop the Ouro Windows service via sc.exe."""
    guard = _windows_only()
    if guard is not None:
        return guard

    ok, out = _run(["sc", "stop", _SERVICE_NAME])
    if not ok:
        return False, f"sc stop failed: {out}"
    return True, f"Service '{_SERVICE_NAME}' stop requested."


def start_task(pid_path: Path | None = None) -> tuple[bool, str]:
    """Start the Ouro scheduled task via schtasks."""
    guard = _windows_only()
    if guard is not None:
        return guard

    ok, out = _run(["schtasks", "/Run", "/TN", _TASK_NAME])
    if not ok:
        return False, f"schtasks /Run failed: {out}"
    return True, f"Scheduled task '{_TASK_NAME}' started."


def stop_task(pid_path: Path | None = None) -> tuple[bool, str]:
    """Stop the Ouro scheduled task via schtasks.

    Also terminates the process identified by pid_path if present.
    """
    guard = _windows_only()
    if guard is not None:
        return guard

    # Try to kill via PID first for a clean shutdown
    if pid_path is not None and pid_path.exists():
        try:
            pid = int(pid_path.read_text().strip())
            _run(["taskkill", "/PID", str(pid), "/F"])
        except Exception:  # noqa: BLE001
            pass

    ok, out = _run(["schtasks", "/End", "/TN", _TASK_NAME])
    if not ok:
        return False, f"schtasks /End failed: {out}"
    return True, f"Scheduled task '{_TASK_NAME}' stopped."


# ---------------------------------------------------------------------------
# Status queries
# ---------------------------------------------------------------------------


def query_sc_status() -> dict[str, str]:
    """Return a status dict from `sc query Ouro`.

    Keys: state, type, name, error.
    Returns {"error": "..."} when the service is not found or sc fails.
    """
    ok, out = _run(["sc", "query", _SERVICE_NAME])
    if not ok:
        return {"error": out or "Service not found or sc query failed."}

    result: dict[str, str] = {}
    for line in out.splitlines():
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip().lower().replace(" ", "_")] = value.strip()

    # Normalise the state field: "4  RUNNING" → "RUNNING"
    raw_state = result.get("state", "")
    if raw_state:
        # sc output: "4  RUNNING" or "1  STOPPED"
        parts = raw_state.split()
        result["state"] = parts[-1] if parts else raw_state

    return result


def query_task_status() -> dict[str, str]:
    """Return a status dict from `schtasks /Query` for the Ouro task.

    Returns {"error": "..."} when the task is not found.
    """
    ok, out = _run([
        "schtasks", "/Query",
        "/TN", _TASK_NAME,
        "/FO", "LIST",
    ])
    if not ok:
        return {"error": out or "Task not found."}

    result: dict[str, str] = {}
    for line in out.splitlines():
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip().lower().replace(" ", "_")] = value.strip()

    return result


def query_http_status(
    host: str = "127.0.0.1",
    port: int = 8000,
    timeout: float = 3.0,
) -> dict | None:
    """GET /api/v1/service/status and return the parsed JSON dict.

    Returns:
        Parsed JSON dict on success.
        ``{"auth_required": True, "status": "running"}`` when the server
        responds with 401 or 403 (reachable but auth is active).
        ``None`` on any network/connection error or parse failure.
    """
    url = f"http://{host}:{port}/api/v1/service/status"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # nosec B310
            raw = resp.read()
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return {"auth_required": True, "status": "running"}
        return None
    except (urllib.error.URLError, OSError, ValueError):
        return None


def read_service_state(service_dir: Path) -> dict | None:
    """Read the local ``service.state.json`` heartbeat file.

    Returns the parsed dict, or ``None`` if the file is absent or unreadable.
    The dict contains: ``status``, ``pid``, ``started_at``, ``heartbeat_at``
    (all written by :class:`ServiceSupervisor`).
    """
    state_path = service_dir / "service.state.json"
    try:
        text = state_path.read_text(encoding="utf-8")
        return json.loads(text)
    except (OSError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# Log helpers
# ---------------------------------------------------------------------------


def tail_file(path: Path, lines: int = 50) -> list[str]:
    """Return the last `lines` lines from a text file.

    Returns an empty list when the file does not exist or cannot be read.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        all_lines = text.splitlines()
        return all_lines[-lines:] if len(all_lines) > lines else all_lines
    except OSError:
        return []


def follow_file(path: Path, poll_interval: float = 0.4) -> Generator[str, None, None]:
    """Yield new lines from a growing log file (blocking tail -f equivalent).

    Yields lines as they appear. Stops when the caller breaks / closes the
    generator. The file does not need to exist when the generator starts —
    it will wait for creation.

    Args:
        path:          Path to the log file.
        poll_interval: Seconds between file checks when no new data.
    """
    offset = 0

    while True:
        if not path.exists():
            time.sleep(poll_interval)
            continue

        try:
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                fh.seek(offset)
                while True:
                    chunk = fh.read(4096)
                    if chunk:
                        for line in chunk.splitlines():
                            yield line
                        offset = fh.tell()
                    else:
                        time.sleep(poll_interval)
                        # Re-seek to detect truncation (log rotation)
                        fh.seek(0, 2)
                        new_end = fh.tell()
                        if new_end < offset:
                            # File was truncated; restart from beginning
                            offset = 0
                        break
        except OSError:
            time.sleep(poll_interval)
