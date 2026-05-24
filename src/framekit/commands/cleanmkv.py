from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger
from rich import box
from rich.table import Table

from framekit.core.cli_helpers import join_path_parts
from framekit.core.i18n import tr
from framekit.core.paths import PathResolver, get_presets_dir
from framekit.core.settings import SettingsStore
from framekit.core.tools import ToolRegistry
from framekit.core.verbose import configure_verbosity, is_verbose
from framekit.modules.cleanmkv.planner import get_builtin_preset
from framekit.modules.cleanmkv.presets import (
    list_available_presets,
    load_named_external_preset,
    load_preset_file,
    save_named_preset,
    validate_preset,
)
from framekit.modules.cleanmkv.scanner import scan_folder, scan_mkv_file
from framekit.modules.cleanmkv.service import CleanMkvService
from framekit.modules.cleanmkv.wizard import run_cleanmkv_track_selector, run_cleanmkv_wizard
from framekit.ui.branding import print_module_banner
from framekit.ui.click_helper import click
from framekit.ui.console import (
    console,
    print_error,
    print_exception_error,
    print_info,
    print_success,
    print_warning,
)
from framekit.ui.progress import framekit_progress
from framekit.ui.unified_selector import confirm_choice, text_input


class CleanMkvOperationError(RuntimeError):
    """Raised when CleanMKV fails to apply changes (errors already printed)."""


@dataclass(slots=True)
class _CleanMkvContext:
    settings: dict
    folder: Path
    work_folder: Path
    registry: ToolRegistry
    output_dir_name: str
    copy_unchanged_files: bool
    interactive_confirmation: bool
    use_wizard: bool
    preset: Any
    scans: list | None


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


def _build_cleanmkv_summary_table(report, *, applied: bool) -> Table:
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
    modified_or_planned = report.modified if applied else planned_changes
    modified_label = (
        tr("common.modified", default="Modified")
        if applied
        else tr("common.planned_changes", default="Planned changes")
    )

    summary.add_row(tr("common.files", default="Files"), str(report.scanned))
    summary.add_row(tr("common.processed", default="Processed"), str(report.processed))
    summary.add_row(tr("common.success", default="Success"), str(successes))
    summary.add_row(tr("common.errors", default="Errors"), str(errors))
    summary.add_row(modified_label, str(modified_or_planned))
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
    return summary


def _build_cleanmkv_detail_table(detail, *, index: int) -> Table:
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
    return table


def _print_cleanmkv_preview(report, *, details: bool = False, applied: bool = False) -> None:
    console.print(_build_cleanmkv_summary_table(report, applied=applied))

    if not details:
        return

    console.print()
    for index, detail in enumerate(report.details, start=1):
        console.print(_build_cleanmkv_detail_table(detail, index=index))


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


def _validate_and_resolve_path(
    path: str | None,
    resolver: PathResolver,
) -> tuple[int | None, Path | None, bool]:
    """Validate and resolve the input path.

    Args:
        path: Input path (file or folder)
        resolver: Path resolver instance

    Returns:
        Tuple of (error_code, resolved_path, is_single_file)
        error_code is None if successful
    """
    is_single_file = False
    folder = resolver.resolve_start_folder("cleanmkv", path or None)

    if not folder.exists():
        print_error(
            tr(
                "cleanmkv.error.folder_not_found",
                default="Folder not found: {folder}",
                folder=folder,
            )
        )
        return 1, None, False

    if folder.is_file():
        if folder.suffix.lower() != ".mkv":
            print_error(
                tr(
                    "cleanmkv.error.invalid_file_type",
                    default="File is not an MKV: {file}",
                    file=folder,
                )
            )
            return 1, None, False
        is_single_file = True

    if not folder.is_dir() and not is_single_file:
        print_error(f"Folder not found: {folder}")
        return 1, None, False

    return None, folder, is_single_file


