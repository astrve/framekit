from __future__ import annotations

from pathlib import Path

from swirrl.core import audit_log
from swirrl.core.runs.ledger import new_run_id, record_move
from swirrl.core.runs.rollback import rollback_run


def test_audit_log_append_read_purge(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit_log, "get_config_dir", lambda: tmp_path)

    audit_log.append_audit_event(
        action="rename", module="renamer", payload={"src": "a", "dst": "b"}
    )
    audit_log.append_audit_event(action="upload", module="upload", status="error")

    rows = audit_log.read_audit_events(limit=10)
    assert len(rows) == 2
    assert rows[-1]["action"] == "upload"

    deleted = audit_log.purge_audit_events()
    assert deleted >= 1
    assert audit_log.read_audit_events(limit=10) == []


def test_rollback_run_reverts_recorded_move(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("swirrl.core.runs.ledger.get_config_dir", lambda: tmp_path)

    src = tmp_path / "video.mkv"
    dst = tmp_path / "video.renamed.mkv"
    src.write_text("x", encoding="utf-8")
    src.rename(dst)

    run_id = new_run_id("renamer")
    record_move(run_id=run_id, module="renamer", src=src, dst=dst)

    result = rollback_run(run_id)
    assert result.total == 1
    assert result.reverted == 1
    assert not result.errors
    assert src.exists()
    assert not dst.exists()
