"""Batch processing service: queue + pipeline orchestration."""

from __future__ import annotations

import inspect
import threading
import time
import traceback
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from framekit.core.diagnostics import get_module_log_file
from framekit.core.i18n import tr
from framekit.core.parallel import get_optimal_worker_count
from framekit.core.performance import profile_time
from framekit.modules.batch.errors import BatchErrorType
from framekit.modules.batch.models import (
    BatchConfig,
    BatchItem,
    BatchResult,
    BatchStatus,
)
from framekit.modules.batch.queue import BatchQueue
from framekit.modules.batch.scanner import is_valid_release, scan_parent_folder
from framekit.ui.console import print_error, print_info

if TYPE_CHECKING:
    from framekit.modules.batch.dashboard import BatchDashboard


def _pipeline_accepts_kwarg(pipeline_runner: Callable, kwarg_name: str) -> bool:
    """Return ``True`` when ``pipeline_runner`` accepts one named kwarg."""
    try:
        signature = inspect.signature(pipeline_runner)
    except (TypeError, ValueError):
        return False
    parameters = signature.parameters
    if kwarg_name in parameters:
        return True
    return any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters.values())


def _pipeline_accepts_step_callback(pipeline_runner: Callable) -> bool:
    """Return ``True`` when ``pipeline_runner`` exposes a ``step_callback`` arg.

    Inspect the signature explicitly. Catching ``TypeError`` was previously used
    here but silently swallowed unrelated ``TypeError``s raised from inside the
    runner. Builtins or C-backed callables that hide their signature default to
    "not accepted" — the caller still works without progress updates.
    """
    return _pipeline_accepts_kwarg(pipeline_runner, "step_callback")


def _pipeline_accepts_result_callback(pipeline_runner: Callable) -> bool:
    """Return ``True`` when ``pipeline_runner`` accepts ``result_callback``."""
    return _pipeline_accepts_kwarg(pipeline_runner, "result_callback")


def _pipeline_failure_summary(
    pipeline_results: dict[str, dict] | None,
    current_module: str | None,
) -> tuple[str, str | None]:
    if pipeline_results:
        if current_module:
            current_result = pipeline_results.get(current_module)
            if (
                current_result
                and not current_result.get("success")
                and not current_result.get("skipped")
            ):
                error = str(current_result.get("error") or "").strip() or None
                return current_module, error
        for module_name, result in pipeline_results.items():
            if not result.get("success") and not result.get("skipped"):
                error = str(result.get("error") or "").strip() or None
                return module_name, error
    return current_module or "pipeline", None


# Module label map used for the dashboard's "Current step" display
MODULE_LABELS: dict[str, str] = {
    "renamer": "Renaming files",
    "cleanmkv": "Remuxing MKV",
    "encoder": "Encoding video",
    "nfo": "Generating NFO",
    "torrent": "Creating torrent",
    "prez": "Generating presentation",
    "upload": "Uploading release",
}


