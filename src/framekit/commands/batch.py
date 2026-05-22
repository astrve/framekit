"""Batch processing command: pipeline applied to many releases."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from framekit.core.cli_helpers import join_path_parts
from framekit.core.i18n import tr
from framekit.modules.batch.dashboard import BatchDashboard
from framekit.modules.batch.models import BatchConfig, BatchStatus
from framekit.modules.batch.scanner import count_video_files, detect_release_type
from framekit.modules.batch.service import BatchService
from framekit.ui.branding import print_module_banner
from framekit.ui.click_helper import click
from framekit.ui.console import (
    console,
    print_error,
    print_info,
    print_success,
    print_warning,
)
from framekit.ui.unified_selector import (
    SelectorDivider,
    SelectorEntry,
    SelectorOption,
    confirm_choice,
    text_input,
)
from framekit.ui.unified_selector import (
    select_many as _select_many,
)
from framekit.ui.unified_selector import (
    select_one as _select_one,
)

# ----- helpers -----


def _print_batch_progress(current: int, total: int, release_name: str) -> None:
    """Fallback non-dashboard progress (used when dashboard is disabled)."""
    console.print()
    console.rule(
        Text(
            tr(
                "batch.progress.processing",
                default="Processing {current} of {total}: {name}",
                current=current,
                total=total,
                name=release_name,
            ),
            style="bold cyan",
        ),
        style="cyan",
    )
    console.print()


def _print_batch_summary(service: BatchService) -> None:
    """Final recap table when dashboard is disabled."""
    console.print()
    items = service.queue.get_items()

    table = Table(
        title=tr("batch.summary.title", default="Batch Processing Summary"),
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column(tr("batch.summary.release", default="Release"), style="white", no_wrap=False)
    table.add_column(tr("batch.summary.status", default="Status"), justify="center", width=12)
    table.add_column(
        tr("batch.summary.details", default="Details"), style="bright_black", no_wrap=False
    )

    success_count = 0
    failed_count = 0
    for item in items:
        if item.status == BatchStatus.COMPLETED:
            status_text = Text("[OK]", style="bold green")
            success_count += 1
            details = ""
        elif item.status == BatchStatus.FAILED:
            status_text = Text("[FAILED]", style="bold red")
            failed_count += 1
            details = item.error_message or ""
        else:
            status_text = Text(f"[{item.status.value.upper()}]", style="yellow")
            details = ""
        table.add_row(item.display_name, status_text, details)

    console.print(table)
    console.print()

    if failed_count == 0:
        print_success(
            tr(
                "batch.summary.all_success",
                default="All {count} release(s) processed successfully",
                count=success_count,
            )
        )
    else:
        print_warning(
            tr(
                "batch.summary.with_failures",
                default="{success} succeeded, {failed} failed out of {total} release(s)",
                success=success_count,
                failed=failed_count,
                total=len(items),
            )
        )


def _select_pipeline_preset() -> str | None:
    """Forward to the pipeline command's own preset selector to avoid duplicating UI."""
    from framekit.commands.pipeline import (
        _select_pipeline_preset as _pp,  # pyright: ignore[reportPrivateUsage]  # Internal helper shared between command modules
    )

    return _pp()


# ----- interactive queue manager -----


_STATUS_STYLE: dict[BatchStatus, str] = {
    BatchStatus.PENDING: "bright_black",
    BatchStatus.PROCESSING: "yellow",
    BatchStatus.COMPLETED: "green",
    BatchStatus.FAILED: "red",
    BatchStatus.SKIPPED: "bright_black",
}


