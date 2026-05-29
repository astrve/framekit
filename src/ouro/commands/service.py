"""ouro service — service lifecycle management (Windows + Linux).

Subcommands:
    install    Install Ouro as a Windows service or scheduled task.
    uninstall  Remove the installed service or scheduled task.
    start      Start the service.
    stop       Stop the service.
    restart    Stop then start the service.
    status     Show the current service status.
    logs       Tail or follow service log output.
"""

from __future__ import annotations

import sys

from ouro.ui.click_helper import click

# ---------------------------------------------------------------------------
# Group
# ---------------------------------------------------------------------------


@click.group(
    "service",
    help=(
        "Manage the Ouro background service.\n\n"
        "Install Ouro as a persistent background service:\n\n"
        "    ouro service install\n\n"
        "Windows modes:\n"
        "  nssm  — preferred; handles log redirection and restart-on-failure.\n"
        "  sc    — built-in fallback using sc.exe; no log redirection.\n"
        "  task  — scheduled task (ONLOGON); usually no admin rights required,\n"
        "          though an elevated shell or group policy may still block it.\n\n"
        "Linux mode:\n"
        "  systemd — current-user unit (~/.config/systemd/user/ouro.service)."
    ),
)
def service_group() -> None:
    """Ouro service management commands."""


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------


@service_group.command("install")
@click.option(
    "--mode",
    type=click.Choice(["auto", "nssm", "sc", "task", "systemd"]),
    default="auto",
    show_default=True,
    help=(
        "Install mode. Windows: auto -> nssm -> sc. "
        "Linux: auto -> systemd (user unit)."
    ),
)
@click.option("--host", default="127.0.0.1", show_default=True, help="Bind host.")
@click.option("--port", default=8000, type=int, show_default=True, help="Bind port.")
def install_command(mode: str, host: str, port: int) -> None:
    """Install Ouro as a background service."""
    platform_kind = _platform_kind()

    if platform_kind == "windows":
        from ouro.core.paths import get_service_dir
        from ouro.core.service.windows import (
            _find_nssm,
            _python_exe,
            install_nssm,
            install_sc,
            install_task,
        )

        if mode == "systemd":
            click.echo("ERROR: --mode=systemd is Linux-only.", err=True)
            sys.exit(1)

        python_exe = _python_exe()
        service_dir = get_service_dir()
        service_dir.mkdir(parents=True, exist_ok=True)
        log_out = str(service_dir / "service.out.log")
        log_err = str(service_dir / "service.err.log")

        nssm = _find_nssm()

        resolved_mode = mode
        if mode == "auto":
            if nssm:
                resolved_mode = "nssm"
            else:
                resolved_mode = "sc"
                click.echo(
                    "NOTE: nssm not found. Using sc.exe (no log redirection). "
                    "Install nssm for better log handling: https://nssm.cc/",
                    err=True,
                )

        if resolved_mode == "nssm":
            if not nssm:
                click.echo(
                    "ERROR: nssm not found. Install nssm first: https://nssm.cc/\n"
                    "Or use --mode=sc or --mode=task.",
                    err=True,
                )
                sys.exit(1)
            ok, msg = install_nssm(nssm, python_exe, host, port, log_out, log_err)
        elif resolved_mode == "sc":
            ok, msg = install_sc(python_exe, host, port)
        else:  # task
            ok, msg = install_task(python_exe, host, port, service_dir)
    elif platform_kind == "linux":
        from ouro.core.service.linux import install_systemd_user

        resolved_mode = "systemd" if mode == "auto" else mode
        if resolved_mode != "systemd":
            click.echo(
                "ERROR: On Linux, use --mode=systemd (or --mode=auto).",
                err=True,
            )
            sys.exit(1)
        ok, msg = install_systemd_user(host=host, port=port)
    else:
        _unsupported_platform_exit("install")
        return

    if not ok:
        click.echo(f"ERROR: {msg}", err=True)
        sys.exit(1)

    click.echo(msg)
    click.echo(
        "\nTo verify: ouro service status\n"
        "To start:  ouro service start\n"
        "Logs:      ouro service logs"
    )


# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------


