from __future__ import annotations

import os
import sys
from collections.abc import Callable, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Generic, TypeVar, cast

from rich.console import Group
from rich.live import Live
from rich.padding import Padding
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from framekit.core.i18n import tr
from framekit.ui.console import ACCENT, console

T = TypeVar("T")
IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:
    import msvcrt as _msvcrt

    _msvcrt_any = cast(Any, _msvcrt)
else:
    import select as _select
    import termios as _termios
    import tty as _tty

    _select_any = cast(Any, _select)
    _termios_any = cast(Any, _termios)
    _tty_any = cast(Any, _tty)

    _tcgetattr = _termios_any.tcgetattr
    _tcsetattr = _termios_any.tcsetattr
    _tcsadrain = _termios_any.TCSADRAIN
    _setraw = _tty_any.setraw


class SelectorAction(StrEnum):
    """Selector action."""

    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    TOGGLE = "TOGGLE"
    TOGGLE_ALL = "TOGGLE_ALL"
    OPEN = "OPEN"
    EXPAND = "EXPAND"
    CONFIRM = "CONFIRM"
    CANCEL = "CANCEL"
    NONE = "NONE"


@dataclass(frozen=True, slots=True)
class SelectorOption(Generic[T]):
    """Option entry: selector."""

    value: T
    label: str
    hint: str | None = None
    selected: bool = False
    disabled: bool = False
    disabled_reason: str | None = None


@dataclass(frozen=True, slots=True)
class SelectorDivider:
    """Selector divider."""

    label: str = ""


SelectorEntry = SelectorOption[Any] | SelectorDivider


@dataclass(slots=True)
class SelectorTheme:
    """Selector theme."""

    title_style: str = "bold white"
    title_rule_style: str = "bright_black"

    cursor_text_style: str = f"bold {ACCENT}"

    text_style: str = "white"
    selected_style: str = f"bold {ACCENT}"
    unselected_style: str = "white"

    hint_style: str = "bright_black"
    divider_style: str = "bright_black"
    disabled_style: str = "bright_black"

    footer_style: str = "bright_black"
    meta_style: str = ACCENT


@dataclass(slots=True)
class SelectorState:
    """Selector state."""

    title: str
    entries: list[SelectorEntry]
    page_size: int = 8
    minimal_count: int = 0
    multi: bool = True
    selected_indices: set[int] = field(default_factory=set)
    cursor_index: int = 0
    scroll_offset: int = 0

    def __post_init__(self) -> None:
        """Normalise page size and seed initial selection state."""
        self.page_size = max(1, self.page_size)

        if not self.selected_indices:
            initial: set[int] = set()
            for idx, entry in enumerate(self.entries):
                if isinstance(entry, SelectorOption) and entry.selected and not entry.disabled:
                    initial.add(idx)
            self.selected_indices = initial

        selectable = self.selectable_indices()

        if self.selected_indices:
            self.cursor_index = sorted(self.selected_indices)[0]
        else:
            self.cursor_index = selectable[0] if selectable else 0

    def selectable_indices(self) -> list[int]:
        """Handle selectable indices."""
        result: list[int] = []
        for idx, entry in enumerate(self.entries):
            if isinstance(entry, SelectorOption) and not entry.disabled:
                result.append(idx)
        return result

    def selected_values(self) -> list[Any]:
        """Handle selected values."""
        values: list[Any] = []
        for idx, entry in enumerate(self.entries):
            if idx in self.selected_indices and isinstance(entry, SelectorOption):
                values.append(entry.value)
        return values

    def can_confirm(self) -> bool:
        """Return ``True`` if can confirm."""
        if not self.multi:
            return True
        return len(self.selected_indices) >= self.minimal_count

    def current_entry(self) -> SelectorOption[Any] | None:
        """Handle current entry."""
        if self.cursor_index < 0 or self.cursor_index >= len(self.entries):
            return None

        entry = self.entries[self.cursor_index]
        if isinstance(entry, SelectorOption):
            return entry
        return None


