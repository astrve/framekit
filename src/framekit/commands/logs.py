from __future__ import annotations

import json
import re
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from rich.table import Table

from framekit.core.diagnostics import default_log_file, get_log_file, redact
from framekit.core.i18n import tr
from framekit.ui.click_helper import click
from framekit.ui.console import (
    console,
    print_error,
    print_info,
    print_success,
    print_warning,
)

MODULE_LOG_RE = re.compile(r"^[A-Za-z0-9_-]+_logs_\d{8}_\d{4}\.log$")


def _is_supported_log_path(path: Path) -> bool:
    name = path.name
    return (
        name == "framekit.log"
        or name.startswith("framekit.log.")
        or bool(MODULE_LOG_RE.match(name))
    )


def _resolve_log_file(path: str | None) -> Path:
    if path:
        resolved = Path(path).expanduser().resolve()
        if not _is_supported_log_path(resolved):
            raise click.ClickException(
                "Unsupported log path. Use framekit.log, framekit.log.* or <module>_logs_YYYYMMDD_HHMM.log."
            )
        return resolved
    return get_log_file() or default_log_file()


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _parse_json_dict(payload: str) -> dict[str, Any] | None:
    if not (payload.startswith("{") and payload.endswith("}")):
        return None
    try:
        value = json.loads(payload)
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _extract_loguru_payload(line: str) -> str | None:
    marker = " - "
    marker_index = line.find(marker)
    if marker_index == -1:
        return None
    return line[marker_index + len(marker) :].strip()


def _parse_log_line(line: str) -> dict[str, Any] | None:
    stripped = line.strip()
    if not stripped:
        return None
    parsed_direct = _parse_json_dict(stripped)
    if parsed_direct is not None:
        return parsed_direct
    payload = _extract_loguru_payload(stripped)
    if payload is None:
        return None
    return _parse_json_dict(payload)


def _line_level(line: str) -> str:
    parsed = _parse_log_line(line)
    if parsed is not None:
        return str(parsed.get("level", "")).upper()

    # Fallback for non-JSON lines.
    for level in ("TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        if f"| {level}" in line:
            return level
    return ""


def _line_message(line: str) -> str:
    parsed = _parse_log_line(line)
    if parsed is not None:
        return str(parsed.get("message", "") or "")

    marker = " - "
    marker_index = line.find(marker)
    if marker_index != -1:
        return line[marker_index + len(marker) :].strip()
    return line.strip()


def _matches_level(line: str, level: str | None) -> bool:
    if not level:
        return True
    return _line_level(line) == level.upper()


def _safe_display_line(line: str) -> str:
    parsed = _parse_log_line(line)
    if parsed is not None:
        redacted_obj = redact(parsed, redact_values=True)
        if isinstance(redacted_obj, dict):
            return json.dumps(redacted_obj, ensure_ascii=False)
    redacted_line = redact(line, redact_values=True)
    return redacted_line if isinstance(redacted_line, str) else line


def _ensure_primary_log_file(log_file: Path) -> None:
    if log_file.name != "framekit.log":
        raise click.ClickException("Destructive operations require the primary framekit.log file.")


def _tail_initial_window(log_file: Path, *, level: str | None, lines: int) -> int:
    baseline = _read_lines(log_file)
    filtered = [line for line in baseline if _matches_level(line, level)]
    for line in filtered[-max(1, lines) :]:
        console.print(_safe_display_line(line))
    return log_file.stat().st_size if log_file.exists() else 0


def _tail_new_lines(log_file: Path, *, level: str | None, last_size: int) -> int:
    current_size = log_file.stat().st_size
    if current_size < last_size:
        last_size = 0
    if current_size == last_size:
        return last_size

    try:
        with log_file.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(last_size)
            new_lines = handle.read().splitlines()
            new_size = handle.tell()
    except OSError:
        return last_size

    for line in new_lines:
        if _matches_level(line, level):
            console.print(_safe_display_line(line))
    return new_size


def _remove_rotated_logs(log_dir: Path, log_file: Path, *, older_than: int) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=max(0, older_than))
    delete_all_rotated = older_than <= 0
    removed = 0
    for candidate in log_dir.glob("framekit.log*"):
        if candidate == log_file:
            continue
        try:
            if candidate.is_symlink() or not candidate.is_file():
                continue
            mtime = datetime.fromtimestamp(candidate.stat().st_mtime, UTC)
            if delete_all_rotated or mtime <= cutoff:
                candidate.unlink()
                removed += 1
        except OSError:
            continue
    return removed