def _resolve_cleanmkv_preset(
    use_track_selector: bool,
    use_wizard: bool,
    is_single_file: bool,
    folder: Path,
    registry: ToolRegistry,
    save_preset: str | None,
    preset_file: str | None,
    external_preset: str | None,
    preset_name: str | None,
    settings: dict,
) -> tuple[int | None, Any, list | None]:
    """Resolve the CleanMKV preset to use.

    Args:
        use_track_selector: Whether to use interactive track selector
        use_wizard: Whether to use wizard mode
        is_single_file: Whether processing a single file
        folder: Path to file or folder
        registry: Tool registry instance
        save_preset: Name to save preset as
        preset_file: Path to preset file
        external_preset: External preset name
        preset_name: Preset name
        settings: Settings dictionary

    Returns:
        Tuple of (error_code, preset, scans)
        error_code is None if successful
    """
    scans = None

    try:
        if use_track_selector:
            if is_single_file:
                scans = [scan_mkv_file(folder, registry)]
            else:
                scans = scan_folder(folder, registry)
            if not scans:
                print_error(
                    tr(
                        "nfo.error.no_mkv",
                        default="No MKV files found in folder: {folder}",
                        folder=folder,
                    )
                )
                return 1, None, None

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
        return 1, None, None
    except RuntimeError as exc:
        print_error(str(exc) or "CleanMKV scan failed.")
        return 1, None, None
    except Exception as exc:
        print_error(
            tr(
                "cleanmkv.error.scan_or_preset_failed",
                default="CleanMKV setup failed: {error}",
                error=str(exc),
            )
        )
        return 1, None, None

    return None, preset, scans


def _apply_cleanmkv_changes(
    service: CleanMkvService,
    work_folder: Path,
    preset: Any,
    output_dir_name: str,
    registry: ToolRegistry,
    copy_unchanged_files: bool,
    scans: list | None,
    plans: list,
) -> tuple[Any, list]:
    """Apply CleanMKV changes with progress tracking.

    Args:
        service: CleanMKV service instance
        work_folder: Working folder path
        preset: CleanMKV preset
        output_dir_name: Output directory name
        registry: Tool registry instance
        copy_unchanged_files: Whether to copy unchanged files
        scans: Pre-scanned MKV files (optional)
        plans: Execution plans from preview

    Returns:
        Tuple of (report, plans)
    """
    total_files_count = len(plans)
    with framekit_progress(
        tr("cleanmkv.progress.processing", default="Processing MKV files"),
        total=total_files_count or None,
        unit="count",
        show_bar=False,
        show_eta=False,
    ) as _raw_advance:

        def advance(amount: int = 1, *, files: int = 0) -> None:
            _raw_advance(1)

        report, plans = _run_cleanmkv_service(
            service,
            work_folder,
            preset=preset,
            output_dir_name=output_dir_name,
            apply_changes=True,
            registry=registry,
            copy_unchanged_files=copy_unchanged_files,
            scans=scans,
            progress_callback=advance,
        )
    return report, plans


def _print_cleanmkv_summary(
    report: Any,
    folder: Path,
    preset: Any,
    apply_changes: bool,
    use_wizard: bool,
    save_preset: str | None,
) -> None:
    """Print CleanMKV operation summary.

    Args:
        report: Operation report
        folder: Processed folder path
        preset: Used preset
        apply_changes: Whether changes were applied
        use_wizard: Whether wizard was used
        save_preset: Preset save name (if any)
    """
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


def _run_cleanmkv_preflight(check_tools: bool) -> int | None:
    if not check_tools:
        return None
    registry = ToolRegistry()
    status = registry.get_status("mkvmerge")
    if not status.available:
        print_error(
            tr(
                "cleanmkv.error.tool_check_failed",
                default="Tool check failed: {error}",
                error=status.error or "mkvmerge not available",
            )
        )
        return 1
    print_success(
        tr(
            "cleanmkv.success.tool_check",
            default="Tool check passed: mkvmerge {version}",
            version=status.version or "available",
        )
    )
    return None


