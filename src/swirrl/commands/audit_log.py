from __future__ import annotations

import json

from swirrl.core.audit_log import purge_audit_events, read_audit_events
from swirrl.ui.click_helper import click
from swirrl.ui.console import print_info, print_success


@click.group("audit-log")
def audit_log_group() -> None:
    """Inspect and maintain Swirrl audit log."""


@audit_log_group.command("show")
@click.option("--limit", type=int, default=50, show_default=True, help="Max events to show")
@click.option("--json", "as_json", is_flag=True, help="Print as JSON instead of line-by-line")
def audit_log_show_command(limit: int, as_json: bool) -> None:
    """Show recent audit events."""
    events = read_audit_events(limit=limit)
    if as_json:
        print(json.dumps(events, ensure_ascii=True, indent=2, sort_keys=True))
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


@audit_log_group.command("purge")
def audit_log_purge_command() -> None:
    """Purge audit log and rotated files."""
    deleted = purge_audit_events()
    print_success(f"Purged audit logs ({deleted} file(s) removed).")
