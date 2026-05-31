"""Tests for the interactive pipeline step-checkpoint mechanism (P5).

Covers the Approve / Skip / Back / Abort semantics added to
``pipeline_orchestrator._run_pipeline_with_progress`` and its checkpoint
IPC helpers. No external media tools are required.
"""

from __future__ import annotations

import json
from pathlib import Path

from swirrl.commands import pipeline_orchestrator as o


def _steps(calls: list[str]):
    """Build three trivial steps that record their execution order."""
    def make(name: str):
        def _cb() -> int:
            calls.append(name)
            return 0
        return _cb

    return [(name, name.upper(), make(name)) for name in ("a", "b", "c")]


def test_non_interactive_runs_all_steps_in_order(monkeypatch):
    monkeypatch.delenv("SWIRRL_JOB_CHECKPOINT_DIR", raising=False)
    calls: list[str] = []
    results = o._run_pipeline_with_progress(_steps(calls), stop_on_error=True)
    assert calls == ["a", "b", "c"]
    assert all(results[name]["success"] for name in ("a", "b", "c"))
    assert not any(results[name].get("skipped") for name in ("a", "b", "c"))


def test_wait_step_response_maps_selection_index(tmp_path: Path):
    chk = tmp_path
    for idx, expected in [(0, "approve"), (1, "skip"), (2, "back"), (3, "abort")]:
        (chk / "response.json").write_text(json.dumps({"selection_index": idx}), encoding="utf-8")
        assert o._wait_step_response(chk, timeout=1.0) == expected


def test_write_step_checkpoint_offers_back_only_after_first(tmp_path: Path):
    o._write_step_checkpoint(tmp_path, "renamer", "Renamer", index=1, total=3, can_back=False)
    payload = json.loads((tmp_path / "pending.json").read_text(encoding="utf-8"))
    labels = [opt["label"] for opt in payload["options"]]
    assert "Back" not in labels
    assert labels[0] == "Approve" and "Abort" in labels
    assert payload["step_index"] == 1 and payload["step_total"] == 3
    assert payload["summary"]  # rich per-step description, not just the label

    o._write_step_checkpoint(tmp_path, "cleanmkv", "CleanMKV", index=2, total=3, can_back=True)
    payload2 = json.loads((tmp_path / "pending.json").read_text(encoding="utf-8"))
    assert "Back" in [opt["label"] for opt in payload2["options"]]


def test_interactive_skip_and_abort(tmp_path: Path, monkeypatch):
    """Drive the loop via responses written by a side thread."""
    import threading
    import time

    chk = tmp_path
    monkeypatch.setenv("SWIRRL_JOB_CHECKPOINT_DIR", str(chk))
    calls: list[str] = []

    # Plan: approve a, skip b, abort at c.
    plan = [o._STEP_ACTION_APPROVE, o._STEP_ACTION_SKIP, o._STEP_ACTION_ABORT]

    def responder() -> None:
        pending = chk / "pending.json"
        response = chk / "response.json"
        for action in plan:
            # Wait for the orchestrator to publish a fresh pending checkpoint.
            for _ in range(200):
                if pending.exists() and not response.exists():
                    break
                time.sleep(0.01)
            response.write_text(json.dumps({"selection_index": action}), encoding="utf-8")
            # Wait for the orchestrator to consume it before the next round.
            for _ in range(200):
                if not response.exists():
                    break
                time.sleep(0.01)

    thread = threading.Thread(target=responder, daemon=True)
    thread.start()
    results = o._run_pipeline_with_progress(_steps(calls), stop_on_error=True)
    thread.join(timeout=5.0)

    assert calls == ["a"]  # only 'a' ran; 'b' skipped, 'c' aborted
    assert results["a"]["success"] and not results["a"].get("skipped")
    assert results["b"].get("skipped") is True
    assert results["c"].get("skipped") is True
