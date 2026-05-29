"""Regression tests for the pipeline preview / dry-run flow.

Background
----------

The ``_handle_preview_and_confirmation`` helper in
``ouro.commands.pipeline`` previously referenced ``dry_run`` in its body
without declaring it as a parameter, raising ``NameError`` whenever
``--preview`` was used. This module locks in the fix:

* ``_handle_preview_and_confirmation`` accepts ``dry_run`` as a keyword arg.
* The caller threads the pipeline-level ``dry_run`` flag through.

The tests are intentionally introspective: they assert the function
signature so a future refactor that drops the parameter fails loudly here
instead of crashing the user.
"""

from __future__ import annotations

import inspect

from ouro.commands import pipeline as pipeline_module
from ouro.commands import pipeline_preview as pipeline_preview_module


def test_handle_preview_accepts_dry_run_kwarg() -> None:
    """The signature must expose ``dry_run`` as a keyword argument."""

    sig = inspect.signature(pipeline_module._handle_preview_and_confirmation)
    assert "dry_run" in sig.parameters, (
        "_handle_preview_and_confirmation must accept a dry_run parameter; "
        "see ADR-0002 and the regression bug fixed on 2026-05-17."
    )
    param = sig.parameters["dry_run"]
    assert param.default is False, "dry_run should default to False"
    assert param.annotation in (bool, "bool"), "dry_run should be typed as bool"


def test_handle_preview_body_uses_dry_run_parameter() -> None:
    """Source of the helper must consume the parameter, not a free variable.

    A simple textual check guards against a future refactor that re-introduces
    a bare ``dry_run`` reference relying on a closure or module-level name.
    """

    source = inspect.getsource(pipeline_module._handle_preview_and_confirmation)
    assert "dry_run=dry_run" in source or "PipelineContext(dry_run=dry_run" in source, (
        "dry_run must be passed into PipelineContext from the parameter"
    )


def test_handle_preview_caller_threads_dry_run() -> None:
    """The single caller must pass ``dry_run`` through.

    We pull the source of ``run_pipeline_command`` and look for the call.
    A failing assertion here means a refactor stopped forwarding the flag,
    re-introducing the original bug at the seam between the CLI and the
    helper.
    """

    source = inspect.getsource(pipeline_module.run_pipeline_command)
    assert "_handle_preview_and_confirmation(" in source, (
        "run_pipeline_command should still call _handle_preview_and_confirmation"
    )
    assert "dry_run=dry_run" in source, (
        "run_pipeline_command must forward `dry_run=dry_run` to "
        "_handle_preview_and_confirmation; otherwise --preview crashes."
    )


def test_run_pipeline_command_exposes_dry_run() -> None:
    """The public CLI runner must keep ``dry_run`` as a keyword argument."""

    sig = inspect.signature(pipeline_module.run_pipeline_command)
    assert "dry_run" in sig.parameters
    assert sig.parameters["dry_run"].default is False


def test_preview_renamer_uses_language_profile_default(monkeypatch, tmp_path) -> None:
    """Pipeline preview should compute default lang from active language profile."""
    from ouro.modules.renamer.service import RenamerService

    captured: dict[str, str] = {}

    def _fake_build_plan(self, folder, **kwargs):
        _ = self, folder
        captured["default_lang"] = str(kwargs.get("default_lang", ""))
        return []

    monkeypatch.setattr(RenamerService, "build_plan", _fake_build_plan)

    settings = {
        "general": {"locale": "en"},
        "modules": {
            "renamer": {
                "profile": "fr_tracker",
                "default_language_tag": "MULTI.VFF",
                "language_profiles": {
                    "active": "fr_tracker",
                    "profiles": {},
                },
            }
        },
    }

    preview = pipeline_preview_module._gather_renamer_preview(tmp_path, settings, ())
    assert preview == {"files": []}
    assert captured["default_lang"] == "VFF"
