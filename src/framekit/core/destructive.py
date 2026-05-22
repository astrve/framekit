"""Centralised confirmation prompt for destructive operations.

Modules that overwrite files, delete folders, push to trackers, or wipe the
vault should funnel through :func:`confirm_destructive` so users get a
consistent UX and can bypass *every* prompt with a single global ``--yes``
flag (or the ``FRAMEKIT_AUTO_YES=1`` env var).
"""

from __future__ import annotations

import os
import sys

from framekit.core.i18n import tr
from framekit.ui.console import console

_AUTO_YES_ENV = "FRAMEKIT_AUTO_YES"


def auto_yes_enabled() -> bool:
    """Return ``True`` when the user has globally opted into ``--yes``."""
    value = os.environ.get(_AUTO_YES_ENV, "").strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


def confirm_destructive(
    prompt: str,
    *,
    default: bool = False,
    abort_message: str | None = None,
) -> bool:
    """Ask the user to confirm a destructive action.

    Returns ``True`` when the operation should proceed. Always returns
    ``True`` when ``FRAMEKIT_AUTO_YES=1`` is set or stdin is not a TTY
    (non-interactive contexts cannot answer prompts; the caller is expected
    to have validated intent already, e.g. via a CLI ``--yes`` flag that
    sets the env var).

    Args:
        prompt: Question to display, e.g. ``"Overwrite Release.mkv?"``.
        default: Default answer if the user presses Enter on a TTY.
        abort_message: Optional message printed on a "no" answer. When
            ``None``, a short generic notice is printed.
    """
    if auto_yes_enabled():
        return True
    if not sys.stdin.isatty():
        # No way to ask — treat as proceed only when ``default`` is True so
        # accidental piping doesn't wipe data. Caller can override via env.
        return default

    suffix = " [Y/n]" if default else " [y/N]"
    while True:
        try:
            raw = console.input(f"[bold yellow]?[/bold yellow] {prompt}{suffix} ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print()
            return False

        if not raw:
            return default
        if raw in {"y", "yes", "o", "oui", "s", "sí", "si"}:
            return True
        if raw in {"n", "no", "non"}:
            if abort_message:
                console.print(f"[dim]{abort_message}[/dim]")
            else:
                console.print(f"[dim]{tr('destructive.aborted', default='Cancelled.')}[/dim]")
            return False
        console.print(
            f"[red]{tr('destructive.invalid_input', default='Please answer yes or no.')}[/red]"
        )


def set_auto_yes(value: bool) -> None:
    """Programmatically toggle the global auto-yes mode.

    Used by ``__main__`` when the user passes ``--yes`` at the CLI root.
    """
    if value:
        os.environ[_AUTO_YES_ENV] = "1"
    else:
        os.environ.pop(_AUTO_YES_ENV, None)


__all__ = [
    "auto_yes_enabled",
    "confirm_destructive",
    "set_auto_yes",
]
