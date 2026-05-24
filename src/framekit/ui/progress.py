from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Protocol

from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from framekit.core.i18n import tr
from framekit.ui.console import console


class ProgressAdvance(Protocol):
    """Callable protocol for advancing a progress indicator."""

    def __call__(self, amount: int = 1, *, files: int = 0) -> None:
        """Advance the progress indicator by ``amount`` units and ``files`` files."""
        ...


def _format_bytes(value: float | int | None) -> str:
    """Format bytes into human-readable format."""
    number = float(value or 0)
    units = ("B", "KB", "MB", "GB", "TB")
    for index, unit in enumerate(units):
        if number < 1024 or index == len(units) - 1:
            if unit == "B":
                return f"{int(number)} B"
            return f"{number:.2f} {unit}"
        number /= 1024
    return f"{number:.2f} TB"


def _transfer_column(total: int | None, *, is_bytes: bool) -> str:
    if is_bytes:
        return "[progress.bar]{task.fields[transfer]}"
    return "[progress.bar]{task.completed}/{task.total}" if total else ""


def _update_metrics_state(metrics, *, success: bool | None, skipped: bool) -> None:
    if success is True:
        metrics.increment_completed()
        return
    if success is False:
        metrics.increment_failed()
        return
    if skipped:
        metrics.increment_skipped()


def _print_summary(total: int, metrics, *, total_bytes: int | None) -> None:
    console.print()
    console.print("[bold]Summary:[/bold]")
    console.print(f"  Total: {total}")
    console.print(f"  Completed: {metrics.completed_items}")
    console.print(f"  Failed: {metrics.failed_items}")
    console.print(f"  Skipped: {metrics.skipped_items}")
    console.print(f"  Success Rate: {metrics.success_rate:.1f}%")
    if total_bytes:
        console.print(f"  Compression: {metrics.compression_ratio:.1f}%")


def _console_has_active_live_display() -> bool:
    """Return True when Rich Live is already active on the shared console."""
    live = getattr(console, "_live", None)
    return live is not None


@contextmanager
def framekit_progress(
    label: str,
    *,
    total: int | None = None,
    unit: str = "count",
    total_files: int | None = None,
    show_bar: bool = True,
    show_eta: bool = True,
) -> Generator[ProgressAdvance, None, None]:
    """Create a Framekit-styled progress bar.

    Args:
        label: Description text for the progress bar
        total: Total number of items to process
        unit: Unit type ('count' or 'bytes')
        total_files: Total number of files (optional)
        show_bar: Whether to show the bar column
        show_eta: Whether to show the remaining time column

    Yields:
        ProgressAdvance: Function to advance the progress bar
    """
    if _console_has_active_live_display():
        # A parent dashboard already owns the terminal Live context.
        # Returning a no-op avoids nested LiveError while preserving callbacks.
        def advance(_amount: int = 1, *, files: int = 0) -> None:
            _ = files
            return None

        yield advance
        return

    is_bytes = unit == "bytes"
    columns: list = [
        SpinnerColumn(),
        TextColumn("[progress.bar]{task.description}"),
    ]
    if show_bar:
        columns.append(
            BarColumn(
                complete_style="progress.complete",
                finished_style="progress.complete",
                bar_width=20,
            )
        )
    columns.append(TextColumn(_transfer_column(total, is_bytes=is_bytes)))
    if total_files is not None:
        columns.append(TextColumn("[progress.bar]{task.fields[files]}"))
    columns.append(TimeElapsedColumn())
    if show_eta:
        columns.append(TimeRemainingColumn())
    progress = Progress(
        *columns,
        console=console,
        transient=True,
    )
    with progress:
        task = progress.add_task(
            label or tr("common.processing", default="Processing"),
            total=total,
            transfer=(f"0 B / {_format_bytes(total)}" if is_bytes else ""),
            files=(f"0/{total_files} files" if total_files is not None else ""),
            files_done=0,
        )

        def advance(amount: int = 1, *, files: int = 0) -> None:
            if amount:
                progress.advance(task, amount)
            current = progress.tasks[task]
            if files:
                done = int(current.fields.get("files_done", 0)) + files
                progress.update(task, files_done=done)
                if total_files is not None:
                    progress.update(task, files=f"{done}/{total_files} files")
            if is_bytes:
                completed = current.completed
                progress.update(
                    task,
                    transfer=f"{_format_bytes(completed)} / {_format_bytes(total)}",
                )

        yield advance


