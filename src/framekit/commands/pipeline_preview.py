"""Pipeline preview rendering functions.

This module handles preview display and comparison tables for the pipeline command.
"""

from __future__ import annotations

from pathlib import Path

from rich import box
from rich.table import Table

from framekit.core.i18n import tr
from framekit.core.models.nfo import ReleaseNfoData
from framekit.core.release_inspection import inspect_release_completeness
from framekit.ui.console import console

# Module constants from pipeline.py
PIPELINE_MODULES = ("renamer", "cleanmkv", "nfo", "prez", "torrent", "upload", "encoder")


def _module_label(module: str) -> str:
    """Return a human-readable label for a pipeline module."""
    labels = {
        "renamer": tr("renamer.title", default="Renamer"),
        "cleanmkv": tr("cleanmkv.title", default="CleanMKV"),
        "nfo": tr("nfo.title", default="NFO"),
        "torrent": tr("torrent.title", default="Torrent"),
        "prez": tr("prez.title", default="Prez"),
        "upload": tr("upload.title", default="Upload"),
        "encoder": tr("encoder.title", default="Encoder"),
    }
    return labels.get(module, module.title())


def _pipeline_explain_text() -> str:
    """Return explanation text for the pipeline command."""
    return tr(
        "pipeline.explain.text",
        default=(
            "The pipeline command orchestrates multiple modules in sequence:\n\n"
            "1. Renamer: Standardize filenames\n"
            "2. CleanMKV: Remove unwanted tracks\n"
            "3. NFO: Generate release information\n"
            "4. Torrent: Create torrent file\n"
            "5. Prez: Generate presentation files\n"
            "6. Upload: Upload to trackers\n"
            "7. Encoder: Encode video files (opt-in)\n\n"
            "Use --preset to load a saved configuration.\n"
            "Use --preview to see what will happen before execution."
        ),
    )


def _display_or_dash(value: str | None) -> str:
    return value if value else "-"


def _metadata_label(enabled: bool) -> str:
    if enabled:
        return tr("common.enabled", default="Enabled")
    return tr("common.disabled", default="Disabled")


def _gather_renamer_preview(
    root: Path, settings: dict, remove_terms: tuple[str, ...]
) -> dict[str, list[dict[str, str | bool]]]:
    from framekit.modules.renamer.service import RenamerService

    renamer_settings = settings.get("modules", {}).get("renamer", {})
    default_lang = renamer_settings.get("default_lang", "en")
    force_lang = renamer_settings.get("force_lang", False)
    service = RenamerService()
    plan = service.build_plan(
        root,
        default_lang=default_lang,
        force_lang=force_lang,
        remove_terms=remove_terms,
    )
    return {
        "files": [
            {
                "original": item.source.name,
                "renamed": item.target.name,
                "changed": item.changed,
                "collision": item.collision,
            }
            for item in plan
        ]
    }


def _gather_cleanmkv_preview(work_folder: Path, store, settings: dict) -> dict:
    from framekit.core.tools import ToolRegistry
    from framekit.modules.cleanmkv.scanner import scan_folder

    cleanmkv_settings = settings.get("modules", {}).get("cleanmkv", {})
    preset_name = cleanmkv_settings.get("preset", "default")
    registry = ToolRegistry(store)
    scans = scan_folder(work_folder, registry)
    return {
        "preset": preset_name,
        "files": [{"filename": scan.path.name} for scan in scans],
    }


def _gather_nfo_preview(settings: dict, nfo_locale: str) -> dict:
    nfo_settings = settings.get("modules", {}).get("nfo", {})
    return {
        "template": nfo_settings.get("template", "default"),
        "locale": nfo_locale,
    }


def _gather_prez_preview(settings: dict) -> dict:
    prez_settings = settings.get("modules", {}).get("prez", {})
    return {
        "preset": prez_settings.get("preset", "default"),
        "html_template": prez_settings.get("html_template", "-") or "-",
        "bbcode_template": prez_settings.get("bbcode_template", "-") or "-",
    }