def _render_queue_panel(service: BatchService) -> None:
    """Show the current queue as a Rich table panel."""
    items = service.queue.get_items()
    if not items:
        console.print(
            Panel(
                Text(
                    tr(
                        "batch.queue.empty",
                        default="Queue is empty — add releases from the menu below.",
                    ),
                    style="bright_black",
                ),
                title=tr("batch.queue.title_panel", default="Batch queue"),
                border_style="cyan",
                expand=False,
            )
        )
        return

    table = Table(
        box=box.SIMPLE_HEAD,
        show_lines=False,
        expand=False,
        header_style="bold cyan",
    )
    table.add_column("#", justify="right", style="bright_black", no_wrap=True)
    table.add_column("Sel", justify="center", no_wrap=True)
    table.add_column("On", justify="center", no_wrap=True)
    table.add_column(tr("batch.summary.release", default="Release"), style="white")
    table.add_column(tr("batch.summary.status", default="Status"), no_wrap=True)
    table.add_column(tr("batch.queue.details", default="Details"), style="bright_black")

    stats = {"completed": 0, "failed": 0, "pending": 0, "processing": 0, "skipped": 0}
    for idx, it in enumerate(items, start=1):
        stats[it.status.value] = stats.get(it.status.value, 0) + 1
        sel = "[bold cyan]x[/]" if it.selected else " "
        on = "[green]●[/]" if it.enabled else "[bright_black]○[/]"
        status = f"[{_STATUS_STYLE[it.status]}]{it.status.value}[/{_STATUS_STYLE[it.status]}]"
        details = it.error_message or ""
        if not details:
            try:
                n = count_video_files(it.path)
                rtype = detect_release_type(it.path)
                details = f"{n} file(s) · {rtype}"
            except Exception:
                details = ""
        table.add_row(str(idx), sel, on, it.display_name, status, details)

    summary = (
        f"[green]{stats['completed']} done[/]  "
        f"[red]{stats['failed']} failed[/]  "
        f"[yellow]{stats['processing']} running[/]  "
        f"[bright_black]{stats['pending']} pending[/]  "
        f"[bright_black]· total {len(items)}[/]"
    )
    console.print(
        Panel(
            table,
            title=tr("batch.queue.title_panel", default="Batch queue"),
            subtitle=summary,
            border_style="cyan",
            expand=False,
        )
    )


# --- submenu: add releases ---


def _handle_add_scan(service: BatchService, default_path: str, recursive: bool) -> None:
    try:
        folder = text_input(
            title=tr("batch.input.parent_folder", default="Parent folder path"),
            default=default_path,
            mandatory=True,
        )
    except KeyboardInterrupt:
        return
    added = service.build_queue_from_folder(Path(folder), recursive=recursive)
    if added > 0:
        print_success(
            tr(
                "batch.info.releases_added",
                default="Added {count} release(s) to queue",
                count=added,
            )
        )


def _handle_add_single(service: BatchService, default_path: str) -> None:
    try:
        folder = text_input(
            title=tr("batch.input.release_folder", default="Release folder path"),
            default=default_path,
            mandatory=True,
        )
    except KeyboardInterrupt:
        return
    path = Path(folder)
    if service.add_release_to_queue(path):
        print_success(
            tr("batch.info.release_added", default="Added to queue: {folder}", folder=path.name)
        )


def _handle_add_load_file(service: BatchService) -> None:
    try:
        file = text_input(
            title=tr("batch.input.load_file", default="Queue .json file path"),
            default="",
            mandatory=True,
        )
    except KeyboardInterrupt:
        return
    if service.load_queue(Path(file)):
        print_success(
            tr(
                "batch.info.queue_loaded",
                default="Queue loaded: {count} release(s)",
                count=len(service.queue.get_items()),
            )
        )
    else:
        print_error(
            tr(
                "batch.error.queue_load_failed",
                default="Failed to load queue from: {path}",
                path=file,
            )
        )


def _submenu_add(service: BatchService, initial_path: Path | None) -> None:
    entries: list[SelectorEntry] = [
        SelectorOption(
            value="scan",
            label=tr(
                "batch.add.scan", default="Scan parent folder (subfolders containing video files)"
            ),
            hint=tr("batch.add.scan_hint", default="quick"),
        ),
        SelectorOption(
            value="scan_deep",
            label=tr("batch.add.scan_deep", default="Recursive scan (walks up to 2 levels deep)"),
            hint=tr("batch.add.scan_deep_hint", default="nested"),
        ),
        SelectorOption(
            value="single",
            label=tr("batch.add.single", default="Add a single release folder"),
            hint=tr("batch.add.single_hint", default="manual"),
        ),
        SelectorOption(
            value="load_file",
            label=tr("batch.add.load_file", default="Load queue from .json file"),
            hint=tr("batch.add.load_file_hint", default="merge"),
        ),
        SelectorDivider(),
        SelectorOption(value="back", label=tr("batch.action.back", default="◀ Back"), hint=""),
    ]
    try:
        choice = select_one(
            title=tr("batch.menu.add", default="Add releases"),
            entries=entries,
            page_size=8,
        )
    except KeyboardInterrupt:
        return
    if not choice or choice == "back":
        return

    default_path = str(initial_path) if initial_path else ""

    handlers: dict[str, Callable[[], None]] = {
        "scan": lambda: _handle_add_scan(service, default_path, recursive=False),
        "scan_deep": lambda: _handle_add_scan(service, default_path, recursive=True),
        "single": lambda: _handle_add_single(service, default_path),
        "load_file": lambda: _handle_add_load_file(service),
    }
    handler = handlers.get(choice)
    if handler is not None:
        handler()


# --- submenu: edit items ---


