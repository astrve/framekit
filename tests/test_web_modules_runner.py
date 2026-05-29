from __future__ import annotations

from datetime import UTC, datetime, timedelta
import sqlite3
import subprocess
import time
from threading import Event
from uuid import uuid4

import pytest

import ouro.web.modules as web_modules
from ouro.web.modules import (
    ModuleJob,
    RunModuleRequest,
    RunModuleResponse,
    cancel_module_job,
    enqueue_module_job,
    get_module_job,
    rerun_module_job,
    run_module_command,
)


def test_run_module_command_parses_json_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ouro.web.modules.run_safe",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=["python", "-m", "ouro", "doctor", "--json"],
            returncode=0,
            stdout='{"checks":[{"status":"ok"}]}',
            stderr="",
        ),
    )

    result = run_module_command(
        RunModuleRequest(
            module="doctor",
            args_text="--json",
            dry_run=False,
            auto_yes=False,
            confirm_destructive=False,
        )
    )

    assert result.ok is True
    assert result.parsed_kind == "json"
    assert isinstance(result.parsed_payload, dict)
    assert result.parsed_payload["checks"][0]["status"] == "ok"


def test_run_module_command_blocks_destructive_without_confirmation() -> None:
    with pytest.raises(ValueError, match="confirm_destructive=true"):
        run_module_command(
            RunModuleRequest(
                module="renamer",
                args_text="C:/demo",
                dry_run=False,
                auto_yes=False,
                confirm_destructive=False,
            )
        )


def test_enqueue_module_job_completes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ouro.web.modules._run_module_command_cancellable",
        lambda _request, *, job_id, cancel_event, on_output=None: RunModuleResponse(
            ok=True,
            argv=["python", "-m", "ouro", "doctor", "--json"],
            returncode=0,
            stdout='{"checks":[]}',
            stderr="",
            parsed_kind="json",
            parsed_payload={"checks": []},
        ),
    )

    job = enqueue_module_job(
        RunModuleRequest(
            module="doctor",
            args_text="--json",
            dry_run=False,
            auto_yes=False,
            confirm_destructive=False,
        )
    )

    for _ in range(80):
        status = get_module_job(job.id)
        if status and status.status in {"completed", "failed"}:
            break
        time.sleep(0.01)
    else:
        raise AssertionError("job did not finish in time")

    final = get_module_job(job.id)
    assert final is not None
    assert final.status == "completed"
    assert final.result is not None
    assert final.result.ok is True