def gather_preview_data(
    root: Path,
    work_folder: Path,
    store,  # SettingsStore
    settings: dict,
    enabled_modules: tuple[str, ...],
    remove_terms: tuple[str, ...],
    nfo_locale: str,
) -> dict:
    """Gather detailed information about what the pipeline will do.

    Args:
        root: Root release folder
        work_folder: Working folder
        store: Settings store instance
        settings: Settings dictionary
        enabled_modules: Tuple of enabled module names
        remove_terms: Terms to remove during renaming
        nfo_locale: NFO locale

    Returns:
        Dictionary containing preview data for each module
    """
    preview_data = {
        "renamer": {},
        "cleanmkv": {},
        "nfo": {},
        "prez": {},
    }

    if "renamer" in enabled_modules:
        try:
            preview_data["renamer"] = _gather_renamer_preview(root, settings, remove_terms)
        except Exception:
            preview_data["renamer"]["files"] = []

    if "cleanmkv" in enabled_modules:
        try:
            preview_data["cleanmkv"] = _gather_cleanmkv_preview(work_folder, store, settings)
        except Exception:
            preview_data["cleanmkv"]["files"] = []
            preview_data["cleanmkv"]["preset"] = (
                settings.get("modules", {}).get("cleanmkv", {}).get("preset", "default")
            )

    if "nfo" in enabled_modules:
        preview_data["nfo"] = _gather_nfo_preview(settings, nfo_locale)

    if "prez" in enabled_modules:
        preview_data["prez"] = _gather_prez_preview(settings)

    return preview_data


# Maintain backward compatibility with old name
_gather_preview_data = gather_preview_data


def _overview_table(
    *,
    folder: Path,
    root: Path,
    work_folder: Path,
    output_folder: Path,
    release: ReleaseNfoData,
    enabled_modules: tuple[str, ...],
    metadata_enabled: bool,
) -> Table:
    overview = Table(
        title=tr("pipeline.preview.overview", default="Overview"),
        box=box.ROUNDED,
        expand=True,
    )
    overview.add_column(tr("common.field", default="Field"), style="cyan", width=24)
    overview.add_column(tr("common.value", default="Value"), style="white")
    overview.add_row(tr("common.folder", default="Folder"), str(folder))
    overview.add_row(tr("pipeline.preview.input_folder", default="Input folder"), str(root))
    overview.add_row(tr("pipeline.preview.work_folder", default="Work folder"), str(work_folder))
    overview.add_row(
        tr("pipeline.preview.output_folder", default="Output folder"), str(output_folder)
    )
    overview.add_row(
        tr("common.release_title", default="Release Title"), release.release_title or "-"
    )
    overview.add_row(tr("common.media_kind", default="Media Kind"), release.media_kind or "-")
    overview.add_row(
        tr("pipeline.preview.modules", default="Modules"),
        ", ".join(_module_label(m) for m in enabled_modules) or "-",
    )
    overview.add_row(
        tr("common.metadata", default="Metadata"),
        tr("common.enabled", default="Enabled")
        if metadata_enabled
        else tr("common.disabled", default="Disabled"),
    )
    return overview


def _print_renamer_preview_table(preview_data: dict) -> None:
    files = preview_data.get("renamer", {}).get("files")
    if not files:
        return
    renamer_table = Table(
        title=tr("pipeline.preview.renamer_changes", default="Renamer: Filename Changes"),
        box=box.ROUNDED,
        expand=True,
    )
    renamer_table.add_column(
        tr("pipeline.preview.original", default="Original"), style="yellow", ratio=1
    )
    renamer_table.add_column("→", style="bright_black", width=3, justify="center")
    renamer_table.add_column(
        tr("pipeline.preview.renamed", default="Renamed"), style="green", ratio=1
    )
    renamer_table.add_column(tr("common.status", default="Status"), style="cyan", width=12)
    shown_files = files[:10]
    for file_info in shown_files:
        status = (
            "collision"
            if file_info["collision"]
            else ("changed" if file_info["changed"] else "unchanged")
        )
        status_label = {
            "collision": tr("renamer.status.collision", default="Collision"),
            "changed": tr("renamer.status.changed", default="Changed"),
            "unchanged": tr("renamer.status.unchanged", default="Unchanged"),
        }.get(status, status)
        renamer_table.add_row(file_info["original"], "→", file_info["renamed"], status_label)
    if len(files) > 10:
        renamer_table.add_row(
            f"... and {len(files) - 10} more files",
            "",
            "",
            "",
            style="bright_black",
        )
    console.print(renamer_table)
    console.print()