class SelectorEngine:
    """Selector engine."""

    def __init__(self, state: SelectorState) -> None:
        self.state = state

    def move_cursor(self, delta: int) -> None:
        """Handle move cursor."""
        selectable = self.state.selectable_indices()
        if not selectable:
            return

        try:
            current_pos = selectable.index(self.state.cursor_index)
        except ValueError:
            current_pos = 0

        new_pos = (current_pos + delta) % len(selectable)
        self.state.cursor_index = selectable[new_pos]

    def change_page(self, delta: int) -> None:
        """Handle change page."""
        if not self.state.entries:
            return

        total_rows = len(self.state.entries)
        total_pages = max(1, (total_rows + self.state.page_size - 1) // self.state.page_size)
        current_page = self.state.scroll_offset // self.state.page_size
        new_page = current_page + delta

        if not (0 <= new_page < total_pages):
            return

        self.state.scroll_offset = new_page * self.state.page_size

        visible = self.visible_indices()
        selectable_visible = [idx for idx in visible if idx in self.state.selectable_indices()]
        if selectable_visible:
            self.state.cursor_index = selectable_visible[0]

    def toggle_current(self) -> None:
        """Handle toggle current."""
        idx = self.state.cursor_index
        if idx < 0 or idx >= len(self.state.entries):
            return

        entry = self.state.entries[idx]
        if not isinstance(entry, SelectorOption) or entry.disabled:
            return

        if self.state.multi:
            if idx in self.state.selected_indices:
                self.state.selected_indices.remove(idx)
            else:
                self.state.selected_indices.add(idx)
        else:
            self.state.selected_indices = {idx}

    def toggle_all(self) -> None:
        """Handle toggle all."""
        if not self.state.multi:
            return

        selectable = set(self.state.selectable_indices())
        if self.state.selected_indices == selectable:
            self.state.selected_indices.clear()
        else:
            self.state.selected_indices = selectable

    def select_current_and_confirm(self) -> bool:
        """Handle select current and confirm."""
        if not self.state.multi:
            idx = self.state.cursor_index
            if idx in self.state.selectable_indices():
                self.state.selected_indices = {idx}
                return True

        return self.state.can_confirm()

    def visible_indices(self) -> list[int]:
        """Handle visible indices."""
        if not self.state.entries:
            return []

        cursor = self.state.cursor_index

        if cursor < self.state.scroll_offset:
            self.state.scroll_offset = cursor
        elif cursor >= self.state.scroll_offset + self.state.page_size:
            self.state.scroll_offset = cursor - self.state.page_size + 1

        start = self.state.scroll_offset
        end = start + self.state.page_size
        return list(range(start, min(end, len(self.state.entries))))


class SelectorRenderer:
    """Selector renderer."""

    def __init__(
        self,
        theme: SelectorTheme | None = None,
        *,
        allow_open: bool = False,
    ) -> None:
        self.theme = theme or SelectorTheme()
        self.allow_open = allow_open

    def _cursor_style_for(self, base_style: str, is_cursor: bool) -> str:
        if is_cursor:
            return self.theme.cursor_text_style
        return base_style

    def _build_option_label(self, entry: SelectorOption[Any], is_cursor: bool) -> Text:
        base_style = self._cursor_style_for(self.theme.text_style, is_cursor)
        text = Text(entry.label, style=base_style)

        if entry.disabled:
            reason = entry.disabled_reason or tr("common.disabled", default="disabled")
            text.append("  ", style=base_style)
            text.append(
                f"[{reason}]",
                style=self._cursor_style_for(self.theme.disabled_style, is_cursor),
            )

        return text

    def _build_hint_text(self, entry: SelectorOption[Any], is_cursor: bool) -> Text:
        if not entry.hint:
            return Text(" ", style=self.theme.hint_style)

        if is_cursor:
            return Text(entry.hint, style=self.theme.cursor_text_style)

        return Text(entry.hint, style=self.theme.hint_style)

    def _build_indicator(self, idx: int, state: SelectorState, is_cursor: bool) -> Text:
        entry = state.entries[idx]

        if isinstance(entry, SelectorDivider):
            return Text("")

        if entry.disabled:
            style = self.theme.cursor_text_style if is_cursor else self.theme.disabled_style
            return Text("[ ]", style=style)

        selected = idx in state.selected_indices
        symbol = "[X]" if selected else "[ ]"

        if is_cursor:
            return Text(symbol, style=self.theme.cursor_text_style)

        if selected:
            return Text(symbol, style=self.theme.selected_style)

        return Text(symbol, style=self.theme.unselected_style)

    def _build_divider(self, label: str) -> Text:
        content = f"─ {label} ─" if label else "────────────────"
        return Text(content, style=self.theme.divider_style)

    def _build_footer(self, state: SelectorState) -> Text:
        total_rows = len(state.entries)
        total_pages = max(1, (total_rows + state.page_size - 1) // state.page_size)
        current_page = (state.scroll_offset // state.page_size) + 1
        selected_count = len(state.selected_indices)

        footer = Text(style=self.theme.footer_style)

        if state.multi:
            footer.append("space", style="bold white")
            footer.append(
                f" {tr('selector.toggle', default='toggle')}   ", style=self.theme.footer_style
            )
            footer.append("a", style="bold white")
            footer.append(f" {tr('selector.all', default='all')}   ", style=self.theme.footer_style)

        footer.append("enter", style="bold white")
        footer.append(
            f" {tr('selector.confirm', default='confirm')}   ", style=self.theme.footer_style
        )
        footer.append("↑/↓", style="bold white")
        footer.append(f" {tr('selector.move', default='move')}   ", style=self.theme.footer_style)
        footer.append("←/→", style="bold white")
        footer.append(f" {tr('selector.page', default='page')}", style=self.theme.footer_style)

        if self.allow_open:
            footer.append("   ")
            footer.append("o", style="bold white")
            footer.append(f" {tr('selector.open', default='open')}", style=self.theme.footer_style)

        footer.append("   ")
        footer.append(
            tr("selector.selected_count", default="{count} selected", count=selected_count),
            style=self.theme.meta_style,
        )
        footer.append("   ")
        footer.append(
            tr(
                "selector.page_count",
                default="page {current}/{total}",
                current=current_page,
                total=total_pages,
            ),
            style=self.theme.meta_style,
        )

        return footer

    def render(self, state: SelectorState, engine: SelectorEngine):
        """Handle render."""
        visible_indices = engine.visible_indices()

        table = Table(
            show_header=False,
            show_edge=False,
            box=None,
            pad_edge=False,
            padding=(0, 1, 0, 0),
            expand=True,
        )
        table.add_column("Indicator", justify="right", no_wrap=True, width=4)
        table.add_column("Option", overflow="ellipsis", no_wrap=True, ratio=5)
        table.add_column("Hint", justify="right", no_wrap=True, ratio=2)

        for idx in visible_indices:
            entry = state.entries[idx]
            is_cursor = idx == state.cursor_index

            if isinstance(entry, SelectorDivider):
                table.add_row(Text(""), self._build_divider(entry.label), Text(""))
                continue

            indicator = self._build_indicator(idx, state, is_cursor)
            label = self._build_option_label(entry, is_cursor)
            hint = self._build_hint_text(entry, is_cursor)
            table.add_row(indicator, label, hint)

        rows_rendered = len(visible_indices)
        for _ in range(state.page_size - rows_rendered):
            table.add_row(Text(" "), Text(" "), Text(" "))

        title_rule = Rule(
            Text(state.title, style=self.theme.title_style),
            style=self.theme.title_rule_style,
        )

        footer = self._build_footer(state)

        return Padding(
            Group(
                title_rule,
                table,
                Text(""),
                footer,
            ),
            (0, 2),
        )


class SelectorInputAdapter:
    """Selector input adapter."""

    _CHAR_ACTIONS: dict[str, SelectorAction] = {
        " ": SelectorAction.TOGGLE,
        "a": SelectorAction.TOGGLE_ALL,
        "o": SelectorAction.OPEN,
        "e": SelectorAction.EXPAND,
        "w": SelectorAction.UP,
        "k": SelectorAction.UP,
        "s": SelectorAction.DOWN,
        "j": SelectorAction.DOWN,
        "h": SelectorAction.LEFT,
        "d": SelectorAction.RIGHT,
        "l": SelectorAction.RIGHT,
        "q": SelectorAction.CANCEL,
    }

    def read_action(self) -> SelectorAction:
        """Handle read action."""
        if IS_WINDOWS:
            return self._read_windows()
        return self._read_unix()

    def _read_windows(self) -> SelectorAction:
        key = _msvcrt_any.getch()

        if key in (b"\x03", b"\x1b"):
            return SelectorAction.CANCEL

        if key in (b"\xe0", b"\x00"):
            key = _msvcrt_any.getch()
            mapping = {
                b"H": SelectorAction.UP,
                b"P": SelectorAction.DOWN,
                b"K": SelectorAction.LEFT,
                b"M": SelectorAction.RIGHT,
            }
            return mapping.get(key, SelectorAction.NONE)

        try:
            char = key.decode("utf-8", errors="ignore")
        except Exception:
            return SelectorAction.NONE

        return self._map_char(char)

    @contextmanager
    def _raw_mode(self):
        fd = sys.stdin.fileno()
        old_settings = _tcgetattr(fd)
        try:
            _setraw(fd)
            yield
        finally:
            _tcsetattr(fd, _tcsadrain, old_settings)

    def _read_unix(self) -> SelectorAction:
        with self._raw_mode():
            ch1 = sys.stdin.read(1)

            if ch1 == "\x03":
                return SelectorAction.CANCEL

            if ch1 == "\x1b":
                ready, _, _ = _select_any.select([sys.stdin], [], [], 0.05)
                if ready:
                    ch2 = sys.stdin.read(1)
                    if ch2 in ("[", "O"):
                        ch3 = sys.stdin.read(1)
                        mapping = {
                            "A": SelectorAction.UP,
                            "B": SelectorAction.DOWN,
                            "C": SelectorAction.RIGHT,
                            "D": SelectorAction.LEFT,
                        }
                        return mapping.get(ch3, SelectorAction.NONE)
                return SelectorAction.CANCEL

            return self._map_char(ch1)

    def _map_char(self, char: str) -> SelectorAction:
        if char in ("\r", "\n"):
            return SelectorAction.CONFIRM
        return self._CHAR_ACTIONS.get(char.lower(), SelectorAction.NONE)


class SelectorRunner:
    """Selector runner."""

    def __init__(
        self,
        *,
        title: str,
        entries: Sequence[SelectorEntry],
        page_size: int = 8,
        minimal_count: int = 0,
        multi: bool = True,
        theme: SelectorTheme | None = None,
        on_open_current: Callable[[Any], None] | None = None,
    ) -> None:
        self.state = SelectorState(
            title=title,
            entries=list(entries),
            page_size=page_size,
            minimal_count=minimal_count,
            multi=multi,
        )
        self.engine = SelectorEngine(self.state)
        self.renderer = SelectorRenderer(
            theme,
            allow_open=on_open_current is not None,
        )
        self.input_adapter = SelectorInputAdapter()
        self.on_open_current = on_open_current

    def _open_current(self) -> None:
        if self.on_open_current is None:
            return

        entry = self.state.current_entry()
        if entry is None or entry.disabled:
            return

        self.on_open_current(entry.value)

    def _handle_action(self, action: SelectorAction) -> list[Any] | None:
        handlers: dict[SelectorAction, Callable[[], None]] = {
            SelectorAction.UP: lambda: self.engine.move_cursor(-1),
            SelectorAction.DOWN: lambda: self.engine.move_cursor(1),
            SelectorAction.LEFT: lambda: self.engine.change_page(-1),
            SelectorAction.RIGHT: lambda: self.engine.change_page(1),
            SelectorAction.TOGGLE: self.engine.toggle_current,
            SelectorAction.TOGGLE_ALL: self.engine.toggle_all,
            SelectorAction.OPEN: self._open_current,
        }
        if action == SelectorAction.CONFIRM and self.engine.select_current_and_confirm():
            return self.state.selected_values()
        if action == SelectorAction.CANCEL:
            raise KeyboardInterrupt
        handler = handlers.get(action)
        if handler is not None:
            handler()
        return None

    def run(self) -> list[Any]:
        """Handle run."""
        try:
            with Live(
                self.renderer.render(self.state, self.engine),
                console=console,
                auto_refresh=False,
                transient=True,
            ) as live:
                while True:
                    live.update(self.renderer.render(self.state, self.engine), refresh=True)
                    action = self.input_adapter.read_action()
                    selected_values = self._handle_action(action)
                    if selected_values is not None:
                        return selected_values
        except KeyboardInterrupt:
            raise


def select_many(
    *,
    title: str,
    entries: Sequence[SelectorEntry],
    page_size: int = 8,
    minimal_count: int = 0,
    theme: SelectorTheme | None = None,
    on_open_current: Callable[[Any], None] | None = None,
) -> list[Any]:
    """Handle select many."""
    if not sys.stdin.isatty():
        raise RuntimeError(
            tr(
                "selector.error.headless",
                default="Interactive selection is not available in headless mode (no TTY).",
            )
        )
    runner = SelectorRunner(
        title=title,
        entries=entries,
        page_size=page_size,
        minimal_count=minimal_count,
        multi=True,
        theme=theme,
        on_open_current=on_open_current,
    )
    return runner.run()


def select_one(
    *,
    title: str,
    entries: Sequence[SelectorEntry],
    page_size: int = 8,
    theme: SelectorTheme | None = None,
    on_open_current: Callable[[Any], None] | None = None,
) -> Any:
    """Handle select one."""
    if not sys.stdin.isatty():
        raise RuntimeError(
            tr(
                "selector.error.headless",
                default="Interactive selection is not available in headless mode (no TTY).",
            )
        )
    runner = SelectorRunner(
        title=title,
        entries=entries,
        page_size=page_size,
        minimal_count=1,
        multi=False,
        theme=theme,
        on_open_current=on_open_current,
    )
    values = runner.run()
    return values[0] if values else None


def confirm_choice(
    *,
    title: str,
    default: bool = True,
    yes_label: str | None = None,
    no_label: str | None = None,
) -> bool | None:
    """Handle confirm choice."""
    try:
        result = select_one(
            title=title,
            entries=[
                SelectorOption(
                    value=True,
                    label=yes_label or tr("common.yes", default="Yes"),
                    selected=default,
                ),
                SelectorOption(
                    value=False,
                    label=no_label or tr("common.no", default="No"),
                    selected=not default,
                ),
            ],
            page_size=4,
        )
    except KeyboardInterrupt:
        return None

    if result is None:
        return None
    return bool(result)


def text_input(
    *,
    title: str,
    default: str = "",
    mandatory: bool = False,
) -> str:
    """Handle text input."""
    if not sys.stdin.isatty():
        raise RuntimeError(
            tr(
                "selector.error.headless",
                default="Interactive selection is not available in headless mode (no TTY).",
            )
        )

    console.print()
    console.rule(Text(title, style="bold white"), style=ACCENT)

    while True:
        value = console.input("[white]> [/white]").strip()
        if not value and default:
            value = default

        if mandatory and not value:
            console.print(
                f"[bold red]{tr('status.err', default='[ERR]')}[/bold red] "
                f"{tr('common.value_required', default='This value cannot be empty.')}"
            )
            continue

        return value