class EnhancedProgressAdvance(Protocol):
    """Callable protocol for advancing enhanced progress with metrics."""

    def __call__(
        self,
        amount: int = 1,
        *,
        success: bool | None = None,
        skipped: bool = False,
    ) -> None:
        """Advance the progress indicator with metrics tracking."""
        ...


@contextmanager
def enhanced_progress(
    label: str,
    *,
    total: int | None = None,
    unit: str = "count",
    total_bytes: int | None = None,
    show_metrics: bool = False,
    show_summary: bool = False,
) -> Generator[EnhancedProgressAdvance, None, None]:
    """Create an enhanced progress bar with metrics tracking.

    Args:
        label: Description text for the progress bar
        total: Total number of items to process
        unit: Unit type ('count' or 'bytes')
        total_bytes: Total bytes to process (for compression tracking)
        show_metrics: Whether to show detailed metrics
        show_summary: Whether to show summary after completion

    Yields:
        EnhancedProgressAdvance: Function to advance the progress bar with metrics
    """
    if _console_has_active_live_display():
        def advance(
            _amount: int = 1,
            *,
            success: bool | None = None,
            skipped: bool = False,
        ) -> None:
            _ = success
            _ = skipped
            return None

        yield advance
        return

    from framekit.core.reporting import ProgressMetrics

    metrics = ProgressMetrics(
        total_items=total or 0,
        total_bytes=total_bytes or 0,
    )

    is_bytes = unit == "bytes"
    columns: list = [
        SpinnerColumn(),
        TextColumn("[progress.bar]{task.description}"),
    ]

    columns.append(
        BarColumn(
            complete_style="progress.complete",
            finished_style="progress.complete",
            bar_width=20,
        )
    )

    if show_metrics:
        columns.append(TextColumn("[progress.bar]{task.fields[metrics]}"))

    columns.append(TextColumn(_transfer_column(total, is_bytes=is_bytes)))

    columns.append(TimeElapsedColumn())
    columns.append(TimeRemainingColumn())

    progress = Progress(
        *columns,
        console=console,
        transient=True,
    )

    with progress:
        task = progress.add_task(
            label or tr("common.processing", default="Processing"),
            total=total,
            transfer=(f"0 B / {_format_bytes(total_bytes)}" if is_bytes else ""),
            metrics="",
        )

        def advance(
            amount: int = 1,
            *,
            success: bool | None = None,
            skipped: bool = False,
        ) -> None:
            if amount:
                progress.advance(task, amount)

            _update_metrics_state(metrics, success=success, skipped=skipped)

            if is_bytes:
                metrics.add_bytes(amount)

            # Update display
            current = progress.tasks[task]
            if is_bytes:
                completed = current.completed
                progress.update(
                    task,
                    transfer=f"{_format_bytes(completed)} / {_format_bytes(total_bytes)}",
                )

            if show_metrics:
                rate = format_rate(metrics.processing_rate)
                success_pct = f"{metrics.success_rate:.1f}%"
                progress.update(
                    task,
                    metrics=f"{rate} | {success_pct} success",
                )

        yield advance

    if show_summary and total:
        _print_summary(total, metrics, total_bytes=total_bytes)


def format_rate(rate: float) -> str:
    """Format processing rate."""
    return f"{rate:.2f} items/s"


def format_bytes_rate(bytes_per_sec: float) -> str:
    """Format bytes per second rate."""
    return f"{_format_bytes(bytes_per_sec)}/s"


def format_compression_ratio(ratio: float) -> str:
    """Format compression ratio as percentage."""
    return f"{ratio:.1f}%"


def format_eta_time(seconds: float) -> str:
    """Format ETA in human-readable format."""
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        minutes = int(seconds / 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    hours = int(seconds / 3600)
    minutes = int((seconds % 3600) / 60)
    return f"{hours}h {minutes}m"
