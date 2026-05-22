"""File event handler for Watch Mode."""

import threading
from datetime import datetime, timedelta
from pathlib import Path
from queue import Queue

from loguru import logger
from rich.console import Console

from .models import ProcessingResult, WatchConfig
from .notifier import WindowsNotifier
from .validator import FileValidator


class FileHandler:
    """Handles file system events for watched folders."""

    def __init__(
        self,
        config: WatchConfig,
        validator: FileValidator,
        notifier: WindowsNotifier,
        processing_queue: Queue,
    ):
        self.config = config
        self.validator = validator
        self.notifier = notifier
        self.processing_queue = processing_queue

        self.file_timestamps: dict[str, datetime] = {}
        self.processing_files: set[str] = set()
        self.status_update_interval = 30
        self.status_timer: threading.Timer | None = None
        self.start_time = datetime.now()
        self.files_processed = 0
        self.recent_events: list = []
        self.errors_count = 0
        self.console = Console()

    def on_created(self, file_path: Path) -> None:
        """Handle file creation event."""
        logger.info(f"File created: {file_path.name}")

        if self.validator.is_temporary(file_path):
            logger.debug(f"Ignoring temporary file: {file_path.name}")
            return

        if not self.validator.is_valid_extension(file_path):
            logger.debug(
                f"Ignoring file with invalid extension: {file_path.name} ({file_path.suffix})"
            )
            return

        self.file_timestamps[str(file_path)] = datetime.now()
        logger.info(
            f"File queued for validation: {file_path.name} (queue size: {self.processing_queue.qsize()})"
        )
        self.log_event("created", file_path)
        self.processing_queue.put(file_path)

    def on_modified(self, file_path: Path) -> None:
        """Handle file modification event."""
        if str(file_path) in self.file_timestamps:
            self.file_timestamps[str(file_path)] = datetime.now()
            logger.debug(f"File modified (updating timestamp): {file_path.name}")

    def on_moved(self, src_path: Path, dest_path: Path) -> None:
        """Handle file move event."""
        logger.info(f"File moved: {src_path} -> {dest_path}")
        self.on_created(dest_path)

    def process_file(self, file_path: Path, preset: str) -> ProcessingResult:
        """Process a validated file through the pipeline."""
        import time

        from framekit.commands.pipeline import run_pipeline_command

        start_time = time.time()

        try:
            self.processing_files.add(str(file_path))
            self.notifier.notify_started(file_path.name)
            logger.info(f"Starting pipeline for {file_path.name} with preset '{preset}'")

            release_folder = file_path.parent
            try:
                return_code = run_pipeline_command(
                    path=str(release_folder),
                    nfo_locale=None,
                    announce=None,
                    preset=None,
                    preview=False,
                    explain=False,
                    with_metadata=None,
                    remove_terms=(),
                    select_modules=False,
                    select_templates=False,
                    select_terms=False,
                    nfo_mode=None,
                    enabled_modules=None,
                    pipeline_preset=preset,
                    auto_mode=True,
                    step_callback=None,
                )
                success = return_code == 0
                error_msg = None if success else f"Pipeline returned error code {return_code}"
            except Exception as pipeline_error:
                success = False
                error_msg = f"Pipeline execution error: {pipeline_error!s}"
                logger.exception(f"Pipeline execution failed: {pipeline_error}")

            output_path = release_folder / "output"
            if not output_path.exists():
                output_path = release_folder

            duration = time.time() - start_time

            if success:
                self.notifier.notify_success(file_path.name, duration)
                logger.info(
                    f"Pipeline completed successfully for {file_path.name} ({duration:.1f}s)"
                )
                self.files_processed += 1
                self.log_event("processed", file_path)
                return ProcessingResult(
                    success=True, file_path=file_path, duration=duration, output_path=output_path
                )
            else:
                self.notifier.notify_error(file_path.name, error_msg or "Unknown error")
                logger.error(f"Pipeline failed for {file_path.name}: {error_msg}")
                self.errors_count += 1
                self.log_event("failed", file_path)
                return ProcessingResult(
                    success=False, file_path=file_path, duration=duration, error=error_msg
                )

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            self.notifier.notify_error(file_path.name, error_msg)
            logger.exception(f"Error processing {file_path.name}: {e}")
            return ProcessingResult(
                success=False, file_path=file_path, duration=duration, error=error_msg
            )
        finally:
            self.processing_files.discard(str(file_path))
            self.file_timestamps.pop(str(file_path), None)

    def handle_failed_file(self, file_path: Path, error: str) -> None:
        """Handle a failed file by moving it to the failed folder."""
        if not self.config.error_handling.move_on_error:
            logger.info(f"Not moving failed file (move_on_error=False): {file_path.name}")
            return

        try:
            failed_folder = file_path.parent / self.config.error_handling.failed_folder
            failed_folder.mkdir(exist_ok=True)
            dest_path = failed_folder / file_path.name
            counter = 1
            while dest_path.exists():
                dest_path = failed_folder / f"{file_path.stem}_{counter}{file_path.suffix}"
                counter += 1
            file_path.rename(dest_path)
            logger.info(f"Moved failed file to: {dest_path}")
        except Exception as e:
            logger.error(f"Failed to move file to failed folder: {e}")

    def start_periodic_status(self) -> None:
        """Start periodic status updates."""
        if self.status_timer:
            self.status_timer.cancel()
        self.status_timer = threading.Timer(
            self.status_update_interval, self._periodic_status_update
        )
        self.status_timer.daemon = True
        self.status_timer.start()

    def _periodic_status_update(self) -> None:
        """Display periodic status update."""
        status = self.get_current_status()
        self.console.print("\n[dim]--- Watch Status Update ---[/dim]")
        self.console.print(f"Uptime: {self._format_uptime(status.uptime_seconds())}")
        self.console.print(f"Processed: {status.files_processed} | Queue: {status.files_in_queue}")
        self.start_periodic_status()

    def stop_periodic_status(self) -> None:
        """Stop periodic status updates."""
        if self.status_timer:
            self.status_timer.cancel()
            self.status_timer = None

    def get_current_status(self):
        """Get current watch status."""
        from .models import WatchStatus

        return WatchStatus(
            running=True,
            start_time=self.start_time,
            files_processed=self.files_processed,
            files_in_queue=self.processing_queue.qsize(),
            recent_events=self.recent_events[-10:],
            last_activity=self.recent_events[-1].get("timestamp") if self.recent_events else None,
            errors_count=self.errors_count,
        )

    def log_event(self, event_type: str, file_path: Path) -> None:
        """Log a watch event."""
        event = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "timestamp": datetime.now(),
            "type": event_type,
            "file": str(file_path.name),
        }
        self.recent_events.append(event)
        if len(self.recent_events) > 50:
            self.recent_events = self.recent_events[-50:]

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