def _select_edit_action(count: int) -> str | None:
    action_entries: list[SelectorEntry] = [
        SelectorDivider(tr("batch.edit.action", default="Action for selected items")),
        SelectorOption(
            value="toggle_enabled",
            label=tr("batch.edit.toggle_enabled", default="Toggle enabled/disabled"),
            hint=tr("batch.edit.toggle_enabled_hint", default="enable/disable selected items"),
            selected=False,
        ),
        SelectorOption(
            value="remove_selected",
            label=tr("batch.edit.remove_selected", default="Remove from queue"),
            hint=tr("batch.edit.remove_selected_hint", default="delete selected items"),
            selected=False,
        ),
        SelectorOption(
            value="cancel",
            label=tr("batch.action.cancel", default="Cancel (keep selection)"),
            hint="",
            selected=True,
        ),
    ]
    try:
        return select_one(
            title=tr(
                "batch.edit.choose_action",
                default="Choose action for {count} selected item(s)",
                count=count,
            ),
            entries=action_entries,
            page_size=6,
        )
    except KeyboardInterrupt:
        return None


def _apply_edit_action(service: BatchService, items: list, action: str) -> None:
    sel = [it for it in items if it.selected]
    if action == "toggle_enabled":
        for it in sel:
            it.enabled = not it.enabled
        service.queue.auto_save()
        print_info(
            tr(
                "batch.info.enabled_toggled",
                default="Toggled enabled on {count} item(s)",
                count=len(sel),
            )
        )
        return
    if action == "remove_selected":
        if confirm_choice(
            title=tr(
                "batch.confirm.remove_selected",
                default="Remove {count} selected release(s)?",
                count=len(sel),
            ),
            default=True,
        ):
            for it in sel:
                service.queue.remove(it)
            service.queue.auto_save()
            print_info(
                tr(
                    "batch.info.selected_removed",
                    default="Removed {count} selected release(s)",
                    count=len(sel),
                )
            )


def _submenu_edit(service: BatchService) -> None:
    items = service.queue.get_items()
    if not items:
        print_info(tr("batch.info.queue_empty", default="Queue is empty"))
        return

    item_entries: list[SelectorEntry] = [
        SelectorDivider(tr("batch.edit.select_items", default="Select items to modify"))
    ]
    for idx, it in enumerate(items):
        on = "●" if it.enabled else "○"
        item_entries.append(
            SelectorOption(
                value=str(idx),
                label=f"{on} {it.display_name}",
                hint=it.status.value,
                selected=it.selected,
            )
        )

    try:
        selected_indices = select_many(
            title=tr("batch.menu.edit", default="Edit queue items"),
            entries=item_entries,
            page_size=min(20, len(items) + 2),
            minimal_count=0,
        )
    except KeyboardInterrupt:
        return

    for idx, it in enumerate(items):
        it.selected = str(idx) in selected_indices
    service.queue.auto_save()

    if not selected_indices:
        return

    action = _select_edit_action(len(selected_indices))
    if not action or action == "cancel":
        return

    _apply_edit_action(service, items, action)


# --- submenu: manage queue ---


def _submenu_manage(service: BatchService) -> None:
    entries: list[SelectorEntry] = [
        SelectorOption(
            value="retry_failed",
            label=tr(
                "batch.action.retry_failed", default="Retry failed releases (reset → pending)"
            ),
            hint=tr("batch.action.retry_failed_hint", default="failed → pending"),
        ),
        SelectorOption(
            value="remove_completed",
            label=tr("batch.action.remove_completed", default="Remove completed releases"),
            hint=tr("batch.action.remove_completed_hint", default="cleanup"),
        ),
        SelectorOption(
            value="clear_queue",
            label=tr("batch.action.clear_queue", default="Clear entire queue"),
            hint=tr("batch.action.clear_queue_hint", default="remove all"),
        ),
        SelectorDivider(),
        SelectorOption(value="back", label=tr("batch.action.back", default="◀ Back"), hint=""),
    ]
    try:
        choice = select_one(
            title=tr("batch.menu.manage", default="Manage queue"),
            entries=entries,
            page_size=8,
        )
    except KeyboardInterrupt:
        return
    if not choice or choice == "back":
        return

    if choice == "retry_failed":
        n = service.retry_failed()
        if n:
            print_success(
                tr(
                    "batch.info.retry_reset",
                    default="Reset {count} failed release(s) for retry",
                    count=n,
                )
            )
        else:
            print_info(tr("batch.info.no_failed", default="No failed releases to retry"))
        return

    if choice == "remove_completed":
        n = service.remove_completed()
        if n:
            print_success(
                tr(
                    "batch.info.completed_removed",
                    default="Removed {count} completed release(s)",
                    count=n,
                )
            )
        else:
            print_info(tr("batch.info.no_completed", default="No completed releases to remove"))
        return

    if choice == "clear_queue":
        count = len(service.queue.get_items())
        if confirm_choice(
            title=tr(
                "batch.confirm.clear_queue",
                default="Clear all {count} releases from queue?",
                count=count,
            ),
            default=False,
        ):
            service.clear_queue()
            print_info(tr("batch.info.queue_cleared", default="Queue cleared"))


