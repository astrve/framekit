from __future__ import annotations

import subprocess
import time

import pytest

from framekit.web.modules import (
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
        "framekit.web.modules.run_safe",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=["python", "-m", "framekit", "doctor", "--json"],
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
        "framekit.web.modules._run_module_command_cancellable",
        lambda _request, *, job_id, cancel_event: RunModuleResponse(
            ok=True,
            argv=["python", "-m", "framekit", "doctor", "--json"],
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
                    argv=["python", "-m", "framekit", "inspect"],
                    returncode=130,
                    stdout="",
                    stderr="Cancelled by user.",
                )
            time.sleep(0.01)
        return RunModuleResponse(
            ok=True,
            argv=["python", "-m", "framekit", "inspect"],
            returncode=0,
            stdout="done",
            stderr="",
        )

    monkeypatch.setattr("framekit.web.modules._run_module_command_cancellable", fake_runner)

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
        "framekit.web.modules._run_module_command_cancellable",
        lambda _request, *, job_id, cancel_event: RunModuleResponse(
            ok=True,
            argv=["python", "-m", "framekit", "inspect"],
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
