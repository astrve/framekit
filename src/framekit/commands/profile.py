"""Configuration profile management commands."""

from __future__ import annotations

import json
from typing import Any

from rich.table import Table

from framekit.core.i18n import tr
from framekit.core.settings.profiles import (
    delete_profile,
    get_active_profile,
    list_profiles,
    load_profile,
    save_profile,
    set_active_profile,
)
from framekit.core.settings.store import SettingsStore
from framekit.ui.click_helper import click
from framekit.ui.console import console, print_error, print_info, print_success
from framekit.ui.unified_selector import SelectorOption, confirm_choice, text_input
from framekit.ui.unified_selector import select_many as _select_many
from framekit.ui.unified_selector import select_one as _select_one


@click.group("profile")
def profile_group() -> None:
    """Manage configuration profiles.

    Profiles let you switch between different workflow configurations
    (tracker presets, templates, modules) with a single command.
    """


@profile_group.command("list")
def profile_list() -> None:
    """List available profiles."""
    profiles = list_profiles()
    active = get_active_profile()

    if not profiles:
        print_info("No profiles found. Create one with: fk profile create <name>")
        return

    table = Table(title="Configuration Profiles")
    table.add_column("Name")
    table.add_column("Active", justify="center")
    table.add_column("Description")

    for name in profiles:
        is_active = "●" if name == active else ""
        try:
            data = load_profile(name)
            desc = data.get("description", "")
        except Exception:
            desc = "(error loading)"
        table.add_row(name, is_active, desc)

    console.print(table)


@profile_group.command("use")
@click.argument("name", required=False)
def profile_use(name: str | None) -> None:
    """Activate a profile (or select interactively)."""
    profiles = list_profiles()
    if not profiles:
        print_error("No profiles available. Create one first: fk profile create <name>")
        return

    if name is None:
        options = [SelectorOption(label=p, value=p) for p in profiles]
        chosen = select_one(options, title="Select profile to activate")
        if chosen is None:
            return
        name = chosen.value

    try:
        set_active_profile(name)
        print_success(f"Active profile: {name}")
    except FileNotFoundError:
        print_error(f"Profile not found: {name}")


@profile_group.command("clear")
def profile_clear() -> None:
    """Deactivate the current profile (use base settings)."""
    set_active_profile(None)
    print_success("Profile cleared. Using base settings.")


_ALL_MODULES = ("renamer", "cleanmkv", "nfo", "torrent", "prez", "encoder", "upload")
_LOCALE_CHOICES = ("auto", "en", "fr", "es")
_PREZ_FORMATS = ("both", "html", "bbcode", "mediainfo")


