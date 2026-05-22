from __future__ import annotations

from importlib import metadata as importlib_metadata

from framekit.commands.alias import alias_command
from framekit.commands.batch import batch_command
from framekit.commands.browse import browse_command
from framekit.commands.cleanmkv import cleanmkv_command
from framekit.commands.doctor import doctor_command
from framekit.commands.encoder import encode_group
from framekit.commands.examples import examples_command
from framekit.commands.extract import extract_command
from framekit.commands.init import init_command
from framekit.commands.inspect import inspect_command
from framekit.commands.language import language_command
from framekit.commands.logs import logs_command
from framekit.commands.metadata import metadata_command
from framekit.commands.nfo import nfo_command
from framekit.commands.pipeline import pipeline_command
from framekit.commands.prez import prez_command
from framekit.commands.profile import profile_group
from framekit.commands.renamer import renamer_command
from framekit.commands.rollback import rollback_command
from framekit.commands.screenshot import screenshot_command
from framekit.commands.seedbox import seedbox_group
from framekit.commands.settings import settings_command
from framekit.commands.setup import setup_command
from framekit.commands.sort import sort_command
from framekit.commands.tools import rename_parent_command
from framekit.commands.torrent import torrent_command
from framekit.commands.upload import upload_group
from framekit.commands.validate import validate_command
from framekit.commands.watch import watch_group
from framekit.core.i18n import tr

# Prefer rich_click if available; fall back to click when the rich integration is not installed.
from framekit.ui.click_helper import click


# ---------------------------------------------------------------------------
# rich_click command groups — organizes `fk -h` into named sections
# ---------------------------------------------------------------------------
def _configure_rich_click() -> None:
    try:
        import rich_click
    except ImportError:
        return

    rich_click.rich_click.COMMAND_GROUPS = {
        "framekit": [
            {
                "name": tr("cli.section.configuration", default="Configuration"),
                "commands": ["init", "setup", "language", "about"],
            },
            {
                "name": tr("cli.section.tools", default="Tools"),
                "commands": [
                    "settings",
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
        resolved_name = self._aliases.get(cmd_name, cmd_name)
        return super().get_command(ctx, resolved_name)


def _get_version() -> str:
    """Return the installed Framekit version."""
    for distribution_name in ("framekit-cli", "framekit"):
        try:
            return importlib_metadata.version(distribution_name)
        except importlib_metadata.PackageNotFoundError:
            continue
        except Exception:  # nosec B112
            continue

    try:
        from framekit import __version__

        return __version__
    except Exception:
        return "2.0.0"


@click.command(
    "about",
    help=tr("cli.about.help", default="Show Framekit version, copyright and license information."),
)
def about_command() -> None:
    """Handle about command."""
    version = _get_version()
    click.echo(
        "\n"
        f"Framekit {version}\n"
        "Copyright (C) 2026 astrve\n\n"
        "This program comes with ABSOLUTELY NO WARRANTY.\n"
        "This is free software, and you are welcome to redistribute it\n"
        "under the terms of the GNU General Public License v3.0.\n\n"
        "Repository: https://github.com/astrve/framekit\n"
        "License: GNU General Public License v3.0\n"
        "See the LICENSE file for the full license text.\n"
    )


@click.group(
    cls=AliasedGroup,
    context_settings={"help_option_names": ["-h", "--help"]},
    help=tr(
        "cli.main.help",
        default=(
            "Framekit — tracker-ready media workflow toolkit.\n\n"
            "Use '<command> -h' for detailed help on any command.\n"
            "Add --dry-run where available to preview changes."
        ),
    ),
)
@click.version_option(
    version=_get_version(),
    prog_name="framekit",
)
def cli() -> None:
    """Handle cli."""


# Configuration
cli.add_command(about_command, "about")
cli.add_command(init_command, "init")
cli.add_command(setup_command, "setup")
cli.add_command(language_command, "language")

# Tools
cli.add_command(settings_command, "settings")
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

# Aliases
cli.add_alias("license", "about")
cli.add_alias("doc", "doctor")
cli.add_alias("diag", "doctor")
cli.add_alias("lang", "language")
cli.add_alias("cfg", "settings")
cli.add_alias("set", "settings")
cli.add_alias("ins", "inspect")
cli.add_alias("ren", "renamer")
cli.add_alias("cmk", "cleanmkv")
cli.add_alias("nf", "nfo")
cli.add_alias("meta", "metadata")
cli.add_alias("md", "metadata")
cli.add_alias("tor", "torrent")
cli.add_alias("sc", "screenshot")
cli.add_alias("screens", "screenshot")
cli.add_alias("ext", "extract")
cli.add_alias("pipe", "pipeline")
cli.add_alias("pr", "pipeline")
cli.add_alias("ex", "examples")
cli.add_alias("bat", "batch")
cli.add_alias("enc", "encode")
cli.add_alias("up", "upload")
cli.add_alias("rp", "rename-parent")


# ---------------------------------------------------------------------------
# Third-party plugins (``framekit.modules`` entry-points)
# ---------------------------------------------------------------------------
def _load_third_party_plugins() -> None:
    import os

    if os.environ.get("FRAMEKIT_DISABLE_PLUGINS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return
    try:
        from framekit.core.plugins import load_plugins

        load_plugins(cli)
    except Exception:  # nosec B110
        pass


_load_third_party_plugins()
