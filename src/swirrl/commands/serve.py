"""swirrl serve — Start the Swirrl web service.

Launches the FastAPI application under uvicorn with an exclusive service lock,
PID file, and heartbeat. Only one instance may run per config directory.

Security: binding to a non-loopback address is refused unless at least one
admin user exists (auth is active).
"""

from __future__ import annotations

import sys

from swirrl.ui.click_helper import click


@click.command(
    "serve",
    help=(
        "Start the Swirrl web service.\n\n"
        "Binds to 127.0.0.1:8000 by default. "
        "Binding to a non-loopback address requires auth to be enabled "
        "(add an admin user first with 'swirrl user add --admin')."
    ),
)
@click.option("--host", default="127.0.0.1", show_default=True, help="Bind host.")
@click.option("--port", default=8000, type=int, show_default=True, help="Bind port.")
@click.option(
    "--reload",
    is_flag=True,
    default=False,
    hidden=True,
    help="Enable hot-reload (development only).",
)
def serve_command(host: str, port: int, reload: bool) -> None:
    """Start the Swirrl web service."""
    # ------------------------------------------------------------------
    # Security: refuse non-loopback binding when auth is disabled
    # ------------------------------------------------------------------
    _loopback = {"127.0.0.1", "localhost", "::1"}
    if host not in _loopback:
        from swirrl.web.app import _is_auth_active

        if not _is_auth_active():
            click.echo(
                "ERROR: Cannot bind to a non-loopback address when auth is disabled.\n"
                "Enable auth first: swirrl user add --admin\n"
                "Or start with the default host: swirrl serve --host 127.0.0.1",
                err=True,
            )
            sys.exit(1)

    # ------------------------------------------------------------------
    # Acquire exclusive service lock
    # ------------------------------------------------------------------
    from swirrl.core.paths import get_service_dir
    from swirrl.core.service.supervisor import ServiceSupervisor

    supervisor = ServiceSupervisor(get_service_dir())
    try:
        supervisor.acquire()
    except RuntimeError as exc:
        click.echo(f"ERROR: {exc}", err=True)
        sys.exit(1)

    # ------------------------------------------------------------------
    # Recover persisted jobs, start embedded watcher, then run uvicorn
    # ------------------------------------------------------------------
    try:
        from swirrl.web.modules import (
            _load_jobs_from_db,
            start_embedded_watcher,
            stop_embedded_watcher,
        )
        from swirrl.core.service.events import emit_service_event

        _load_jobs_from_db()
        start_embedded_watcher()
        emit_service_event(
            "service.started",
            message="Swirrl service started",
            data={"host": host, "port": port},
        )

        try:
            import uvicorn

            uvicorn.run(
                "swirrl.web.app:create_app",
                host=host,
                port=port,
                factory=True,
                reload=reload,
                log_level="info",
            )
        finally:
            emit_service_event("service.stopped", message="Swirrl service stopped")
            stop_embedded_watcher()
    finally:
        supervisor.release()
