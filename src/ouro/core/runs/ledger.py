from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ouro.core.paths import get_config_dir


def _runs_dir() -> Path:
    path = get_config_dir() / "runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_runs_ledger_path() -> Path:
    """Return NDJSON ledger path for reversible run operations."""
    return _runs_dir() / "ledger.ndjson"


@dataclass(slots=True)
class LedgerEntry:
    """Single reversible filesystem action bound to a run-id."""

    run_id: str
    action: str
    src: str
    dst: str
    module: str
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "action": self.action,
            "src": self.src,
            "dst": self.dst,
            "module": self.module,
            "timestamp": self.timestamp,
        }


def new_run_id(module: str) -> str:
    """Generate run-id with module prefix, UTC timestamp, random suffix."""
    stamp = time.strftime("%Y%m%d%H%M%S", time.gmtime())
    return f"{module}-{stamp}-{uuid.uuid4().hex[:8]}"


def append_ledger_entry(entry: LedgerEntry) -> None:
    """Append one ledger entry."""
    path = get_runs_ledger_path()
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry.to_dict(), ensure_ascii=True, sort_keys=True))
        fh.write("\n")


def record_move(*, run_id: str, module: str, src: Path, dst: Path) -> None:
    """Record one move/rename operation for later rollback."""
    append_ledger_entry(
        LedgerEntry(
            run_id=run_id,
            action="move",
            src=str(src),
            dst=str(dst),
            module=module,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
    )


def read_run_entries(run_id: str) -> list[LedgerEntry]:
    """Load all ledger entries for a specific run-id."""
    path = get_runs_ledger_path()
    if not path.exists():
        return []
    rows: list[LedgerEntry] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(payload.get("run_id", "")) != run_id:
                continue
            rows.append(
                LedgerEntry(
                    run_id=run_id,
                    action=str(payload.get("action", "")),
                    src=str(payload.get("src", "")),
                    dst=str(payload.get("dst", "")),
                    module=str(payload.get("module", "")),
                    timestamp=str(payload.get("timestamp", "")),
                )
            )
    return rows
