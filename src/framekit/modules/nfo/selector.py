from __future__ import annotations

from framekit.ui.selector import confirm_choice


def choose_yes_no(
    title: str,
    yes_label: str = "Yes",
    no_label: str = "No",
    default_yes: bool = True,
) -> bool | None:
    try:
        return confirm_choice(
            title=title,
            default=default_yes,
            yes_label=yes_label,
            no_label=no_label,
        )
    except KeyboardInterrupt:
        return None
