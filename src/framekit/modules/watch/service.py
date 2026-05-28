"""Main watcher service for Watch Mode."""

from __future__ import annotations

import json
import os
import signal
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Thread

from loguru import logger
from rich.console import Console
from rich.table import Table
from watchfiles import Change, watch

from .handler import FileHandler
from .models import WatchConfig, WatchFolder, WatchStatus
from .notifier import WindowsNotifier
from .validator import FileValidator

# Project-local PID file. Lives next to the active framekit.yaml so a stop
# command issued from the same working directory always targets the right
# instance.
WATCH_PID_FILENAME = ".framekit_watch.pid"


def _pid_file_path() -> Path:
    return Path.cwd() / WATCH_PID_FILENAME


def read_running_watcher_pid() -> int | None:
    """Return the PID of a running watcher, or ``None`` if none is alive."""
    pid_path = _pid_file_path()
    if not pid_path.exists():
        return None
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    if pid <= 0 or not _pid_is_alive(pid):
        # Stale PID file — remove it so subsequent calls do not loop.
        with _suppress_oserror():
            pid_path.unlink()
        return None
    return pid


def stop_running_watcher(timeout_seconds: float = 10.0) -> bool:
    """Signal a running watcher to stop. Return ``True`` on success.

    Sends ``SIGTERM`` on POSIX. On Windows the equivalent is
    ``CTRL_BREAK_EVENT`` when the watcher runs in its own process group;
    otherwise falls back to ``TerminateProcess`` via ``os.kill``. The function
    waits up to ``timeout_seconds`` for the PID file to disappear.
    """
    pid = read_running_watcher_pid()
    if pid is None:
        return False

    try:
        if sys.platform == "win32":
            # Plain os.kill on Windows maps to TerminateProcess for SIGTERM
            # and to GenerateConsoleCtrlEvent for CTRL_BREAK_EVENT. The
            # watcher catches SIGINT/SIGTERM in _setup_signal_handlers.
            try:
                os.kill(pid, signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
            except (AttributeError, OSError):
                os.kill(pid, signal.SIGTERM)
        else:
            os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        with _suppress_oserror():
            _pid_file_path().unlink(missing_ok=True)
        return False
    except OSError as exc:
        logger.error(f"Cannot signal watcher pid {pid}: {exc}")
        return False

    deadline = time.monotonic() + max(0.0, timeout_seconds)
    while time.monotonic() < deadline:
        if read_running_watcher_pid() is None:
            return True
        time.sleep(0.2)
    return read_running_watcher_pid() is None


def _pid_is_alive(pid: int) -> bool:
    """Cross-platform liveness probe for a process id."""
    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return False
            exit_code = ctypes.c_ulong(0)
            kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            kernel32.CloseHandle(handle)
            STILL_ACTIVE = 259
            return exit_code.value == STILL_ACTIVE
        except Exception:  # pragma: no cover - defensive: assume not alive
            return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, OSError):
        return False


class _suppress_oserror:
    """Context manager analogous to ``contextlib.suppress(OSError)``.

    Implemented locally so we don't have to import contextlib for one usage.
    """

    def __enter__(self) -> None:  # pragma: no cover - trivial
        return None

    def __exit__(self, exc_type, exc, tb) -> bool:
        return exc_type is not None and issubclass(exc_type, OSError)


