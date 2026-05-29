"""Pipeline batch processing integration.

This module handles batch mode execution for the pipeline command,
integrating with the batch service for queue management.
"""

from __future__ import annotations

import sys
from pathlib import Path

from ouro.core.i18n import tr
from ouro.modules.batch.models import BatchStatus
from ouro.modules.batch.models import BatchConfig
from ouro.modules.batch.service import BatchService
from ouro.ui.branding import print_module_banner
from ouro.ui.console import console, print_error, print_info, print_warning
from ouro.ui.unified_selector import confirm_choice


def _batch_command_helpers():
    from ouro.commands.batch import (
        _build_queue_interactive as _build_batch_queue_interactive,  # pyright: ignore[reportPrivateUsage]  # Internal helper shared between command modules
    )
    from ouro.commands.batch import (
        _print_batch_progress,  # pyright: ignore[reportPrivateUsage]  # Internal helper shared between command modules
        _print_batch_summary,  # pyright: ignore[reportPrivateUsage]  # Internal helper shared between command modules
    )

    return _build_batch_queue_interactive, _print_batch_progress, _print_batch_summary


def _resolve_batch_initial_path(path: str | None) -> tuple[int | None, Path | None]:
    if not path:
        return None, None
    initial_path = Path(path)
    if initial_path.exists():
        return None, initial_path
    print_error(
        tr(
            "batch.error.folder_not_found",
            default="Folder not found: {folder}",
            folder=initial_path,
        )
    )
    return 1, None


def _resolve_auto_pipeline_preset(
    *, auto_mode: bool, pipeline_preset: str | None
) -> tuple[int | None, str | None]:
    if not auto_mode or pipeline_preset:
        return None, pipeline_preset
    if not sys.stdin.isatty():
        print_error(
            tr(
                "batch.error.preset_required",
                default="Auto mode requires --pipeline-preset to be specified in non-interactive mode",
            )
        )
        return 1, None

    from ouro.commands.pipeline import (
        _select_pipeline_preset,  # pyright: ignore[reportPrivateUsage]  # Internal helper shared between command modules
    )

    console.print()
    print_info(
        tr(
            "batch.auto.preset_selection",
            default="Auto mode enabled. Select a pipeline preset for autonomous processing.",
        )
    )
    selected = _select_pipeline_preset()
    if selected:
        return None, selected
    print_info(tr("batch.info.cancelled", default="Batch processing cancelled"))
    return 0, None


def _build_batch_queue(
    *,
    service: BatchService,
    batch_auto: bool,
    initial_path: Path | None,
    build_queue_interactive,
) -> int:
    if batch_auto and initial_path:
        return _build_batch_queue_auto(service=service, initial_path=initial_path)
    if not sys.stdin.isatty():
        print_error(
            tr(
                "batch.error.interactive_required",
                default="Batch mode requires interactive terminal (use --batch-auto for automation)",
            )
        )
        return 1
    ready = build_queue_interactive(service, initial_path)
    if ready:
        return 0
    print_info(tr("batch.info.cancelled", default="Batch processing cancelled"))
    return 0


def _build_batch_queue_auto(*, service: BatchService, initial_path: Path) -> int:
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
    if added == 0:
        return 1
    print_info(
        tr(
            "batch.info.auto_scan_found",
            default="Found {count} release(s) to process",
            count=added,
        )
    )
    return 0


def _confirm_batch_start(*, batch_auto: bool, auto_mode: bool, queue_count: int) -> int:
    if batch_auto or auto_mode:
        return 0
    console.print()
    confirmed = confirm_choice(
        title=tr(
            "batch.confirm.start",
            default="Process {count} release(s) now?",
            count=queue_count,
        ),
        default=True,
    )
    if confirmed:
        return 0
    print_info(tr("batch.info.cancelled", default="Batch processing cancelled"))
    return 0


