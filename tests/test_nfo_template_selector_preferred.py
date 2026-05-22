"""Regression tests for :class:`framekit.modules.nfo.template_selector.TemplateSelector`.

Bug: ``run()`` used to build every entry with ``selected=False``, so the
cursor always landed on the first option (``Default``). A user with
``active_template = "detailed"`` saw the cursor on Default and accidentally
confirmed it by pressing Enter without scrolling. The fix pre-selects the
entry whose ``template_name`` matches ``preferred_name``.
"""

from __future__ import annotations

from unittest.mock import patch

from framekit.modules.nfo.template_selector import TemplateOption, TemplateSelector


def _builtin_options() -> list[TemplateOption]:
    return [
        TemplateOption(
            display_name="Default",
            template_name="default",
            source="builtin",
            scope="universal",
        ),
        TemplateOption(
            display_name="Detailed",
            template_name="detailed",
            source="builtin",
            scope="universal",
        ),
    ]


def test_preferred_entry_is_marked_selected() -> None:
    """The entry whose ``template_name`` matches must be ``selected=True``."""
    captured: dict = {}

    def _spy(*, title, entries, page_size):
        captured["entries"] = entries
        return entries[1].value

    options = _builtin_options()
    with patch("framekit.modules.nfo.template_selector.select_one", side_effect=_spy):
        TemplateSelector(options, preferred_name="detailed").run()

    entries = captured["entries"]
    assert entries[0].selected is False
    assert entries[1].selected is True


def test_preferred_entry_label_is_annotated() -> None:
    """The matching label must carry a ``(current)`` annotation for clarity."""
    captured: dict = {}

    def _spy(*, title, entries, page_size):
        captured["entries"] = entries
        return entries[0].value

    options = _builtin_options()
    with patch("framekit.modules.nfo.template_selector.select_one", side_effect=_spy):
        TemplateSelector(options, preferred_name="detailed").run()

    labels = [entry.label for entry in captured["entries"]]
    assert labels[0] == "Default"
    assert "(current)" in labels[1]
    assert labels[1].startswith("Detailed")


def test_unknown_preferred_leaves_no_selection() -> None:
    """If ``preferred_name`` does not match, no entry is pre-selected."""
    captured: dict = {}

    def _spy(*, title, entries, page_size):
        captured["entries"] = entries
        return entries[0].value

    options = _builtin_options()
    with patch("framekit.modules.nfo.template_selector.select_one", side_effect=_spy):
        TemplateSelector(options, preferred_name="nonexistent").run()

    assert all(entry.selected is False for entry in captured["entries"])
    assert all("(current)" not in entry.label for entry in captured["entries"])


def test_none_preferred_leaves_no_selection() -> None:
    """``preferred_name=None`` keeps the previous behaviour (no pre-selection)."""
    captured: dict = {}

    def _spy(*, title, entries, page_size):
        captured["entries"] = entries
        return entries[0].value

    options = _builtin_options()
    with patch("framekit.modules.nfo.template_selector.select_one", side_effect=_spy):
        TemplateSelector(options, preferred_name=None).run()

    assert all(entry.selected is False for entry in captured["entries"])


def test_returned_option_template_name_matches_selection() -> None:
    """The chosen option's ``template_name`` must round-trip through the selector."""

    def _spy(*, title, entries, page_size):
        # Caller picked the detailed entry.
        return entries[1].value

    options = _builtin_options()
    with patch("framekit.modules.nfo.template_selector.select_one", side_effect=_spy):
        chosen = TemplateSelector(options, preferred_name="default").run()

    assert chosen is not None
    assert chosen.template_name == "detailed"