# --- submenu: save queue ---


def _submenu_save(service: BatchService) -> None:
    try:
        file = text_input(
            title=tr("batch.input.save_file", default="Save queue to .json file path"),
            default="",
            mandatory=True,
        )
    except KeyboardInterrupt:
        return
    if service.save_queue(Path(file)):
        print_success(tr("batch.info.queue_saved", default="Queue saved to: {path}", path=file))
    else:
        print_error(
            tr(
                "batch.error.queue_save_failed",
                default="Failed to save queue to: {path}",
                path=file,
            )
        )


# --- main loop ---


def _build_queue_menu_entries(items: list) -> list[SelectorEntry]:
    entries: list[SelectorEntry] = []
    if items:
        ready = sum(
            1
            for it in items
            if it.enabled and it.status in {BatchStatus.PENDING, BatchStatus.FAILED}
        )
        entries.append(
            SelectorOption(
                value="launch",
                label=tr("batch.menu.launch", default="▶ Launch processing"),
                hint=f"{ready} " + tr("batch.releases.ready", default="ready"),
            )
        )
        entries.append(SelectorDivider())
    entries.extend(
        [
            SelectorOption(
                value="add",
                label=tr("batch.menu.add", default="➕ Add releases…"),
                hint=tr("batch.menu.add_hint", default="scan / single / load"),
            ),
            SelectorOption(
                value="edit",
                label=tr("batch.menu.edit", default="✎ Edit items…"),
                hint=tr("batch.menu.edit_hint", default="select, toggle, remove"),
                disabled=not items,
                disabled_reason=tr("batch.menu.empty", default="queue empty"),
            ),
            SelectorOption(
                value="manage",
                label=tr("batch.menu.manage", default="⚙ Manage queue…"),
                hint=tr("batch.menu.manage_hint", default="retry / remove done / clear"),
                disabled=not items,
                disabled_reason=tr("batch.menu.empty", default="queue empty"),
            ),
            SelectorOption(
                value="save",
                label=tr("batch.menu.save", default="💾 Save queue to file…"),
                hint="",
                disabled=not items,
                disabled_reason=tr("batch.menu.empty", default="queue empty"),
            ),
            SelectorDivider(),
            SelectorOption(
                value="quit",
                label=tr("batch.menu.quit", default="✖ Quit"),
                hint="",
            ),
        ]
    )
    return entries


def _build_queue_interactive(service: BatchService, initial_path: Path | None = None) -> bool:
    """Hub-and-spoke queue manager. Returns True if user picks Launch."""
    while True:
        console.print()
        _render_queue_panel(service)
        items = service.queue.get_items()
        entries = _build_queue_menu_entries(items)

        try:
            choice = select_one(
                title=tr(
                    "batch.queue.title",
                    default="Batch queue manager ({count} releases)",
                    count=len(items),
                ),
                entries=entries,
                page_size=10,
            )
        except KeyboardInterrupt:
            return False

        if not choice or choice == "quit":
            return False
        if choice == "launch":
            return bool(items)

        handlers = {
            "add": lambda: _submenu_add(service, initial_path),
            "edit": lambda: _submenu_edit(service),
            "manage": lambda: _submenu_manage(service),
            "save": lambda: _submenu_save(service),
        }
        handler = handlers.get(choice)
        if handler is not None:
            handler()


# ----- click command helpers -----


def _do_add_folder(service: BatchService, folder_path: str) -> int:
    added = service.build_queue_from_folder(Path(folder_path))
    if added > 0:
        print_success(
            tr(
                "batch.info.releases_added",
                default="Added {count} release(s) to queue",
                count=added,
            )
        )
    return 0


def _do_add_release(service: BatchService, release_path: str) -> int:
    path = Path(release_path)
    if service.add_release_to_queue(path):
        print_success(
            tr(
                "batch.info.release_added",
                default="Added to queue: {folder}",
                folder=path.name,
            )
        )
    return 0


def _do_list_queue(service: BatchService) -> int:
    items = service.queue.get_items()
    if not items:
        print_info(tr("batch.info.queue_empty", default="Queue is empty"))
    else:
        console.print()
        for idx, it in enumerate(items, start=1):
            console.print(f"{idx}. {it.display_name} - {it.status.value}")
        console.print()
        print_info(
            tr(
                "batch.info.queue_count",
                default="{count} release(s) in queue",
                count=len(items),
            )
        )
    return 0


