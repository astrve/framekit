"""Shared step-timeline UI helpers for wizard-style CLI flows."""

from rich import box
from rich.panel import Panel
from rich.text import Text

from framekit.ui.console import console

_timeline_displayed = False


def reset_timeline() -> None:
    """Reset the timeline display state for a new wizard flow."""
    global _timeline_displayed
    _timeline_displayed = False


def show_step_timeline(current_step: str, all_steps: list[str]) -> None:
    """Render an inline progress timeline showing completed/current/remaining steps."""
    global _timeline_displayed

    timeline = Text()
    current_idx = all_steps.index(current_step) if current_step in all_steps else len(all_steps)
    for i, step in enumerate(all_steps):
        if i > 0:
            timeline.append(" > ", style="dim white")
        if step == current_step:
            timeline.append(step, style="bold cyan")
        elif i < current_idx:
            timeline.append(f"[OK] {step}", style="green")
        else:
            timeline.append(step, style="dim white")

    if _timeline_displayed:
        console.file.write("\033[3A\033[J")
        console.file.flush()

    console.print()
    console.print(timeline)
    console.print()

    if not _timeline_displayed:
        _timeline_displayed = True


def show_step(
    title: str, body: str, current_step: str | None = None, all_steps: list[str] | None = None
) -> None:
    """Display a wizard step panel, optionally preceded by the timeline bar."""
    if current_step and all_steps:
        show_step_timeline(current_step, all_steps)
    console.print(Panel(body, title=title, border_style="white", box=box.HEAVY, expand=True))
