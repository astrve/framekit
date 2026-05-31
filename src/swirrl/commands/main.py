from __future__ import annotations

from importlib import metadata as importlib_metadata

from swirrl.commands.alias import alias_command
from swirrl.commands.batch import batch_command
from swirrl.commands.browse import browse_command
from swirrl.commands.cleanmkv import cleanmkv_command
from swirrl.commands.config import config_group
from swirrl.commands.doctor import doctor_command
from swirrl.commands.encoder import encode_group
from swirrl.commands.examples import examples_command
from swirrl.commands.extract import extract_command
from swirrl.commands.init import init_command
from swirrl.commands.inspect import inspect_command
from swirrl.commands.language import language_command
from swirrl.commands.logs import logs_command
from swirrl.commands.metadata import metadata_command
from swirrl.commands.nfo import nfo_command
from swirrl.commands.pipeline import pipeline_command
from swirrl.commands.prez import prez_command
from swirrl.commands.profile import profile_group
from swirrl.commands.renamer import renamer_command
from swirrl.commands.rollback import rollback_command
from swirrl.commands.screenshot import screenshot_command
from swirrl.commands.serve import serve_command
from swirrl.commands.service import service_group
from swirrl.commands.seedbox import seedbox_group
from swirrl.commands.settings import settings_command
from swirrl.commands.setup import setup_command
from swirrl.commands.sort import sort_command
from swirrl.commands.tools import rename_parent_command
from swirrl.commands.torrent import torrent_command
from swirrl.commands.upload import upload_group
from swirrl.commands.validate import validate_command
from swirrl.commands.watch import watch_group
from swirrl.core.aliases import AliasError, AliasManager
from swirrl.core.i18n import tr
from swirrl.core.settings import SettingsStore

# Prefer rich_click if available; fall back to click when the rich integration is not installed.
from swirrl.ui.click_helper import click


# ---------------------------------------------------------------------------
# rich_click command groups — organizes `swirrl -h` into named sections
# ---------------------------------------------------------------------------
def _configure_rich_click() -> None:
    try:
        import rich_click
    except ImportError:
        return

    rich_click.rich_click.COMMAND_GROUPS = {
        "swirrl": [
            {
                "name": tr("cli.section.configuration", default="Configuration"),
                "commands": ["init", "setup", "serve", "service", "language", "about"],
            },
            {
                "name": tr("cli.section.tools", default="Tools"),
                "commands": [
                    "settings",
                    "config",
                    "alias",
                    "doctor",
                    "logs",
                    "rollback",
                    "examples",
                    "rename-parent",
                    "validate",
                ],
            },
            {
                "name": tr("cli.section.navigation", default="Navigation"),
                "commands": ["profile", "inspect", "browse", "sort"],
            },
            {
                "name": tr("cli.section.media", default="Media processing"),
                "commands": ["extract", "screenshot", "encode", "watch", "seedbox"],
            },
            {
                "name": tr("cli.section.workflow", default="Workflow"),
                "commands": [
                    "renamer",
                    "cleanmkv",
                    "metadata",
                    "nfo",
                    "torrent",
                    "prez",
                    "upload",
                    "pipeline",
                    "batch",
                ],
            },
        ],
    }


_configure_rich_click()


try:
    from rich_click import RichGroup as _BaseGroup
except ImportError:
    _BaseGroup = click.Group  # type: ignore[misc,assignment]


