"""Unified selector interface for domain-specific selection patterns.

Provides a standard way to present choices to users across all Ouro
modules — files, tracks, metadata, templates, trackers, etc. — with
consistent keyboard navigation, headless fallback, and theming.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Generic, TypeVar, cast

from ouro.core.exceptions import HeadlessAmbiguityError
from ouro.core.i18n import tr
from ouro.ui.console import ACCENT, console
from ouro.ui.selector import (
    SelectorAction,
    SelectorDivider,
    SelectorEntry,
    SelectorInputAdapter,
    SelectorOption,
    SelectorRunner,
    SelectorTheme,
)
from ouro.ui.selector import (
    select_many as _legacy_select_many,
)
from ouro.ui.selector import (
    select_one as _legacy_select_one,
)

T = TypeVar("T")

__all__ = [
    "HeadlessAmbiguityError",
    "SelectionItem",
    "SelectionResult",
    "UnifiedSelector",
    "SelectorAction",
    "SelectorDivider",
    "SelectorEntry",
    "SelectorInputAdapter",
    "SelectorOption",
    "SelectorRunner",
    "SelectorTheme",
    "select_many",
    "select_one",
    "confirm_choice",
    "text_input",
]


@dataclass(frozen=True, slots=True)
class SelectionItem(Generic[T]):
    """A selectable item with display metadata."""

    value: T
    label: str
    description: str | None = None
    group: str | None = None
    disabled: bool = False
    disabled_reason: str | None = None
    preselected: bool = False


@dataclass(slots=True)
class SelectionResult(Generic[T]):
    """Result of a selection operation."""

    items: list[T] = field(default_factory=list)
    cancelled: bool = False

    @property
    def value(self) -> T | None:
        return self.items[0] if self.items else None

    @property
    def is_empty(self) -> bool:
        return not self.items and not self.cancelled


class UnifiedSelector(Generic[T]):
    """Unified selector that wraps the core SelectorRunner for domain use.

    Provides:
    - Grouped items with dividers
    - Headless/non-interactive fallback (returns preselected or first item)
    - Consistent theming
    - Single-select and multi-select modes
    - Optional action on item focus (e.g., open URL)

    Usage:
        selector = UnifiedSelector(
            title="Choose a tracker",
            items=[
                SelectionItem(value="bhd", label="Beyond-HD", group="UNIT3D"),
                SelectionItem(value="blu", label="Blutopia", group="UNIT3D"),
                SelectionItem(value="red", label="Redacted", group="Gazelle"),
            ],
        )
        result = selector.select()
        if not result.cancelled:
            chosen = result.value
    """

    def __init__(
        self,
        *,
        title: str,
        items: Sequence[SelectionItem[T]],
        multi: bool = False,
        page_size: int = 8,
        allow_empty: bool = False,
        theme: SelectorTheme | None = None,
        on_focus: Callable[[T], None] | None = None,
        headless_default: T | None = None,
    ):
        self.title = title
        self.items = list(items)
        self.multi = multi
        self.page_size = page_size
        self.allow_empty = allow_empty
        self.theme = theme
        self.on_focus = on_focus
        self.headless_default = headless_default

    def _build_entries(self) -> list[SelectorOption[T] | SelectorDivider]:
        """Convert items to selector entries with group dividers."""
        entries: list[SelectorOption[T] | SelectorDivider] = []
        last_group: str | None = None

        for item in self.items:
            if item.group and item.group != last_group:
                entries.append(SelectorDivider(label=item.group))
                last_group = item.group

            hint = item.description
            entries.append(
                SelectorOption(
                    value=item.value,
                    label=item.label,
                    hint=hint,
                    selected=item.preselected,
                    disabled=item.disabled,
                    disabled_reason=item.disabled_reason,
                )
            )

        return entries

    def _headless_fallback(self) -> SelectionResult[T]:
        """Return deterministic selection in headless mode or raise ambiguity."""
        if self.headless_default is not None:
            return SelectionResult(items=[self.headless_default])

        enabled_items = self._enabled_items()
        preselected = self._preselected_values(enabled_items)
        resolved = (
            self._resolve_multi_headless_selection(enabled_items, preselected)
            if self.multi
            else self._resolve_single_headless_selection(enabled_items, preselected)
        )
        if resolved is not None:
            return resolved

        raise HeadlessAmbiguityError(
            tr(
                "selector.error.headless_ambiguity",
                default="Headless selection is ambiguous for '{title}'. Provide an explicit default.",
                title=self.title,
            )
        )

    def _enabled_items(self) -> list[SelectionItem[T]]:
        return [item for item in self.items if not item.disabled]

    def _preselected_values(self, enabled_items: list[SelectionItem[T]]) -> list[T]:
        return [item.value for item in enabled_items if item.preselected]

    def _resolve_multi_headless_selection(
        self,
        enabled_items: list[SelectionItem[T]],
        preselected: list[T],
    ) -> SelectionResult[T] | None:
        if preselected:
            return SelectionResult(items=preselected)
        if self.allow_empty:
            return SelectionResult(items=[])
        if len(enabled_items) == 1:
            return SelectionResult(items=[enabled_items[0].value])
        return None

    def _resolve_single_headless_selection(
        self,
        enabled_items: list[SelectionItem[T]],
        preselected: list[T],
    ) -> SelectionResult[T] | None:
        if len(preselected) == 1:
            return SelectionResult(items=[preselected[0]])
        if len(enabled_items) == 1:
            return SelectionResult(items=[enabled_items[0].value])
        return None

    def select(self) -> SelectionResult[T]:
        """Run the selection.

        Returns SelectionResult with chosen items or cancelled=True.
        """
        if not sys.stdin.isatty():
            return self._headless_fallback()

        if not self.items:
            return SelectionResult(cancelled=True)

        entries = self._build_entries()

        try:
            if self.multi:
                values = select_many(
                    title=self.title,
                    entries=entries,
                    page_size=self.page_size,
                    minimal_count=0 if self.allow_empty else 1,
                    theme=self.theme,
                    on_open_current=self.on_focus,
                )
                if not values and not self.allow_empty:
                    return SelectionResult(cancelled=True)
                return SelectionResult(items=values)
            else:
                value = select_one(
                    title=self.title,
                    entries=entries,
                    page_size=self.page_size,
                    theme=self.theme,
                    on_open_current=self.on_focus,
                )
                if value is None:
                    return SelectionResult(cancelled=True)
                return SelectionResult(items=[value])
        except (KeyboardInterrupt, EOFError):
            return SelectionResult(cancelled=True)

    def select_or_default(self, default: T) -> T:
        """Select with automatic fallback to default on cancel or headless."""
        try:
            result = self.select()
        except HeadlessAmbiguityError:
            return default
        if result.cancelled or result.is_empty:
            return default
        return result.value  # type: ignore[return-value]


def _resolve_entries(
    args: tuple[object, ...], kwargs: dict[str, object], *, fn_name: str
) -> tuple[Sequence[SelectorEntry], str]:
    """Normalize legacy and modern selector signatures."""
    entries = kwargs.pop("entries", None)
    title = kwargs.pop("title", None)

    if entries is None and args:
        entries = args[0]
        args = args[1:]

    if title is None and args:
        maybe_title = args[0]
        if isinstance(maybe_title, str):
            title = maybe_title

    if entries is None:
        raise TypeError(f"{fn_name}() missing required argument: 'entries'")
    if title is None:
        raise TypeError(f"{fn_name}() missing required argument: 'title'")

    return cast(Sequence[SelectorEntry], entries), str(title)


def select_many(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Unified multi-select with deterministic headless behavior."""
    entries, title = _resolve_entries(args, kwargs, fn_name="select_many")
    page_size = int(kwargs.pop("page_size", 8))
    minimal_count = int(kwargs.pop("minimal_count", kwargs.pop("min_selection", 0)))
    theme = kwargs.pop("theme", None)
    on_open_current = kwargs.pop("on_open_current", None)
    auto_mode = bool(kwargs.pop("auto_mode", False))
    default_values = kwargs.pop("default", kwargs.pop("defaults", ()))

    if kwargs:
        unknown = ", ".join(sorted(kwargs))
        raise TypeError(f"select_many() got unexpected keyword argument(s): {unknown}")

    if not sys.stdin.isatty() or auto_mode:
        if default_values:
            return list(default_values)
        selector = UnifiedSelector(
            title=title,
            items=[
                SelectionItem(
                    value=entry.value,
                    label=entry.label,
                    description=entry.hint,
                    disabled=entry.disabled,
                    disabled_reason=entry.disabled_reason,
                    preselected=entry.selected,
                )
                for entry in entries
                if isinstance(entry, SelectorOption)
            ],
            multi=True,
            page_size=page_size,
            allow_empty=minimal_count == 0,
            theme=theme,
            on_focus=on_open_current,
        )
        return selector.select().items

    return _legacy_select_many(
        title=title,
        entries=entries,
        page_size=page_size,
        minimal_count=minimal_count,
        theme=theme,
        on_open_current=on_open_current,
    )


