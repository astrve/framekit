from __future__ import annotations

import io
import json
import sys
from datetime import datetime
from typing import Any, Literal

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ouro.core.diagnostics import (
    format_traceback,
    get_log_file,
    is_debug_enabled,
    log_event,
    log_exception,
)
from ouro.core.i18n import tr
from ouro.ui.branding import ouro_theme


def _utf8_stdout() -> io.TextIOWrapper | None:
    """Return a UTF-8 wrapper around stdout for Rich, or None to use default."""
    stream = sys.stdout
    if getattr(stream, "encoding", "utf-8").lower().replace("-", "") == "utf8":
        return None
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass
    return None


_utf8_stdout()

console = Console(theme=ouro_theme, legacy_windows=False)

# Export accent color for selector
from ouro.ui.branding import Colors  # noqa: E402

ACCENT = Colors.OURO_ACCENT_PRIMARY


def _is_debug_mode() -> bool:
    """Check if debug mode is enabled from Click context or diagnostics."""
    # First check diagnostics (environment variable or --debug flag)
    if is_debug_enabled():
        return True

    # Then check Click context
    ctx = click.get_current_context(silent=True)
    if ctx and ctx.obj and isinstance(ctx.obj, dict):
        return ctx.obj.get("debug", False)
    return False


def _is_quiet_mode() -> bool:
    """Check if quiet mode is enabled from Click context."""
    ctx = click.get_current_context(silent=True)
    if ctx and ctx.obj and isinstance(ctx.obj, dict):
        return ctx.obj.get("quiet", False)
    return False


# Spacing utilities
def print_blank_line(count: int = 1) -> None:
    """Print blank lines for spacing."""
    for _ in range(count):
        console.print()


def print_separator(width: int = 40, char: str = "─") -> None:
    """Print horizontal separator."""
    import sys

    # Use ASCII fallback on Windows to avoid encoding issues
    if sys.platform == "win32":
        char = "-"
    console.print(f"[separator]{char * width}[/separator]")


# Status message functions with text-based indicators
def print_success(message: str) -> None:
    """Print success message with [OK] indicator (shown unless in quiet mode)."""
    if not _is_quiet_mode():
        from ouro.ui.branding import StatusIndicators

        console.print(f"[status.success]{StatusIndicators.OK}[/status.success]   {message}")


def print_warning(message: str) -> None:
    """Print warning message with [WARN] indicator (shown unless in quiet mode)."""
    if not _is_quiet_mode():
        from ouro.ui.branding import StatusIndicators

        console.print(f"[status.warning]{StatusIndicators.WARN}[/status.warning] {message}")


def print_error(message: str) -> None:
    """Print error message with [ERR] indicator (always shown, even in quiet mode)."""
    from ouro.ui.branding import StatusIndicators

    console.print(f"[status.error]{StatusIndicators.ERR}[/status.error]  {message}")


def print_info(message: str) -> None:
    """Print info message with [INFO] indicator (shown unless in quiet mode)."""
    if not _is_quiet_mode():
        from ouro.ui.branding import StatusIndicators

        console.print(f"[status.info]{StatusIndicators.INFO}[/status.info] {message}")


def print_skip(message: str) -> None:
    """Print skip message with [SKIP] indicator (shown unless in quiet mode)."""
    if not _is_quiet_mode():
        from ouro.ui.branding import StatusIndicators

        console.print(f"[status.skip]{StatusIndicators.SKIP}[/status.skip] {message}")


def print_processing(message: str) -> None:
    """Print processing message with [PROC] indicator (shown unless in quiet mode)."""
    if not _is_quiet_mode():
        from ouro.ui.branding import StatusIndicators

        console.print(f"[status.processing]{StatusIndicators.PROC}[/status.processing] {message}")


def print_done(message: str) -> None:
    """Print done message with [DONE] indicator (shown unless in quiet mode)."""
    if not _is_quiet_mode():
        from ouro.ui.branding import StatusIndicators

        console.print(f"[status.done]{StatusIndicators.DONE}[/status.done] {message}")


