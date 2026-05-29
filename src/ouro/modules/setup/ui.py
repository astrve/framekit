"""Rich UI components for setup wizard."""

from __future__ import annotations

from typing import Any

from rich.align import Align
from rich.console import Group
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from ouro.core.i18n import tr
from ouro.ui.console import ACCENT, console


def show_wizard_header(step: int, total_steps: int, title: str) -> None:
    """Display wizard header with progress.

    Args:
        step: Current step number
        total_steps: Total number of steps
        title: Step title
    """
    console.print()

    # Progress indicator
    progress_text = Text()
    progress_text.append(
        tr("wizard.step_progress", default="Step {step}/{total}", step=step, total=total_steps),
        style=f"bold {ACCENT}",
    )

    # Progress bar
    filled = int((step / total_steps) * 30)
    empty = 30 - filled
    bar = "█" * filled + "░" * empty
    progress_text.append(f"\n{bar}", style=ACCENT)

    # Title
    title_text = Text(title, style="bold white")

    panel = Panel(
        Group(progress_text, Text(""), title_text),
        border_style=ACCENT,
        padding=(1, 2),
    )

    console.print(panel)
    console.print()


def show_help_text(text: str) -> None:
    """Display help text in a styled panel.

    Args:
        text: Help text to display
    """
    help_panel = Panel(
        Text(text, style="bright_black"),
        title=tr("wizard.help", default="ℹ Help"),
        title_align="left",
        border_style="bright_black",
        padding=(0, 1),
    )
    console.print(help_panel)
    console.print()


def show_example(example: str) -> None:
    """Display an example in a styled format.

    Args:
        example: Example text to display
    """
    example_text = Text()
    example_text.append(
        tr("wizard.example", default="Example: "),
        style="bright_black",
    )
    example_text.append(example, style=f"italic {ACCENT}")
    console.print(example_text)
    console.print()


def show_validation_error(error: str) -> None:
    """Display a validation error message.

    Args:
        error: Error message to display
    """
    error_text = Text()
    error_text.append("✗ ", style="bold red")
    error_text.append(error, style="red")
    console.print(error_text)
    console.print()


def show_success_message(message: str) -> None:
    """Display a success message.

    Args:
        message: Success message to display
    """
    success_text = Text()
    success_text.append("✓ ", style="bold green")
    success_text.append(message, style="green")
    console.print(success_text)
    console.print()


def show_warning_message(message: str) -> None:
    """Display a warning message.

    Args:
        message: Warning message to display
    """
    warning_text = Text()
    warning_text.append("⚠ ", style="bold yellow")
    warning_text.append(message, style="yellow")
    console.print(warning_text)
    console.print()


def show_info_message(message: str) -> None:
    """Display an info message.

    Args:
        message: Info message to display
    """
    info_text = Text()
    info_text.append("ℹ ", style=f"bold {ACCENT}")
    info_text.append(message, style=ACCENT)
    console.print(info_text)
    console.print()


def show_configuration_summary(config: dict[str, Any]) -> None:
    """Display configuration summary in a table.

    Args:
        config: Configuration dictionary to display
    """
    table = Table(
        title=tr("wizard.summary.title", default="Configuration Summary"),
        title_style=f"bold {ACCENT}",
        show_header=True,
        header_style="bold white",
        border_style=ACCENT,
        padding=(0, 1),
    )

    table.add_column(tr("wizard.summary.setting", default="Setting"), style="white", no_wrap=True)
    table.add_column(tr("wizard.summary.value", default="Value"), style=ACCENT)

    def add_config_rows(data: dict[str, Any], prefix: str = "") -> None:
        """Recursively add configuration rows."""
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                # Add section header
                table.add_row(
                    Text(full_key, style="bold white"),
                    Text("", style="bright_black"),
                )
                add_config_rows(value, full_key)
            elif isinstance(value, list):
                # Format lists
                if value:
                    formatted = ", ".join(str(v) for v in value[:3])
                    if len(value) > 3:
                        formatted += f" ... (+{len(value) - 3} more)"
                    table.add_row(f"  {key}", formatted)
                else:
                    table.add_row(f"  {key}", Text("(empty)", style="bright_black"))
            elif value is None:
                table.add_row(f"  {key}", Text("(not set)", style="bright_black"))
            elif isinstance(value, bool):
                table.add_row(
                    f"  {key}",
                    Text("✓ Yes" if value else "✗ No", style="green" if value else "red"),
                )
            else:
                # Redact sensitive values
                if any(
                    sensitive in key.lower() for sensitive in ["token", "password", "secret", "key"]
                ):
                    display_value = "••••••••"
                else:
                    display_value = str(value)
                    if len(display_value) > 50:
                        display_value = display_value[:47] + "..."
                table.add_row(f"  {key}", display_value)

    add_config_rows(config)

    console.print()
    console.print(table)
    console.print()


