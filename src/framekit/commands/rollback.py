from __future__ import annotations

from framekit.core.audit_log import append_audit_event
from framekit.core.paths import get_config_dir
from framekit.core.runs.rollback import rollback_run
from framekit.ui.click_helper import click
from framekit.ui.console import print_error, print_info, print_success, print_warning


@click.command("rollback")
@click.argument("run_id", metavar="OPERATION_ID")
@click.option("--dry-run", is_flag=True, help="Preview rollback actions without filesystem changes")
def rollback_command(run_id: str, dry_run: bool) -> None:
    """Undo a previous operation using its operation ID.

    OPERATION_ID is the unique identifier printed at the end of every
    successful renamer, cleanmkv or pipeline run. Format:
    module-YYYYMMDDHHMMSS-xxxxxxxx  (e.g. renamer-20250521064900-a1b2c3d4).

    The ID is shown in the terminal output after applying changes.
    You can also find it in the run ledger at:
    ~/.config/framekit/runs/ledger.ndjson
    """
    result = rollback_run(run_id, dry_run=dry_run)
    if result.total == 0:
        _ledger = get_config_dir() / "runs" / "ledger.ndjson"
        print_warning(
            f"No operations found for ID: {run_id}\n"
            "The operation ID is shown after applying changes (e.g. fk renamer --apply).\n"
            f"Check the run ledger at: {_ledger}"
        )
        return

    if result.errors:
        for error in result.errors:
            print_error(error)
    print_info(
        f"Rollback summary: total={result.total} reverted={result.reverted} "
        f"skipped={result.skipped} errors={len(result.errors)}"
    )
    append_audit_event(
        action="rollback",
        module="pipeline",
        run_id=run_id,
        status="ok" if not result.errors else "error",
        payload={
            "dry_run": dry_run,
            "total": result.total,
            "reverted": result.reverted,
            "skipped": result.skipped,
            "errors": result.errors,
        },
    )
    if result.errors:
        return
    print_success("Rollback completed.")
