"""Real-time monitoring dashboard for batch processing."""

from __future__ import annotations

import contextlib
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

from rich.align import Align
from rich.console import Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TaskID, TextColumn
from rich.table import Table
from rich.text import Text

from framekit.core.i18n import tr
from framekit.modules.batch.models import BatchItem, BatchStatus
from framekit.ui.console import console


@dataclass
class DashboardStats:
    """Aggregated counters + timing for the dashboard."""

    total: int = 0
    completed: int = 0
    failed: int = 0
    processing: int = 0
    pending: int = 0
    start_time: float = field(default_factory=time.time)
    current_item_start: float | None = None

    @property
    def elapsed_seconds(self) -> float:
        """Handle elapsed seconds."""
        return time.time() - self.start_time

    @property
    def current_item_elapsed(self) -> float:
        """Handle current item elapsed."""
        if self.current_item_start is None:
            return 0.0
        return time.time() - self.current_item_start

    @property
    def average_time_per_item(self) -> float:
        """Handle average time per item."""
        if self.completed == 0:
            return 0.0
        return self.elapsed_seconds / self.completed

    @property
    def estimated_remaining_seconds(self) -> float:
        """Handle estimated remaining seconds."""
        if self.completed == 0:
            return 0.0
        remaining = self.total - self.completed - self.failed
        return self.average_time_per_item * max(remaining, 0)

    @property
    def success_rate(self) -> float:
        """Handle success rate."""
        processed = self.completed + self.failed
        if processed == 0:
            return 0.0
        return (self.completed / processed) * 100


@dataclass
class LogEntry:
    """Single activity-log entry."""

    timestamp: datetime
    message: str
    style: str = "white"


def _fmt_hms(seconds: float) -> str:
    """Format seconds as H:MM:SS or M:SS."""
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