def show_welcome_banner() -> None:
    """Display welcome banner for the wizard."""
    banner = Text()
    banner.append("╔═══════════════════════════════════════════════════════════╗\n", style=ACCENT)
    banner.append("║                                                           ║\n", style=ACCENT)
    banner.append("║           ", style=ACCENT)
    banner.append("Welcome to Ouro Setup Wizard", style="bold white")
    banner.append("            ║\n", style=ACCENT)
    banner.append("║                                                           ║\n", style=ACCENT)
    banner.append("╚═══════════════════════════════════════════════════════════╝", style=ACCENT)

    console.print()
    console.print(Align.center(banner))
    console.print()


def show_completion_banner() -> None:
    """Display completion banner."""
    banner = Text()
    banner.append("╔═══════════════════════════════════════════════════════════╗\n", style="green")
    banner.append("║                                                           ║\n", style="green")
    banner.append("║              ", style="green")
    banner.append("✓ Setup Complete!", style="bold green")
    banner.append("                      ║\n", style="green")
    banner.append("║                                                           ║\n", style="green")
    banner.append("╚═══════════════════════════════════════════════════════════╝", style="green")

    console.print()
    console.print(Align.center(banner))
    console.print()


def show_navigation_help() -> None:
    """Display navigation help."""
    help_text = Text()
    help_text.append(tr("wizard.nav.enter", default="Enter"), style="bold white")
    help_text.append(" = ", style="bright_black")
    help_text.append(tr("wizard.nav.next", default="Next"), style="white")
    help_text.append("  |  ", style="bright_black")
    help_text.append(tr("wizard.nav.b", default="B"), style="bold white")
    help_text.append(" = ", style="bright_black")
    help_text.append(tr("wizard.nav.back", default="Back"), style="white")
    help_text.append("  |  ", style="bright_black")
    help_text.append(tr("wizard.nav.s", default="S"), style="bold white")
    help_text.append(" = ", style="bright_black")
    help_text.append(tr("wizard.nav.skip", default="Skip"), style="white")
    help_text.append("  |  ", style="bright_black")
    help_text.append(tr("wizard.nav.q", default="Q"), style="bold white")
    help_text.append(" = ", style="bright_black")
    help_text.append(tr("wizard.nav.quit", default="Quit"), style="white")

    console.print(Align.center(help_text))
    console.print()


def create_progress_spinner(description: str) -> Progress:
    """Create a progress spinner for long operations.

    Args:
        description: Description of the operation

    Returns:
        Progress object
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console,
        transient=True,
    )


def prompt_input(
    prompt: str,
    default: str = "",
    password: bool = False,
) -> str:
    """Prompt user for input with styled prompt.

    Args:
        prompt: Prompt text
        default: Default value
        password: If True, hide input

    Returns:
        User input
    """
    prompt_text = Text()
    prompt_text.append("❯ ", style=f"bold {ACCENT}")
    prompt_text.append(prompt, style="white")

    if default:
        prompt_text.append(f" [{default}]", style="bright_black")

    prompt_text.append(": ", style="white")

    console.print(prompt_text, end="")

    if password:
        import getpass

        value = getpass.getpass("")
    else:
        value = input()

    return value.strip() or default


def confirm_action(prompt: str, default: bool = True) -> bool:
    """Prompt user for yes/no confirmation.

    Args:
        prompt: Prompt text
        default: Default value

    Returns:
        True if confirmed, False otherwise
    """
    default_text = "Y/n" if default else "y/N"

    prompt_text = Text()
    prompt_text.append("❯ ", style=f"bold {ACCENT}")
    prompt_text.append(prompt, style="white")
    prompt_text.append(f" [{default_text}]", style="bright_black")
    prompt_text.append(": ", style="white")

    console.print(prompt_text, end="")

    value = input().strip().lower()

    if not value:
        return default

    return value in ["y", "yes", "true", "1"]


def show_profile_comparison() -> None:
    """Display comparison table of setup profiles."""
    table = Table(
        title=tr("wizard.profiles.comparison", default="Profile Comparison"),
        title_style=f"bold {ACCENT}",
        show_header=True,
        header_style="bold white",
        border_style=ACCENT,
        padding=(0, 1),
    )

    table.add_column(tr("wizard.profiles.feature", default="Feature"), style="white")
    table.add_column(tr("wizard.profiles.normal", default="Normal"), style="green")
    table.add_column(tr("wizard.profiles.advanced", default="Advanced"), style="yellow")

    table.add_row(
        tr("wizard.profiles.questions", default="Questions"),
        tr("wizard.profiles.minimal", default="Minimal"),
        tr("wizard.profiles.all", default="All"),
    )
    table.add_row(
        tr("wizard.profiles.help_text", default="Help Text"),
        "✗",
        "✓",
    )
    table.add_row(
        tr("wizard.profiles.defaults", default="Defaults"),
        tr("wizard.profiles.sensible", default="Sensible"),
        tr("wizard.profiles.minimal_defaults", default="Minimal"),
    )
    table.add_row(
        tr("wizard.profiles.time", default="Setup Time"),
        tr("wizard.profiles.fast", default="~2 min"),
        tr("wizard.profiles.medium", default="~5 min"),
    )

    console.print()
    console.print(table)
    console.print()
