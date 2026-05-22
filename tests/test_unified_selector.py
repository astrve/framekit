"""Unit tests for :mod:`framekit.ui.unified_selector` (ADR-0004).

Covers:

* ``SelectionItem`` / ``SelectionResult`` dataclass semantics.
* Headless-mode fallback paths (no TTY, with/without preselection,
  with/without explicit ``headless_default``).
* TTY-mode dispatch to ``select_one`` / ``select_many`` (both calls
  monkeypatched so no real terminal interaction occurs).
* Cancellation paths: KeyboardInterrupt, EOFError, ``select_one``
  returning ``None``, multi-select returning empty when not allowed.
* The ``select_or_default`` convenience helper.

These tests anchor the "one selector for every domain" contract: any
future migration of a per-feature selector to ``UnifiedSelector`` must
keep these assertions green.
"""

from __future__ import annotations

from typing import Any

import pytest

from framekit.core.exceptions import HeadlessAmbiguityError
from framekit.ui import unified_selector as us_module
from framekit.ui.unified_selector import (
    SelectionItem,
    SelectionResult,
    UnifiedSelector,
)

# ---------------------------------------------------------------------------
# SelectionItem / SelectionResult
# ---------------------------------------------------------------------------


def test_selection_item_defaults() -> None:
    item = SelectionItem(value="x", label="X")
    assert item.value == "x"
    assert item.label == "X"
    assert item.description is None
    assert item.group is None
    assert item.disabled is False
    assert item.preselected is False


def test_selection_result_value_returns_first() -> None:
    res = SelectionResult(items=["a", "b"])
    assert res.value == "a"


def test_selection_result_value_none_when_empty() -> None:
    res = SelectionResult(items=[])
    assert res.value is None


def test_selection_result_is_empty_true_for_no_items_no_cancel() -> None:
    res = SelectionResult()
    assert res.is_empty is True


def test_selection_result_is_empty_false_when_cancelled() -> None:
    res = SelectionResult(cancelled=True)
    assert res.is_empty is False


# ---------------------------------------------------------------------------
# Headless paths
# ---------------------------------------------------------------------------