def _build_batch_pipeline_config(
    *,
    pipeline_preset: str | None,
    nfo_locale: str | None,
    announce: str | None,
    preset: str | None,
    with_metadata: bool | None,
    remove_terms: tuple[str, ...],
    select_templates: bool | None,
    nfo_mode: str | None,
    enabled_modules: tuple[str, ...] | None,
    auto_mode: bool,
) -> BatchConfig:
    return BatchConfig(
        pipeline_preset=pipeline_preset,
        nfo_locale=nfo_locale,
        announce=announce,
        preset=preset,
        with_metadata=with_metadata,
        remove_terms=remove_terms,
        select_templates=False if auto_mode else (select_templates or False),
        nfo_mode=nfo_mode,
        enabled_modules=enabled_modules,
        auto_mode=auto_mode,
    )


def _run_batch_queue(
    *,
    service: BatchService,
    config: BatchConfig,
    progress_callback,
    summary_callback,
) -> int:
    from ouro.commands.pipeline import run_pipeline_command

    try:
        results = service.process_queue(
            config=config,
            pipeline_runner=run_pipeline_command,
            progress_callback=progress_callback,
        )
    except KeyboardInterrupt:
        print_warning(tr("batch.warning.stopped", default="Batch processing stopped by user"))
        summary_callback(service)
        return 1

    summary_callback(service)
    failed_count = sum(1 for result in results if result.item.status == BatchStatus.FAILED)
    return 1 if failed_count > 0 else 0


def run_batch_pipeline(
    *,
    path: str | None,
    nfo_locale: str | None,
    announce: str | None,
    preset: str | None = None,
    with_metadata: bool | None = None,
    remove_terms: tuple[str, ...] = (),
    select_modules: bool | None = None,
    select_templates: bool | None = None,
    select_terms: bool | None = None,
    nfo_mode: str | None = None,
    enabled_modules: tuple[str, ...] | None = None,
    batch_auto: bool = False,
    pipeline_preset: str | None = None,
    auto_mode: bool = False,
) -> int:
    """Run pipeline in batch mode, processing multiple releases.

    Args:
        path: Initial path to scan or process
        nfo_locale: NFO locale override
        announce: Torrent announce URL
        preset: Prez preset name
        with_metadata: Enable metadata fetching
        remove_terms: Terms to remove during renaming
        select_modules: Enable module selection
        select_templates: Enable template selection
        select_terms: Enable term selection
        nfo_mode: NFO mode override
        enabled_modules: Explicitly enabled modules
        batch_auto: Auto mode for batch scanning
        pipeline_preset: Pipeline preset name
        auto_mode: Run fully autonomous

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    build_queue_interactive, print_batch_progress, print_batch_summary = _batch_command_helpers()
    print_module_banner("Pipeline - Batch Mode")
    service = BatchService()
    path_error, initial_path = _resolve_batch_initial_path(path)
    if path_error is not None:
        return path_error

    preset_error, pipeline_preset = _resolve_auto_pipeline_preset(
        auto_mode=auto_mode,
        pipeline_preset=pipeline_preset,
    )
    if preset_error is not None:
        return preset_error

    queue_code = _build_batch_queue(
        service=service,
        batch_auto=batch_auto,
        initial_path=initial_path,
        build_queue_interactive=build_queue_interactive,
    )
    if queue_code != 0:
        return queue_code

    confirm_code = _confirm_batch_start(
        batch_auto=batch_auto,
        auto_mode=auto_mode,
        queue_count=len(service.queue),
    )
    if confirm_code != 0:
        return confirm_code

    config = _build_batch_pipeline_config(
        pipeline_preset=pipeline_preset,
        nfo_locale=nfo_locale,
        announce=announce,
        preset=preset,
        with_metadata=with_metadata,
        remove_terms=remove_terms,
        select_templates=select_templates,
        nfo_mode=nfo_mode,
        enabled_modules=enabled_modules,
        auto_mode=auto_mode,
    )
    return _run_batch_queue(
        service=service,
        config=config,
        progress_callback=print_batch_progress,
        summary_callback=print_batch_summary,
    )
