from framekit.ui.selector import (
    SelectorDivider,
    SelectorEngine,
    SelectorOption,
    SelectorState,
)


def test_selector_initial_cursor_skips_dividers_and_disabled():
    state = SelectorState(
        title="Test",
        entries=[
            SelectorDivider("Section"),
            SelectorOption(value="a", label="A", disabled=True),
            SelectorOption(value="b", label="B"),
        ],
        page_size=5,
        minimal_count=0,
        multi=True,
    )

    assert state.cursor_index == 2


def test_selector_toggle_current_multi():
    state = SelectorState(
        title="Test",
        entries=[
            SelectorOption(value="a", label="A"),
            SelectorOption(value="b", label="B"),
        ],
        page_size=5,
        minimal_count=0,
        multi=True,
    )
    engine = SelectorEngine(state)

    engine.toggle_current()
    assert state.selected_values() == ["a"]

    engine.toggle_current()
    assert state.selected_values() == []


def test_selector_toggle_current_single():
    state = SelectorState(
        title="Test",
        entries=[
            SelectorOption(value="a", label="A"),
            SelectorOption(value="b", label="B"),
        ],
        page_size=5,
        minimal_count=1,
        multi=False,
    )
    engine = SelectorEngine(state)

    engine.toggle_current()
    assert state.selected_values() == ["a"]

    engine.move_cursor(1)
    engine.toggle_current()
    assert state.selected_values() == ["b"]


def test_selector_toggle_all_skips_disabled():
    state = SelectorState(
        title="Test",
        entries=[
            SelectorOption(value="a", label="A"),
            SelectorOption(value="b", label="B", disabled=True),
            SelectorOption(value="c", label="C"),
        ],
        page_size=5,
        minimal_count=0,
        multi=True,
    )
    engine = SelectorEngine(state)

    engine.toggle_all()
    assert state.selected_values() == ["a", "c"]


def test_selector_can_confirm_respects_minimal_count():
    state = SelectorState(
        title="Test",
        entries=[
            SelectorOption(value="a", label="A"),
            SelectorOption(value="b", label="B"),
        ],
        page_size=5,
        minimal_count=2,
        multi=True,
    )
    engine = SelectorEngine(state)

    assert state.can_confirm() is False
    engine.toggle_current()
    assert state.can_confirm() is False
    engine.move_cursor(1)
    engine.toggle_current()
    assert state.can_confirm() is True
