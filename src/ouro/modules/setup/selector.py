from __future__ import annotations

from dataclasses import dataclass

from ouro.ui.unified_selector import SelectorOption
from ouro.ui.unified_selector import select_one as _select_one


@dataclass(slots=True)
class ChoiceOption:
    """Option entry: choice."""

    value: str
    label: str
    description: str = ""


def choose_option(
    title: str,
    options: list[ChoiceOption],
    preferred_value: str | None = None,
    page_size: int = 8,
) -> str | None:
    """Handle choose option."""
    entries: list[SelectorOption[str]] = [
        SelectorOption(
            value=option.value,
            label=option.label,
            hint=option.description or None,
            selected=preferred_value is not None and option.value == preferred_value,
        )
        for option in options
    ]

    try:
        return select_one(
            title=title,
            entries=entries,
            page_size=page_size,
        )
    except KeyboardInterrupt:
        return None


select_one = _select_one  # backwards-compatible patch target for tests