def _run_profile_wizard(description: str) -> dict[str, Any]:
    """Interactive wizard that builds profile overrides step by step."""
    overrides: dict[str, Any] = {}

    # ── Step 1: Enabled modules ─────────────────────────────────────────
    console.print("\n[bold]1/5[/bold] — Enabled pipeline modules")
    module_options = [
        SelectorOption(label=m, value=m, selected=(m not in ("encoder", "upload")))
        for m in _ALL_MODULES
    ]
    chosen_modules = _select_many(
        title=tr("profile.wizard.modules", default="Select modules for this profile"),
        entries=module_options,
    )
    if chosen_modules:
        overrides.setdefault("modules", {}).setdefault("pipeline", {})["enabled_modules"] = list(
            chosen_modules
        )

    # ── Step 2: CleanMKV preset ─────────────────────────────────────────
    if "cleanmkv" in (chosen_modules or []):
        console.print("\n[bold]2/5[/bold] — CleanMKV preset")
        cmk_options = [SelectorOption(label=p, value=p) for p in ("multi", "anime", "vo", "custom")]
        cmk_preset = select_one(
            cmk_options,
            title=tr("profile.wizard.cleanmkv_preset", default="CleanMKV preset"),
        )
        if cmk_preset:
            overrides.setdefault("modules", {}).setdefault("cleanmkv", {})["default_preset"] = (
                cmk_preset
            )
    else:
        console.print("\n[bold]2/5[/bold] — CleanMKV preset [dim](skipped)[/dim]")

    # ── Step 3: NFO locale + template ───────────────────────────────────
    if "nfo" in (chosen_modules or []):
        console.print("\n[bold]3/5[/bold] — NFO settings")
        nfo_locale_options = [SelectorOption(label=loc, value=loc) for loc in _LOCALE_CHOICES]
        nfo_locale = select_one(
            nfo_locale_options,
            title=tr("profile.wizard.nfo_locale", default="NFO locale"),
        )
        if nfo_locale:
            overrides.setdefault("modules", {}).setdefault("nfo", {})["locale"] = nfo_locale
    else:
        console.print("\n[bold]3/5[/bold] — NFO settings [dim](skipped)[/dim]")

    # ── Step 4: Prez format + locale ────────────────────────────────────
    if "prez" in (chosen_modules or []):
        console.print("\n[bold]4/5[/bold] — Prez settings")
        fmt_options = [SelectorOption(label=f, value=f) for f in _PREZ_FORMATS]
        prez_fmt = select_one(
            fmt_options,
            title=tr("profile.wizard.prez_format", default="Prez output format"),
        )
        if prez_fmt:
            overrides.setdefault("modules", {}).setdefault("prez", {})["format"] = prez_fmt

        prez_locale_options = [SelectorOption(label=loc, value=loc) for loc in _LOCALE_CHOICES]
        prez_locale = select_one(
            prez_locale_options,
            title=tr("profile.wizard.prez_locale", default="Prez locale"),
        )
        if prez_locale:
            overrides.setdefault("modules", {}).setdefault("prez", {})["locale"] = prez_locale
    else:
        console.print("\n[bold]4/5[/bold] — Prez settings [dim](skipped)[/dim]")

    # ── Step 5: Auto mode ───────────────────────────────────────────────
    console.print("\n[bold]5/5[/bold] — Pipeline behaviour")
    auto = confirm_choice(
        title=tr("profile.wizard.auto_mode", default="Enable auto mode (no prompts)?"),
        default=False,
    )
    if auto:
        overrides.setdefault("modules", {}).setdefault("pipeline", {})["auto_mode"] = True

    return overrides


@profile_group.command("create")
@click.argument("name")
@click.option("--description", "-d", default="", help="Profile description")
@click.option(
    "--from-current", is_flag=True, help="Capture current non-default settings as profile"
)
@click.option(
    "--wizard", "-w", is_flag=True, help="Interactive wizard to build profile step by step"
)
def profile_create(name: str, description: str, from_current: bool, wizard: bool) -> None:
    """Create a new profile.

    Examples:
        fk profile create anime -d "Anime workflow with subs"
        fk profile create movie-4k --from-current
        fk profile create my-preset --wizard
    """
    if from_current:
        store = SettingsStore()
        current = store.load()
        overrides = current
    elif wizard:
        if not description:
            description = text_input(
                title=tr("profile.wizard.description", default="Profile description (optional)"),
            )
        overrides = _run_profile_wizard(description)
    else:
        overrides = {}

    try:
        path = save_profile(name, overrides, description=description)
        print_success(f"Created profile: {name}")
        print_info(f"Edit at: {path}")
    except ValueError as e:
        print_error(str(e))


@profile_group.command("delete")
@click.argument("name")
def profile_delete(name: str) -> None:
    """Delete a profile."""
    if not confirm_choice(title=f"Delete profile '{name}'?", default=False):
        return

    if delete_profile(name):
        active = get_active_profile()
        if active == name:
            set_active_profile(None)
        print_success(f"Deleted profile: {name}")
    else:
        print_error(f"Profile not found: {name}")


@profile_group.command("show")
@click.argument("name")
def profile_show(name: str) -> None:
    """Show profile contents."""
    try:
        data = load_profile(name)
    except FileNotFoundError:
        print_error(f"Profile not found: {name}")
        return

    console.print(f"[bold]Profile:[/] {name}")
    if data.get("description"):
        console.print(f"[dim]Description:[/] {data['description']}")
    console.print()
    console.print_json(json.dumps(data.get("overrides", {}), indent=2))


select_one = _select_one  # backwards-compatible patch target for tests