def select_one(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Unified single-select with deterministic headless behavior."""
    entries, title = _resolve_entries(args, kwargs, fn_name="select_one")
    page_size = int(kwargs.pop("page_size", 8))
    theme = kwargs.pop("theme", None)
    on_open_current = kwargs.pop("on_open_current", None)
    auto_mode = bool(kwargs.pop("auto_mode", False))
    default_value = kwargs.pop("default", None)

    if kwargs:
        unknown = ", ".join(sorted(kwargs))
        raise TypeError(f"select_one() got unexpected keyword argument(s): {unknown}")

    if not sys.stdin.isatty() or auto_mode:
        if default_value is not None:
            return default_value
        selector = UnifiedSelector(
            title=title,
            items=[
                SelectionItem(
                    value=entry.value,
                    label=entry.label,
                    description=entry.hint,
                    disabled=entry.disabled,
                    disabled_reason=entry.disabled_reason,
                    preselected=entry.selected,
                )
                for entry in entries
                if isinstance(entry, SelectorOption)
            ],
            multi=False,
            page_size=page_size,
            allow_empty=False,
            theme=theme,
            on_focus=on_open_current,
        )
        return selector.select().value

    return _legacy_select_one(
        title=title,
        entries=entries,
        page_size=page_size,
        theme=theme,
        on_open_current=on_open_current,
    )


def confirm_choice(
    *,
    title: str,
    default: bool = True,
    yes_label: str | None = None,
    no_label: str | None = None,
) -> bool | None:
    """Unified confirm helper with headless default support."""
    options = [
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
    ]

    try:
        result = select_one(
            title=title,
            entries=options,
            page_size=4,
            default=default if not sys.stdin.isatty() else None,
        )
    except (KeyboardInterrupt, EOFError):
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
    """Unified text input with strict headless behavior."""
    if not sys.stdin.isatty():
        if default:
            return default
        if mandatory:
            raise HeadlessAmbiguityError(
                tr(
                    "selector.error.headless_ambiguity",
                    default="Headless selection is ambiguous for '{title}'. Provide an explicit default.",
                    title=title,
                )
            )
        return ""

    console.print()
    console.rule(title, style=ACCENT)

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
