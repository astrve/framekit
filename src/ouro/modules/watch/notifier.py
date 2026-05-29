"""Cross-platform notifications for Watch Mode using desktop-notifier."""

import asyncio
import threading
from typing import Any

from loguru import logger

from .models import NotificationConfig

DesktopNotifier: Any = None
Urgency: Any = None
try:
    from desktop_notifier import DesktopNotifier as _DesktopNotifier  # type: ignore
    from desktop_notifier import Urgency as _Urgency  # type: ignore

    DesktopNotifier = _DesktopNotifier
    Urgency = _Urgency
    _notifier_ok = True
except ImportError:
    _notifier_ok = False

NOTIFIER_AVAILABLE: bool = _notifier_ok


class WindowsNotifier:
    """Handles cross-platform desktop notifications."""

    def __init__(self, config: NotificationConfig):
        self.config = config
        self.notifier: Any | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None

        if self.config.enabled:
            if NOTIFIER_AVAILABLE:
                try:
                    self._loop = asyncio.new_event_loop()
                    self._loop_thread = threading.Thread(target=self._loop.run_forever, daemon=True)
                    self._loop_thread.start()

                    future = asyncio.run_coroutine_threadsafe(self._init_notifier(), self._loop)
                    future.result(timeout=5)
                    logger.info("Desktop notifications enabled")
                except Exception as e:
                    logger.warning(f"Failed to initialize desktop notifier: {e}")
                    self.notifier = None
            else:
                logger.warning(
                    "desktop-notifier library not available. "
                    "Install it with: pip install desktop-notifier"
                )

    async def _init_notifier(self) -> None:
        self.notifier = DesktopNotifier(app_name="Ouro", notification_limit=10)

    def _show_notification(self, title: str, message: str, urgency: Any = None) -> None:
        if not self.config.enabled:
            logger.debug(f"Notification disabled: {title} - {message}")
            return

        if self.notifier is None or self._loop is None:
            logger.debug(f"Desktop notifier not available: {title} - {message}")
            return

        try:
            if urgency is None and Urgency is not None:
                urgency = Urgency.Normal

            future = asyncio.run_coroutine_threadsafe(
                self.notifier.send(title=title, message=message, urgency=urgency), self._loop
            )
            future.result(timeout=5)
            logger.debug(f"Desktop notification shown: {title}")
        except Exception as e:
            logger.error(f"Failed to show desktop notification: {e}")

    def notify_started(self, file_name: str) -> None:
        """Handle notify started."""
        if not self.config.on_start:
            return
        self._show_notification(
            title="Ouro Watch Mode",
            message=f"Processing started: {file_name}",
            urgency=Urgency.Normal if Urgency else None,
        )
        logger.info(f"Notification sent: Processing started for {file_name}")

    def notify_success(self, file_name: str, duration: float) -> None:
        """Handle notify success."""
        if not self.config.on_success:
            return

        minutes = int(duration // 60)
        seconds = int(duration % 60)
        duration_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"

        self._show_notification(
            title="Ouro Watch Mode - Success",
            message=f"Completed: {file_name}\nDuration: {duration_str}",
            urgency=Urgency.Normal if Urgency else None,
        )
        logger.info(f"Notification sent: Processing succeeded for {file_name}")

    def notify_error(self, file_name: str, error: str) -> None:
        """Handle notify error."""
        if not self.config.on_error:
            return

        max_length = 100
        if len(error) > max_length:
            error = error[:max_length] + "..."

        self._show_notification(
            title="Ouro Watch Mode - Error",
            message=f"Failed: {file_name}\nError: {error}",
            urgency=Urgency.Critical if Urgency else None,
        )
        logger.info(f"Notification sent: Processing failed for {file_name}")

    def notify_watch_started(self, folders: list[str]) -> None:
        """Handle notify watch started."""
        if not self.config.enabled or not self.config.on_watch_started:
            return

        folder_count = len(folders)
        message = f"Watching {folder_count} folder{'s' if folder_count != 1 else ''}"

        self._show_notification(
            title="Ouro Watch Mode Started",
            message=message,
            urgency=Urgency.Normal if Urgency else None,
        )
        logger.info("Notification sent: Watch mode started")

    def notify_watch_stopped(self) -> None:
        """Handle notify watch stopped."""
        if not self.config.enabled or not self.config.on_watch_started:
            return

        self._show_notification(
            title="Ouro Watch Mode",
            message="Watch mode stopped",
            urgency=Urgency.Low if Urgency else None,
        )
        logger.info("Notification sent: Watch mode stopped")