def _do_clear_queue(service: BatchService) -> int:
    service.clear_queue()
    print_success(tr("batch.info.queue_cleared", default="Queue cleared"))
    return 0


def _do_remove_index(service: BatchService, index: int) -> int:
    if service.remove_from_queue(index):
        print_success(
            tr(
                "batch.info.item_removed",
                default="Removed item {index} from queue",
                index=index,
            )
        )
    else:
        print_error(
            tr(
                "batch.error.invalid_index",
                default="Invalid index: {index}",
                index=index,
            )
        )
    return 0


def _do_save_queue(service: BatchService, path: str) -> int:
    if service.save_queue(Path(path)):
        print_success(tr("batch.info.queue_saved", default="Queue saved to: {path}", path=path))
    else:
        print_error(
            tr(
                "batch.error.queue_save_failed",
                default="Failed to save queue to: {path}",
                path=path,
            )
        )
    return 0


def _do_load_queue(service: BatchService, path: str) -> int:
    if service.load_queue(Path(path)):
        print_success(
            tr(
                "batch.info.queue_loaded",
                default="Queue loaded: {count} release(s)",
                count=len(service.queue.get_items()),
            )
        )
    else:
        print_error(
            tr(
                "batch.error.queue_load_failed",
                default="Failed to load queue from: {path}",
                path=path,
            )
        )
    return 0


def _do_retry_failed(service: BatchService) -> int:
    n = service.retry_failed()
    if n:
        print_success(
            tr(
                "batch.info.retry_reset",
                default="Reset {count} failed release(s) for retry",
                count=n,
            )
        )
    else:
        print_info(tr("batch.info.no_failed", default="No failed releases to retry"))
    return 0


def _do_remove_completed(service: BatchService) -> int:
    n = service.remove_completed()
    if n:
        print_success(
            tr(
                "batch.info.completed_removed",
                default="Removed {count} completed release(s)",
                count=n,
            )
        )
    else:
        print_info(tr("batch.info.no_completed", default="No completed releases to remove"))
    return 0


def _handle_non_processing_actions(
    service: BatchService,
    add_folder_path: str | None,
    add_release_path: str | None,
    list_queue: bool,
    clear_queue_flag: bool,
    remove_index: int | None,
    save_queue_path: str | None,
    load_queue_path: str | None,
    retry_failed: bool,
    remove_completed: bool,
) -> int | None:
    """Handle non-processing batch actions (add, list, clear, etc.).

    Returns exit code if action was handled, None otherwise.
    """
    if add_folder_path:
        return _do_add_folder(service, add_folder_path)
    if add_release_path:
        return _do_add_release(service, add_release_path)
    if list_queue:
        return _do_list_queue(service)
    if clear_queue_flag:
        return _do_clear_queue(service)
    if remove_index is not None:
        return _do_remove_index(service, remove_index)
    if save_queue_path:
        return _do_save_queue(service, save_queue_path)
    if load_queue_path:
        return _do_load_queue(service, load_queue_path)
    if retry_failed:
        return _do_retry_failed(service)
    if remove_completed:
        return _do_remove_completed(service)
    return None


def _build_queue_auto_scan(service: BatchService, initial_path: Path) -> int:
    if not initial_path.is_dir():
        print_error(
            tr(
                "batch.error.not_a_directory",
                default="Path is not a directory: {folder}",
                folder=initial_path,
            )
        )
        return 1
    added = service.build_queue_from_folder(initial_path)
    if added == 0 and not service.queue.get_items():
        print_warning(tr("batch.warning.no_releases_found", default="No releases found"))
        return 1
    if added:
        print_info(
            tr(
                "batch.info.auto_scan_found",
                default="Found {count} release(s) to process",
                count=added,
            )
        )
    return 0


def _build_processing_queue(
    service: BatchService,
    auto: bool,
    initial_path: Path | None,
) -> int:
    """Build the batch processing queue.

    Returns 0 for success, 1 for error.
    """
    if auto and initial_path:
        return _build_queue_auto_scan(service, initial_path)

    if initial_path and initial_path.is_dir():
        added = service.build_queue_from_folder(initial_path)
        if added:
            print_info(
                tr(
                    "batch.info.releases_added",
                    default="Added {count} release(s) to queue",
                    count=added,
                )
            )

    if not sys.stdin.isatty():
        print_error(
            tr(
                "batch.error.interactive_required",
                default="Batch mode requires interactive terminal (use --auto for automation)",
            )
        )
        return 1
    if not _build_queue_interactive(service, initial_path):
        print_info(tr("batch.info.cancelled", default="Batch processing cancelled"))
        return 0

    return 0


