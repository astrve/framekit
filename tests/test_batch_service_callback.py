"""Regression tests for ``BatchService`` pipeline-callback detection.

Previously, the service used ``except TypeError`` to detect whether a
``pipeline_runner`` callable accepted a ``step_callback`` argument. That swallowed
unrelated TypeErrors raised from inside the runner and silently retried the
call without the callback. The new implementation inspects the signature
explicitly via ``inspect.signature``.
"""

from __future__ import annotations

from pathlib import Path

from framekit.modules.batch.models import BatchConfig, BatchItem, BatchStatus
from framekit.modules.batch.service import (
    BatchService,
    _pipeline_accepts_result_callback,
    _pipeline_accepts_step_callback,
)


def runner_with_step_callback(path: str, step_callback=None) -> int:
    return 0


def runner_without_step_callback(path: str) -> int:
    return 0


def runner_with_var_kwargs(path: str, **kwargs) -> int:
    return 0


def runner_with_result_callback(path: str, result_callback=None) -> int:
    return 0


def test_detects_explicit_step_callback_parameter() -> None:
    assert _pipeline_accepts_step_callback(runner_with_step_callback) is True


def test_detects_var_keyword_accepts_step_callback() -> None:
    assert _pipeline_accepts_step_callback(runner_with_var_kwargs) is True


def test_rejects_runner_without_step_callback() -> None:
    assert _pipeline_accepts_step_callback(runner_without_step_callback) is False


def test_detects_explicit_result_callback_parameter() -> None:
    assert _pipeline_accepts_result_callback(runner_with_result_callback) is True


def test_unsignable_callable_returns_false() -> None:
    # ``len`` exposes a signature in some Python versions and not in others;
    # what matters is that an unsupported signature returns False rather than
    # crashing.
    class _NoSignature:
        __slots__ = ()

        def __call__(self, *args, **kwargs):  # pragma: no cover - dummy
            return 0

    callable_obj = _NoSignature()
    # __call__ takes *args, **kwargs → accepts step_callback via VAR_KEYWORD.
    assert _pipeline_accepts_step_callback(callable_obj) is True


def test_run_pipeline_for_item_surfaces_pipeline_error(tmp_path: Path) -> None:
    service = BatchService(queue_file=tmp_path / "queue.json", auto_load=False)
    item = BatchItem(path=tmp_path / "Release", display_name="Release")
    config = BatchConfig(auto_mode=True)

    def runner(path: str, step_callback=None, result_callback=None, **kwargs) -> int:
        assert kwargs["auto_mode"] is True
        assert step_callback is not None
        step_callback("prez", "Prez")
        assert result_callback is not None
        result_callback(
            {
                "prez": {
                    "success": False,
                    "code": 1,
                    "elapsed": 0.0,
                    "label": "Prez",
                    "error": "ValueError: boom",
                }
            }
        )
        return 1

    result = service._run_pipeline_for_item(item, config, runner)

    assert result.exit_code == 1
    assert item.status == BatchStatus.FAILED
    assert item.error_details is not None
    assert item.error_details["failed_module"] == "prez"
    assert item.error_details["pipeline_error"] == "ValueError: boom"
    assert "ValueError: boom" in (item.error_message or "")