@pytest.fixture
def headless(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force ``sys.stdin.isatty()`` to ``False`` so the headless branch runs."""

    class _NoTty:
        def isatty(self) -> bool:
            return False

    monkeypatch.setattr(us_module.sys, "stdin", _NoTty())


@pytest.mark.usefixtures("headless")
def test_headless_returns_headless_default_when_set() -> None:
    selector: UnifiedSelector[str] = UnifiedSelector(
        title="Pick",
        items=[SelectionItem(value="a", label="A"), SelectionItem(value="b", label="B")],
        headless_default="b",
    )
    result = selector.select()
    assert result.cancelled is False
    assert result.value == "b"


@pytest.mark.usefixtures("headless")
def test_headless_returns_preselected_when_no_default() -> None:
    selector: UnifiedSelector[str] = UnifiedSelector(
        title="Pick",
        items=[
            SelectionItem(value="a", label="A"),
            SelectionItem(value="b", label="B", preselected=True),
        ],
    )
    result = selector.select()
    assert result.value == "b"


@pytest.mark.usefixtures("headless")
def test_headless_multi_returns_all_preselected() -> None:
    selector: UnifiedSelector[str] = UnifiedSelector(
        title="Pick",
        multi=True,
        items=[
            SelectionItem(value="a", label="A", preselected=True),
            SelectionItem(value="b", label="B"),
            SelectionItem(value="c", label="C", preselected=True),
        ],
    )
    result = selector.select()
    assert sorted(result.items) == ["a", "c"]


@pytest.mark.usefixtures("headless")
def test_headless_raises_when_ambiguous_without_default() -> None:
    selector: UnifiedSelector[str] = UnifiedSelector(
        title="Pick",
        items=[
            SelectionItem(value="a", label="A", disabled=True),
            SelectionItem(value="b", label="B"),
            SelectionItem(value="c", label="C"),
        ],
    )
    with pytest.raises(HeadlessAmbiguityError):
        selector.select()


@pytest.mark.usefixtures("headless")
def test_headless_raises_when_no_items_enabled() -> None:
    selector: UnifiedSelector[str] = UnifiedSelector(
        title="Pick",
        items=[
            SelectionItem(value="a", label="A", disabled=True),
            SelectionItem(value="b", label="B", disabled=True),
        ],
    )
    with pytest.raises(HeadlessAmbiguityError):
        selector.select()


@pytest.mark.usefixtures("headless")
def test_headless_raises_when_items_empty() -> None:
    selector: UnifiedSelector[str] = UnifiedSelector(title="Pick", items=[])
    with pytest.raises(HeadlessAmbiguityError):
        selector.select()


# ---------------------------------------------------------------------------
# TTY paths (mocked select_one / select_many)
# ---------------------------------------------------------------------------


@pytest.fixture
def tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force a TTY so the interactive branch runs."""

    class _Tty:
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(us_module.sys, "stdin", _Tty())


def test_select_one_dispatches_to_select_one(tty: None, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_select_one(**kwargs: Any) -> str:
        captured.update(kwargs)
        return "b"

    monkeypatch.setattr(us_module, "select_one", _fake_select_one)
    selector: UnifiedSelector[str] = UnifiedSelector(
        title="Pick",
        items=[SelectionItem(value="a", label="A"), SelectionItem(value="b", label="B")],
    )
    result = selector.select()
    assert result.value == "b"
    assert captured["title"] == "Pick"


def test_select_one_returns_cancelled_when_select_one_returns_none(
    tty: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(us_module, "select_one", lambda **kwargs: None)
    selector: UnifiedSelector[str] = UnifiedSelector(
        title="Pick", items=[SelectionItem(value="a", label="A")]
    )
    result = selector.select()
    assert result.cancelled is True


def test_select_many_dispatches_to_select_many(tty: None, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_select_many(**kwargs: Any) -> list[str]:
        captured.update(kwargs)
        return ["a", "c"]

    monkeypatch.setattr(us_module, "select_many", _fake_select_many)
    selector: UnifiedSelector[str] = UnifiedSelector(
        title="Pick",
        multi=True,
        items=[
            SelectionItem(value="a", label="A"),
            SelectionItem(value="b", label="B"),
            SelectionItem(value="c", label="C"),
        ],
    )
    result = selector.select()
    assert result.items == ["a", "c"]
    assert captured["title"] == "Pick"


def test_select_many_cancels_when_empty_and_not_allow_empty(
    tty: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(us_module, "select_many", lambda **kwargs: [])
    selector: UnifiedSelector[str] = UnifiedSelector(
        title="Pick",
        multi=True,
        items=[SelectionItem(value="a", label="A")],
    )
    result = selector.select()
    assert result.cancelled is True


def test_select_many_returns_empty_when_allow_empty(
    tty: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(us_module, "select_many", lambda **kwargs: [])
    selector: UnifiedSelector[str] = UnifiedSelector(
        title="Pick",
        multi=True,
        allow_empty=True,
        items=[SelectionItem(value="a", label="A")],
    )
    result = selector.select()
    assert result.cancelled is False
    assert result.items == []


@pytest.mark.parametrize("exc_cls", [KeyboardInterrupt, EOFError])
def test_select_catches_interrupts(
    tty: None, monkeypatch: pytest.MonkeyPatch, exc_cls: type[BaseException]
) -> None:
    def _raise(**kwargs: Any) -> str:
        raise exc_cls()

    monkeypatch.setattr(us_module, "select_one", _raise)
    selector: UnifiedSelector[str] = UnifiedSelector(
        title="Pick", items=[SelectionItem(value="a", label="A")]
    )
    result = selector.select()
    assert result.cancelled is True


# ---------------------------------------------------------------------------
# Grouped entries (divider emission)
# ---------------------------------------------------------------------------


def test_build_entries_inserts_group_dividers(tty: None, monkeypatch: pytest.MonkeyPatch) -> None:
    captured_entries: list[Any] = []

    def _capture(**kwargs: Any) -> str:
        captured_entries.extend(kwargs["entries"])
        return "a"

    monkeypatch.setattr(us_module, "select_one", _capture)
    selector: UnifiedSelector[str] = UnifiedSelector(
        title="Pick",
        items=[
            SelectionItem(value="a", label="A", group="G1"),
            SelectionItem(value="b", label="B", group="G1"),
            SelectionItem(value="c", label="C", group="G2"),
        ],
    )
    selector.select()
    # Two dividers + three options.
    divider_labels = [
        e.label for e in captured_entries if hasattr(e, "label") and not hasattr(e, "value")
    ]
    assert "G1" in divider_labels
    assert "G2" in divider_labels


# ---------------------------------------------------------------------------
# select_or_default
# ---------------------------------------------------------------------------


def test_select_or_default_returns_chosen(tty: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(us_module, "select_one", lambda **kwargs: "chosen")
    selector: UnifiedSelector[str] = UnifiedSelector(
        title="Pick", items=[SelectionItem(value="chosen", label="C")]
    )
    assert selector.select_or_default("fallback") == "chosen"


def test_select_or_default_returns_fallback_on_cancel(
    tty: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(us_module, "select_one", lambda **kwargs: None)
    selector: UnifiedSelector[str] = UnifiedSelector(
        title="Pick", items=[SelectionItem(value="chosen", label="C")]
    )
    assert selector.select_or_default("fallback") == "fallback"


@pytest.mark.usefixtures("headless")
def test_select_or_default_returns_fallback_when_headless_no_options() -> None:
    selector: UnifiedSelector[str] = UnifiedSelector(title="Pick", items=[])
    assert selector.select_or_default("fallback") == "fallback"


# ---------------------------------------------------------------------------
# Required keyword arguments
# ---------------------------------------------------------------------------


def test_unified_selector_requires_keyword_args() -> None:
    """``title`` and ``items`` are keyword-only — caught at construction."""

    with pytest.raises(TypeError):
        # Positional invocation must fail; the contract is keyword-only so
        # call sites cannot drift into ambiguous ordering across selectors.
        UnifiedSelector("Pick", [SelectionItem(value="a", label="A")])  # type: ignore[misc]
