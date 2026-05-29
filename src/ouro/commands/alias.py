"""CLI commands for managing command aliases."""

from __future__ import annotations

import json
import sys
from typing import Any

from rich import box
from rich.table import Table

from ouro.core.aliases import AliasError, AliasManager, InvalidAliasNameError
from ouro.core.paths import get_settings_path
from ouro.core.settings import SettingsStore
from ouro.ui.click_helper import click
from ouro.ui.console import console, print_error, print_success, print_warning


def _get_alias_manager() -> AliasManager:
    """Get the alias manager instance."""
    settings_path = get_settings_path()
    store = SettingsStore(settings_path)
    return AliasManager(store)


def _format_alias_table(aliases: dict[str, Any], title: str = "Aliases") -> Table:
    """Format aliases as a Rich table.

    Args:
        aliases: Dictionary of alias definitions
        title: Table title

    Returns:
        Formatted Rich table
    """
    table = Table(title=title, box=box.ROUNDED, expand=True)
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Command", style="green")
    table.add_column("Description", style="dim")
    table.add_column("Status", justify="center", style="yellow")

    for name, alias in sorted(aliases.items()):
        status = "✓" if alias.enabled else "✗"
        status_style = "green" if alias.enabled else "red"
        table.add_row(
            name,
            alias.command,
            alias.description or "-",
            f"[{status_style}]{status}[/{status_style}]",
        )

    return table


@click.group(
    name="alias",
    help="Manage command aliases for Ouro.",
)
def alias_command() -> None:
    """Alias command group."""


@alias_command.command(
    name="list",
    help="List all command aliases.",
)
@click.option(
    "--user",
    is_flag=True,
    help="Show only user-defined aliases.",
)
@click.option(
    "--builtin",
    is_flag=True,
    help="Show only built-in aliases.",
)
@click.option(
    "--enabled",
    is_flag=True,
    help="Show only enabled aliases.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output as JSON.",
)
def list_aliases(
    user: bool,
    builtin: bool,
    enabled: bool,
    json_output: bool,
) -> None:
    """List command aliases."""
    try:
        manager = _get_alias_manager()
        aliases = manager.list_aliases(
            user_only=user,
            builtin_only=builtin,
            enabled_only=enabled,
        )

        if json_output:
            # Convert to JSON-serializable format
            output = {
                name: {
                    "command": alias.command,
                    "description": alias.description,
                    "enabled": alias.enabled,
                }
                for name, alias in aliases.items()
            }
            console.print(json.dumps(output, indent=2))
        else:
            if not aliases:
                print_warning("No aliases found.")
                return

            # Determine title
            if user:
                title = "User Aliases"
            elif builtin:
                title = "Built-in Aliases"
            else:
                title = "All Aliases"

            table = _format_alias_table(aliases, title)
            console.print(table)

            # Print summary
            total = len(aliases)
            enabled_count = sum(1 for a in aliases.values() if a.enabled)
            console.print(f"\nTotal: {total} aliases ({enabled_count} enabled)")

    except Exception as exc:
        print_error(f"Failed to list aliases: {exc}")
        sys.exit(1)


@alias_command.command(
    name="show",
    help="Show details of a specific alias.",
)
@click.argument("name")
def show_alias(name: str) -> None:
    """Show alias details."""
    try:
        manager = _get_alias_manager()
        alias = manager.get_alias(name)

        if alias is None:
            print_error(f"Alias '{name}' not found.")
            sys.exit(1)

        # Create a single-row table
        table = Table(box=box.ROUNDED, expand=True)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Name", alias.name)
        table.add_row("Command", alias.command)
        table.add_row("Description", alias.description or "-")
        table.add_row(
            "Status",
            "[green]Enabled[/green]" if alias.enabled else "[red]Disabled[/red]",
        )

        console.print(table)

    except Exception as exc:
        print_error(f"Failed to show alias: {exc}")
        sys.exit(1)


@alias_command.command(
    name="add",
    help="Add a new command alias.",
)
@click.argument("name")
@click.argument("command")
@click.option(
    "--description",
    "-d",
    default="",
    help="Description of the alias.",
)
@click.option(
    "--disabled",
    is_flag=True,
    help="Create the alias in disabled state.",
)
def add_alias(
    name: str,
    command: str,
    description: str,
    disabled: bool,
) -> None:
    """Add a new alias."""
    try:
        manager = _get_alias_manager()
        manager.add_alias(
            name=name,
            command=command,
            description=description,
            enabled=not disabled,
        )

        print_success(f"Alias '{name}' added successfully.")
        console.print(f"  [cyan]{name}[/cyan] → [green]{command}[/green]")

    except InvalidAliasNameError as exc:
        print_error(f"Invalid alias name: {exc}")
        sys.exit(1)
    except AliasError as exc:
        print_error(f"Failed to add alias: {exc}")
        sys.exit(1)
    except Exception as exc:
        print_error(f"Unexpected error: {exc}")
        sys.exit(1)


@alias_command.command(
    name="remove",
    help="Remove a command alias.",
)
@click.argument("name")
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Skip confirmation prompt.",
)
def remove_alias(name: str, force: bool) -> None:
    """Remove an alias."""
    try:
        manager = _get_alias_manager()

        # Check if alias exists
        alias = manager.get_alias(name)
        if alias is None:
            print_error(f"Alias '{name}' not found.")
            sys.exit(1)

        # Confirm removal unless --force or global --yes
        if not force:
            from ouro.core.destructive import confirm_destructive

            if not confirm_destructive(f"Remove alias '{name}'?"):
                return

        manager.remove_alias(name)
        print_success(f"Alias '{name}' removed successfully.")

    except AliasError as exc:
        print_error(f"Failed to remove alias: {exc}")
        sys.exit(1)
    except Exception as exc:
        print_error(f"Unexpected error: {exc}")
        sys.exit(1)


@alias_command.command(
    name="enable",
    help="Enable a disabled alias.",
)
@click.argument("name")
def enable_alias(name: str) -> None:
    """Enable an alias."""
    try:
        manager = _get_alias_manager()
        manager.enable_alias(name)
        print_success(f"Alias '{name}' enabled.")

    except AliasError as exc:
        print_error(f"Failed to enable alias: {exc}")
        sys.exit(1)
    except Exception as exc:
        print_error(f"Unexpected error: {exc}")
        sys.exit(1)


@alias_command.command(
    name="disable",
    help="Disable an alias.",
)
@click.argument("name")
def disable_alias(name: str) -> None:
    """Disable an alias."""
    try:
        manager = _get_alias_manager()
        manager.disable_alias(name)
        print_success(f"Alias '{name}' disabled.")

    except AliasError as exc:
        print_error(f"Failed to disable alias: {exc}")
        sys.exit(1)
    except Exception as exc:
        print_error(f"Unexpected error: {exc}")
        sys.exit(1)