def _validate_cleanmkv_start(
    *,
    list_presets: bool,
    check_tools: bool,
    apply_changes: bool,
    dry_run: bool,
) -> int | None:
    if list_presets:
        _print_presets_list()
        return 0

    preflight_code = _run_cleanmkv_preflight(check_tools)
    if preflight_code is not None:
        return preflight_code

    if apply_changes and dry_run:
        print_error(
            tr(
                "common.error.apply_and_dry_run",
                default="--apply and --dry-run cannot be used together.",
            )
        )
        return 1
    return None


def _resolve_cleanmkv_execution_flags(
    *,
    apply_changes: bool,
    dry_run: bool,
    auto_mode: bool,
    preset_name: str | None,
    preset_file: str | None,
    external_preset: str | None,
    wizard: bool,
) -> tuple[bool, bool, bool]:
    explicit_preset_requested = bool(preset_name or preset_file or external_preset)
    interactive_confirmation = not apply_changes and not dry_run and not auto_mode
    use_track_selector = interactive_confirmation and not explicit_preset_requested and not wizard
    use_wizard = wizard and not auto_mode
    return interactive_confirmation, use_track_selector, use_wizard


def _print_cleanmkv_report_errors(report: Any) -> None:
    if not report.errors:
        return
    msgs = " | ".join(e.message for e in report.errors)
    for error in report.errors:
        print_error(error.message)
    raise CleanMkvOperationError(msgs)


def _print_cleanmkv_diff(
    show_diff: bool, scans: list | None, plans: list, registry: ToolRegistry
) -> None:
    if not show_diff or not scans:
        return
    from framekit.modules.cleanmkv.diff import print_diff_for_plans

    print_diff_for_plans(scans, plans, registry)


def _run_cleanmkv_preview(
    *,
    service: CleanMkvService,
    work_folder: Path,
    preset: Any,
    output_dir_name: str,
    registry: ToolRegistry,
    copy_unchanged_files: bool,
    scans: list | None,
):
    return _run_cleanmkv_service(
        service,
        work_folder,
        preset=preset,
        output_dir_name=output_dir_name,
        apply_changes=False,
        registry=registry,
        copy_unchanged_files=copy_unchanged_files,
        scans=scans,
    )


def _apply_cleanmkv_and_report(
    *,
    service: CleanMkvService,
    work_folder: Path,
    preset: Any,
    output_dir_name: str,
    registry: ToolRegistry,
    copy_unchanged_files: bool,
    scans: list | None,
    plans: list,
    show_diff: bool,
    show_details: bool,
) -> None:
    report, _plans = _apply_cleanmkv_changes(
        service,
        work_folder,
        preset,
        output_dir_name,
        registry,
        copy_unchanged_files,
        scans,
        plans,
    )
    _print_cleanmkv_preview(report, details=show_details, applied=True)
    _print_cleanmkv_diff(show_diff, scans, plans, registry)
    _print_cleanmkv_report_errors(report)


def _prepare_cleanmkv_context(
    *,
    path: str | None,
    apply_changes: bool,
    dry_run: bool,
    auto_mode: bool,
    wizard: bool,
    save_preset: str | None,
    preset_file: str | None,
    external_preset: str | None,
    preset_name: str | None,
    output_dir_name_override: str | None,
) -> tuple[int | None, _CleanMkvContext | None]:
    store = SettingsStore()
    settings = store.load()
    resolver = PathResolver(settings)
    registry = ToolRegistry(store)

    error_code, folder, is_single_file = _validate_and_resolve_path(path, resolver)
    if error_code is not None:
        return error_code, None
    assert folder is not None, "folder should not be None after successful validation"  # nosec B101

    work_folder = folder.parent if is_single_file else folder
    output_dir_name = output_dir_name_override or settings["modules"]["cleanmkv"]["output_dir_name"]
    copy_unchanged_files = bool(settings["modules"]["cleanmkv"].get("copy_unchanged_files", True))

    interactive_confirmation, use_track_selector, use_wizard = _resolve_cleanmkv_execution_flags(
        apply_changes=apply_changes,
        dry_run=dry_run,
        auto_mode=auto_mode,
        preset_name=preset_name,
        preset_file=preset_file,
        external_preset=external_preset,
        wizard=wizard,
    )

    error_code, preset, scans = _resolve_cleanmkv_preset(
        use_track_selector,
        use_wizard,
        is_single_file,
        folder,
        registry,
        save_preset,
        preset_file,
        external_preset,
        preset_name,
        settings,
    )
    if error_code is not None:
        return error_code, None

    return (
        None,
        _CleanMkvContext(
            settings=settings,
            folder=folder,
            work_folder=work_folder,
            registry=registry,
            output_dir_name=output_dir_name,
            copy_unchanged_files=copy_unchanged_files,
            interactive_confirmation=interactive_confirmation,
            use_wizard=use_wizard,
            preset=preset,
            scans=scans,
        ),
    )


