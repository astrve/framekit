from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from framekit.core.diagnostics import (
    format_traceback,
    get_log_file,
    is_debug_enabled,
    log_exception,
)
from framekit.core.i18n import tr

console = Console()

SUCCESS = "#22c55e"
WARNING = "#f59e0b"
ERROR = "#ef4444"
ACCENT = "#bf945c"
ACCENT_BRIGHT = "#e2b97d"
TEXT = "white"


def print_success(message: str) -> None:
    console.print(f"[bold {SUCCESS}]{tr('status.ok', default='[OK]')}[/bold {SUCCESS}] {message}")


def print_warning(message: str) -> None:
    console.print(f"[bold {WARNING}]{tr('status.warn', default='[!]')}[/bold {WARNING}] {message}")


def print_error(message: str) -> None:
    console.print(f"[bold {ERROR}]{tr('status.err', default='[ERR]')}[/bold {ERROR}] {message}")


def print_info(message: str) -> None:
    console.print(f"[bold {TEXT}]{tr('status.info', default='[INFO]')}[/bold {TEXT}] {message}")


def print_exception_error(exc: BaseException, *, message: str | None = None) -> None:
    """Print a user-facing error, and emit traceback/logs when debug is enabled."""

    log_exception(exc)
    print_error(message or str(exc) or exc.__class__.__name__)

    log_file = get_log_file()
    if log_file is not None:
        print_info(tr("debug.log_file", default="Debug log") + f": {log_file}")

    if is_debug_enabled():
        console.print(
            Panel(
                format_traceback(exc),
                title=tr("debug.traceback", default="Traceback"),
                border_style=ERROR,
                expand=True,
            )
        )


def print_json(data: Any) -> None:
    console.print_json(json.dumps(data, ensure_ascii=False))


def print_doctor_table(title: str, rows: list[tuple[str, str]]) -> None:
    table = Table(
        title=title,
        expand=True,
        border_style="white",
    )
    table.add_column("Field", width=24, no_wrap=True)
    table.add_column("Value", ratio=1)

    for key, value in rows:
        table.add_row(key, value)

    console.print(table)
