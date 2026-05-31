"""Watch Mode Module for Swirrl.

This module provides automatic file watching and processing capabilities.
It monitors specified folders for new video files and automatically processes
them through the Swirrl pipeline.
"""

from .handler import FileHandler
from .models import (
    ErrorHandlingConfig,
    LoggingConfig,
    NotificationConfig,
    ProcessingResult,
    ValidationConfig,
    WatchConfig,
    WatchFolder,
    WatchStatus,
)
from .notifier import WindowsNotifier
from .service import WatcherService
from .validator import FileValidator

__all__ = [
    "ErrorHandlingConfig",
    "FileHandler",
    "FileValidator",
    "LoggingConfig",
    "NotificationConfig",
    "ProcessingResult",
    "ValidationConfig",
    "WatchConfig",
    "WatchFolder",
    "WatchStatus",
    "WatcherService",
    "WindowsNotifier",
]