@service_group.command("uninstall")
@click.option(
    "--mode",
    type=click.Choice(["auto", "nssm", "sc", "task", "systemd"]),
    default="auto",
    show_default=True,
    help="Uninstall mode. Windows auto: nssm->sc. Linux auto: systemd.",
)
@click.confirmation_option(
    prompt="Remove the Ouro service/task? This will stop it if running."
)
def uninstall_command(mode: str) -> None:
    """Remove installed Ouro service unit/task."""
    platform_kind = _platform_kind()

    if platform_kind == "windows":
        from ouro.core.service.windows import (
            _find_nssm,
            uninstall_nssm,
            uninstall_sc,
            uninstall_task,
        )

        if mode == "systemd":
            click.echo("ERROR: --mode=systemd is Linux-only.", err=True)
            sys.exit(1)

        nssm = _find_nssm()

        resolved_mode = mode
        if mode == "auto":
            resolved_mode = "nssm" if nssm else "sc"

        if resolved_mode == "nssm":
            if not nssm:
                click.echo("nssm not found — trying sc.exe instead.", err=True)
                ok, msg = uninstall_sc()
            else:
                ok, msg = uninstall_nssm(nssm)
        elif resolved_mode == "sc":
            ok, msg = uninstall_sc()
        else:
            ok, msg = uninstall_task()
    elif platform_kind == "linux":
        from ouro.core.service.linux import uninstall_systemd_user

        resolved_mode = "systemd" if mode == "auto" else mode
        if resolved_mode != "systemd":
            click.echo(
                "ERROR: On Linux, use --mode=systemd (or --mode=auto).",
                err=True,
            )
            sys.exit(1)
        ok, msg = uninstall_systemd_user()
    else:
        _unsupported_platform_exit("uninstall")
        return

    if ok:
        click.echo(msg)
    else:
        click.echo(f"ERROR: {msg}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------


@service_group.command("start")
@click.option(
    "--mode",
    type=click.Choice(["auto", "sc", "task", "systemd"]),
    default="auto",
    show_default=True,
    help="Start mode.",
)
def start_command(mode: str) -> None:
    """Start the Ouro service."""
    platform_kind = _platform_kind()

    if platform_kind == "windows":
        if mode == "systemd":
            click.echo("ERROR: --mode=systemd is Linux-only.", err=True)
            sys.exit(1)
        from ouro.core.paths import get_service_dir
        from ouro.core.service.windows import start_service_sc, start_task

        resolved_mode = _resolve_windows_run_mode(mode)
        if resolved_mode == "sc":
            ok, msg = start_service_sc()
        else:
            pid_path = get_service_dir() / "service.pid"
            ok, msg = start_task(pid_path)
    elif platform_kind == "linux":
        from ouro.core.service.linux import start_systemd_user

        resolved_mode = "systemd" if mode == "auto" else mode
        if resolved_mode != "systemd":
            click.echo(
                "ERROR: On Linux, use --mode=systemd (or --mode=auto).",
                err=True,
            )
            sys.exit(1)
        ok, msg = start_systemd_user()
    else:
        _unsupported_platform_exit("start")
        return

    if ok:
        click.echo(msg)
    else:
        click.echo(f"ERROR: {msg}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# stop
# ---------------------------------------------------------------------------


@service_group.command("stop")
@click.option(
    "--mode",
    type=click.Choice(["auto", "sc", "task", "systemd"]),
    default="auto",
    show_default=True,
    help="Stop mode.",
)
def stop_command(mode: str) -> None:
    """Stop the Ouro service."""
    platform_kind = _platform_kind()

    if platform_kind == "windows":
        if mode == "systemd":
            click.echo("ERROR: --mode=systemd is Linux-only.", err=True)
            sys.exit(1)
        from ouro.core.paths import get_service_dir
        from ouro.core.service.windows import stop_service_sc, stop_task

        resolved_mode = _resolve_windows_run_mode(mode)
        if resolved_mode == "sc":
            ok, msg = stop_service_sc()
        else:
            pid_path = get_service_dir() / "service.pid"
            ok, msg = stop_task(pid_path)
    elif platform_kind == "linux":
        from ouro.core.service.linux import stop_systemd_user

        resolved_mode = "systemd" if mode == "auto" else mode
        if resolved_mode != "systemd":
            click.echo(
                "ERROR: On Linux, use --mode=systemd (or --mode=auto).",
                err=True,
            )
            sys.exit(1)
        ok, msg = stop_systemd_user()
    else:
        _unsupported_platform_exit("stop")
        return

    if ok:
        click.echo(msg)
    else:
        click.echo(f"ERROR: {msg}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# restart
# ---------------------------------------------------------------------------


@service_group.command("restart")
@click.option(
    "--mode",
    type=click.Choice(["auto", "sc", "task", "systemd"]),
    default="auto",
    show_default=True,
    help="Service mode.",
)
def restart_command(mode: str) -> None:
    """Stop then start the Ouro service."""
    platform_kind = _platform_kind()

    if platform_kind == "windows":
        if mode == "systemd":
            click.echo("ERROR: --mode=systemd is Linux-only.", err=True)
            sys.exit(1)

        from ouro.core.paths import get_service_dir
        from ouro.core.service.windows import (
            start_service_sc,
            start_task,
            stop_service_sc,
            stop_task,
        )

        resolved_mode = _resolve_windows_run_mode(mode)
        pid_path = get_service_dir() / "service.pid"

        if resolved_mode == "sc":
            ok, msg = stop_service_sc()
        else:
            ok, msg = stop_task(pid_path)

        if not ok:
            # Non-fatal: service may already be stopped
            click.echo(f"NOTE: stop reported: {msg}", err=True)

        if resolved_mode == "sc":
            ok, msg = start_service_sc()
        else:
            ok, msg = start_task(pid_path)
    elif platform_kind == "linux":
        from ouro.core.service.linux import restart_systemd_user

        resolved_mode = "systemd" if mode == "auto" else mode
        if resolved_mode != "systemd":
            click.echo(
                "ERROR: On Linux, use --mode=systemd (or --mode=auto).",
                err=True,
            )
            sys.exit(1)
        ok, msg = restart_systemd_user()
    else:
        _unsupported_platform_exit("restart")
        return

    if ok:
        click.echo(msg)
    else:
        click.echo(f"ERROR: {msg}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@service_group.command("status")
@click.option("--host", default="127.0.0.1", show_default=True, help="Service host.")
@click.option("--port", default=8000, type=int, show_default=True, help="Service port.")
@click.option("--json", "output_json", is_flag=True, default=False, help="Output JSON.")
def status_command(host: str, port: int, output_json: bool) -> None:
    """Show the current Ouro service status."""
    import json as _json
    import time as _time

    from ouro.core.paths import get_service_dir

    platform_kind = _platform_kind()

    if platform_kind == "windows":
        from ouro.core.service.windows import (
            query_http_status,
            query_sc_status,
            query_task_status,
            read_service_state,
        )
    elif platform_kind == "linux":
        from ouro.core.service.linux import (
            query_http_status,
            query_systemd_status,
            read_service_state,
        )
    else:
        _unsupported_platform_exit("status")
        return

    # Try HTTP first (most accurate when service is running)
    http_status = query_http_status(host, port)
    auth_required = bool(http_status and http_status.get("auth_required"))

    # When auth blocks HTTP, fall back to the local heartbeat file
    local_state: dict | None = None
    if auth_required or http_status is None:
        local_state = read_service_state(get_service_dir())

    if platform_kind == "windows":
        sc_status = query_sc_status()
        task_status = query_task_status()
        systemd_status: dict[str, str] = {}
    elif platform_kind == "linux":
        sc_status = {}
        task_status = {}
        systemd_status = query_systemd_status()
    else:
        sc_status = {}
        task_status = {}
        systemd_status = {}

    combined = {
        "http": http_status,
        "local_state": local_state,
        "sc": sc_status,
        "task": task_status,
        "systemd": systemd_status,
    }

    if output_json:
        click.echo(_json.dumps(combined, indent=2))
        return

    # Human-readable output
    if http_status and not auth_required:
        # Full detail from HTTP API
        status_val = http_status.get("status", "unknown")
        pid = http_status.get("pid")
        uptime = http_status.get("uptime_seconds")
        click.echo(f"Status:  {status_val}")
        if pid:
            click.echo(f"PID:     {pid}")
        if uptime is not None:
            mins, secs = divmod(int(uptime), 60)
            hours, mins = divmod(mins, 60)
            click.echo(f"Uptime:  {hours}h {mins}m {secs}s")
        watcher = http_status.get("watcher")
        if watcher:
            w_status = watcher.get("status", "unknown")
            folders = watcher.get("folders_active", 0)
            click.echo(f"Watcher: {w_status} ({folders} folder(s) active)")
    elif auth_required:
        # Service is reachable but auth blocks the status endpoint
        click.echo("Status:  running (auth required for full details)")
        click.echo(f"         {host}:{port} returned 401/403")
        if local_state:
            pid = local_state.get("pid")
            started_at = local_state.get("started_at")
            heartbeat_at = local_state.get("heartbeat_at")
            if pid:
                click.echo(f"PID:     {pid}  (from local state file)")
            if started_at and heartbeat_at:
                uptime_s = int(_time.time() - started_at)
                mins, secs = divmod(uptime_s, 60)
                hours, mins = divmod(mins, 60)
                click.echo(f"Uptime:  ~{hours}h {mins}m {secs}s  (from local state file)")
                age = int(_time.time() - heartbeat_at)
                click.echo(f"Heartbeat: {age}s ago")
        click.echo(
            "Hint: authenticate with 'ouro user' or query the API with a JWT token."
        )
    elif local_state and local_state.get("status") == "running":
        # HTTP unreachable but local state says running (process may be starting)
        pid = local_state.get("pid")
        click.echo("Status:  running (HTTP not yet reachable)")
        if pid:
            click.echo(f"PID:     {pid}  (from local state file)")
    elif platform_kind == "linux":
        state = systemd_status.get("state")
        main_pid = systemd_status.get("mainpid", "0")
        if state:
            click.echo(f"Systemd state: {state}")
            if main_pid and main_pid != "0":
                click.echo(f"PID:          {main_pid}")
        elif "error" in systemd_status:
            click.echo(f"Systemd: {systemd_status['error']}")
        else:
            click.echo("Ouro service is not running (HTTP unreachable).")
    elif platform_kind == "windows":
        # Fall back to sc / task info
        sc_state = sc_status.get("state")
        if sc_state:
            click.echo(f"SC state: {sc_state}")
        elif "error" in sc_status:
            click.echo(f"SC: {sc_status['error']}")

        task_status_val = task_status.get("status")
        if task_status_val:
            click.echo(f"Task status: {task_status_val}")
        elif "error" in task_status:
            click.echo(f"Task: {task_status['error']}")

        if not sc_state and not task_status_val:
            click.echo(
                "Ouro service is not running "
                "(HTTP unreachable, no SC/task entry found)."
            )
    else:
        click.echo("Ouro service is not running (HTTP unreachable).")


# ---------------------------------------------------------------------------
# logs
# ---------------------------------------------------------------------------


@service_group.command("logs")
@click.option(
    "--follow", "-f",
    is_flag=True,
    default=False,
    help="Follow log output (like tail -f).",
)
@click.option(
    "--lines", "-n",
    default=50,
    type=int,
    show_default=True,
    help="Number of lines to show (without --follow).",
)
@click.option(
    "--stderr",
    is_flag=True,
    default=False,
    help="Show stderr log instead of stdout log.",
)
def logs_command(follow: bool, lines: int, stderr: bool) -> None:
    """Tail or follow the Ouro service log."""
    platform_kind = _platform_kind()

    if platform_kind == "linux":
        from ouro.core.service.linux import journal_logs

        if stderr:
            click.echo(
                "NOTE: --stderr is Windows-only. Linux uses journald per unit.",
                err=True,
            )

        ok, output = journal_logs(lines=lines, follow=follow)
        if not ok:
            click.echo(f"ERROR: {output}", err=True)
            sys.exit(1)
        if output:
            for line in output.splitlines():
                click.echo(line)
        return

    if platform_kind != "windows":
        _unsupported_platform_exit("logs")
        return

    from ouro.core.paths import get_service_dir
    from ouro.core.service.windows import follow_file, tail_file

    service_dir = get_service_dir()
    log_path = service_dir / ("service.err.log" if stderr else "service.out.log")

    if follow:
        click.echo(f"Following {log_path} (Ctrl+C to stop)...")
        try:
            for line in follow_file(log_path):
                click.echo(line)
        except KeyboardInterrupt:
            pass
    else:
        recent = tail_file(log_path, lines)
        if not recent:
            click.echo(
                f"No log output found at {log_path}\n"
                "The service may not be running, or no output has been written yet.\n"
                "Note: if installed with --mode=task, logs are written only after\n"
                "the first task run. Start it with: schtasks /Run /TN Ouro"
            )
        else:
            for line in recent:
                click.echo(line)


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _resolve_windows_run_mode(mode: str) -> str:
    """Resolve 'auto' to 'sc' or 'task' based on service presence."""
    if mode != "auto":
        return mode
    # Check if a Windows service entry exists
    from ouro.core.service.windows import query_sc_status
    sc = query_sc_status()
    if "error" not in sc:
        return "sc"
    return "task"


def _platform_kind() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    return "unsupported"


def _unsupported_platform_exit(action: str) -> None:
    click.echo(
        (
            f"ERROR: Service {action} is supported on Windows and Linux only. "
            f"Current platform: {sys.platform}"
        ),
        err=True,
    )
    sys.exit(1)