class AliasedGroup(_BaseGroup):  # type: ignore[misc]
    """Aliased group."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._aliases: dict[str, str] = {}

    def add_alias(self, alias: str, target: str) -> None:
        """Handle add alias."""
        self._aliases[alias] = target

    def get_command(self, ctx: click.Context, cmd_name: str):
        """Return the command."""
        if cmd_name in self._aliases and self._is_configured_alias_removed(cmd_name):
            return None
        resolved_name = self._aliases.get(cmd_name, cmd_name)
        return super().get_command(ctx, resolved_name)

    def resolve_command(self, ctx: click.Context, args: list[str]):
        """Resolve static aliases and user-defined aliases before Click dispatch."""
        if not args:
            return super().resolve_command(ctx, args)

        command_name = args[0]
        if super().get_command(ctx, command_name):
            return super().resolve_command(ctx, args)
        if command_name in self._aliases and not self._is_configured_alias_removed(command_name):
            return super().resolve_command(ctx, args)

        resolved = self._resolve_configured_alias(command_name, args[1:])
        if resolved is None:
            return super().resolve_command(ctx, args)

        target_command = self.get_command(ctx, resolved.command)
        if target_command is None:
            return super().resolve_command(ctx, [resolved.command, *resolved.args])
        return resolved.command, target_command, resolved.args

    def _resolve_configured_alias(self, command_name: str, args: list[str]):
        try:
            manager = AliasManager(SettingsStore())
            settings = manager.settings_store.load()
            aliases_enabled = settings.get("aliases", {}).get("enabled", True)
            if not aliases_enabled or manager.get_alias(command_name) is None:
                return None
            return manager.resolve(command_name, args)
        except AliasError as exc:
            raise click.UsageError(str(exc)) from exc
        except Exception:
            return None

    def _is_configured_alias_removed(self, alias: str) -> bool:
        try:
            settings = SettingsStore().load()
            removed = settings.get("aliases", {}).get("removed", [])
            return isinstance(removed, list) and alias in removed
        except Exception:
            return False


def _get_version() -> str:
    """Return the installed Swirrl version."""
    for distribution_name in ("swirrl-auto", "swirrl"):
        try:
            return importlib_metadata.version(distribution_name)
        except importlib_metadata.PackageNotFoundError:
            continue
        except Exception:  # nosec B112
            continue

    try:
        from swirrl import __version__

        return __version__
    except Exception:
        return "2.0.0"


@click.command(
    "about",
    help=tr("cli.about.help", default="Show Swirrl version, copyright and license information."),
)
def about_command() -> None:
    """Handle about command."""
    version = _get_version()
    click.echo(
        "\n"
        f"Swirrl {version}\n"
        "Copyright (C) 2026 astrve\n\n"
        "This program comes with ABSOLUTELY NO WARRANTY.\n"
        "This is free software, and you are welcome to redistribute it\n"
        "under the terms of the GNU General Public License v3.0.\n\n"
        "Repository: https://github.com/astrve/swirrl\n"
        "License: GNU General Public License v3.0\n"
        "See the LICENSE file for the full license text.\n"
    )


@click.group(
    cls=AliasedGroup,
    context_settings={"help_option_names": ["-h", "--help"]},
    help=tr(
        "cli.main.help",
        default=(
            "Swirrl — tracker-ready media workflow toolkit.\n\n"
            "Use '<command> -h' for detailed help on any command.\n"
            "Add --dry-run where available to preview changes."
        ),
    ),
)
@click.version_option(
    version=_get_version(),
    prog_name="swirrl",
)
def cli() -> None:
    """Handle cli."""


# Configuration
cli.add_command(about_command, "about")
cli.add_command(init_command, "init")
cli.add_command(setup_command, "setup")
cli.add_command(serve_command, "serve")
cli.add_command(service_group, "service")
cli.add_command(language_command, "language")

# Tools
cli.add_command(settings_command, "settings")
cli.add_command(config_group, "config")
cli.add_command(alias_command, "alias")
cli.add_command(doctor_command, "doctor")
cli.add_command(logs_command, "logs")
cli.add_command(rollback_command, "rollback")
cli.add_command(examples_command, "examples")
cli.add_command(rename_parent_command, "rename-parent")
cli.add_command(validate_command, "validate")

# Navigation
cli.add_command(profile_group, "profile")
cli.add_command(inspect_command, "inspect")
cli.add_command(browse_command, "browse")
cli.add_command(sort_command, "sort")

# Media processing
cli.add_command(extract_command, "extract")
cli.add_command(screenshot_command, "screenshot")
cli.add_command(encode_group, "encode")
cli.add_command(watch_group, "watch")
cli.add_command(seedbox_group, "seedbox")

# Workflow
cli.add_command(renamer_command, "renamer")
cli.add_command(cleanmkv_command, "cleanmkv")
cli.add_command(metadata_command, "metadata")
cli.add_command(nfo_command, "nfo")
cli.add_command(torrent_command, "torrent")
cli.add_command(prez_command, "prez")
cli.add_command(upload_group, "upload")
cli.add_command(pipeline_command, "pipeline")
cli.add_command(batch_command, "batch")

# Static short aliases removed by design.
# The `alias` command remains available for explicit user-defined aliases.


# ---------------------------------------------------------------------------
# Third-party plugins (``swirrl.modules`` entry-points)
# ---------------------------------------------------------------------------
def _load_third_party_plugins() -> None:
    import os

    if os.environ.get("SWIRRL_DISABLE_PLUGINS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return
    try:
        from swirrl.core.plugins import load_plugins

        load_plugins(cli)
    except Exception:  # nosec B110
        pass


_load_third_party_plugins()