def test_cancel_module_job_marks_cancelled(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_runner(
        _request: RunModuleRequest, *, job_id: str, cancel_event
    ) -> RunModuleResponse:
        for _ in range(200):
            if cancel_event.is_set():
                return RunModuleResponse(
                    ok=False,
                    argv=["python", "-m", "ouro", "inspect"],
                    returncode=130,
                    stdout="",
                    stderr="Cancelled by user.",
                )
            time.sleep(0.01)
        return RunModuleResponse(
            ok=True,
            argv=["python", "-m", "ouro", "inspect"],
            returncode=0,
            stdout="done",
            stderr="",
        )

    monkeypatch.setattr("ouro.web.modules._run_module_command_cancellable", fake_runner)

    job = enqueue_module_job(
        RunModuleRequest(
            module="inspect",
            args_text="C:/demo",
            dry_run=False,
            auto_yes=False,
            confirm_destructive=False,
        )
    )
    cancel_module_job(job.id)

    for _ in range(120):
        current = get_module_job(job.id)
        if current and current.status == "cancelled":
            break
        time.sleep(0.01)
    else:
        raise AssertionError("job was not cancelled in time")

    final = get_module_job(job.id)
    assert final is not None
    assert final.status == "cancelled"


def test_rerun_module_job_creates_new_job(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ouro.web.modules._run_module_command_cancellable",
        lambda _request, *, job_id, cancel_event, on_output=None: RunModuleResponse(
            ok=True,
            argv=["python", "-m", "ouro", "inspect"],
            returncode=0,
            stdout="ok",
            stderr="",
        ),
    )

    original = enqueue_module_job(
        RunModuleRequest(
            module="inspect",
            args_text="C:/demo",
            dry_run=False,
            auto_yes=False,
            confirm_destructive=False,
        )
    )
    for _ in range(120):
        current = get_module_job(original.id)
        if current and current.status in {"completed", "failed", "cancelled"}:
            break
        time.sleep(0.01)

    rerun = rerun_module_job(original.id)
    assert rerun is not None
    assert rerun.id != original.id
    assert rerun.request.module == "inspect"


def _setup_isolated_jobs_db(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    db_path = tmp_path / "module_jobs.sqlite3"
    monkeypatch.setattr(web_modules, "_jobs_db_path", lambda: db_path)
    monkeypatch.setattr(web_modules, "_ensure_worker_started", lambda: None)
    with web_modules._JOBS_LOCK:
        web_modules._JOBS.clear()
        web_modules._JOB_CANCEL_EVENTS.clear()
        web_modules._JOB_PROCESSES.clear()
    web_modules._init_db()


def _make_job(
    request: RunModuleRequest,
    *,
    status: str = "pending",
    attempts: int = 0,
    max_attempts: int = 3,
    next_retry_at: str | None = None,
    paused: bool = False,
) -> ModuleJob:
    return ModuleJob(
        id=str(uuid4()),
        status=status,
        created_at=datetime.now(UTC).isoformat(),
        started_at=None,
        finished_at=None,
        request=request,
        attempts=attempts,
        max_attempts=max_attempts,
        next_retry_at=next_retry_at,
        last_failure_kind=None,
        retryable=False,
        paused=paused,
    )


def test_claim_pending_job_skips_future_next_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _setup_isolated_jobs_db(monkeypatch, tmp_path)
    request = RunModuleRequest(
        module="inspect",
        args_text="C:/demo",
        dry_run=False,
        auto_yes=False,
        confirm_destructive=False,
    )
    future_retry = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
    job = _make_job(request, next_retry_at=future_retry, attempts=0, max_attempts=3)
    web_modules._persist_job(job)

    claimed = web_modules._claim_pending_job_from_db("worker-test")
    assert claimed is None


def test_claim_pending_job_increments_attempts_on_claim(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _setup_isolated_jobs_db(monkeypatch, tmp_path)
    request = RunModuleRequest(
        module="inspect",
        args_text="C:/demo",
        dry_run=False,
        auto_yes=False,
        confirm_destructive=False,
    )
    job = _make_job(request, attempts=0, max_attempts=3)
    web_modules._persist_job(job)

    claimed = web_modules._claim_pending_job_from_db("worker-test")
    assert claimed is not None
    job_id, _payload_json, attempts_after_claim = claimed
    assert job_id == job.id
    assert attempts_after_claim == 1

    with web_modules._db_connect() as conn:
        row = conn.execute(
            "SELECT attempts, status FROM web_module_jobs WHERE id = ?",
            (job.id,),
        ).fetchone()
    assert row is not None
    assert int(row["attempts"]) == 1
    assert str(row["status"]) == "running"


def test_claim_pending_job_skips_paused(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _setup_isolated_jobs_db(monkeypatch, tmp_path)
    request = RunModuleRequest(
        module="inspect",
        args_text="C:/demo",
        dry_run=False,
        auto_yes=False,
        confirm_destructive=False,
    )
    paused_job = _make_job(request, paused=True)
    web_modules._persist_job(paused_job)
    claimed = web_modules._claim_pending_job_from_db("worker-test")
    assert claimed is None


def test_claim_pending_job_respects_allowed_categories(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _setup_isolated_jobs_db(monkeypatch, tmp_path)
    request = RunModuleRequest(
        module="inspect",
        args_text="C:/demo",
        dry_run=False,
        auto_yes=False,
        confirm_destructive=False,
    )
    upload_job = _make_job(request)
    transform_job = _make_job(request)
    web_modules._persist_job(upload_job.model_copy(update={"category": "upload"}))
    web_modules._persist_job(transform_job.model_copy(update={"category": "transform"}))
    claimed = web_modules._claim_pending_job_from_db("worker-test", allowed_categories={"transform"})
    assert claimed is not None
    job_id, _payload_json, _attempts = claimed
    assert job_id == transform_job.id


def test_execute_job_timeout_requeues_same_job_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _setup_isolated_jobs_db(monkeypatch, tmp_path)
    request = RunModuleRequest(
        module="inspect",
        args_text="C:/demo",
        dry_run=False,
        auto_yes=False,
        confirm_destructive=False,
    )
    job = _make_job(request, status="running", attempts=1, max_attempts=3)
    with web_modules._JOBS_LOCK:
        web_modules._JOBS[job.id] = job
        web_modules._JOB_CANCEL_EVENTS[job.id] = Event()
    web_modules._persist_job(job)

    monkeypatch.setattr(
        web_modules,
        "_run_module_command_cancellable",
        lambda _request, *, job_id, cancel_event, on_output=None: RunModuleResponse(
            ok=False,
            argv=["python", "-m", "ouro", "inspect"],
            returncode=124,
            stdout="",
            stderr="Timed out after 5s.",
        ),
    )

    web_modules._execute_job(job.id)
    final = get_module_job(job.id)
    assert final is not None
    assert final.id == job.id
    assert final.status == "pending"
    assert final.last_failure_kind == "timeout"
    assert final.next_retry_at is not None
    assert final.attempts == 1


def test_execute_job_timeout_on_unsafe_apply_mode_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _setup_isolated_jobs_db(monkeypatch, tmp_path)
    request = RunModuleRequest(
        module="renamer",
        args_text="C:/demo",
        dry_run=False,
        auto_yes=False,
        confirm_destructive=True,
    )
    job = _make_job(request, status="running", attempts=1, max_attempts=1)
    with web_modules._JOBS_LOCK:
        web_modules._JOBS[job.id] = job
        web_modules._JOB_CANCEL_EVENTS[job.id] = Event()
    web_modules._persist_job(job)

    monkeypatch.setattr(
        web_modules,
        "_run_module_command_cancellable",
        lambda _request, *, job_id, cancel_event, on_output=None: RunModuleResponse(
            ok=False,
            argv=["python", "-m", "ouro", "renamer"],
            returncode=124,
            stdout="",
            stderr="Timed out after 5s.",
        ),
    )

    web_modules._execute_job(job.id)
    final = get_module_job(job.id)
    assert final is not None
    assert final.status == "failed"
    assert final.last_failure_kind == "timeout"
    assert final.next_retry_at is None
    assert final.max_attempts == 1


def test_load_jobs_from_db_restart_recovery_retryable_vs_terminal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _setup_isolated_jobs_db(monkeypatch, tmp_path)

    retryable_request = RunModuleRequest(
        module="inspect",
        args_text="C:/demo",
        dry_run=False,
        auto_yes=False,
        confirm_destructive=False,
    )
    unsafe_request = RunModuleRequest(
        module="renamer",
        args_text="C:/demo",
        dry_run=False,
        auto_yes=False,
        confirm_destructive=True,
    )

    retryable_running = _make_job(retryable_request, status="running", attempts=1, max_attempts=3)
    unsafe_running = _make_job(unsafe_request, status="running", attempts=1, max_attempts=1)
    pending_job = _make_job(retryable_request, status="pending", attempts=0, max_attempts=3)
    web_modules._persist_job(retryable_running)
    web_modules._persist_job(unsafe_running)
    web_modules._persist_job(pending_job)

    web_modules._load_jobs_from_db()

    recovered_retryable = get_module_job(retryable_running.id)
    recovered_unsafe = get_module_job(unsafe_running.id)
    recovered_pending = get_module_job(pending_job.id)

    assert recovered_retryable is not None
    assert recovered_retryable.status == "pending"
    assert recovered_retryable.last_failure_kind == "interrupted_restart"
    assert recovered_retryable.next_retry_at is not None

    assert recovered_unsafe is not None
    assert recovered_unsafe.status == "failed"
    assert recovered_unsafe.last_failure_kind == "interrupted_restart"
    assert recovered_unsafe.next_retry_at is None

    assert recovered_pending is not None
    assert recovered_pending.status == "pending"


def test_priority_pause_resume_helpers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _setup_isolated_jobs_db(monkeypatch, tmp_path)
    request = RunModuleRequest(
        module="inspect",
        args_text="C:/demo",
        dry_run=False,
        auto_yes=False,
        confirm_destructive=False,
    )
    job = _make_job(request, status="pending", attempts=0, max_attempts=3)
    with web_modules._JOBS_LOCK:
        web_modules._JOBS[job.id] = job
        web_modules._JOB_CANCEL_EVENTS[job.id] = Event()
    web_modules._persist_job(job)

    updated = web_modules.set_module_job_priority(job.id, 7)
    assert updated is not None
    assert updated.priority == 7

    paused = web_modules.pause_module_job(job.id)
    assert paused is not None
    assert paused.paused is True

    resumed = web_modules.resume_module_job(job.id)
    assert resumed is not None
    assert resumed.paused is False


def test_jobs_db_additive_migration_from_legacy_schema(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    db_path = tmp_path / "legacy_jobs.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE web_module_jobs (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        conn.commit()

    monkeypatch.setattr(web_modules, "_jobs_db_path", lambda: db_path)
    web_modules._init_db()

    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(web_module_jobs)").fetchall()}
        indexes = {row[1] for row in conn.execute("PRAGMA index_list(web_module_jobs)").fetchall()}

    assert "max_attempts" in columns
    assert "next_retry_at" in columns
    assert "last_failure_kind" in columns
    assert "paused" in columns
    assert "idx_web_module_jobs_claim" in indexes
    assert "idx_web_module_jobs_pending_unpaused" in indexes
