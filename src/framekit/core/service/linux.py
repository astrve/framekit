"""Linux user-service management for Framekit via systemd --user.

Provides helpers for installing, uninstalling, starting, stopping, and
querying a Framekit service unit in ``~/.config/systemd/user``.

Public functions return ``(ok: bool, message: str)`` and do not raise on
operational errors so the CLI layer can handle output/exit codes consistently.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

_UNIT_NAME = "framekit.service"
_DESCRIPTION = "Framekit Web Service"


def _run(args: list[str], timeout: float = 15.0) -> tuple[bool, str]:
    """Run subprocess and return ``(success, combined_output)``."""
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


def _linux_only() -> tuple[bool, str] | None:
    """Return error tuple on unsupported OS, else ``None``."""
    if not sys.platform.startswith("linux"):
        return False, "Linux service management is only supported on Linux."
    return None


def _find_systemctl() -> str | None:
    """Return path to ``systemctl`` when present."""
    return shutil.which("systemctl")


def _find_journalctl() -> str | None:
    """Return path to ``journalctl`` when present."""
    return shutil.which("journalctl")


def _systemd_user_dir() -> Path:
    """Return systemd user-unit directory."""
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    root = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return root / "systemd" / "user"


def _build_exec_start(host: str, port: int) -> str:
    """Return ExecStart command using ``framekit serve``."""
    framekit_exe = shutil.which("framekit")
    host_arg = shlex.quote(host)
    if framekit_exe:
        return (
            f"{shlex.quote(framekit_exe)} serve "
            f"--host {host_arg} --port {int(port)}"
        )
    return (
        f"{shlex.quote(sys.executable)} -m framekit serve "
        f"--host {host_arg} --port {int(port)}"
    )


def _build_unit_text(host: str, port: int) -> str:
    """Build systemd unit file content."""
    exec_start = _build_exec_start(host, port)
    return (
        "[Unit]\n"
        f"Description={_DESCRIPTION}\n"
        "After=network.target\n\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart={exec_start}\n"
        "Restart=on-failure\n"
        "RestartSec=5\n"
        "Environment=PYTHONUNBUFFERED=1\n\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )


def _is_missing_unit_message(message: str) -> bool:
    low = message.lower()
    patterns = (
        "not loaded",
        "not-found",
        "no such file",
        "unit framekit.service could not be found",
        "unit framekit.service not found",
    )
    return any(pattern in low for pattern in patterns)


def install_systemd_user(
    host: str,
    port: int,
    unit_dir: Path | None = None,
) -> tuple[bool, str]:
    """Install framekit user-service unit and enable at login."""
    guard = _linux_only()
    if guard is not None:
        return guard

    systemctl = _find_systemctl()
    if not systemctl:
        return False, "systemctl not found. Install systemd user tools first."

    target_dir = unit_dir or _systemd_user_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    unit_path = target_dir / _UNIT_NAME
    unit_path.write_text(_build_unit_text(host, port), encoding="utf-8")

    ok, out = _run([systemctl, "--user", "daemon-reload"])
    if not ok:
        return False, f"systemctl --user daemon-reload failed: {out}"

    ok, out = _run([systemctl, "--user", "enable", _UNIT_NAME])
    if not ok:
        return False, f"systemctl --user enable failed: {out}"

    return True, (
        f"Installed user unit: {unit_path}\n"
        f"Enabled at login: {_UNIT_NAME}\n"
        f"Start now: systemctl --user start {_UNIT_NAME}"
    )


def uninstall_systemd_user(unit_dir: Path | None = None) -> tuple[bool, str]:
    """Disable and remove framekit user-service unit."""
    guard = _linux_only()
    if guard is not None:
        return guard

    systemctl = _find_systemctl()
    if not systemctl:
        return False, "systemctl not found. Install systemd user tools first."

    ok, out = _run([systemctl, "--user", "disable", "--now", _UNIT_NAME])
    if not ok and not _is_missing_unit_message(out):
        return False, f"systemctl --user disable --now failed: {out}"

    target_dir = unit_dir or _systemd_user_dir()
    unit_path = target_dir / _UNIT_NAME
    try:
        unit_path.unlink(missing_ok=True)
    except OSError as exc:
        return False, f"Failed to remove unit file {unit_path}: {exc}"

    ok, out = _run([systemctl, "--user", "daemon-reload"])
    if not ok:
        return False, f"systemctl --user daemon-reload failed: {out}"

    return True, f"Removed user unit '{_UNIT_NAME}'."


def start_systemd_user() -> tuple[bool, str]:
    """Start framekit user-service."""
    guard = _linux_only()
    if guard is not None:
        return guard
    systemctl = _find_systemctl()
    if not systemctl:
        return False, "systemctl not found. Install systemd user tools first."
    ok, out = _run([systemctl, "--user", "start", _UNIT_NAME])
    if not ok:
        return False, f"systemctl --user start failed: {out}"
    return True, f"User service '{_UNIT_NAME}' start requested."


def stop_systemd_user() -> tuple[bool, str]:
    """Stop framekit user-service."""
    guard = _linux_only()
    if guard is not None:
        return guard
    systemctl = _find_systemctl()
    if not systemctl:
        return False, "systemctl not found. Install systemd user tools first."
    ok, out = _run([systemctl, "--user", "stop", _UNIT_NAME])
    if not ok:
        return False, f"systemctl --user stop failed: {out}"
    return True, f"User service '{_UNIT_NAME}' stop requested."


def restart_systemd_user() -> tuple[bool, str]:
    """Restart framekit user-service."""
    guard = _linux_only()
    if guard is not None:
        return guard
    systemctl = _find_systemctl()
    if not systemctl:
        return False, "systemctl not found. Install systemd user tools first."
    ok, out = _run([systemctl, "--user", "restart", _UNIT_NAME])
    if not ok:
        return False, f"systemctl --user restart failed: {out}"
    return True, f"User service '{_UNIT_NAME}' restart requested."


def query_systemd_status() -> dict[str, str]:
    """Return status from ``systemctl --user show framekit.service``."""
    guard = _linux_only()
    if guard is not None:
        return {"error": guard[1]}
    systemctl = _find_systemctl()
    if not systemctl:
        return {"error": "systemctl not found"}

    ok, out = _run(
        [
            systemctl,
            "--user",
            "show",
            _UNIT_NAME,
            "--property=LoadState,ActiveState,SubState,UnitFileState,MainPID",
            "--no-pager",
        ],
        timeout=5.0,
    )
    if not ok:
        return {"error": out or f"Failed to query {_UNIT_NAME}"}

    result: dict[str, str] = {}
    for line in out.splitlines():
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip().lower()] = value.strip()

    if result.get("loadstate") == "not-found":
        result["error"] = f"Unit {_UNIT_NAME} is not installed."

    active = result.get("activestate")
    if active:
        result["state"] = active.upper()
    return result


def query_http_status(
    host: str = "127.0.0.1",
    port: int = 8000,
    timeout: float = 3.0,
) -> dict | None:
    """GET ``/api/v1/service/status`` and return parsed JSON."""
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
    """Read local ``service.state.json`` heartbeat file."""
    state_path = service_dir / "service.state.json"
    try:
        text = state_path.read_text(encoding="utf-8")
        return json.loads(text)
    except (OSError, json.JSONDecodeError):
        return None


def journal_logs(lines: int = 50, follow: bool = False) -> tuple[bool, str]:
    """Return/tail journal logs for framekit user unit."""
    guard = _linux_only()
    if guard is not None:
        return guard

    journalctl = _find_journalctl()
    if not journalctl:
        return False, "journalctl not found. Install systemd journal tools first."

    cmd = [
        journalctl,
        "--user",
        "-u",
        _UNIT_NAME,
        "-n",
        str(max(1, int(lines))),
        "--no-pager",
    ]
    if follow:
        cmd.insert(5, "-f")
        try:
            subprocess.run(cmd, check=False)  # nosec B603
            return True, ""
        except FileNotFoundError:
            return False, f"Executable not found: {journalctl}"
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)
    return _run(cmd, timeout=20.0)