def _finalize_non_interactive_cleanmkv(apply_changes: bool) -> None:
    if apply_changes:
        print_success(tr("cleanmkv.success.completed", default="CleanMKV operation completed."))
        return
    print_success(tr("cleanmkv.success.dry_run_completed", default="CleanMKV dry-run completed."))


def _run_interactive_cleanmkv_apply(
    *,
    service: CleanMkvService,
    context: _CleanMkvContext,
    plans: list,
    show_diff: bool,
    show_details: bool,
) -> int:
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
        return 0

    _apply_cleanmkv_and_report(
        service=service,
        work_folder=context.work_folder,
        preset=context.preset,
        output_dir_name=context.output_dir_name,
        registry=context.registry,
        copy_unchanged_files=context.copy_unchanged_files,
        scans=context.scans,
        plans=plans,
        show_diff=show_diff,
        show_details=show_details,
    )
    print_success(tr("cleanmkv.success.completed", default="CleanMKV operation completed."))
    return 0


def _preview_and_maybe_apply_cleanmkv(
    *,
    service: CleanMkvService,
    context: _CleanMkvContext,
    apply_changes: bool,
    show_diff: bool,
):
    report, plans = _run_cleanmkv_preview(
        service=service,
        work_folder=context.work_folder,
        preset=context.preset,
        output_dir_name=context.output_dir_name,
        registry=context.registry,
        copy_unchanged_files=context.copy_unchanged_files,
        scans=context.scans,
    )

    if not apply_changes:
        return report, plans

    report, _plans = _apply_cleanmkv_changes(
        service,
        context.work_folder,
        context.preset,
        context.output_dir_name,
        context.registry,
        context.copy_unchanged_files,
        context.scans,
        plans,
    )
    _print_cleanmkv_diff(show_diff, context.scans, plans, context.registry)
    return report, plans


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
    show_diff: bool = False,
    auto_mode: bool = False,
    output_dir_name_override: str | None = None,
    check_tools: bool = False,
) -> int:
    """CleanMKV command entry point.

    Args:
        path: Path to MKV file or folder
        apply_changes: Apply changes immediately
        dry_run: Preview changes without applying
        preset_name: Name of preset to use
        preset_file: Path to preset file
        external_preset: External preset name
        wizard: Use interactive wizard
        save_preset: Save preset with this name
        list_presets: List available presets
        show_details: Show detailed output
        auto_mode: Automatic mode (no interaction)
        output_dir_name_override: Override output directory name
        check_tools: Check tool availability before processing

    Returns:
        Exit code (0 for success, 1 for error)
    """
    start_code = _validate_cleanmkv_start(
        list_presets=list_presets,
        check_tools=check_tools,
        apply_changes=apply_changes,
        dry_run=dry_run,
    )
    if start_code is not None:
        return start_code

    error_code, context = _prepare_cleanmkv_context(
        path=path,
        apply_changes=apply_changes,
        dry_run=dry_run,
        auto_mode=auto_mode,
        wizard=wizard,
        save_preset=save_preset,
        preset_file=preset_file,
        external_preset=external_preset,
        preset_name=preset_name,
        output_dir_name_override=output_dir_name_override,
    )
    if error_code is not None:
        return error_code
    assert context is not None, "context should not be None after successful preparation"  # nosec B101

    print_module_banner("CleanMKV")

    print_info(
        tr(
            "cleanmkv.info.using_preset",
            default="Using preset: {name}",
            name=context.preset.name or external_preset or preset_name or "default",
        )
    )

    service = CleanMkvService()
    report, plans = _preview_and_maybe_apply_cleanmkv(
        service=service,
        context=context,
        apply_changes=apply_changes,
        show_diff=show_diff,
    )

    _print_cleanmkv_preview(report, details=show_details, applied=apply_changes)
    _print_cleanmkv_summary(
        report,
        context.folder,
        context.preset,
        apply_changes,
        context.use_wizard,
        save_preset,
    )

    _print_cleanmkv_report_errors(report)

    if context.interactive_confirmation:
        return _run_interactive_cleanmkv_apply(
            service=service,
            context=context,
            plans=plans,
            show_diff=show_diff,
            show_details=show_details,
        )

    _finalize_non_interactive_cleanmkv(apply_changes)
    return 0


