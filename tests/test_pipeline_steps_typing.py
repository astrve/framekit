"""Regression tests for ``ouro.commands.pipeline_steps`` typing setup.

A prior bug used ``if False:  # TYPE_CHECKING`` as a placeholder. Static
analysis stopped resolving ``PipelineContext`` and the IDE / pyright
experience degraded. These tests lock in the real ``TYPE_CHECKING`` guard
documented in ADR-0002.
"""

from __future__ import annotations

import inspect

from ouro.commands import pipeline_steps


def test_pipeline_steps_imports_typing_type_checking() -> None:
    """Module must import ``TYPE_CHECKING`` so the guard is meaningful."""

    source = inspect.getsource(pipeline_steps)
    assert "from typing import TYPE_CHECKING" in source, (
        "pipeline_steps.py must import TYPE_CHECKING for the type-only "
        "import block guarding PipelineContext."
    )


def test_pipeline_steps_does_not_use_literal_false_guard() -> None:
    """Reject the literal ``if False:`` placeholder that broke type resolution."""

    source = inspect.getsource(pipeline_steps)
    assert "if False:  # TYPE_CHECKING" not in source, (
        "Replace `if False:  # TYPE_CHECKING` with `if TYPE_CHECKING:` so "
        "static analysers resolve PipelineContext (ADR-0002)."
    )


def test_pipeline_steps_guards_pipeline_context_import() -> None:
    """The PipelineContext import must live under a TYPE_CHECKING block."""

    source = inspect.getsource(pipeline_steps)
    assert "if TYPE_CHECKING:" in source
    # The import follows the guard within a small window of lines.
    lines = source.splitlines()
    guard_idx = next(i for i, line in enumerate(lines) if "if TYPE_CHECKING:" in line)
    window = "\n".join(lines[guard_idx : guard_idx + 5])
    assert "from ouro.commands.pipeline import PipelineContext" in window
