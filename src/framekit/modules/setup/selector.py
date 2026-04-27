from __future__ import annotations

from dataclasses import dataclass

from framekit.ui.selector import SelectorOption, select_one


@dataclass(slots=True)
class ChoiceOption:
    value: str
    label: str
    description: str = ""


def choose_option(
    title: str,
    options: list[ChoiceOption],
    preferred_value: str | None = None,
    page_size: int = 8,
) -> str | None:
    entries: list[SelectorOption[str]] = []

    for option in options:
        entries.append(
            SelectorOption(
                value=option.value,
                label=option.label,
                hint=option.description or None,
                selected=False,
            )
        )

    try:
        return select_one(
            title=title,
            entries=entries,
            page_size=page_size,
        )
    except KeyboardInterrupt:
        return None
