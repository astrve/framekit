from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .ledger import LedgerEntry, read_run_entries


@dataclass(slots=True)
class RollbackResult:
    """Aggregated rollback execution result."""

    run_id: str
    total: int = 0
    reverted: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def _rollback_move(entry: LedgerEntry, *, dry_run: bool) -> tuple[bool, str | None]:
    src = Path(entry.src)
    dst = Path(entry.dst)
    if not dst.exists():
        return (False, f"Missing destination to revert: {dst}")
    if src.exists():
        return (False, f"Source already exists, refusing overwrite: {src}")
    if dry_run:
        return (True, None)
    src.parent.mkdir(parents=True, exist_ok=True)
    dst.rename(src)
    return (True, None)


def rollback_run(run_id: str, *, dry_run: bool = False) -> RollbackResult:
    """Rollback a run by replaying inverse move operations in reverse order."""
    entries = read_run_entries(run_id)
    result = RollbackResult(run_id=run_id, total=len(entries))
    for entry in reversed(entries):
        if entry.action != "move":
            result.skipped += 1
            continue
        ok, error = _rollback_move(entry, dry_run=dry_run)
        if ok:
            result.reverted += 1
            continue
        result.errors.append(error or f"Unknown rollback error for {entry.dst}")
    return result
