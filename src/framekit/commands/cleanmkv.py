from __future__ import annotations

# Prefer rich_click if available; fall back to click when the rich integration is not installed.
try:
    import rich_click as click  # type: ignore[import-not-found]
except Exception:
    import click  # type: ignore[import-not-found]
from rich import box
from rich.table import Table

from framekit.core.i18n import tr
from framekit.core.paths import PathResolver, get_presets_dir
from framekit.core.settings import SettingsStore
from framekit.core.tools import ToolRegistry
from framekit.modules.cleanmkv.planner import get_builtin_preset
from framekit.modules.cleanmkv.presets import (
    list_available_presets,
    load_named_external_preset,
    load_preset_file,
    save_named_preset,
    validate_preset,
)
from framekit.modules.cleanmkv.scanner import scan_folder
from framekit.modules.cleanmkv.service import CleanMkvService
from framekit.modules.cleanmkv.wizard import run_cleanmkv_track_selector, run_cleanmkv_wizard
from framekit.ui.branding import print_module_banner
from framekit.ui.console import (
    console,
    print_error,
    print_exception_error,
    print_info,
    print_success,
    print_warning,
)
from framekit.ui.progress import framekit_progress
from framekit.ui.selector import confirm_choice, text_input


def _join_path_parts(parts: tuple[str, ...]) -> str:
    return " ".join(part for part in parts if part).strip()


def _status_style(status: str) -> str:
    mapping = {
        "planned": "white",
        "copy-only": "yellow",
        "copied": "green",
        "remuxed": "green",
        "error": "red",
        "skipped": "yellow",
    }
    return mapping.get(status, "white")


def _status_label(status: str) -> str:
    key = status.replace("-", "_")
    return tr(f"operation.status.{key}", default=status)


def _print_presets_list() -> None:
    data = list_available_presets()

    table = Table(
        title=tr("cleanmkv.presets.available_title", default="Available CleanMKV Presets"),
        expand=True,
        box=box.HEAVY,
        border_style="white",
    )
    table.add_column(tr("common.type", default="Type"), width=12, no_wrap=True)
    table.add_column("Presets", ratio=1)

    table.add_row(
        tr("cleanmkv.preset_builtin", default="builtin"), ", ".join(data["builtin"]) or "-"
    )
    table.add_row(
        tr("cleanmkv.preset_external", default="external"), ", ".join(data["external"]) or "-"
    )
    console.print(table)