class BatchService:
    """Queue + pipeline orchestration for batch releases."""

    def __init__(self, queue_file: Path | None = None, auto_load: bool = False) -> None:
        self._queue = BatchQueue(queue_file)
        self._paused = False
        self._cancelled = False
        self._lock = threading.Lock()
        self._cancel_event = threading.Event()

        if auto_load and self._queue.queue_file_exists():
            self._queue.load()
            self._reset_stale_processing()

    def _reset_stale_processing(self) -> None:
        """Reset any item left in PROCESSING (from a previous crashed run) back to PENDING."""
        changed = False
        for item in self._queue.get_items():
            if item.status == BatchStatus.PROCESSING:
                item.status = BatchStatus.PENDING
                item.current_module = None
                item.current_step = None
                item.error_message = None
                changed = True
        if changed:
            self._queue.auto_save()

    # ----- pause / cancel -----

    def pause(self) -> None:
        """Handle pause."""
        with self._lock:
            self._paused = True

    def resume(self) -> None:
        """Handle resume."""
        with self._lock:
            self._paused = False

    def cancel(self) -> None:
        """Handle cancel."""
        with self._lock:
            self._cancelled = True
        self._cancel_event.set()

    def is_paused(self) -> bool:
        """Return ``True`` if is paused."""
        with self._lock:
            return self._paused

    def is_cancelled(self) -> bool:
        """Return ``True`` if is cancelled."""
        with self._lock:
            return self._cancelled

    # ----- queue accessors -----

    @property
    def queue(self) -> BatchQueue:
        """Handle queue."""
        return self._queue

    def get_queue_status(self) -> dict:
        """Return the queue status."""
        s = self._queue.get_status()
        return {
            "total": s.total,
            "pending": s.pending,
            "processing": s.processing,
            "completed": s.completed,
            "failed": s.failed,
            "skipped": s.skipped,
        }

    # ----- queue building -----

    def build_queue_from_folder(
        self,
        parent_path: Path,
        *,
        recursive: bool = False,
        max_depth: int = 2,
    ) -> int:
        """Build queue from folder."""
        logger.info(
            f"Building queue from folder: {parent_path} (recursive={recursive}, max_depth={max_depth})"
        )

        if not parent_path.exists() or not parent_path.is_dir():
            logger.error(f"Folder not found: {parent_path}")
            print_error(
                tr(
                    "batch.error.folder_not_found",
                    default="Folder not found: {folder}",
                    folder=parent_path,
                )
            )
            return 0

        releases = scan_parent_folder(parent_path, recursive=recursive, max_depth=max_depth)
        if not releases:
            logger.warning(f"No releases found in: {parent_path}")
            print_info(
                tr(
                    "batch.warning.no_releases_found",
                    default="No releases found in: {folder}",
                    folder=parent_path,
                )
            )
            return 0

        added = 0
        for release in releases:
            if not self._queue.contains_path(release):
                self._queue.add_path(release)
                added += 1
        if added:
            self._queue.auto_save()

        logger.info(f"Queue built successfully: {added}/{len(releases)} releases added")
        return added

    def add_release_to_queue(self, release_path: Path) -> bool:
        """Handle add release to queue."""
        if not is_valid_release(release_path):
            print_error(
                tr(
                    "batch.error.invalid_release",
                    default="Not a valid release folder (no .mkv files): {folder}",
                    folder=release_path,
                )
            )
            return False
        if self._queue.contains_path(release_path):
            print_info(
                tr(
                    "batch.warning.already_in_queue",
                    default="Release already in queue: {folder}",
                    folder=release_path.name,
                )
            )
            return False
        self._queue.add_path(release_path)
        self._queue.auto_save()
        return True

    def clear_queue(self) -> None:
        """Handle clear queue."""
        self._queue.clear()
        self._queue.auto_save()

    def remove_from_queue(self, index: int) -> bool:
        """Handle remove from queue."""
        removed = self._queue.remove_at(index)
        if removed:
            self._queue.auto_save()
        return removed is not None

    def save_queue(self, path: Path | None = None) -> bool:
        """Save queue."""
        return self._queue.save(path)

    def load_queue(self, path: Path | None = None) -> bool:
        """Load queue."""
        return self._queue.load(path)

    def get_failed_items(self) -> list[BatchItem]:
        """Return the failed items."""
        return [it for it in self._queue.get_items() if it.status == BatchStatus.FAILED]

    def retry_failed(self) -> int:
        """Handle retry failed."""
        failed = self.get_failed_items()
        for item in failed:
            item.status = BatchStatus.PENDING
            item.error_message = None
            item.processing_time = None
            item.current_module = None
            item.current_step = None
        if failed:
            self._queue.auto_save()
        return len(failed)

    def remove_completed(self) -> int:
        """Handle remove completed."""
        completed = [it for it in self._queue.get_items() if it.status == BatchStatus.COMPLETED]
        for item in completed:
            self._queue.remove(item)
        if completed:
            self._queue.auto_save()
        return len(completed)

    # ----- processing -----

    @profile_time("process_queue")
    def process_queue(
        self,
        config: BatchConfig,
        pipeline_runner: Callable,
        progress_callback: Callable | None = None,
        dashboard: BatchDashboard | None = None,
        *,
        parallel: bool = False,
        max_concurrent: int = 2,
    ) -> list[BatchResult]:
        """Iterate the queue and run pipeline_runner on each enabled, not-yet-done item."""
        items = self._queue.get_items()

        logger.info(
            f"Starting queue processing: {len(items)} items (parallel={parallel}, max_concurrent={max_concurrent if parallel else 1}, auto_mode={config.auto_mode})"
        )

        if not items:
            logger.warning("No items in queue to process")
            return []

        # Reset cancel flag for fresh run
        with self._lock:
            self._cancelled = False
        self._cancel_event.clear()

        if parallel and len(items) > 1 and max_concurrent > 1:
            return self._process_parallel(
                items, config, pipeline_runner, progress_callback, dashboard, max_concurrent
            )

        return self._process_sequential(
            items, config, pipeline_runner, progress_callback, dashboard
        )

    def _process_sequential(
        self,
        items: list[BatchItem],
        config: BatchConfig,
        pipeline_runner: Callable,
        progress_callback: Callable | None,
        dashboard: BatchDashboard | None,
    ) -> list[BatchResult]:
        results: list[BatchResult] = []

        for idx, item in enumerate(items, start=1):
            if self._cancel_requested(dashboard):
                break
            if self._handle_non_processable_item(item, results):
                continue
            self._wait_while_paused(dashboard)
            if self._cancel_requested(dashboard):
                break
            if not self._confirm_item_processing(config, dashboard, item, idx, len(items), results):
                continue
            self._mark_item_processing(item)
            self._notify_item_start(item, idx, len(items), dashboard, progress_callback)
            result = self._run_pipeline_for_item(
                item, config, pipeline_runner, dashboard, self._cancel_event
            )
            self._finalize_processed_item(item, result, results, dashboard)

        success_count = sum(1 for r in results if r.success)
        logger.info(f"Queue processing completed: {success_count}/{len(results)} successful")
        return results

    def _handle_non_processable_item(self, item: BatchItem, results: list[BatchResult]) -> bool:
        if not item.enabled:
            if item.status not in (BatchStatus.COMPLETED, BatchStatus.SKIPPED):
                item.status = BatchStatus.SKIPPED
            results.append(BatchResult(item=item, exit_code=0, duration_seconds=0.0))
            return True
        return item.status in (BatchStatus.COMPLETED, BatchStatus.SKIPPED)

    def _confirm_item_processing(
        self,
        config: BatchConfig,
        dashboard: BatchDashboard | None,
        item: BatchItem,
        idx: int,
        total: int,
        results: list[BatchResult],
    ) -> bool:
        if config.auto_mode or dashboard:
            return True
        from framekit.ui.unified_selector import confirm_choice

        confirmed = confirm_choice(
            title=tr(
                "batch.confirm.process_item",
                default="Process {name}? ({current}/{total})",
                name=item.display_name,
                current=idx,
                total=total,
            ),
            default=True,
        )
        if confirmed:
            return True
        item.status = BatchStatus.SKIPPED
        results.append(BatchResult(item=item, exit_code=0, duration_seconds=0.0))
        self._queue.auto_save()
        return False

    def _mark_item_processing(self, item: BatchItem) -> None:
        item.status = BatchStatus.PROCESSING
        self._queue.auto_save()

    def _notify_item_start(
        self,
        item: BatchItem,
        idx: int,
        total: int,
        dashboard: BatchDashboard | None,
        progress_callback: Callable | None,
    ) -> None:
        logger.info(f"Processing batch item: {item.display_name} ({idx}/{total}) path={item.path}")
        if dashboard:
            dashboard.update_current_item(item)
            dashboard.update_queue_status()
        if progress_callback:
            progress_callback(idx, total, item.display_name)

    def _finalize_processed_item(
        self,
        item: BatchItem,
        result: BatchResult,
        results: list[BatchResult],
        dashboard: BatchDashboard | None,
    ) -> None:
        results.append(result)
        self._queue.auto_save()
        if result.success:
            logger.info(
                f"Batch item completed: {item.display_name} ({result.duration_seconds:.1f}s)"
            )
        else:
            logger.error(
                f"Batch item failed: {item.display_name} error={item.error_message} ({result.duration_seconds:.1f}s)"
            )
        if not dashboard:
            return
        if result.success:
            dashboard.mark_item_completed(item)
            return
        dashboard.mark_item_failed(item, item.error_message or "Unknown error")

    def _process_parallel(
        self,
        items: list[BatchItem],
        config: BatchConfig,
        pipeline_runner: Callable,
        progress_callback: Callable | None,
        dashboard: BatchDashboard | None,
        max_concurrent: int,
    ) -> list[BatchResult]:
        results: list[BatchResult] = []
        workers = min(max_concurrent, get_optimal_worker_count())

        logger.info(f"Starting parallel processing: {len(items)} items, {workers} workers")

        print_info(
            tr(
                "batch.info.parallel_processing",
                default="Processing {count} releases with {workers} workers",
                count=len(items),
                workers=workers,
            )
        )

        active_items = self._active_parallel_items(items)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_item = self._submit_parallel_items(
                executor, active_items, config, pipeline_runner, dashboard
            )
            completed = 0
            for future in as_completed(future_to_item):
                if self._cancel_requested(dashboard):
                    self._cancel_parallel_futures(future_to_item)
                    break
                item = future_to_item[future]
                completed = self._handle_parallel_future(
                    future,
                    item,
                    results,
                    dashboard,
                    progress_callback,
                    completed,
                    len(active_items),
                )
        return results

    def _active_parallel_items(self, items: list[BatchItem]) -> list[BatchItem]:
        return [
            item
            for item in items
            if item.enabled and item.status not in (BatchStatus.COMPLETED, BatchStatus.SKIPPED)
        ]

    def _submit_parallel_items(
        self,
        executor: ThreadPoolExecutor,
        items: list[BatchItem],
        config: BatchConfig,
        pipeline_runner: Callable,
        dashboard: BatchDashboard | None,
    ) -> dict:
        future_to_item: dict = {}
        for item in items:
            item.status = BatchStatus.PROCESSING
            future = executor.submit(
                self._run_pipeline_for_item,
                item,
                config,
                pipeline_runner,
                dashboard,
                self._cancel_event,
            )
            future_to_item[future] = item
        return future_to_item

    def _cancel_parallel_futures(self, future_to_item: dict) -> None:
        for future in future_to_item:
            future.cancel()

    def _handle_parallel_future(
        self,
        future,
        item: BatchItem,
        results: list[BatchResult],
        dashboard: BatchDashboard | None,
        progress_callback: Callable | None,
        completed: int,
        total_items: int,
    ) -> int:
        try:
            result = future.result()
        except Exception as exc:
            self._record_parallel_exception(item, exc, results, dashboard)
            return completed

        results.append(result)
        completed += 1
        self._notify_parallel_result(item, result, dashboard)
        if progress_callback:
            progress_callback(completed, total_items, item.display_name)
        return completed

    def _record_parallel_exception(
        self,
        item: BatchItem,
        exc: Exception,
        results: list[BatchResult],
        dashboard: BatchDashboard | None,
    ) -> None:
        item.status = BatchStatus.FAILED
        item.error_message = str(exc)
        results.append(BatchResult(item=item, exit_code=1, duration_seconds=0.0))
        if dashboard:
            dashboard.mark_item_failed(item, str(exc))

    def _notify_parallel_result(
        self, item: BatchItem, result: BatchResult, dashboard: BatchDashboard | None
    ) -> None:
        if not dashboard:
            return
        if result.success:
            dashboard.mark_item_completed(item)
            return
        dashboard.mark_item_failed(item, item.error_message or "Unknown error")

    # ----- error categorization -----

    def _categorize_error(
        self, exc: Exception, item: BatchItem
    ) -> tuple[str, BatchErrorType, dict]:
        """Categorize an exception into a user-friendly error message and type.

        Args:
            exc: The exception that occurred
            item: The batch item being processed

        Returns:
            Tuple of (error_message, error_type, error_details)
        """
        error_details = {
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "item_path": str(item.path),
            "current_module": item.current_module,
        }

        exc_str = str(exc).lower()
        exc_type = type(exc).__name__
        for resolver in (
            self._classify_permission_error,
            self._classify_file_missing_error,
            self._classify_missing_track_error,
            self._classify_index_error,
            self._classify_key_error,
            self._classify_value_error,
            self._classify_tool_error,
            self._classify_corrupted_error,
        ):
            classified = resolver(exc, item, exc_str, exc_type, error_details)
            if classified is not None:
                return classified
        return (
            tr("batch.error.unexpected", default="Unexpected error: {msg}", msg=str(exc)[:200]),
            BatchErrorType.UNEXPECTED_ERROR,
            error_details,
        )

    def _classify_permission_error(
        self, exc: Exception, item: BatchItem, exc_str: str, _exc_type: str, details: dict
    ) -> tuple[str, BatchErrorType, dict] | None:
        if not (
            isinstance(exc, PermissionError)
            or "permission denied" in exc_str
            or "access denied" in exc_str
        ):
            return None
        return (
            tr(
                "batch.error.permission",
                default="Permission denied - check file ownership and permissions for: {path}",
                path=item.display_name,
            ),
            BatchErrorType.PERMISSION_ERROR,
            details,
        )

    def _classify_file_missing_error(
        self, exc: Exception, item: BatchItem, exc_str: str, _exc_type: str, details: dict
    ) -> tuple[str, BatchErrorType, dict] | None:
        if not (
            isinstance(exc, FileNotFoundError)
            or "not found" in exc_str
            or "no such file" in exc_str
        ):
            return None
        if "preset" in exc_str or ".yaml" in exc_str:
            return (
                tr(
                    "batch.error.missing_preset",
                    default="Preset not found - check preset name and path: {msg}",
                    msg=str(exc),
                ),
                BatchErrorType.MISSING_PRESET,
                details,
            )
        return (
            tr(
                "batch.error.file_not_found",
                default="File not found: {path}",
                path=item.display_name,
            ),
            BatchErrorType.CORRUPTED_FILE,
            details,
        )

    def _classify_missing_track_error(
        self, _exc: Exception, item: BatchItem, exc_str: str, _exc_type: str, details: dict
    ) -> tuple[str, BatchErrorType, dict] | None:
        if "track" not in exc_str:
            return None
        if not any(term in exc_str for term in ("missing", "not found", "no audio", "no subtitle")):
            return None
        track_type = (
            "audio" if "audio" in exc_str else "subtitle" if "subtitle" in exc_str else "track"
        )
        return (
            tr(
                "batch.error.missing_track",
                default="Missing {track_type} track - file incompatible with preset: {name}",
                track_type=track_type,
                name=item.display_name,
            ),
            BatchErrorType.MISSING_TRACK,
            details,
        )

    def _classify_index_error(
        self, exc: Exception, item: BatchItem, _exc_str: str, exc_type: str, details: dict
    ) -> tuple[str, BatchErrorType, dict] | None:
        if not (isinstance(exc, IndexError) or exc_type == "IndexError"):
            return None
        return (
            tr(
                "batch.error.incompatible",
                default="File structure incompatible with preset - check track configuration: {name}",
                name=item.display_name,
            ),
            BatchErrorType.INCOMPATIBLE_FILE,
            details,
        )

    def _classify_key_error(
        self, exc: Exception, _item: BatchItem, _exc_str: str, exc_type: str, details: dict
    ) -> tuple[str, BatchErrorType, dict] | None:
        if not (isinstance(exc, KeyError) or exc_type == "KeyError"):
            return None
        return (
            tr(
                "batch.error.validation",
                default="Configuration validation failed - missing required field: {msg}",
                msg=str(exc),
            ),
            BatchErrorType.VALIDATION_ERROR,
            details,
        )

    def _classify_value_error(
        self, exc: Exception, _item: BatchItem, _exc_str: str, exc_type: str, details: dict
    ) -> tuple[str, BatchErrorType, dict] | None:
        if not (isinstance(exc, ValueError) or exc_type == "ValueError"):
            return None
        return (
            tr("batch.error.validation_value", default="Validation error: {msg}", msg=str(exc)),
            BatchErrorType.VALIDATION_ERROR,
            details,
        )

    def _classify_tool_error(
        self, exc: Exception, _item: BatchItem, exc_str: str, _exc_type: str, details: dict
    ) -> tuple[str, BatchErrorType, dict] | None:
        if not any(tool in exc_str for tool in ("mkvmerge", "ffmpeg", "mkvextract", "mkvpropedit")):
            return None
        tool_name = (
            "mkvmerge"
            if "mkvmerge" in exc_str
            else "ffmpeg"
            if "ffmpeg" in exc_str
            else "external tool"
        )
        return (
            tr(
                "batch.error.tool",
                default="{tool} failed - check tool installation and file integrity: {msg}",
                tool=tool_name,
                msg=str(exc)[:100],
            ),
            BatchErrorType.TOOL_ERROR,
            details,
        )

    def _classify_corrupted_error(
        self, _exc: Exception, item: BatchItem, exc_str: str, _exc_type: str, details: dict
    ) -> tuple[str, BatchErrorType, dict] | None:
        if not any(word in exc_str for word in ("corrupt", "invalid", "malformed", "damaged")):
            return None
        return (
            tr(
                "batch.error.corrupted",
                default="File appears corrupted or invalid: {name}",
                name=item.display_name,
            ),
            BatchErrorType.CORRUPTED_FILE,
            details,
        )

    def validate_batch_items(
        self,
        items: list[BatchItem],
        config: BatchConfig,
    ) -> dict[str, list[str]]:
        """Pre-validate batch items before processing.

        Args:
            items: List of batch items to validate
            config: Batch configuration

        Returns:
            Dictionary mapping item IDs to list of validation warnings
        """
        warnings: dict[str, list[str]] = {}

        for item in items:
            item_warnings = self._validate_batch_item(item, config)
            if item_warnings:
                warnings[item.id] = item_warnings

        return warnings

    def _validate_batch_item(self, item: BatchItem, config: BatchConfig) -> list[str]:
        warnings: list[str] = []
        warnings.extend(self._validate_item_path(item))
        warnings.extend(self._validate_cleanmkv_preset(config))
        warnings.extend(self._validate_pipeline_preset(config))
        return warnings

    def _validate_item_path(self, item: BatchItem) -> list[str]:
        warnings: list[str] = []
        if not item.path.exists():
            warnings.append(
                tr(
                    "batch.validation.path_not_exists",
                    default="Path does not exist: {path}",
                    path=str(item.path),
                )
            )
            return warnings
        if not item.path.is_dir():
            warnings.append(
                tr(
                    "batch.validation.not_directory",
                    default="Path is not a directory: {path}",
                    path=str(item.path),
                )
            )
            return warnings
        try:
            list(item.path.iterdir())
        except PermissionError:
            warnings.append(
                tr(
                    "batch.validation.no_permission",
                    default="No read permission for: {path}",
                    path=str(item.path),
                )
            )
        except Exception:  # nosec B110
            pass
        return warnings

    def _validate_cleanmkv_preset(self, config: BatchConfig) -> list[str]:
        if not config.preset:
            return []
        from framekit.core.paths import get_cleanmkv_presets_dir, get_config_dir

        preset_exists = any(
            (directory / f"{config.preset}.yaml").exists()
            for directory in [
                get_cleanmkv_presets_dir(),
                get_cleanmkv_presets_dir(get_config_dir()),
            ]
        )
        if preset_exists:
            return []
        return [
            tr(
                "batch.validation.preset_not_found",
                default="CleanMKV preset not found: {preset}",
                preset=config.preset,
            )
        ]

    def _validate_pipeline_preset(self, config: BatchConfig) -> list[str]:
        if not config.pipeline_preset:
            return []
        from framekit.core.paths import get_config_dir, get_pipeline_presets_dir

        preset_exists = any(
            (directory / f"{config.pipeline_preset}.yaml").exists()
            for directory in [
                get_pipeline_presets_dir(),
                get_pipeline_presets_dir(get_config_dir()),
            ]
        )
        if preset_exists:
            return []
        return [
            tr(
                "batch.validation.pipeline_preset_not_found",
                default="Pipeline preset not found: {preset}",
                preset=config.pipeline_preset,
            )
        ]

    # ----- per-item pipeline run -----

    def _run_pipeline_for_item(
        self,
        item: BatchItem,
        config: BatchConfig,
        pipeline_runner: Callable,
        dashboard: BatchDashboard | None = None,
        cancel_event: threading.Event | None = None,
    ) -> BatchResult:
        """Run the pipeline runner for a single item, wiring step updates to the dashboard."""
        start = time.time()
        pipeline_results: dict[str, dict] | None = None

        def _step_callback(module_name: str, label: str) -> None:
            if cancel_event and cancel_event.is_set():
                raise KeyboardInterrupt
            item.current_module = module_name
            item.current_step = label
            if dashboard:
                dashboard.update_module_progress(module_name, 0.0, step=label)
                dashboard.add_log_entry(
                    tr(
                        "batch.log.step",
                        default="{name}: {module}",
                        name=item.display_name,
                        module=label,
                    ),
                    style="cyan",
                )

        def _result_callback(results: dict[str, dict]) -> None:
            nonlocal pipeline_results
            pipeline_results = results

        kwargs = config.to_pipeline_kwargs()
        # Dashboard owns the TTY: pipeline MUST run non-interactively or it will deadlock
        # waiting for prompts (cleanmkv confirm, nfo selectors, etc.). Force auto_mode.
        if dashboard is not None:
            kwargs["auto_mode"] = True

        if _pipeline_accepts_step_callback(pipeline_runner):
            kwargs["step_callback"] = _step_callback
        if _pipeline_accepts_result_callback(pipeline_runner):
            kwargs["result_callback"] = _result_callback

        try:
            exit_code = pipeline_runner(path=str(item.path), **kwargs)
        except KeyboardInterrupt:
            item.status = BatchStatus.FAILED
            item.error_message = tr("batch.release.interrupted", default="Interrupted by user")
            item.current_module = None
            item.current_step = None
            duration = time.time() - start
            item.processing_time = duration
            raise
        except Exception as exc:
            # Categorize the error for better user feedback
            error_message, error_type, error_details = self._categorize_error(exc, item)

            item.status = BatchStatus.FAILED
            item.error_message = error_message
            item.error_type = error_type
            item.error_details = error_details
            item.current_module = None
            item.current_step = None
            duration = time.time() - start
            item.processing_time = duration

            # Log full traceback for debugging
            logger.error(
                f"Batch item failed: {item.display_name} ({error_type.value})\n"
                f"Error: {error_message}\n"
                f"Traceback:\n{traceback.format_exc()}"
            )

            return BatchResult(item=item, exit_code=1, duration_seconds=duration)

        if exit_code == 0:
            item.status = BatchStatus.COMPLETED
        else:
            item.status = BatchStatus.FAILED
            failed_module, pipeline_error = _pipeline_failure_summary(
                pipeline_results, item.current_module
            )
            module_log_file = get_module_log_file(failed_module)
            if pipeline_error:
                item.error_message = tr(
                    "batch.release.failed_at_module_detail",
                    default="[{module}] failed — exit code {code}: {error}",
                    module=failed_module,
                    code=exit_code,
                    error=pipeline_error,
                )
            else:
                item.error_message = tr(
                    "batch.release.failed_at_module",
                    default="[{module}] failed — exit code {code}",
                    module=failed_module,
                    code=exit_code,
                )
            item.error_type = BatchErrorType.TOOL_ERROR
            item.error_details = {
                "exit_code": exit_code,
                "item_path": str(item.path),
                "current_module": item.current_module,
                "failed_module": failed_module,
            }
            if pipeline_error:
                item.error_details["pipeline_error"] = pipeline_error
            if module_log_file is not None:
                item.error_details["module_log_file"] = str(module_log_file)
            logger.error(
                f"Batch pipeline failed: {item.display_name} module={failed_module} "
                f"code={exit_code} error={pipeline_error or 'unknown'} "
                f"log={module_log_file or 'n/a'}"
            )

        item.current_module = None
        item.current_step = None
        duration = time.time() - start
        item.processing_time = duration
        return BatchResult(item=item, exit_code=exit_code, duration_seconds=duration)

    # ----- helpers -----

    def _cancel_requested(self, dashboard: BatchDashboard | None) -> bool:
        if self.is_cancelled():
            return True
        if dashboard and dashboard.cancelled:
            print_info(
                tr(
                    "batch.info.cancelled_by_dashboard",
                    default="Batch processing cancelled by user",
                )
            )
            return True
        return False

    def _wait_while_paused(self, dashboard: BatchDashboard | None) -> None:
        while True:
            paused = self.is_paused() or (dashboard and dashboard.paused)
            if not paused or self._cancel_requested(dashboard):
                return
            time.sleep(0.1)
