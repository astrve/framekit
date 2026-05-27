from __future__ import annotations

import json

from rich import box
from rich.table import Table

from framekit.core.cli_helpers import join_path_parts
from framekit.core.i18n import tr
from framekit.core.paths import PathResolver
from framekit.core.release_inspection import inspect_release_completeness
from framekit.core.settings import SettingsStore
from framekit.modules.nfo.builder import build_release_nfo
from framekit.modules.nfo.formatting import format_bytes_human, format_duration_ms_human
from framekit.modules.nfo.scanner import scan_nfo_folder
from framekit.ui.branding import print_module_banner

# Prefer rich_click if available; fall back to click when the rich integration is not installed.
from framekit.ui.click_helper import click
from framekit.ui.console import console, print_error


def _resolve_inspect_folder(path: str | None):
    store = SettingsStore()
    settings = store.load()
    resolver = PathResolver(settings)
    return resolver.resolve_start_folder("nfo", path or None)


def _inspect_summary_table(folder, release, completeness) -> Table:
    table = Table(
        title=tr("inspect.summary", default="Release inspection"), box=box.HEAVY, expand=True
    )
    table.add_column(tr("common.field", default="Field"), width=26, no_wrap=True)
    table.add_column(tr("common.value", default="Value"), ratio=1)
    for label, value in _inspect_rows(folder, release, completeness):
        table.add_row(label, value)
    return table


def _inspect_rows(folder, release, completeness) -> list[tuple[str, str]]:
    missing_codes = _missing_episode_codes(completeness.missing_codes)
    return [
        (tr("common.folder", default="Folder"), str(folder)),
        (tr("common.media_kind", default="Media Kind"), _dash(release.media_kind)),
        (tr("common.release_title", default="Release Title"), _dash(release.release_title)),
        (tr("common.series", default="Series"), _dash(release.series_title)),
        (tr("common.year", default="Year"), _dash(release.year)),
        (tr("common.episodes", default="Episodes"), str(len(release.episodes))),
        (tr("inspect.episode_completeness", default="Episode completeness"), completeness.label),
        (tr("inspect.missing_episodes", default="Missing episodes"), missing_codes),
        (tr("common.file_size", default="File Size"), format_bytes_human(release.total_size_bytes)),
        (
            tr("common.total_duration", default="Total Duration"),
            format_duration_ms_human(release.total_duration_ms),
        ),
        (tr("common.source", default="Source"), _dash(release.source)),
        (tr("common.resolution", default="Resolution"), _dash(release.resolution)),
        (tr("common.video", default="Video"), _dash(release.video_tag)),
        (tr("common.audio", default="Audio"), _dash(release.audio_tag)),
        (tr("common.language", default="Language"), _dash(release.language_tag)),
    ]


def _dash(value: str | None) -> str:
    return value if value else "-"


def _missing_episode_codes(codes: list[str]) -> str:
    if not codes:
        return "-"
    return ", ".join(codes)


def run_inspect_command(path: str | None, json_output: bool = False) -> int:
    """Run inspect command."""
    if not json_output:
        print_module_banner("Inspect")
    folder = _resolve_inspect_folder(path)

    if not folder.exists() or not folder.is_dir():
        if json_output:
            print(json.dumps({"error": f"Folder not found: {folder}"}, ensure_ascii=False))
        else:
            print_error(
                tr(
                    "cleanmkv.error.folder_not_found",
                    default="Folder not found: {folder}",
                    folder=folder,
                )
            )
        raise SystemExit(1)

    episodes = scan_nfo_folder(folder)
    if not episodes:
        if json_output:
            print(json.dumps({"error": f"No MKV files found in folder: {folder}"}, ensure_ascii=False))
        else:
            print_error(
                tr("nfo.error.no_mkv", default="No MKV files found in folder: {folder}", folder=folder)
            )
        raise SystemExit(1)

    release = build_release_nfo(folder, episodes)
    completeness = inspect_release_completeness(release)

    if json_output:
        payload = {
            "media_kind": release.media_kind,
            "release_title": release.release_title,
            "series_title": release.series_title,
            "year": release.year,
            "episode_count": len(release.episodes),
            "completeness_label": completeness.label,
            "missing_codes": completeness.missing_codes,
            "size_bytes": release.total_size_bytes,
            "duration_ms": release.total_duration_ms,
            "source": release.source,
            "resolution": release.resolution,
            "video_tag": release.video_tag,
            "audio_tag": release.audio_tag,
            "language_tag": release.language_tag,
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    console.print(_inspect_summary_table(folder, release, completeness))
    return 0


@click.command(
    "inspect",
    help=tr(
        "cli.inspect.help", default="Inspect a release folder and summarize detected structure."
    ),
)
@click.argument("path_parts", nargs=-1)
@click.option("--json", "json_output", is_flag=True, default=False, help="Output structured JSON to stdout instead of a table.")
def inspect_command(path_parts: tuple[str, ...], json_output: bool) -> int:
    """Handle inspect command."""
    return run_inspect_command(join_path_parts(path_parts) or None, json_output=json_output)