def print_debug(
    message: str, *, module: str | None = None, context: dict[str, Any] | None = None
) -> None:
    """Print debug message with data flow information (shown only in debug mode).

    Args:
        message: The debug message to display
        module: Optional module name for context
        context: Optional context data to log
    """
    if _is_debug_mode():
        from ouro.ui.branding import StatusIndicators

        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        if module:
            formatted_msg = f"[text.secondary]{timestamp} {StatusIndicators.INFO} [{module}] {message}[/text.secondary]"
        else:
            formatted_msg = (
                f"[text.secondary]{timestamp} {StatusIndicators.INFO} {message}[/text.secondary]"
            )

        console.print(formatted_msg)

        # Log to file if context provided
        if context:
            log_event("DEBUG", message, module=module, **context)


def debug_module_entry(module: str, **context: Any) -> None:
    """Log module entry point for debugging data flow.

    Args:
        module: Module name
        **context: Additional context data
    """
    if _is_debug_mode():
        print_debug("→ Entering module", module=module, context=context)


def debug_module_exit(module: str, **context: Any) -> None:
    """Log module exit point for debugging data flow.

    Args:
        module: Module name
        **context: Additional context data
    """
    if _is_debug_mode():
        print_debug("← Exiting module", module=module, context=context)


def debug_data_flow(message: str, module: str | None = None, **data: Any) -> None:
    """Log data flow between modules for debugging.

    Args:
        message: Description of the data flow
        module: Optional module name
        **data: Data being passed
    """
    if _is_debug_mode():
        print_debug(message, module=module, context=data)


def debug_decision(message: str, module: str | None = None, **context: Any) -> None:
    """Log key decision points for debugging.

    Args:
        message: Description of the decision
        module: Optional module name
        **context: Decision context
    """
    if _is_debug_mode():
        print_debug(f"⚡ {message}", module=module, context=context)


# Header functions
def print_main_header(text: str) -> None:
    """Print main application header."""
    print_blank_line()
    console.print(f"[header.main]{text.upper()}[/header.main]")
    print_blank_line(2)


def print_section_header(text: str, *, with_separator: bool = True) -> None:
    """Print section header with optional separator."""
    print_blank_line()
    console.print(f"[header.section]{text}[/header.section]")
    if with_separator:
        print_separator()
    print_blank_line()


def print_subsection_header(text: str) -> None:
    """Print subsection header."""
    print_blank_line()
    console.print(f"[header.subsection]{text}[/header.subsection]")
    print_blank_line()


def print_exception_error(exc: BaseException, *, message: str | None = None) -> None:
    """Handle print exception error."""
    from ouro.ui.branding import Colors

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
                border_style=Colors.ERROR,
                expand=True,
            )
        )


def print_json(data: Any) -> None:
    """Handle print json."""
    console.print_json(json.dumps(data, ensure_ascii=False))


def print_doctor_table(title: str, rows: list[tuple[str, str]]) -> None:
    """Handle print doctor table."""
    from ouro.ui.branding import Colors

    table = Table(
        title=title,
        expand=True,
        border_style=Colors.PRIMARY,
    )
    table.add_column("Field", width=24, no_wrap=True)
    table.add_column("Value", ratio=1)

    for key, value in rows:
        table.add_row(key, value)

    console.print(table)


def format_module_header(module_name: str) -> str:
    """Format a module header with color."""
    from ouro.ui.branding import get_module_color

    color = get_module_color(module_name)
    return f"[{color}]{module_name.title()}[/{color}]"


def format_status_message(
    status: Literal[
        "success",
        "error",
        "warning",
        "info",
        "pending",
        "in_progress",
        "skip",
        "processing",
        "done",
    ],
    message: str,
) -> str:
    """Format a status message with text-based indicator and color."""
    from ouro.ui.branding import format_status

    return f"{format_status(status)} {message}"


def print_module_status(
    module_name: str,
    status: Literal[
        "success",
        "error",
        "warning",
        "info",
        "pending",
        "in_progress",
        "skip",
        "processing",
        "done",
    ],
    message: str,
) -> None:
    """Print a module-specific status message."""
    from ouro.ui.branding import format_status, get_module_color

    color = get_module_color(module_name)
    status_indicator = format_status(status)
    console.print(f"[{color}]{module_name}[/{color}] {status_indicator} {message}")