class WatcherService:
    """Main service for watching folders and processing files."""

    def __init__(self, config: WatchConfig, embedded: bool = False):
        """Initialise the watcher service.

        Args:
            config: Watch configuration (folders, validation, notifications, …).
            embedded: When *True* the service runs inside a larger host process
                (e.g. ``framekit serve``).  Three behaviours change:

                * Signal handlers are **not** installed — the host process owns
                  its own signal lifecycle.
                * The ``.framekit_watch.pid`` file is **not** written or removed
                  so that ``framekit watch stop`` cannot accidentally terminate
                  the host service process.
                * ``start()`` returns immediately after launching background
                  threads instead of blocking in a ``while`` loop.
        """
        self.config = config
        self._embedded = embedded
        self.processing_queue: Queue = Queue()
        self.stop_event = Event()
        self.processing_thread: Thread | None = None
        self._watch_threads: list[Thread] = []

        self.validator = FileValidator(
            config.validation, config.extensions, config.ignore_extensions
        )
        self.notifier = WindowsNotifier(config.notifications)
        self.handler = FileHandler(config, self.validator, self.notifier, self.processing_queue)

        self.status = WatchStatus()
        self.start_time: float | None = None

        if not self._embedded:
            self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown.

        Signals may only be installed from the main thread. Skip silently when
        the service runs inside a worker thread (tests, embedded mode).
        """

        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, stopping watch mode...")
            self.stop()
            sys.exit(0)

        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except ValueError:
            logger.debug("Signal handlers skipped (not running in main thread).")

    def _validate_configuration(self) -> None:
        """Validate the watch configuration."""
        if not self.config.folders:
            raise ValueError("No folders configured for watching")

        enabled_folders = [f for f in self.config.folders if f.enabled]
        if not enabled_folders:
            raise ValueError("No enabled folders configured for watching")

        for folder in enabled_folders:
            if not folder.path.exists():
                raise ValueError(f"Watch folder does not exist: {folder.path}")
            if not folder.path.is_dir():
                raise ValueError(f"Watch path is not a directory: {folder.path}")

    def _create_folders(self) -> None:
        """Create necessary folders (failed, etc.)."""
        for folder in self.config.folders:
            if not folder.enabled:
                continue
            if self.config.error_handling.move_on_error:
                failed_folder = folder.path / self.config.error_handling.failed_folder
                failed_folder.mkdir(exist_ok=True)
                logger.info(f"Created failed folder: {failed_folder}")

    def _watch_folder(self, folder_path: Path) -> None:
        """Watch a single folder using watchfiles, dispatching events to the handler."""
        logger.info(f"watchfiles: starting watch on {folder_path}")
        try:
            for changes in watch(str(folder_path), stop_event=self.stop_event):
                for change_type, path_str in changes:
                    file_path = Path(path_str)
                    if file_path.is_dir():
                        continue
                    if change_type == Change.added:
                        self.handler.on_created(file_path)
                    elif change_type == Change.modified:
                        self.handler.on_modified(file_path)
        except Exception as e:
            if not self.stop_event.is_set():
                logger.exception(f"Error in watch thread for {folder_path}: {e}")
        logger.info(f"watchfiles: stopped watch on {folder_path}")

    def _process_queue(self) -> None:
        """Process files from the queue."""
        logger.info("Processing thread started")
        while not self.stop_event.is_set():
            try:
                file_path = self.processing_queue.get(timeout=1.0)
                folder_config = self._find_folder_config(file_path)
                if not folder_config:
                    logger.warning(f"No folder configuration found for: {file_path}")
                    continue

                is_valid, reason = self.validator.validate(file_path)
                if not is_valid:
                    logger.info(f"File validation failed: {file_path.name} - {reason}")
                    continue

                self.status.files_processing += 1
                self.status.last_activity = datetime.now()

                result = self.handler.process_file(file_path, folder_config.preset)

                self.status.files_processing -= 1

                if result.success:
                    self.status.files_processed += 1
                    logger.info(f"File processed successfully: {file_path.name}")
                else:
                    self.status.files_failed += 1
                    logger.error(f"File processing failed: {file_path.name}")
                    if result.error:
                        self.handler.handle_failed_file(file_path, result.error)

                self.status.last_activity = datetime.now()

            except Empty:
                continue
            except Exception as e:
                logger.exception(f"Error in processing thread: {e}")

        logger.info("Processing thread stopped")

    def _find_folder_config(self, file_path: Path) -> WatchFolder | None:
        """Find the folder configuration for a file."""
        for folder in self.config.folders:
            if not folder.enabled:
                continue
            try:
                file_path.relative_to(folder.path)
                return folder
            except ValueError:
                continue
        return None

    def start(self) -> None:
        """Start the watcher service."""
        logger.info("Starting watch mode...")

        self._validate_configuration()
        self._create_folders()

        enabled_folders = [f for f in self.config.folders if f.enabled]

        self.stop_event.clear()

        if not self._embedded:
            self._write_pid_file()

        for folder in enabled_folders:
            t = Thread(target=self._watch_folder, args=(folder.path,), daemon=True)
            t.start()
            self._watch_threads.append(t)
            logger.info(f"Watching folder: {folder.path} (preset: {folder.preset})")

        self.processing_thread = Thread(target=self._process_queue, daemon=True)
        self.processing_thread.start()

        self.status.running = True
        self.status.folders_watched = [str(f.path) for f in enabled_folders]
        self.status.start_time = datetime.now()
        self.start_time = time.time()

        if enabled_folders:
            self.status.preset_name = enabled_folders[0].preset

        self.notifier.notify_watch_started(self.status.folders_watched)
        logger.info(f"Watch mode started, monitoring {len(enabled_folders)} folder(s)")

        if self._embedded:
            # In embedded mode the caller owns the process lifecycle.
            # Return immediately; background threads run as daemons.
            return

        try:
            while self.status.running:
                time.sleep(1)
                if self.start_time:
                    self.status.uptime = time.time() - self.start_time
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            self.stop()

    def stop(self) -> None:
        """Stop the watcher service."""
        if not self.status.running:
            logger.warning("Watch mode is not running")
            self._remove_pid_file()
            return

        logger.info("Stopping watch mode...")

        self.stop_event.set()

        for t in self._watch_threads:
            t.join(timeout=5.0)
        self._watch_threads.clear()

        if self.processing_thread:
            self.processing_thread.join(timeout=5.0)

        self.status.running = False
        if not self._embedded:
            self._remove_pid_file()
        self.notifier.notify_watch_stopped()
        logger.info("Watch mode stopped")

    def _write_pid_file(self) -> None:
        path = _pid_file_path()
        try:
            path.write_text(str(os.getpid()), encoding="utf-8")
        except OSError as exc:
            logger.warning(f"Could not write watcher PID file at {path}: {exc}")

    def _remove_pid_file(self) -> None:
        path = _pid_file_path()
        try:
            if path.exists():
                pid_in_file = int(path.read_text(encoding="utf-8").strip() or "0")
                if pid_in_file in (0, os.getpid()):
                    path.unlink()
        except (OSError, ValueError) as exc:
            logger.debug(f"Could not clean up watcher PID file: {exc}")

    def get_status(self) -> WatchStatus:
        """Get current status."""
        if self.start_time and self.status.running:
            self.status.uptime = time.time() - self.start_time
        self.status.files_in_queue = self.processing_queue.qsize()
        return self.status

    def display_status(self, json_output: bool = False) -> None:
        """Display current watch status."""
        console = Console()
        status = self.get_status()

        if json_output:
            console.print(json.dumps(status.to_dict(), indent=2))
            return

        table = Table(title="Watch Mode Status", show_header=True)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        status_icon = "🟢 Active" if status.running else "🔴 Inactive"
        table.add_row("Status", status_icon)

        if status.folders_watched:
            for i, folder in enumerate(status.folders_watched):
                label = "Directory" if i == 0 else ""
                table.add_row(label, folder)

        table.add_row("Preset", status.preset_name)
        table.add_row("Uptime", self._format_uptime(status.uptime_seconds()))
        table.add_row("Files Monitored", str(status.files_monitored))
        table.add_row("Files Processed", str(status.files_processed))
        table.add_row("Files Failed", str(status.files_failed))
        table.add_row("Queue Size", str(status.files_in_queue))
        table.add_row("Errors", str(status.errors_count))

        if status.last_activity:
            table.add_row("Last Activity", status.last_activity.strftime("%Y-%m-%d %H:%M:%S"))

        console.print(table)

        if status.recent_events:
            self._display_recent_events(status.recent_events, console)

    def _format_uptime(self, seconds: float) -> str:
        """Format uptime in human-readable format."""
        td = timedelta(seconds=int(seconds))
        days = td.days
        hours, remainder = divmod(td.seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        parts.append(f"{secs}s")
        return " ".join(parts)

    def _display_recent_events(self, events: list, console: Console) -> None:
        """Display recent watch events."""
        if not events:
            return
        event_table = Table(title="Recent Events (Last 10)", show_header=True)
        event_table.add_column("Time", style="dim")
        event_table.add_column("Event", style="yellow")
        event_table.add_column("File", style="blue")
        for event in events[-10:]:
            event_table.add_row(
                event.get("time", ""),
                event.get("type", ""),
                event.get("file", ""),
            )
        console.print(event_table)