def _unique_labels(report, key: str, *, source: str = "before") -> str:
    values: list[str] = []
    seen: set[str] = set()
    for detail in report.details:
        data = detail.before if source == "before" else detail.after
        raw = data.get(key, [])
        items = raw if isinstance(raw, list) else [raw]
        for item in items:
            value = str(item or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            values.append(value)
    return ", ".join(values) or "-"


def _first_output_example(report) -> str:
    for detail in report.details:
        source = str(detail.before.get("source", "") or "")
        target = str(detail.after.get("target", "") or "")
        if source and target:
            return f"{source} → {target}"
    return "-"


def _print_cleanmkv_preview(report, *, details: bool = False, applied: bool = False) -> None:
    summary = Table(
        title=tr("cleanmkv.preview_summary", default="CleanMKV Preview Summary"),
        expand=True,
        box=box.HEAVY,
        border_style="white",
    )
    summary.add_column(tr("common.field", default="Field"), width=28, no_wrap=True)
    summary.add_column(tr("common.value", default="Value"), ratio=1)

    successes = sum(1 for detail in report.details if detail.status not in {"error", "skipped"})
    errors = len(report.errors) + sum(1 for detail in report.details if detail.status == "error")
    planned_changes = sum(
        1 for detail in report.details if detail.status in {"planned", "copy-only"}
    )
    summary.add_row(tr("common.files", default="Files"), str(report.scanned))
    summary.add_row(tr("common.processed", default="Processed"), str(report.processed))
    summary.add_row(tr("common.success", default="Success"), str(successes))
    summary.add_row(tr("common.errors", default="Errors"), str(errors))
    summary.add_row(
        tr("common.modified", default="Modified")
        if applied
        else tr("common.planned_changes", default="Planned changes"),
        str(report.modified if applied else planned_changes),
    )
    summary.add_row(tr("common.skipped", default="Skipped"), str(report.skipped))
    summary.add_row(
        tr("cleanmkv.audio_kept", default="Audio tracks kept"),
        _unique_labels(report, "audio_labels"),
    )
    summary.add_row(
        tr("cleanmkv.subtitles_kept", default="Subtitle tracks kept"),
        _unique_labels(report, "subtitle_labels"),
    )
    summary.add_row(
        tr("cleanmkv.default_audio", default="Default Audio"),
        _unique_labels(report, "default_audio_label", source="after"),
    )
    summary.add_row(
        tr("cleanmkv.default_subtitle", default="Default Subtitle"),
        _unique_labels(report, "default_subtitle_label", source="after"),
    )
    summary.add_row(tr("common.example", default="Example"), _first_output_example(report))
    console.print(summary)

    if not details:
        return

    console.print()
    for index, detail in enumerate(report.details, start=1):
        status_color = _status_style(detail.status)
        table = Table(
            title=tr("common.item_number", default="Item {index}", index=index),
            expand=True,
            box=box.HEAVY,
            border_style="white",
        )
        table.add_column(tr("common.field", default="Field"), width=24, no_wrap=True)
        table.add_column(tr("common.value", default="Value"), ratio=1, overflow="fold")
        table.add_row(tr("common.source", default="Source"), str(detail.before.get("source", "-")))
        table.add_row(tr("common.target", default="Target"), str(detail.after.get("target", "-")))
        audio = detail.before.get("audio_labels", []) or []
        subs = detail.before.get("subtitle_labels", []) or []
        table.add_row(
            tr("common.audio", default="Audio"), ", ".join(str(item) for item in audio) or "-"
        )
        table.add_row(
            tr("common.subtitles", default="Subtitles"),
            ", ".join(str(item) for item in subs) or "-",
        )
        table.add_row(
            tr("cleanmkv.default_audio", default="Default Audio"),
            str(detail.after.get("default_audio_label") or "-"),
        )
        table.add_row(
            tr("cleanmkv.default_subtitle", default="Default Subtitle"),
            str(detail.after.get("default_subtitle_label") or "-"),
        )
        table.add_row(
            tr("common.status", default="Status"),
            f"[{status_color}]{_status_label(detail.status)}[/{status_color}]",
        )
        table.add_row(tr("common.message", default="Message"), detail.message or "-")
        console.print(table)


def _save_wizard_preset_if_needed(preset, explicit_name: str | None) -> None:
    validated = validate_preset(preset)

    if explicit_name:
        target = get_presets_dir() / f"{explicit_name}.json"
        if target.exists():
            overwrite = confirm_choice(
                title=tr(
                    "cleanmkv.confirm.overwrite_preset",
                    default="Preset '{name}' already exists. Overwrite?",
                    name=explicit_name,
                ),
                default=False,
                yes_label=tr("cleanmkv.choice.overwrite", default="Overwrite"),
                no_label=tr("common.cancel", default="Cancel"),
            )
            if not overwrite:
                print_warning(
                    tr("cleanmkv.warning.preset_save_cancelled", default="Preset save cancelled.")
                )
                return

        saved_path = save_named_preset(validated, explicit_name)
        print_success(
            tr("cleanmkv.success.preset_saved", default="Preset saved: {path}", path=saved_path)
        )
        return

    should_save = confirm_choice(
        title=tr("cleanmkv.confirm.save_preset", default="Save this preset?"),
        default=True,
        yes_label=tr("common.yes", default="Yes"),
        no_label=tr("common.no", default="No"),
    )

    if not should_save:
        return

    while True:
        preset_name = text_input(
            title=tr("cleanmkv.input.preset_name", default="Preset Name"),
            mandatory=True,
        )

        target = get_presets_dir() / f"{preset_name}.json"
        if target.exists():
            overwrite = confirm_choice(
                title=tr(
                    "cleanmkv.confirm.overwrite_preset",
                    default="Preset '{name}' already exists. Overwrite?",
                    name=preset_name,
                ),
                default=False,
                yes_label=tr("cleanmkv.choice.overwrite", default="Overwrite"),
                no_label=tr("cleanmkv.choice.choose_another_name", default="Choose another name"),
            )
            if not overwrite:
                continue

        saved_path = save_named_preset(validated, preset_name)
        print_success(
            tr("cleanmkv.success.preset_saved", default="Preset saved: {path}", path=saved_path)
        )
        return


def _resolve_preset(
    *,
    wizard: bool,
    save_preset: str | None,
    preset_file: str | None,
    external_preset: str | None,
    preset_name: str | None,
    settings: dict,
):
    if wizard:
        preset = run_cleanmkv_wizard()
        validated = validate_preset(preset)

        _save_wizard_preset_if_needed(validated, save_preset)
        return validated

    if preset_file:
        return load_preset_file(preset_file)

    if external_preset:
        return load_named_external_preset(external_preset)

    final_name = preset_name or settings["modules"]["cleanmkv"]["default_preset"]
    return get_builtin_preset(final_name)


def _run_cleanmkv_service(
    service,
    folder,
    *,
    preset,
    output_dir_name,
    apply_changes,
    registry,
    copy_unchanged_files,
    scans,
    progress_callback=None,
):
    kwargs = {
        "preset": preset,
        "output_dir_name": output_dir_name,
        "apply_changes": apply_changes,
        "registry": registry,
        "copy_unchanged_files": copy_unchanged_files,
        "scans": scans,
    }
    if progress_callback is not None:
        kwargs["progress_callback"] = progress_callback
    try:
        return service.run(folder, **kwargs)
    except TypeError as exc:
        if "progress_callback" not in str(exc):
            raise
        kwargs.pop("progress_callback", None)
        return service.run(folder, **kwargs)


def run_cleanmkv_command(
    *,
    path: str | None,
    apply_changes: bool,
    dry_run: bool,
    preset_name: str | None,
    preset_file: str | None,
    external_preset: str | None,
    wizard: bool,
    save_preset: str | None,
    list_presets: bool,
    show_details: bool = False,
) -> int:
    if list_presets:
        _print_presets_list()
        return 0

    if apply_changes and dry_run:
        print_error(
            tr(
                "common.error.apply_and_dry_run",
                default="--apply and --dry-run cannot be used together.",
            )
        )
        return 1

    store = SettingsStore()
    settings = store.load()
    resolver = PathResolver(settings)
    registry = ToolRegistry(store)

    print_module_banner("CleanMKV")

    folder = resolver.resolve_start_folder("cleanmkv", path or None)
    if not folder.exists() or not folder.is_dir():
        print_error(
            tr(
                "cleanmkv.error.folder_not_found",
                default="Folder not found: {folder}",
                folder=folder,
            )
        )
        return 1

    output_dir_name = settings["modules"]["cleanmkv"]["output_dir_name"]
    copy_unchanged_files = bool(settings["modules"]["cleanmkv"].get("copy_unchanged_files", True))
    explicit_preset_requested = bool(preset_name or preset_file or external_preset)
    interactive_confirmation = not apply_changes and not dry_run
    use_track_selector = interactive_confirmation and not explicit_preset_requested and not wizard
    use_wizard = wizard
    scans = None

    try:
        if use_track_selector:
            scans = scan_folder(folder, registry)
            if not scans:
                print_error(
                    tr(
                        "nfo.error.no_mkv",
                        default="No MKV files found in folder: {folder}",
                        folder=folder,
                    )
                )
                return 1

            preset = run_cleanmkv_track_selector(scans)
        else:
            preset = _resolve_preset(
                wizard=use_wizard,
                save_preset=save_preset,
                preset_file=preset_file,
                external_preset=external_preset,
                preset_name=preset_name,
                settings=settings,
            )
    except KeyboardInterrupt:
        print_warning(
            tr("cleanmkv.warning.selection_cancelled", default="Interactive selection cancelled.")
        )
        return 1
    except Exception as exc:
        print_exception_error(exc)
        return 1

    service = CleanMkvService()
    report, plans = _run_cleanmkv_service(
        service,
        folder,
        preset=preset,
        output_dir_name=output_dir_name,
        apply_changes=False,
        registry=registry,
        copy_unchanged_files=copy_unchanged_files,
        scans=scans,
    )

    if apply_changes:
        total_bytes = sum(plan.source.stat().st_size for plan in plans if plan.source.exists())
        with framekit_progress(
            tr("cleanmkv.progress.processing", default="Processing MKV files"),
            total=total_bytes or None,
            unit="bytes",
            total_files=len(plans) if len(plans) > 1 else None,
        ) as advance:
            report, _plans = _run_cleanmkv_service(
                service,
                folder,
                preset=preset,
                output_dir_name=output_dir_name,
                apply_changes=True,
                registry=registry,
                copy_unchanged_files=copy_unchanged_files,
                scans=scans,
                progress_callback=advance,
            )

    _print_cleanmkv_preview(report, details=show_details, applied=apply_changes)

    print_info(tr("common.folder", default="Folder") + f": {folder}")
    print_info(tr("common.preset", default="Preset") + f": {preset.name}")
    print_info(tr("nfo.info.scanned", default="Scanned: {count}", count=report.scanned))
    print_info(tr("nfo.info.processed", default="Processed: {count}", count=report.processed))
    if apply_changes:
        print_info(tr("common.modified", default="Modified") + f": {report.modified}")
    else:
        print_info(tr("common.planned_changes", default="Planned changes") + f": {report.modified}")
    print_info(tr("common.skipped", default="Skipped") + f": {report.skipped}")

    if use_wizard and not save_preset:
        print_warning(
            tr(
                "cleanmkv.info.wizard_not_persisted",
                default="Wizard preset was used for this run only. Use --save-preset NAME to persist it.",
            )
        )

    if report.errors:
        for error in report.errors:
            print_error(error.message)
        return 1

    if interactive_confirmation:
        should_apply = confirm_choice(
            title=tr("cleanmkv.confirm.apply_changes", default="Apply this CleanMKV plan now?"),
            default=True,
            yes_label=tr("common.apply", default="Apply"),
            no_label=tr("common.cancel", default="Cancel"),
        )
        if should_apply is None:
            raise KeyboardInterrupt
        if not should_apply:
            print_success(
                tr(
                    "cleanmkv.success.preview_no_apply",
                    default="CleanMKV preview completed without applying changes.",
                )
            )
            settings["modules"]["cleanmkv"]["last_folder"] = str(folder)
            store.save(settings)
            return 0

        total_bytes = sum(plan.source.stat().st_size for plan in plans if plan.source.exists())
        with framekit_progress(
            tr("cleanmkv.progress.processing", default="Processing MKV files"),
            total=total_bytes or None,
            unit="bytes",
            total_files=len(plans) if len(plans) > 1 else None,
        ) as advance:
            report, _plans = _run_cleanmkv_service(
                service,
                folder,
                preset=preset,
                output_dir_name=output_dir_name,
                apply_changes=True,
                registry=registry,
                copy_unchanged_files=copy_unchanged_files,
                scans=scans,
                progress_callback=advance,
            )
        _print_cleanmkv_preview(report, details=show_details, applied=True)

        if report.errors:
            for error in report.errors:
                print_error(error.message)
            return 1

        print_success(tr("cleanmkv.success.completed", default="CleanMKV operation completed."))
    elif apply_changes:
        print_success(tr("cleanmkv.success.completed", default="CleanMKV operation completed."))
    else:
        print_success(
            tr("cleanmkv.success.dry_run_completed", default="CleanMKV dry-run completed.")
        )

    settings["modules"]["cleanmkv"]["last_folder"] = str(folder)
    store.save(settings)

    return 0


@click.command("cleanmkv", help=tr("cli.cleanmkv.help", default="Clean and normalize MKV files."))
@click.argument("path_parts", nargs=-1)
@click.option(
    "-a",
    "--apply",
    "apply_changes",
    is_flag=True,
    help=tr(
        "cli.cleanmkv.option.apply",
        default="Apply changes immediately without interactive confirmation.",
    ),
)
@click.option(
    "-p",
    "--preset",
    "preset_name",
    help=tr("cli.cleanmkv.option.preset", default="Builtin preset name."),
)
@click.option(
    "-pf",
    "--preset-file",
    help=tr("cli.cleanmkv.option.preset_file", default="Load a preset from a JSON file."),
)
@click.option(
    "-ep",
    "--external-preset",
    help=tr("cli.cleanmkv.option.external_preset", default="Load a saved external preset by name."),
)
@click.option(
    "-w",
    "--wizard",
    is_flag=True,
    help=tr("cli.cleanmkv.option.wizard", default="Open the interactive preset wizard."),
)
@click.option(
    "-sp",
    "--save-preset",
    help=tr("cli.cleanmkv.option.save_preset", default="Save the wizard preset under this name."),
)
@click.option(
    "-L",
    "-lp",
    "--list-presets",
    is_flag=True,
    help=tr("cli.cleanmkv.option.list_presets", default="List available presets."),
)
@click.option(
    "--dry-run",
    is_flag=True,
    help=tr(
        "cli.cleanmkv.option.dry_run",
        default="Preview only. Do not ask to apply changes.",
    ),
)
@click.option(
    "--details",
    "show_details",
    is_flag=True,
    help=tr("cli.cleanmkv.option.details", default="Show per-file CleanMKV details."),
)
def cleanmkv_command(
    path_parts: tuple[str, ...],
    apply_changes: bool,
    dry_run: bool,
    preset_name: str | None,
    preset_file: str | None,
    external_preset: str | None,
    wizard: bool,
    save_preset: str | None,
    list_presets: bool,
    show_details: bool,
) -> int:
    return run_cleanmkv_command(
        path=_join_path_parts(path_parts) or None,
        apply_changes=apply_changes,
        dry_run=dry_run,
        preset_name=preset_name,
        preset_file=preset_file,
        external_preset=external_preset,
        wizard=wizard,
        save_preset=save_preset,
        list_presets=list_presets,
        show_details=show_details,
    )