def _print_module_config_table(
    *,
    enabled_modules: tuple[str, ...],
    preview_data: dict,
    announce: str | None,
) -> None:
    config_table = Table(
        title=tr("pipeline.preview.module_config", default="Module Configuration"),
        box=box.ROUNDED,
        expand=True,
    )
    config_table.add_column(tr("common.module", default="Module"), style="cyan", width=16)
    config_table.add_column(tr("common.setting", default="Setting"), style="white", width=20)
    config_table.add_column(tr("common.value", default="Value"), style="green", ratio=1)

    if "cleanmkv" in enabled_modules:
        config_table.add_row(
            _module_label("cleanmkv"),
            tr("cleanmkv.preset", default="Preset"),
            preview_data.get("cleanmkv", {}).get("preset", "-"),
        )
        file_count = len(preview_data.get("cleanmkv", {}).get("files", []))
        if file_count > 0:
            config_table.add_row(
                "",
                tr("pipeline.preview.files_to_process", default="Files to process"),
                str(file_count),
            )

    if "nfo" in enabled_modules:
        config_table.add_row(
            _module_label("nfo"),
            tr("nfo.template", default="Template"),
            preview_data.get("nfo", {}).get("template", "-"),
        )
        config_table.add_row(
            "",
            tr("common.locale", default="Locale"),
            preview_data.get("nfo", {}).get("locale", "-"),
        )

    if "torrent" in enabled_modules:
        config_table.add_row(
            _module_label("torrent"),
            tr("pipeline.preview.announce", default="Announce"),
            announce or "-",
        )

    if "prez" in enabled_modules:
        config_table.add_row(
            _module_label("prez"),
            tr("prez.preset", default="Preset"),
            preview_data.get("prez", {}).get("preset", "-"),
        )
        config_table.add_row(
            "",
            tr("prez.template.html", default="HTML template"),
            preview_data.get("prez", {}).get("html_template", "-"),
        )
        config_table.add_row(
            "",
            tr("prez.template.bbcode", default="BBCode template"),
            preview_data.get("prez", {}).get("bbcode_template", "-"),
        )

    console.print(config_table)
    console.print()


def _print_pipeline_preview_comparison(
    folder: Path,
    release: ReleaseNfoData,
    enabled_modules: tuple[str, ...],
    preview_data: dict,
    *,
    root: Path,
    work_folder: Path,
    output_folder: Path,
    nfo_locale: str,
    announce: str | None,
    preset: str | None,
    metadata_enabled: bool,
) -> None:
    """Print comprehensive preview with comparison table.

    Args:
        folder: Release folder
        release: Release NFO data
        enabled_modules: Tuple of enabled module names
        preview_data: Preview data dictionary from _gather_preview_data
        root: Root folder
        work_folder: Working folder
        output_folder: Output folder
        nfo_locale: NFO locale
        announce: Announce URL
        preset: Prez preset name
        metadata_enabled: Whether metadata fetching is enabled
    """
    console.print()
    console.rule(
        tr("pipeline.preview.title", default="Pipeline Preview"),
        style="bold white",
    )
    console.print()

    console.print(
        _overview_table(
            folder=folder,
            root=root,
            work_folder=work_folder,
            output_folder=output_folder,
            release=release,
            enabled_modules=enabled_modules,
            metadata_enabled=metadata_enabled,
        )
    )
    console.print()
    if "renamer" in enabled_modules:
        _print_renamer_preview_table(preview_data)
    _print_module_config_table(
        enabled_modules=enabled_modules,
        preview_data=preview_data,
        announce=announce,
    )