def _select_pipeline_preset_for_batch(
    auto: bool,
    pipeline_preset: str | None,
) -> tuple[int, str | None]:
    """Select pipeline preset for batch processing.

    Returns (exit_code, preset_name).
    """
    if not pipeline_preset and sys.stdin.isatty():
        console.print()
        if auto:
            print_info(
                tr(
                    "batch.auto.preset_selection",
                    default="Auto mode enabled. Select a pipeline preset for autonomous processing.",
                )
            )
        else:
            print_info(
                tr(
                    "batch.preset_selection",
                    default="Select a pipeline preset for batch processing (optional).",
                )
            )
        if confirm_choice(
            title=tr("batch.confirm.select_preset", default="Select a pipeline preset?"),
            default=True,
        ):
            pipeline_preset = _select_pipeline_preset()
            if pipeline_preset:
                print_info(
                    tr(
                        "batch.info.preset_selected",
                        default="Selected preset: {preset}",
                        preset=pipeline_preset,
                    )
                )
    elif not pipeline_preset and auto and not sys.stdin.isatty():
        print_error(
            tr(
                "batch.error.preset_required",
                default="Auto mode requires --pipeline-preset to be specified in non-interactive mode",
            )
        )
        return 1, None

    return 0, pipeline_preset


def _partition_queue_items(
    service: BatchService,
) -> tuple[list, list]:
    pending_states = {BatchStatus.PENDING, BatchStatus.FAILED, BatchStatus.PROCESSING}
    queue_items = service.queue.get_items()
    processable = [it for it in queue_items if it.enabled and it.status in pending_states]
    already_done = [it for it in queue_items if it.enabled and it.status == BatchStatus.COMPLETED]
    return processable, already_done


def _filter_processable_items(
    service: BatchService,
    auto: bool,
) -> tuple[int, list, list]:
    """Filter processable items and get user confirmation.

    Returns (exit_code, processable_items, already_done_items).
    """
    processable, already_done = _partition_queue_items(service)

    if not processable:
        warning_message = (
            tr(
                "batch.warning.all_completed",
                default="All {count} enabled release(s) already completed. Use --remove-completed or --retry-failed.",
                count=len(already_done),
            )
            if already_done
            else tr("batch.warning.no_enabled", default="No releases enabled for processing")
        )
        print_warning(warning_message)
        return 0, [], []

    if auto:
        return 0, processable, already_done

    console.print()
    if already_done:
        print_info(
            tr(
                "batch.info.skipping_completed",
                default="Skipping {count} already-completed release(s)",
                count=len(already_done),
            )
        )
    if not confirm_choice(
        title=tr(
            "batch.confirm.start",
            default="Process {count} release(s) now?",
            count=len(processable),
        ),
        default=True,
    ):
        print_info(tr("batch.info.cancelled", default="Batch processing cancelled"))
        return 0, [], []

    return 0, processable, already_done


def _validate_batch_mode_flags(auto: bool, manual: bool) -> int | None:
    if not (auto and manual):
        return None
    print_error(
        tr("batch.error.conflicting_modes", default="Cannot use both --auto and --manual modes")
    )
    return 1


def _resolve_batch_initial_path(path_parts: tuple[str, ...]) -> Path | None:
    path = join_path_parts(path_parts)
    return Path(path) if path else None


def _should_auto_load_default_queue(
    initial_path: Path | None,
    load_queue_path: str | None,
) -> bool:
    """Use the persisted default queue only when no explicit source is provided."""
    return initial_path is None and load_queue_path is None


def _build_batch_config(
    *,
    pipeline_preset: str | None,
    nfo_locale: str | None,
    announce: str | None,
    preset: str | None,
    with_metadata: bool | None,
    nfo_mode: str | None,
    enabled_modules: tuple[str, ...] | None,
    auto: bool,
) -> BatchConfig:
    return BatchConfig(
        pipeline_preset=pipeline_preset,
        nfo_locale=nfo_locale,
        announce=announce,
        preset=preset,
        with_metadata=with_metadata,
        nfo_mode=nfo_mode,
        enabled_modules=enabled_modules,
        auto_mode=auto,
    )


def _resolve_batch_dashboard(
    *, use_dashboard: bool | None, service: BatchService
) -> BatchDashboard | None:
    if use_dashboard is None:
        use_dashboard = sys.stdin.isatty() and sys.stdout.isatty()
    if not use_dashboard:
        return None
    try:
        dashboard = BatchDashboard(items=service.queue.get_items())
        dashboard.start()
        return dashboard
    except Exception as exc:
        print_warning(
            tr(
                "batch.warning.dashboard_failed",
                default="Failed to start dashboard: {error}. Continuing without dashboard.",
                error=str(exc),
            )
        )
        return None


