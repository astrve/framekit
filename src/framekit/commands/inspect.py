from __future__ import annotations

# Prefer rich_click if available; fall back to click when the rich integration is not installed.
try:
    import rich_click as click  # type: ignore[import-not-found]
except Exception:
    import click  # type: ignore[import-not-found]
from rich import box
from rich.table import Table

from framekit.core.i18n import tr
from framekit.core.paths import PathResolver
from framekit.core.release_inspection import inspect_release_completeness
from framekit.core.settings import SettingsStore
from framekit.modules.nfo.builder import build_release_nfo
from framekit.modules.nfo.formatting import format_bytes_human, format_duration_ms_human
from framekit.modules.nfo.scanner import scan_nfo_folder
from framekit.ui.branding import print_module_banner
from framekit.ui.console import console, print_error


def _join_path_parts(parts: tuple[str, ...]) -> str:
    return " ".join(part for part in parts if part).strip()


def run_inspect_command(path: str | None) -> int:
    store = SettingsStore()
    settings = store.load()
    resolver = PathResolver(settings)
    folder = resolver.resolve_start_folder("nfo", path or None)

    print_module_banner("Inspect")

    if not folder.exists() or not folder.is_dir():
        print_error(
            tr(
                "cleanmkv.error.folder_not_found",
                default="Folder not found: {folder}",
                folder=folder,
            )
        )
        return 1

    episodes = scan_nfo_folder(folder)
    if not episodes:
        print_error(
            tr("nfo.error.no_mkv", default="No MKV files found in folder: {folder}", folder=folder)
        )
        return 1

    release = build_release_nfo(folder, episodes)
    completeness = inspect_release_completeness(release)

    table = Table(
        title=tr("inspect.summary", default="Release inspection"), box=box.HEAVY, expand=True
    )
    table.add_column(tr("common.field", default="Field"), width=26, no_wrap=True)
    table.add_column(tr("common.value", default="Value"), ratio=1)
    table.add_row(tr("common.folder", default="Folder"), str(folder))
    table.add_row(tr("common.media_kind", default="Media Kind"), release.media_kind or "-")
    table.add_row(tr("common.release_title", default="Release Title"), release.release_title or "-")
    table.add_row(tr("common.series", default="Series"), release.series_title or "-")
    table.add_row(tr("common.year", default="Year"), release.year or "-")
    table.add_row(tr("common.episodes", default="Episodes"), str(len(release.episodes)))
    table.add_row(
        tr("inspect.episode_completeness", default="Episode completeness"), completeness.label
    )
    table.add_row(
        tr("inspect.missing_episodes", default="Missing episodes"),
        ", ".join(completeness.missing_codes) if completeness.missing_codes else "-",
    )
    table.add_row(
        tr("common.file_size", default="File Size"), format_bytes_human(release.total_size_bytes)
    )
    table.add_row(
        tr("common.total_duration", default="Total Duration"),
        format_duration_ms_human(release.total_duration_ms),
    )
    table.add_row(tr("common.source", default="Source"), release.source or "-")
    table.add_row(tr("common.resolution", default="Resolution"), release.resolution or "-")
    table.add_row(tr("common.video", default="Video"), release.video_tag or "-")
    table.add_row(tr("common.audio", default="Audio"), release.audio_tag or "-")
    table.add_row(tr("common.language", default="Language"), release.language_tag or "-")
    console.print(table)
    return 0


@click.command(
    "inspect",
    help=tr(
        "cli.inspect.help", default="Inspect a release folder and summarize detected structure."
    ),
)
@click.argument("path_parts", nargs=-1)
def inspect_command(path_parts: tuple[str, ...]) -> int:
    return run_inspect_command(_join_path_parts(path_parts) or None)