class BatchDashboard:
    """Real-time Rich-Live dashboard for batch processing."""

    def __init__(self, items: list[BatchItem], refresh_rate: float = 0.5) -> None:
        self.items = items
        self.refresh_rate = refresh_rate

        # Count only enabled items
        enabled = [it for it in items if it.enabled]
        self.stats = DashboardStats(total=len(enabled), pending=len(enabled))

        # Current state
        self.current_item: BatchItem | None = None
        self.current_module: str | None = None
        self.current_step: str | None = None
        self.module_progress: float = 0.0

        # Activity log
        self.log_entries: deque[LogEntry] = deque(maxlen=10)

        # Control flags
        self.paused = False
        self.cancelled = False
        self.stopped = False
        self._lock = threading.Lock()

        # Live + layout objects
        self._live: Live | None = None
        self._layout: Layout | None = None
        self._progress: Progress | None = None
        self._main_task: TaskID | None = None
        self._module_task: TaskID | None = None

        # Background threads
        self._heartbeat_thread: threading.Thread | None = None
        self._keyboard_thread: threading.Thread | None = None
        self._keyboard_enabled = sys.stdin.isatty()

    # ----- lifecycle -----

    def start(self) -> None:
        """Initialize layout, start Live + heartbeat + keyboard threads."""
        self._layout = Layout()
        self._layout.split_column(
            Layout(name="header", size=5),
            Layout(name="queue", size=3),
            Layout(name="current", size=6),
            Layout(name="log", ratio=1),
            Layout(name="controls", size=3),
        )

        self._progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(complete_style="green", finished_style="bold green"),
            TextColumn("[progress.percentage]{task.percentage:>5.1f}%"),
            TextColumn("({task.completed}/{task.total})"),
            console=console,
            expand=True,
        )
        self._main_task = self._progress.add_task(
            tr("dashboard.progress.overall", default="Overall progress"),
            total=max(self.stats.total, 1),
        )
        self._module_task = self._progress.add_task(
            tr("dashboard.progress.module", default="Module progress"),
            total=100,
            visible=False,
        )

        self._live = Live(
            self._render(),
            console=console,
            refresh_per_second=max(1.0, 1.0 / self.refresh_rate),
            screen=False,
        )
        self._live.start()

        # Heartbeat: keeps elapsed / ETA fresh while pipeline_runner is blocking
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

        if self._keyboard_enabled:
            self._keyboard_thread = threading.Thread(target=self._keyboard_listener, daemon=True)
            self._keyboard_thread.start()

        self.add_log_entry(
            tr("dashboard.log.started", default="Batch processing started"),
            style="cyan",
        )

    def stop(self) -> None:
        """Stop Live and print a final summary."""
        self.stopped = True
        if self._live:
            with contextlib.suppress(Exception):
                self._live.stop()
        self._print_final_summary()

    # ----- update API (used by BatchService) -----

    def _enabled_items(self) -> list[BatchItem]:
        return [item for item in self.items if item.enabled]

    def _count_items_with_status(self, items: list[BatchItem], status: BatchStatus) -> int:
        return sum(1 for item in items if item.status == status)

    def update_queue_status(self) -> None:
        """Recompute counters from the items list and refresh the main bar."""
        enabled = self._enabled_items()
        self.stats.total = len(enabled)
        self.stats.completed = self._count_items_with_status(enabled, BatchStatus.COMPLETED)
        self.stats.failed = self._count_items_with_status(enabled, BatchStatus.FAILED)
        self.stats.processing = self._count_items_with_status(enabled, BatchStatus.PROCESSING)
        self.stats.pending = self._count_items_with_status(enabled, BatchStatus.PENDING)

        if self._progress and self._main_task is not None:
            done = self.stats.completed + self.stats.failed
            self._progress.update(self._main_task, completed=done, total=max(self.stats.total, 1))

        self._refresh_display()

    def update_current_item(self, item: BatchItem) -> None:
        """Mark a new item as the one being processed."""
        with self._lock:
            self.current_item = item
            self.current_module = None
            self.current_step = None
            self.module_progress = 0.0
            self.stats.current_item_start = time.time()
            if self._progress and self._module_task is not None:
                self._progress.update(self._module_task, visible=False)

        self.add_log_entry(
            tr("dashboard.log.started_item", default="Started: {name}", name=item.display_name),
            style="cyan",
        )

    def update_module_progress(
        self, module_name: str, progress: float = 0.0, step: str | None = None
    ) -> None:
        """Update current module + step within the current item."""
        with self._lock:
            self.current_module = module_name
            self.current_step = step
            self.module_progress = progress
            if self.current_item is not None:
                self.current_item.current_module = module_name
                self.current_item.current_step = step
            if self._progress and self._module_task is not None:
                desc = f"  {module_name}" + (f" - {step}" if step else "")
                self._progress.update(
                    self._module_task,
                    description=desc,
                    completed=progress,
                    visible=True,
                )
        self._refresh_display()

    def add_log_entry(self, message: str, style: str = "white") -> None:
        """Push a line to the activity log."""
        self.log_entries.append(LogEntry(timestamp=datetime.now(), message=message, style=style))
        self._refresh_display()

    def mark_item_completed(self, item: BatchItem) -> None:
        """Handle mark item completed."""
        with self._lock:
            item.status = BatchStatus.COMPLETED
            item.current_module = None
            item.current_step = None
        self.update_queue_status()
        self.add_log_entry(
            tr("dashboard.log.completed_item", default="Completed: {name}", name=item.display_name),
            style="green",
        )

    def mark_item_failed(self, item: BatchItem, error: str) -> None:
        """Handle mark item failed."""
        with self._lock:
            item.status = BatchStatus.FAILED
            item.error_message = error
            item.current_module = None
            item.current_step = None
        self.update_queue_status()
        self.add_log_entry(
            tr("dashboard.log.failed_item", default="Failed: {name}", name=item.display_name),
            style="red",
        )
        if error:
            self.add_log_entry(f"  {error}", style="bright_black")

    # ----- rendering -----

    def _render(self) -> Layout:
        if self._layout is None:
            return Layout()
        self._layout["header"].update(self._render_header())
        self._layout["queue"].update(self._render_queue_status())
        self._layout["current"].update(self._render_current_item())
        self._layout["log"].update(self._render_log())
        self._layout["controls"].update(self._render_controls())
        return self._layout

    def _render_header(self) -> Panel:
        elapsed_str = _fmt_hms(self.stats.elapsed_seconds)
        remaining = self.stats.estimated_remaining_seconds
        if remaining > 0:
            time_info = f"Elapsed: {elapsed_str} | ETA: ~{_fmt_hms(remaining)}"
        else:
            time_info = f"Elapsed: {elapsed_str}"

        done = self.stats.completed + self.stats.failed
        pct = (done / self.stats.total * 100) if self.stats.total > 0 else 0.0

        title = Text(tr("dashboard.title", default="Batch Processing Dashboard"), style="bold cyan")
        line = Text()
        line.append("Progress: ", style="white")
        line.append(f"{pct:.0f}%", style="bold cyan")
        line.append(f" ({done}/{self.stats.total})", style="bright_black")
        line.append(f"  |  {time_info}", style="bright_black")

        content = Group(
            Align.center(title),
            Align.center(line),
            self._progress if self._progress else Text(""),
        )
        return Panel(content, border_style="cyan", padding=(0, 1))

    def _render_queue_status(self) -> Panel:
        line = Text()
        line.append("[OK] ", style="green")
        line.append(
            tr(
                "dashboard.status.completed",
                default="Completed: {count}",
                count=self.stats.completed,
            ),
            style="green",
        )
        line.append("    ")
        line.append("[FAIL] ", style="red")
        line.append(
            tr("dashboard.status.failed", default="Failed: {count}", count=self.stats.failed),
            style="red",
        )
        line.append("    ")
        line.append("[RUN] ", style="yellow")
        line.append(
            tr(
                "dashboard.status.processing",
                default="Processing: {count}",
                count=self.stats.processing,
            ),
            style="yellow",
        )
        line.append("    ")
        line.append("[WAIT] ", style="bright_black")
        line.append(
            tr("dashboard.status.pending", default="Pending: {count}", count=self.stats.pending),
            style="bright_black",
        )
        if self.stats.completed + self.stats.failed > 0:
            line.append("\n")
            line.append(
                tr(
                    "dashboard.status.success_rate",
                    default="Success rate: {rate:.1f}%",
                    rate=self.stats.success_rate,
                ),
                style="cyan",
            )
        return Panel(
            Align.center(line),
            title=tr("dashboard.section.queue_status", default="Queue status"),
            border_style="cyan",
            padding=(0, 1),
        )

    def _render_current_item(self) -> Panel:
        if self.current_item is None:
            return Panel(
                Align.center(
                    Text(
                        tr("dashboard.current.none", default="No item currently processing"),
                        style="bright_black",
                    )
                ),
                title=tr("dashboard.section.current_item", default="Current item"),
                border_style="cyan",
                padding=(0, 1),
            )

        text = Text()
        text.append(tr("dashboard.current.release", default="Release: "), style="white")
        text.append(self.current_item.display_name, style="bold cyan")

        if self.current_module:
            text.append("\n")
            text.append(tr("dashboard.current.module", default="Module: "), style="white")
            text.append(self.current_module.upper(), style="yellow")
            if self.module_progress > 0:
                text.append(f" ({self.module_progress:.0f}%)", style="bright_black")

        if self.current_step:
            text.append("\n")
            text.append(tr("dashboard.current.step", default="Step: "), style="white")
            text.append(self.current_step, style="cyan")

        text.append("\n")
        text.append(
            tr(
                "dashboard.current.time",
                default="Time: {time}",
                time=_fmt_hms(self.stats.current_item_elapsed),
            ),
            style="bright_black",
        )
        return Panel(
            text,
            title=tr("dashboard.section.current_item", default="Current item"),
            border_style="cyan",
            padding=(0, 1),
        )

    def _render_log(self) -> Panel:
        if not self.log_entries:
            return Panel(
                Align.center(
                    Text(tr("dashboard.log.empty", default="No activity yet"), style="bright_black")
                ),
                title=tr("dashboard.section.activity_log", default="Recent activity"),
                border_style="cyan",
                padding=(0, 1),
            )
        text = Text()
        for entry in self.log_entries:
            text.append(f"[{entry.timestamp.strftime('%H:%M:%S')}] ", style="bright_black")
            text.append(entry.message, style=entry.style)
            text.append("\n")
        return Panel(
            text,
            title=tr("dashboard.section.activity_log", default="Recent activity"),
            border_style="cyan",
            padding=(0, 1),
        )

    def _render_controls(self) -> Panel:
        if not self._keyboard_enabled:
            return Panel(Text(""), border_style="cyan", padding=(0, 1))
        ctrl = Text()
        ctrl.append(tr("dashboard.controls.hint", default="Controls: "), style="bright_black")
        if self.paused:
            ctrl.append("[R]", style="bold yellow")
            ctrl.append(tr("dashboard.controls.resume", default="esume "), style="bright_black")
        else:
            ctrl.append("[P]", style="bold yellow")
            ctrl.append(tr("dashboard.controls.pause", default="ause "), style="bright_black")
        ctrl.append("[C]", style="bold red")
        ctrl.append(tr("dashboard.controls.cancel", default="ancel "), style="bright_black")
        ctrl.append("[Q]", style="bold cyan")
        ctrl.append(tr("dashboard.controls.quit", default="uit"), style="bright_black")
        return Panel(Align.center(ctrl), border_style="cyan", padding=(0, 1))

    def _refresh_display(self) -> None:
        if self._live and not self.stopped:
            with contextlib.suppress(Exception):
                self._live.update(self._render())

    # ----- background threads -----

    def _heartbeat_loop(self) -> None:
        """Periodically rebuild panels so elapsed-time / ETA stay current during long blocking calls."""
        while not self.stopped:
            time.sleep(self.refresh_rate)
            if self.stopped:
                break
            self._refresh_display()

    def _keyboard_listener(self) -> None:
        """Listen for control keys (P/R/C/Q) in a background thread."""
        try:
            import msvcrt  # Windows

            while not self.stopped:
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode("utf-8", errors="ignore").lower()
                    self._handle_key(key)
                time.sleep(0.1)
        except ImportError:
            import select
            import termios
            import tty

            old = termios.tcgetattr(sys.stdin)
            try:
                tty.setcbreak(sys.stdin.fileno())
                while not self.stopped:
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        key = sys.stdin.read(1).lower()
                        self._handle_key(key)
            finally:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)

    def _handle_key(self, key: str) -> None:
        if key == "p" and not self.paused:
            self.paused = True
            self.add_log_entry(tr("dashboard.log.paused", default="Paused"), style="yellow")
        elif key == "r" and self.paused:
            self.paused = False
            self.add_log_entry(tr("dashboard.log.resumed", default="Resumed"), style="green")
        elif key == "c":
            self.cancelled = True
            self.add_log_entry(
                tr("dashboard.log.cancelled", default="Cancelling batch processing..."),
                style="red",
            )
        elif key == "q":
            self.add_log_entry(
                tr("dashboard.log.quit", default="Dashboard closed (processing continues)"),
                style="cyan",
            )
            self.stop()

    # ----- final summary -----

    def _print_final_summary(self) -> None:
        console.print()
        table = Table(
            title=tr("dashboard.summary.title", default="Batch Processing Summary"),
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column(tr("dashboard.summary.metric", default="Metric"), style="white")
        table.add_column(
            tr("dashboard.summary.value", default="Value"), justify="right", style="cyan"
        )

        table.add_row(
            tr("dashboard.summary.total", default="Total releases"), str(self.stats.total)
        )
        table.add_row(
            tr("dashboard.summary.completed", default="Completed"),
            f"[green]{self.stats.completed}[/green]",
        )
        table.add_row(
            tr("dashboard.summary.failed", default="Failed"), f"[red]{self.stats.failed}[/red]"
        )
        if self.stats.completed + self.stats.failed > 0:
            table.add_row(
                tr("dashboard.summary.success_rate", default="Success rate"),
                f"{self.stats.success_rate:.1f}%",
            )
        table.add_row(
            tr("dashboard.summary.total_time", default="Total time"),
            _fmt_hms(self.stats.elapsed_seconds),
        )
        if self.stats.completed > 0:
            table.add_row(
                tr("dashboard.summary.avg_time", default="Avg time/release"),
                _fmt_hms(self.stats.average_time_per_item),
            )
        console.print(table)
        console.print()
