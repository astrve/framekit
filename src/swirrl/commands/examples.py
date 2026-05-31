"""``swirrl examples`` — print common command recipes in the active locale.

The wizard and `--help` output are good for *learning* a command, but new
users often need to *see* the workflow before they understand which command
to invoke. This file curates a small set of high-value recipes covering the
main use cases. Translations live in ``swirrl.locales`` so the recipes
follow the active UI locale.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich import box
from rich.panel import Panel
from rich.syntax import Syntax

from swirrl.core.i18n import tr
from swirrl.ui.click_helper import click
from swirrl.ui.console import console


@dataclass(slots=True, frozen=True)
class _Recipe:
    title_key: str
    title_default: str
    description_key: str
    description_default: str
    command: str


_RECIPES: tuple[_Recipe, ...] = (
    _Recipe(
        title_key="examples.recipe.full_pipeline.title",
        title_default="Run the full pipeline on a single release",
        description_key="examples.recipe.full_pipeline.desc",
        description_default=(
            "Renames the files, remuxes a clean MKV, generates the NFO, "
            "creates the .torrent and renders the Prez sheet — in one shot."
        ),
        command="swirrl pipeline /path/to/Release.2024.1080p.WEB-DL.x264-GROUP",
    ),
    _Recipe(
        title_key="examples.recipe.batch.title",
        title_default="Batch a folder of releases unattended",
        description_key="examples.recipe.batch.desc",
        description_default=(
            "Scans every direct subfolder and runs the pipeline on each. "
            "Use a preset to keep the configuration consistent."
        ),
        command="swirrl batch /path/to/releases --auto --pipeline-preset default",
    ),
    _Recipe(
        title_key="examples.recipe.metadata.title",
        title_default="Resolve TMDb metadata for a release",
        description_key="examples.recipe.metadata.desc",
        description_default=(
            "Searches TMDb, prompts you to pick the right title (or accept "
            "the top match with -y), then writes the resolved IDs back."
        ),
        command="swirrl metadata /path/to/Release -y",
    ),
    _Recipe(
        title_key="examples.recipe.cleanmkv.title",
        title_default="Clean an MKV interactively",
        description_key="examples.recipe.cleanmkv.desc",
        description_default=(
            "Opens the track selector, previews the resulting mux command, "
            "and asks for confirmation before remuxing."
        ),
        command="swirrl cleanmkv /path/to/Release.mkv",
    ),
    _Recipe(
        title_key="examples.recipe.nfo.title",
        title_default="Build a localized NFO",
        description_key="examples.recipe.nfo.desc",
        description_default=(
            "Renders the active NFO template in the configured locale and "
            "embeds resolved metadata when -m is passed."
        ),
        command="swirrl nfo /path/to/Release -m",
    ),
    _Recipe(
        title_key="examples.recipe.torrent.title",
        title_default="Create a private torrent",
        description_key="examples.recipe.torrent.desc",
        description_default=(
            "Picks the announce URL from your settings (or override with "
            "--announce) and writes the .torrent next to the release."
        ),
        command="swirrl torrent /path/to/Release --announce https://tracker/announce",
    ),
    _Recipe(
        title_key="examples.recipe.prez.title",
        title_default="Generate a presentation sheet",
        description_key="examples.recipe.prez.desc",
        description_default=("Builds the HTML + BBCode prez files using the selected templates."),
        command="swirrl prez /path/to/Release --html-template aurora --bbcode-template classic",
    ),
    _Recipe(
        title_key="examples.recipe.watch.title",
        title_default="Watch a download folder and auto-process",
        description_key="examples.recipe.watch.desc",
        description_default=(
            "Once configured via ``swirrl watch setup``, this runs in the "
            "foreground and triggers the pipeline whenever a new release "
            "lands in the watched folder."
        ),
        command="swirrl watch start --all",
    ),
    _Recipe(
        title_key="examples.recipe.pipeline_optin.title",
        title_default="Run only specific pipeline modules",
        description_key="examples.recipe.pipeline_optin.desc",
        description_default=(
            "Use opt-in flags to run only the modules you need. "
            "Combine freely: --ren --nfo --tor, or use --all for everything."
        ),
        command="swirrl pipeline /path/to/Release --ren --nfo --tor",
    ),
    _Recipe(
        title_key="examples.recipe.language.title",
        title_default="Set per-module language",
        description_key="examples.recipe.language.desc",
        description_default=(
            "Each module can have its own locale. Use 'auto' to follow the UI "
            "language, or set a specific one. Metadata uses BCP-47 tags."
        ),
        command="swirrl language nfo fr\nswirrl language metadata fr-FR",
    ),
    _Recipe(
        title_key="examples.recipe.profile.title",
        title_default="Create a workflow profile with the wizard",
        description_key="examples.recipe.profile.desc",
        description_default=(
            "Profiles store module selections, presets and locale overrides. "
            "The wizard walks you through each setting interactively."
        ),
        command="swirrl profile create anime --wizard",
    ),
    _Recipe(
        title_key="examples.recipe.doctor.title",
        title_default="Diagnose installation and configuration",
        description_key="examples.recipe.doctor.desc",
        description_default=(
            "Verifies that mkvtoolnix, mediainfo and your TMDb credentials are "
            "ready. Run before reporting a bug."
        ),
        command="swirrl settings doctor",
    ),
    _Recipe(
        title_key="examples.recipe.settings.title",
        title_default="Inspect current settings",
        description_key="examples.recipe.settings.desc",
        description_default="Shows all active settings, cache status and security vault info.",
        command="swirrl settings",
    ),
)


@click.group(
    "examples",
    invoke_without_command=True,
    help=tr(
        "cli.examples.help",
        default=(
            "Print ready-to-copy command recipes covering the main Swirrl "
            "workflows.\n\n"
            "Subcommands:\n"
            "  alias   List command aliases"
        ),
    ),
)
@click.option(
    "--plain",
    is_flag=True,
    help=tr(
        "cli.examples.plain",
        default="Plain output (no panels/colors). Useful for piping to ``less`` or scripts.",
    ),
)
@click.option(
    "-j",
    "--json",
    "json_output",
    is_flag=True,
    help=tr(
        "cli.examples.json",
        default="Emit recipes as a JSON array of {title, description, command} objects.",
    ),
)
@click.pass_context
def examples_command(ctx: click.Context, plain: bool, json_output: bool) -> int:
    """Print curated command recipes in the active UI locale."""
    if ctx.invoked_subcommand is not None:
        return 0
    if json_output:
        from swirrl.core.json_output import emit_json, json_envelope

        rows = [
            {
                "title": tr(recipe.title_key, default=recipe.title_default),
                "description": tr(recipe.description_key, default=recipe.description_default),
                "command": recipe.command,
            }
            for recipe in _RECIPES
        ]
        emit_json(json_envelope(command="examples", data={"recipes": rows}))
        return 0

    if plain:
        for recipe in _RECIPES:
            title = tr(recipe.title_key, default=recipe.title_default)
            description = tr(recipe.description_key, default=recipe.description_default)
            console.print(f"# {title}")
            console.print(f"#   {description}")
            console.print(recipe.command)
            console.print()
        return 0

    console.print(
        Panel(
            tr(
                "examples.intro",
                default=(
                    "Common Swirrl recipes. Copy a line, adjust the paths to "
                    "your release, and run."
                ),
            ),
            title=tr("examples.title", default="Swirrl recipes"),
            border_style="white",
            box=box.HEAVY,
            expand=True,
        )
    )
    console.print()

    for index, recipe in enumerate(_RECIPES, start=1):
        title = tr(recipe.title_key, default=recipe.title_default)
        description = tr(recipe.description_key, default=recipe.description_default)
        console.print(f"[bold cyan]{index}.[/bold cyan] [bold]{title}[/bold]")
        console.print(f"   [dim]{description}[/dim]")
        console.print(
            Syntax(
                recipe.command,
                "bash",
                theme="ansi_dark",
                padding=(0, 2),
                code_width=100,
            )
        )
        console.print()

    return 0


@examples_command.command(
    "alias",
    help=tr("cli.examples.alias.help", default="List all command aliases."),
)
def examples_alias_command() -> None:
    """List command aliases (read-only)."""
    from rich.table import Table

    from swirrl.commands.alias import _get_alias_manager

    try:
        manager = _get_alias_manager()
        aliases = manager.list_aliases()
    except Exception as exc:
        console.print(f"[red]Failed to list aliases: {exc}[/red]")
        return

    if not aliases:
        console.print("[dim]No aliases found.[/dim]")
        return

    table = Table(title="Command Aliases", box=box.HEAVY, expand=True)
    table.add_column("Alias", width=12, no_wrap=True)
    table.add_column("Command", ratio=1)
    table.add_column("Status", width=10, no_wrap=True)

    for name, alias in sorted(aliases.items()):
        status = "[green]on[/green]" if alias.enabled else "[dim]off[/dim]"
        table.add_row(name, alias.command, status)

    console.print(table)