def _run_batch_processing(
    *,
    service: BatchService,
    config: BatchConfig,
    pipeline_runner,
    dashboard: BatchDashboard | None,
) -> tuple[int, list]:
    try:
        results = service.process_queue(
            config=config,
            pipeline_runner=pipeline_runner,
            progress_callback=None if dashboard else _print_batch_progress,
            dashboard=dashboard,
        )
    except KeyboardInterrupt:
        if dashboard:
            dashboard.stop()
        print_warning(tr("batch.warning.stopped", default="Batch processing stopped by user"))
        _print_batch_summary(service)
        return 1, []
    finally:
        if dashboard and not dashboard.stopped:
            dashboard.stop()

    if not dashboard:
        _print_batch_summary(service)
    failed = sum(1 for result in results if not result.success)
    return (1 if failed > 0 else 0), results


# ----- click command -----


@click.command(
    "batch",
    help=tr(
        "cli.batch.help",
        default=(
            "Run the pipeline on multiple releases.\n\n"
            "Build a queue of release folders, optionally pick a pipeline preset, and process "
            "them sequentially with a real-time dashboard.\n\n"
            "Examples:\n"
            "  fk batch                                # Interactive queue builder\n"
            "  fk batch <parent>                       # Scan parent then interactive UI\n"
            "  fk batch <parent> --auto --pipeline-preset films\n"
            "  fk batch --add-folder <parent>          # Build queue, exit\n"
            "  fk batch --list                         # Show current queue\n"
            "  fk batch --process                      # Process saved queue\n"
        ),
    ),
)
@click.argument("path_parts", nargs=-1)
@click.option(
    "-F", "--add-folder", "add_folder_path", help="Add all releases from a parent folder."
)
@click.option("-R", "--add-release", "add_release_path", help="Add a single release manually.")
@click.option("-l", "--list", "list_queue", is_flag=True, help="Show current queue.")
@click.option("--clear", "clear_queue_flag", is_flag=True, help="Clear the queue.")
@click.option("--remove", "remove_index", type=int, help="Remove item at index from queue.")
@click.option("--save-queue", "save_queue_path", help="Save queue to file.")
@click.option("--load-queue", "load_queue_path", help="Load queue from file.")
@click.option("--retry-failed", is_flag=True, help="Retry all failed releases.")
@click.option("--remove-completed", is_flag=True, help="Remove completed releases from queue.")
@click.option("-a", "--auto", is_flag=True, help="Auto mode (no interaction).")
@click.option("--manual", is_flag=True, help="Manual mode (confirm each release).")
@click.option(
    "--dashboard/--no-dashboard",
    "use_dashboard",
    default=None,
    help="Enable/disable real-time dashboard.",
)
@click.option("-p", "--pipeline-preset", help="Pipeline preset to use.")
@click.option(
    "--modules",
    "enabled_modules_option",
    help="Comma-separated modules: renamer,cleanmkv,encoder,nfo,torrent,prez,upload.",
)
@click.option(
    "-L",
    "--locale",
    "nfo_locale",
    type=click.Choice(["auto", "en", "fr", "es"]),
    help="NFO/prez output language.",
)
@click.option("-A", "--announce", help="Tracker announce URL for torrent creation.")
@click.option("--skip-renamer", is_flag=True, help="Skip renamer module")
@click.option("--skip-cleanmkv", is_flag=True, help="Skip cleanmkv module")
@click.option("--skip-encoder", is_flag=True, help="Skip encoder module")
@click.option("--skip-nfo", is_flag=True, help="Skip NFO module")
@click.option("--skip-torrent", is_flag=True, help="Skip torrent module")
@click.option("--skip-prez", is_flag=True, help="Skip prez module")
@click.option("--ren", "opt_renamer", is_flag=True, help="Enable renamer module")
@click.option("--cmk", "opt_cleanmkv", is_flag=True, help="Enable cleanmkv module")
@click.option("--enc", "opt_encoder", is_flag=True, help="Enable encoder module")
@click.option("--nfo", "opt_nfo", is_flag=True, help="Enable NFO module")
@click.option("--tor", "opt_torrent", is_flag=True, help="Enable torrent module")
@click.option("--prez", "opt_prez", is_flag=True, help="Enable prez module")
@click.option(
    "--all", "all_modules", is_flag=True, help="Run all modules without interactive prompt"
)
@click.option("--preset", help="Prez preset for pipeline output.")
@click.option(
    "--with-metadata/--no-metadata",
    "with_metadata",
    default=None,
    help="Enable/disable metadata for NFO/prez.",
)
@click.option(
    "--nfo-mode", type=click.Choice(["global", "per_file", "both"]), help="NFO output mode."
)
def batch_command(
    path_parts: tuple[str, ...],
    add_folder_path: str | None,
    add_release_path: str | None,
    list_queue: bool,
    clear_queue_flag: bool,
    remove_index: int | None,
    save_queue_path: str | None,
    load_queue_path: str | None,
    retry_failed: bool,
    remove_completed: bool,
    auto: bool,
    manual: bool,
    use_dashboard: bool | None,
    pipeline_preset: str | None,
    enabled_modules_option: str | None,
    nfo_locale: str | None,
    announce: str | None,
    skip_renamer: bool = False,
    skip_cleanmkv: bool = False,
    skip_encoder: bool = False,
    skip_nfo: bool = False,
    skip_torrent: bool = False,
    skip_prez: bool = False,
    opt_renamer: bool = False,
    opt_cleanmkv: bool = False,
    opt_encoder: bool = False,
    opt_nfo: bool = False,
    opt_torrent: bool = False,
    opt_prez: bool = False,
    all_modules: bool = False,
    preset: str | None = None,
    with_metadata: bool | None = None,
    nfo_mode: str | None = None,
) -> int:
    """Batch processing entry point."""
    # Import here to avoid circular dependency with pipeline.py
    from framekit.commands.pipeline import run_pipeline_command

    print_module_banner("Batch Processing")

    mode_error = _validate_batch_mode_flags(auto, manual)
    if mode_error is not None:
        return mode_error

    initial_path = _resolve_batch_initial_path(path_parts)
    service = BatchService(auto_load=_should_auto_load_default_queue(initial_path, load_queue_path))

    # Handle non-processing actions
    exit_code = _handle_non_processing_actions(
        service,
        add_folder_path,
        add_release_path,
        list_queue,
        clear_queue_flag,
        remove_index,
        save_queue_path,
        load_queue_path,
        retry_failed,
        remove_completed,
    )
    if exit_code is not None:
        return exit_code

    # Build queue
    exit_code = _build_processing_queue(service, auto, initial_path)
    if exit_code != 0:
        return exit_code

    # Select preset
    exit_code, pipeline_preset = _select_pipeline_preset_for_batch(auto, pipeline_preset)
    if exit_code != 0:
        return exit_code

    # Filter processable items
    exit_code, processable, _already_done = _filter_processable_items(service, auto)
    if exit_code != 0 or not processable:
        return exit_code

    # Opt-in module resolution.
    from framekit.commands.pipeline import PIPELINE_MODULES_DEFAULT

    opt_in: list[str] = []
    if opt_renamer:
        opt_in.append("renamer")
    if opt_cleanmkv:
        opt_in.append("cleanmkv")
    if opt_encoder:
        opt_in.append("encoder")
    if opt_nfo:
        opt_in.append("nfo")
    if opt_torrent:
        opt_in.append("torrent")
    if opt_prez:
        opt_in.append("prez")

    skip_map = {
        "renamer": skip_renamer,
        "cleanmkv": skip_cleanmkv,
        "encoder": skip_encoder,
        "nfo": skip_nfo,
        "torrent": skip_torrent,
        "prez": skip_prez,
    }

    def apply_skips(modules: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(module for module in modules if not skip_map.get(module, False))

    if all_modules:
        resolved_modules: tuple[str, ...] | None = apply_skips(PIPELINE_MODULES_DEFAULT)
    elif opt_in:
        resolved_modules = apply_skips(tuple(opt_in))
    elif enabled_modules_option:
        resolved_modules = apply_skips(
            tuple(it.strip().lower() for it in enabled_modules_option.split(",") if it.strip())
        )
    elif any(skip_map.values()):
        resolved_modules = apply_skips(PIPELINE_MODULES_DEFAULT)
    else:
        resolved_modules = None

    config = _build_batch_config(
        pipeline_preset=pipeline_preset,
        nfo_locale=nfo_locale,
        announce=announce,
        preset=preset,
        with_metadata=with_metadata,
        nfo_mode=nfo_mode,
        enabled_modules=resolved_modules,
        auto=auto,
    )
    if manual:
        use_dashboard = False
    dashboard = _resolve_batch_dashboard(use_dashboard=use_dashboard, service=service)
    exit_code, _results = _run_batch_processing(
        service=service,
        config=config,
        pipeline_runner=run_pipeline_command,
        dashboard=dashboard,
    )
    return exit_code


select_one = _select_one  # backwards-compatible patch target for tests

select_many = _select_many  # backwards-compatible patch target for tests