def _print_pipeline_preview(
    folder: Path,
    release: ReleaseNfoData,
    enabled_modules: tuple[str, ...],
    *,
    root: Path,
    work_folder: Path,
    output_folder: Path,
    nfo_locale: str,
    announce: str | None,
    preset: str | None,
    metadata_enabled: bool,
    html_template: str | None = None,
    bbcode_template: str | None = None,
) -> None:
    """Print simple pipeline preview (headless mode).

    Args:
        folder: Release folder
        release: Release NFO data
        enabled_modules: Tuple of enabled module names
        root: Root folder
        work_folder: Working folder
        output_folder: Output folder
        nfo_locale: NFO locale
        announce: Announce URL
        preset: Prez preset name
        metadata_enabled: Whether metadata fetching is enabled
        html_template: HTML template name
        bbcode_template: BBCode template name
    """
    completeness = inspect_release_completeness(release)
    metadata_label = _metadata_label(metadata_enabled)
    expected_outputs = " → ".join(name for name in PIPELINE_MODULES if name in enabled_modules)
    rows = [
        (tr("common.folder", default="Folder"), str(folder)),
        (tr("pipeline.preview.input_folder", default="Input folder"), str(root)),
        (tr("pipeline.preview.payload_folder", default="Payload folder"), str(work_folder)),
        (tr("pipeline.preview.output_folder", default="Output folder"), str(output_folder)),
        (
            tr("common.release_title", default="Release Title"),
            _display_or_dash(release.release_title),
        ),
        (tr("common.media_kind", default="Media Kind"), _display_or_dash(release.media_kind)),
        (
            tr("pipeline.preview.modules", default="Modules"),
            _display_or_dash(", ".join(enabled_modules)),
        ),
        (tr("common.metadata", default="Metadata"), metadata_label),
        (
            tr("pipeline.preview.nfo_locale", default="NFO/Prez locale"),
            _display_or_dash(nfo_locale),
        ),
        (tr("pipeline.preview.announce", default="Announce"), _display_or_dash(announce)),
        (tr("pipeline.preview.preset", default="Prez preset"), _display_or_dash(preset)),
        (tr("prez.template.html", default="HTML template"), _display_or_dash(html_template)),
        (tr("prez.template.bbcode", default="BBCode template"), _display_or_dash(bbcode_template)),
        (tr("inspect.episode_completeness", default="Episode completeness"), completeness.label),
        (tr("pipeline.preview.expected_outputs", default="Expected outputs"), expected_outputs),
    ]

    table = Table(
        title=tr("pipeline.preview", default="Pipeline preview"), box=box.HEAVY, expand=True
    )
    table.add_column(tr("common.field", default="Field"), width=24, no_wrap=True)
    table.add_column(tr("common.value", default="Value"), ratio=1)
    for label, value in rows:
        table.add_row(label, value)
    console.print(table)


def print_pipeline_report(
    folder: Path,
    results: list[tuple[str, str, str]] | list[tuple[str, str, str, float]],
    total_time: float | None = None,
) -> None:
    """Display enhanced pipeline report with timing.

    Args:
        folder: The folder being processed
        results: List of (module_name, status, details) or (module_name, status, details, elapsed) tuples
        total_time: Total pipeline execution time
    """
    from rich.panel import Panel

    table = Table(
        title=tr("pipeline.report", default="Pipeline report"), box=box.HEAVY, expand=True
    )
    table.add_column(tr("common.module", default="Module"), width=16, no_wrap=True)
    table.add_column(tr("common.status", default="Status"), width=12, no_wrap=True)
    table.add_column(tr("common.details", default="Details"), ratio=1)

    # Check if timing information is included
    has_timing = results and len(results[0]) == 4
    if has_timing:
        table.add_column(tr("common.time", default="Time"), width=10, justify="right", style="dim")

    for result in results:
        if has_timing and len(result) == 4:
            module_name, status, details, elapsed = result
            table.add_row(module_name, status, details, f"{elapsed:.2f}s")
        else:
            module_name, status, details = result[:3]
            table.add_row(module_name, status, details)

    # Add total row if total_time is provided
    if total_time is not None and has_timing:
        table.add_row("[bold]Total[/bold]", "", "", f"[bold]{total_time:.2f}s[/bold]")

    console.print(table)
    console.print(
        Panel(
            str(folder),
            title=tr("common.folder", default="Folder"),
            border_style="white",
            expand=True,
        )
    )


# Maintain backward compatibility with old name
_print_pipeline_report = print_pipeline_report
