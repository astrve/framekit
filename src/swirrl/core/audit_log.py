from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from swirrl.core.paths import get_config_dir

MAX_AUDIT_SIZE_BYTES = 5 * 1024 * 1024
MAX_AUDIT_ROTATIONS = 5


def _audit_dir() -> Path:
    path = get_config_dir() / "audit"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_audit_log_path() -> Path:
    """Return primary NDJSON audit log path."""
    return _audit_dir() / "events.ndjson"


def _rotation_path(index: int) -> Path:
    return _audit_dir() / f"events.ndjson.{index}"


def _rotate_if_needed(path: Path) -> None:
    if not path.exists():
        return
    if path.stat().st_size < MAX_AUDIT_SIZE_BYTES:
        return
    for idx in range(MAX_AUDIT_ROTATIONS, 0, -1):
        src = _rotation_path(idx)
        dst = _rotation_path(idx + 1)
        if idx == MAX_AUDIT_ROTATIONS and src.exists():
            src.unlink(missing_ok=True)
            continue
        if src.exists():
            src.replace(dst)
    path.replace(_rotation_path(1))


def append_audit_event(
    *,
    action: str,
    module: str,
    status: str = "ok",
    run_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one audit event to NDJSON log."""
    path = get_audit_log_path()
    _rotate_if_needed(path)
    event = {
        "event_id": str(uuid.uuid4()),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "action": action,
        "module": module,
        "status": status,
        "run_id": run_id or "",
        "payload": payload or {},
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=True, sort_keys=True))
        fh.write("\n")
    return event


def read_audit_events(limit: int = 100) -> list[dict[str, Any]]:
    """Read recent audit events."""
    path = get_audit_log_path()
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if limit <= 0:
        return rows
    return rows[-limit:]


def purge_audit_events() -> int:
    """Delete audit log and rotation files."""
    count = 0
    for path in [
        get_audit_log_path(),
        *(_rotation_path(i) for i in range(1, MAX_AUDIT_ROTATIONS + 1)),
    ]:
        if path.exists():
            path.unlink()
            count += 1
    return count