def _truncate_log_file(log_file: Path) -> int:
    try:
        if log_file.exists() and (log_file.is_symlink() or not log_file.is_file()):
            print_error(f"Refusing to truncate non-regular log file: {log_file}")
            return 1
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text("", encoding="utf-8")
        return 0
    except OSError as exc:
        print_error(f"Failed to truncate log: {exc}")
        return 1


@click.group(
    "logs",
    help=tr(
        "cli.logs.help",
        default=(
            "Inspect and maintain Framekit diagnostic logs.\n\n"
            "Subcommands:\n"
            "  view    Print recent lines\n"
            "  tail    Stream log updates\n"
            "  analyze Summarize levels and volume\n"
            "  clear   Remove old logs or truncate current\n"
            "  rotate  Force manual rotation of current log\n"
            "  audit   Inspect and maintain audit log\n"
        ),
    ),
)
def logs_command() -> None:
    """Log inspection utilities."""


@logs_command.command("view")
@click.option("--path", "path_opt", type=click.Path(path_type=str), default=None)
@click.option("--lines", type=int, default=100, show_default=True)
@click.option(
    "--level",
    type=click.Choice(["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default=None,
)
def logs_view_command(path_opt: str | None, lines: int, level: str | None) -> int:
    """Display recent log lines."""
    log_file = _resolve_log_file(path_opt)
    all_lines = _read_lines(log_file)
    filtered = [line for line in all_lines if _matches_level(line, level)]
    window = filtered[-max(1, lines) :]

    if not window:
        print_warning(f"No matching log lines in {log_file}")
        return 0

    print_info(f"Showing {len(window)} line(s) from {log_file}")
    for line in window:
        console.print(_safe_display_line(line))
    return 0


@logs_command.command("tail")
@click.option("--path", "path_opt", type=click.Path(path_type=str), default=None)
@click.option("--lines", type=int, default=20, show_default=True)
@click.option(
    "--level",
    type=click.Choice(["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default=None,
)
@click.option("--interval", type=float, default=0.5, show_default=True)
@click.option(
    "--duration",
    type=float,
    default=0.0,
    show_default=True,
    help="Seconds to follow (0 = infinite).",
)
def logs_tail_command(
    path_opt: str | None,
    lines: int,
    level: str | None,
    interval: float,
    duration: float,
) -> int:
    """Tail log file updates."""
    log_file = _resolve_log_file(path_opt)
    if not log_file.exists():
        print_warning(f"Log file not found: {log_file}")
        return 0

    start = time.time()
    last_size = _tail_initial_window(log_file, level=level, lines=lines)
    while True:
        if duration > 0 and (time.time() - start) >= duration:
            return 0

        time.sleep(max(0.1, interval))
        if not log_file.exists():
            continue
        last_size = _tail_new_lines(log_file, level=level, last_size=last_size)


@logs_command.command("analyze")
@click.option("--path", "path_opt", type=click.Path(path_type=str), default=None)
def logs_analyze_command(path_opt: str | None) -> int:
    """Summarize log distribution by level."""
    log_file = _resolve_log_file(path_opt)
    all_lines = _read_lines(log_file)
    if not all_lines:
        print_warning(f"No logs to analyze in {log_file}")
        return 0

    level_counts: Counter[str] = Counter()
    json_entries = 0
    for line in all_lines:
        level = _line_level(line)
        if level:
            level_counts[level] += 1
        if _parse_log_line(line) is not None:
            json_entries += 1

    table = Table(title="Log Analysis", expand=True)
    table.add_column("Metric", no_wrap=True)
    table.add_column("Value")
    table.add_row("Path", str(log_file))
    table.add_row("Total lines", str(len(all_lines)))
    table.add_row("Structured entries", str(json_entries))

    if log_file.exists():
        size_kb = log_file.stat().st_size / 1024.0
        table.add_row("Size", f"{size_kb:.1f} KB")
        mtime = datetime.fromtimestamp(log_file.stat().st_mtime, UTC).isoformat()
        table.add_row("Last modified (UTC)", mtime)

    for level in ("TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        table.add_row(f"{level} count", str(level_counts.get(level, 0)))

    console.print(table)
    return 0


@logs_command.command("clear")
@click.option("--path", "path_opt", type=click.Path(path_type=str), default=None)
@click.option(
    "--older-than",
    type=int,
    default=30,
    show_default=True,
    help="Delete rotated logs older than N days.",
)
@click.option(
    "--all",
    "clear_all",
    is_flag=True,
    help="Also truncate current log file.",
)
@click.option(
    "-y",
    "--yes",
    "assume_yes",
    is_flag=True,
    help="Skip confirmation for --all.",
)
def logs_clear_command(
    path_opt: str | None, older_than: int, clear_all: bool, assume_yes: bool
) -> int:
    """Delete old rotated logs and optionally truncate active log."""
    log_file = _resolve_log_file(path_opt)
    _ensure_primary_log_file(log_file)
    log_dir = log_file.parent
    if not log_dir.exists():
        print_warning(f"Log directory not found: {log_dir}")
        return 0

    removed = _remove_rotated_logs(log_dir, log_file, older_than=older_than)

    truncated = False
    if clear_all:
        from framekit.core.destructive import auto_yes_enabled

        if (
            not assume_yes
            and not auto_yes_enabled()
            and not click.confirm("Truncate current log file?", default=False)
        ):
            print_warning("Skipped truncation.")
        else:
            if _truncate_log_file(log_file) != 0:
                return 1
            truncated = True

    print_success(f"Removed {removed} rotated log file(s).")
    if truncated:
        print_success("Current log truncated.")
    return 0


@logs_command.command("rotate")
@click.option("--path", "path_opt", type=click.Path(path_type=str), default=None)
def logs_rotate_command(path_opt: str | None) -> int:
    """Force manual log rotation."""
    log_file = _resolve_log_file(path_opt)
    _ensure_primary_log_file(log_file)
    if not log_file.exists():
        print_warning(f"Log file not found: {log_file}")
        return 0
    if log_file.is_symlink() or not log_file.is_file():
        print_error(f"Refusing to rotate non-regular log file: {log_file}")
        return 1

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    rotated = log_file.with_name(f"{log_file.name}.{timestamp}")
    try:
        rotated.write_bytes(log_file.read_bytes())
        log_file.write_text("", encoding="utf-8")
    except OSError as exc:
        print_error(f"Rotation failed: {exc}")
        return 1

    print_success(f"Rotated log to {rotated.name}")
    return 0


# ---------------------------------------------------------------------------
# Audit log — merged from former standalone audit-log command
# ---------------------------------------------------------------------------


@logs_command.group(
    "audit",
    help=tr("cli.logs.audit.help", default="Inspect and maintain Framekit audit log."),
)
def logs_audit_group() -> None:
    """Audit log subgroup."""


@logs_audit_group.command("show")
@click.option("--limit", type=int, default=50, show_default=True, help="Max events to show")
@click.option("--json", "as_json", is_flag=True, help="Print as JSON")
def logs_audit_show_command(limit: int, as_json: bool) -> None:
    """Show recent audit events."""
    import json as json_mod

    from framekit.core.audit_log import read_audit_events

    events = read_audit_events(limit=limit)
    if as_json:
        print(json_mod.dumps(events, ensure_ascii=True, indent=2, sort_keys=True))
        return
    if not events:
        print_info("No audit events found.")
        return
    for event in events:
        ts = str(event.get("timestamp", ""))
        module = str(event.get("module", ""))
        action = str(event.get("action", ""))
        run_id = str(event.get("run_id", ""))
        status = str(event.get("status", ""))
        print_info(f"{ts} | {module} | {action} | run={run_id or '-'} | {status}")


@logs_audit_group.command("purge")
def logs_audit_purge_command() -> None:
    """Purge audit log and rotated files."""
    from framekit.core.audit_log import purge_audit_events

    deleted = purge_audit_events()
    print_success(f"Purged audit logs ({deleted} file(s) removed).")
