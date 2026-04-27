from __future__ import annotations

from collections.abc import Iterator
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
    def __call__(self, amount: int = 1, *, files: int = 0) -> None: ...


def _format_bytes(value: float | int | None) -> str:
    number = float(value or 0)
    units = ("B", "KB", "MB", "GB", "TB")
    for index, unit in enumerate(units):
        if number < 1024 or index == len(units) - 1:
            if unit == "B":
                return f"{int(number)} B"
            return f"{number:.2f} {unit}"
        number /= 1024
    return f"{number:.2f} TB"


@contextmanager
def framekit_progress(
    label: str,
    *,
    total: int | None = None,
    unit: str = "count",
    total_files: int | None = None,
) -> Iterator[ProgressAdvance]:
    is_bytes = unit == "bytes"
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold white]{task.description}"),
        BarColumn(),
        TextColumn(
            "{task.fields[transfer]}"
            if is_bytes
            else ("{task.completed}/{task.total}" if total else "")
        ),
        TextColumn("{task.fields[files]}" if total_files is not None else ""),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
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
