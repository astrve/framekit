from __future__ import annotations

import json
from typing import Any

# Prefer rich_click if available; fall back to click when the rich integration is not installed.
try:
    import rich_click as click  # type: ignore[import-not-found]
except Exception:
    import click  # type: ignore[import-not-found]
from rich import box
from rich.table import Table

from framekit.core.exceptions import SettingsError
from framekit.core.i18n import tr
from framekit.core.settings import SettingsStore, redact_settings
from framekit.ui.branding import print_module_banner
from framekit.ui.console import console, print_error, print_success


def _parse_settings_value(raw_value: str) -> Any:
    stripped = raw_value.strip()
    lowered = stripped.lower()
    if lowered in {"true", "yes", "y", "1", "on"}:
        return True
    if lowered in {"false", "no", "n", "0", "off"}:
        return False
    if lowered in {"null", "none"}:
        return ""

    try:
        return json.loads(stripped)
    except Exception:
        return stripped


def _format_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(redact_settings(value), indent=2, ensure_ascii=False)
    return str(redact_settings(value))


def _status(value: Any) -> str:
    if isinstance(value, bool):
        return (
            tr("common.enabled", default="Enabled")
            if value
            else tr("common.disabled", default="Disabled")
        )
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) or "-"
    return str(value or "-")


def _add_rows(table: Table, rows: list[tuple[str, str]]) -> None:
    for key, value in rows:
        table.add_row(key, value)


def _settings_tables(settings: dict[str, Any]) -> list[Table]:
    redacted = redact_settings(settings)
    general = redacted.get("general", {})
    metadata = redacted.get("metadata", {})
    modules = redacted.get("modules", {})
    nfo = modules.get("nfo", {})
    prez = modules.get("prez", {})
    torrent = modules.get("torrent", {})
    pipeline = modules.get("pipeline", {})

    overview = Table(
        title=tr("settings.overview", default="Framekit overview"),
        box=box.HEAVY,
        expand=True,
    )
    overview.add_column(tr("common.field", default="Field"), width=28, no_wrap=True)
    overview.add_column(tr("common.value", default="Value"), ratio=1)
    _add_rows(
        overview,
        [
            ("UI locale", _status(general.get("locale"))),
            ("Default folder", _status(general.get("default_folder"))),
            ("Metadata default", _status(metadata.get("enabled_by_default"))),
            ("NFO metadata", _status(nfo.get("with_metadata"))),
            ("Prez metadata", _status(prez.get("with_metadata"))),
            ("Pipeline metadata", _status(pipeline.get("with_metadata"))),
            ("NFO template", _status(nfo.get("active_template"))),
            (
                "Prez templates",
                f"HTML={_status(prez.get('html_template'))} | "
                f"BBCode={_status(prez.get('bbcode_template'))}",
            ),
            (
                "Torrent announce",
                _status(torrent.get("selected_announce") or torrent.get("announce")),
            ),
            ("Pipeline modules", _status(pipeline.get("enabled_modules"))),
        ],
    )

    metadata_table = Table(
        title=tr("settings.metadata", default="Metadata"),
        box=box.HEAVY,
        expand=True,
    )
    metadata_table.add_column(tr("common.field", default="Field"), width=28, no_wrap=True)
    metadata_table.add_column(tr("common.value", default="Value"), ratio=1)
    _add_rows(
        metadata_table,
        [
            ("Provider", _status(metadata.get("provider"))),
            ("Language", _status(metadata.get("language"))),
            ("Interactive confirmation", _status(metadata.get("interactive_confirmation"))),
            ("Cache TTL (h)", _status(metadata.get("cache_ttl_hours"))),
            ("TMDb API key", _status(metadata.get("tmdb_api_key"))),
            ("TMDb read token", _status(metadata.get("tmdb_read_access_token"))),
        ],
    )

    folders = Table(
        title=tr("settings.paths", default="Module folders"),
        box=box.HEAVY,
        expand=True,
    )
    folders.add_column(tr("common.field", default="Field"), width=28, no_wrap=True)
    folders.add_column(tr("common.value", default="Value"), ratio=1)
    for module_name in ("renamer", "cleanmkv", "nfo", "prez", "torrent", "pipeline", "encoder"):
        module_settings = modules.get(module_name, {})
        folders.add_row(
            f"{module_name}.default_folder", _status(module_settings.get("default_folder"))
        )
        folders.add_row(f"{module_name}.last_folder", _status(module_settings.get("last_folder")))

    return [overview, metadata_table, folders]


def run_settings_show() -> int:
    store = SettingsStore()
    settings = store.load()

    print_module_banner("Settings")
    for table in _settings_tables(settings):
        console.print(table)
        console.print()
    return 0


def run_settings_get(path: str) -> int:
    store = SettingsStore()
    try:
        value = store.get(path)
    except SettingsError as exc:
        print_error(
            tr(
                "settings.error.get_failed",
                default="Could not read setting: {message}",
                message=exc,
            )
        )
        return 1

    console.print(_format_value(value))
    return 0


def run_settings_set(path: str, value: str) -> int:
    store = SettingsStore()
    parsed = _parse_settings_value(value)
    try:
        store.set(path, parsed)
    except SettingsError as exc:
        print_error(
            tr(
                "settings.error.set_failed",
                default="Could not update setting: {message}",
                message=exc,
            )
        )
        return 1

    print_success(tr("settings.success.updated", default="Setting updated: {path}", path=path))
    return 0


def run_settings_reset(path: str) -> int:
    store = SettingsStore()
    try:
        store.reset(path)
    except SettingsError as exc:
        print_error(
            tr(
                "settings.error.reset_failed",
                default="Could not reset setting: {message}",
                message=exc,
            )
        )
        return 1

    print_success(tr("settings.success.reset", default="Setting reset: {path}", path=path))
    return 0


@click.group(
    "settings",
    invoke_without_command=True,
    help=tr("cli.settings.help", default="Inspect and edit current Framekit settings."),
)
@click.pass_context
def settings_command(ctx: click.Context) -> int | None:
    if ctx.invoked_subcommand is None:
        return run_settings_show()
    return None


@settings_command.command(
    "get", help=tr("cli.settings.get.help", default="Read one setting value.")
)
@click.argument("path")
def settings_get_command(path: str) -> int:
    return run_settings_get(path)


@settings_command.command(
    "set", help=tr("cli.settings.set.help", default="Update one setting value.")
)
@click.argument("path")
@click.argument("value")
def settings_set_command(path: str, value: str) -> int:
    return run_settings_set(path, value)


@settings_command.command(
    "reset", help=tr("cli.settings.reset.help", default="Reset one setting to its default value.")
)
@click.argument("path")
def settings_reset_command(path: str) -> int:
    return run_settings_reset(path)