@click.command(
    "cleanmkv",
    help=tr(
        "cli.cleanmkv.help",
        default=(
            "Select audio/subtitle tracks and remux clean MKV copies.\n\n"
            "CleanMKV intelligently selects the best audio and subtitle tracks based on language "
            "preferences, then remuxes files into clean MKV containers without re-encoding.\n\n"
            "Quick examples:\n"
            "  fk cleanmkv <folder>                    # Interactive track selector\n"
            "  fk cmk <folder> --apply                 # Apply without preview confirmation\n"
            "  fk cleanmkv <folder> --preset default   # Use builtin preset\n"
            "  fk cmk <folder> --wizard                # Create custom preset\n"
            "  fk cleanmkv <file.mkv>                  # Process single file\n\n"
            "Features:\n"
            "  • Interactive track selection with preview\n"
            "  • Automatic language-based track filtering\n"
            "  • Preset system for repeatable configurations\n"
            "  • Lossless remuxing (no re-encoding)\n"
            "  • Batch processing support\n\n"
            "Best practices:\n"
            "  • Use interactive mode first to understand track selection\n"
            "  • Create presets with --wizard for repeated workflows\n"
            "  • Use --dry-run to preview changes without applying\n"
            "  • Check output in 'CleanMKV' subfolder\n\n"
            "Related commands: pipeline, batch"
        ),
    ),
)
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
    "--diff",
    "show_diff",
    is_flag=True,
    help=tr("cli.cleanmkv.option.diff", default="Show before/after track comparison after remux."),
)
@click.option(
    "--details",
    "show_details",
    is_flag=True,
    help=tr("cli.cleanmkv.option.details", default="Show per-file CleanMKV details."),
)
@click.option(
    "--check-tools",
    is_flag=True,
    help=tr(
        "cli.cleanmkv.option.check_tools",
        default="Check that required tools (mkvmerge) are available before processing.",
    ),
)
@click.option(
    "--verbose",
    "-v",
    count=True,
    help=tr("cli.cleanmkv.verbose", default="Increase verbosity (-v, -vv, -vvv)"),
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
    show_diff: bool,
    show_details: bool,
    check_tools: bool,
    verbose: int,
) -> int:
    """Handle cleanmkv command."""
    # Configure verbosity
    configure_verbosity(verbose)
    if is_verbose():
        logger.info(f"CleanMKV execution with verbosity level {verbose}")

    try:
        return run_cleanmkv_command(
            path=join_path_parts(path_parts) or None,
            apply_changes=apply_changes,
            dry_run=dry_run,
            preset_name=preset_name,
            preset_file=preset_file,
            external_preset=external_preset,
            wizard=wizard,
            save_preset=save_preset,
            list_presets=list_presets,
            show_details=show_details,
            show_diff=show_diff,
            check_tools=check_tools,
        )
    except CleanMkvOperationError:
        return 1  # errors already printed above
