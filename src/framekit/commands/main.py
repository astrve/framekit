from __future__ import annotations

from importlib import metadata as importlib_metadata

# Prefer rich_click if available; fall back to click when the rich integration is not installed.
try:
    import rich_click as click  # type: ignore[import-not-found]
except Exception:
    import click  # type: ignore[import-not-found]

from framekit.commands.cleanmkv import cleanmkv_command
from framekit.commands.doctor import doctor_command
from framekit.commands.inspect import inspect_command
from framekit.commands.language import language_command
from framekit.commands.metadata import metadata_command
from framekit.commands.nfo import nfo_command
from framekit.commands.pipeline import pipeline_command
from framekit.commands.prez import prez_command
from framekit.commands.renamer import renamer_command
from framekit.commands.settings import settings_command
from framekit.commands.setup import setup_command
from framekit.commands.torrent import torrent_command
from framekit.core.i18n import tr


class AliasedGroup(click.Group):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._aliases: dict[str, str] = {}

    def add_alias(self, alias: str, target: str) -> None:
        self._aliases[alias] = target

    def get_command(self, ctx: click.Context, cmd_name: str):
        resolved_name = self._aliases.get(cmd_name, cmd_name)
        return super().get_command(ctx, resolved_name)


def _get_version() -> str:
    """
    Return the installed Framekit version.

    The public PyPI distribution is named ``framekit-cli`` while the import
    package remains ``framekit``. Prefer the distribution name used for
    publication, then fall back to the import package metadata and finally to
    the in-package ``__version__`` constant for editable/local checkouts.
    """
    for distribution_name in ("framekit-cli", "framekit"):
        try:
            return importlib_metadata.version(distribution_name)
        except importlib_metadata.PackageNotFoundError:
            continue
        except Exception:
            continue

    try:
        from framekit import __version__

        return __version__
    except Exception:
        return "1.1.0"


@click.command(
    "about",
    help=tr("cli.about.help", default="Show Framekit version, copyright and license information."),
)
def about_command() -> None:
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
            "Core workflow:\n"
            "  ren / renamer   Normalize release file names.\n"
            "  cmk / cleanmkv  Select audio/subtitle tracks and remux clean MKV copies.\n"
            "  nf / nfo        Build localized tracker-ready NFO files.\n"
            "  md / metadata   Search and resolve TMDb metadata.\n\n"
            "General commands:\n"
            "  about / license Show version, copyright and license information.\n"
            "  doctor / doc    Check tools, settings, metadata and templates.\n"
            "  inspect / ins   Inspect a release folder and detect completeness.\n"
            "  settings / cfg  Inspect and edit Framekit settings.\n"
            "  language / lang Show or change the interface language.\n"
            "  setup / init    Run the guided setup.\n\n"
            "Diagnostics:\n"
            "  --debug               Print tracebacks and write a debug log.\n"
            "  --log-file <path>     Write structured JSONL logs to a custom path.\n"
            "  FRAMEKIT_DEBUG=1      Enable debug mode from the environment.\n"
            "  FRAMEKIT_LOG_FILE=... Write logs from the environment.\n\n"
            "Useful examples:\n"
            "  fk ren <folder>       Preview then confirm renaming.\n"
            "  fk cmk <folder>       Open the track selector, preview, then confirm remux.\n"
            "  fk nf <folder> -m     Build an NFO with matching localized TMDb metadata.\n"
            "  fk pipe <folder> --announce https://tracker/announce\n"
            "  fk --debug cmk <folder>\n"
            "  fk cfg get general.locale\n"
            "  fk lang set fr\n"
            "  fk about\n"
            "  fk doctor\n\n"
            "Use '<command> -h' for every option and advanced mode. Add --dry-run where available to preview only."
        ),
    ),
)
@click.version_option(
    version=_get_version(),
    prog_name="framekit",
)
def cli() -> None:
    pass


cli.add_command(about_command, "about")
cli.add_command(doctor_command, "doctor")
cli.add_command(language_command, "language")
cli.add_command(settings_command, "settings")
cli.add_command(inspect_command, "inspect")
cli.add_command(renamer_command, "renamer")
cli.add_command(cleanmkv_command, "cleanmkv")
cli.add_command(nfo_command, "nfo")
cli.add_command(metadata_command, "metadata")
cli.add_command(torrent_command, "torrent")
cli.add_command(prez_command, "prez")
cli.add_command(pipeline_command, "pipeline")
cli.add_command(setup_command, "setup")

cli.add_alias("license", "about")
cli.add_alias("doc", "doctor")
cli.add_alias("lang", "language")
cli.add_alias("cfg", "settings")
cli.add_alias("ins", "inspect")
cli.add_alias("ren", "renamer")
cli.add_alias("cmk", "cleanmkv")
cli.add_alias("nf", "nfo")
cli.add_alias("md", "metadata")
cli.add_alias("tor", "torrent")
cli.add_alias("pipe", "pipeline")
cli.add_alias("init", "setup")
