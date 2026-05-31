"""Data models for the Watch Mode module."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class ValidationConfig:
    """Configuration for file validation."""

    stability_timeout: int = 30  # seconds
    check_interval: int = 5  # seconds
    min_file_size: int = 1048576  # 1 MB


@dataclass
class ErrorHandlingConfig:
    """Configuration for error handling."""

    failed_folder: str = "failed"
    max_retries: int = 0
    move_on_error: bool = True


@dataclass
class NotificationConfig:
    """Configuration for notifications."""

    enabled: bool = True
    on_watch_started: bool = True
    on_start: bool = False
    on_success: bool = False
    on_error: bool = True


@dataclass
class LoggingConfig:
    """Configuration for logging."""

    level: str = "INFO"
    file: str = "watch.log"


@dataclass
class WatchFolder:
    """Configuration for a watched folder."""

    path: Path
    preset: str = "default"
    enabled: bool = True
    id: str = ""
    pattern: str = ""
    # Automation chain fields (P4)
    kind_routing: str = "fixed"          # "fixed" | "auto"
    presets_by_kind: dict = field(default_factory=dict)  # {movie, series, single_episode}
    post_actions: dict = field(default_factory=dict)     # {seedbox_push, seedbox_profile, tracker_upload, tracker}

    def __post_init__(self):
        """Convert path to Path object if it's a string."""
        if isinstance(self.path, str):
            self.path = Path(self.path)


@dataclass
class WatchConfig:
    """Main configuration for Watch Mode."""

    enabled: bool = False
    folders: list[WatchFolder] = field(default_factory=list)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    extensions: list[str] = field(default_factory=lambda: [".mkv", ".mp4", ".avi", ".m2ts"])
    ignore_extensions: list[str] = field(
        default_factory=lambda: [".tmp", ".part", ".download", ".crdownload"]
    )
    error_handling: ErrorHandlingConfig = field(default_factory=ErrorHandlingConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    @classmethod
    def from_dict(cls, data: dict) -> "WatchConfig":
        """Create WatchConfig from dictionary."""
        folders = [
            WatchFolder(
                path=Path(folder_data["path"]),
                preset=folder_data.get("preset", "default"),
                enabled=folder_data.get("enabled", True),
                id=str(folder_data.get("rule_id") or folder_data.get("id") or ""),
                pattern=str(folder_data.get("pattern") or ""),
                kind_routing=str(folder_data.get("kind_routing") or "fixed"),
                presets_by_kind=dict(folder_data.get("presets_by_kind") or {}),
                post_actions=dict(folder_data.get("post_actions") or {}),
            )
            for folder_data in data.get("folders", [])
        ]

        return cls(
            enabled=data.get("enabled", False),
            folders=folders,
            validation=ValidationConfig(**data.get("validation", {})),
            extensions=data.get(
                "extensions", cls.__dataclass_fields__["extensions"].default_factory()
            ),
            ignore_extensions=data.get(
                "ignore_extensions", cls.__dataclass_fields__["ignore_extensions"].default_factory()
            ),
            error_handling=ErrorHandlingConfig(**data.get("error_handling", {})),
            notifications=NotificationConfig(**data.get("notifications", {})),
            logging=LoggingConfig(**data.get("logging", {})),
        )


@dataclass
class WatchStatus:
    """Current status of the watch service."""

    running: bool = False
    folders_watched: list[str] = field(default_factory=list)
    files_processing: int = 0
    files_processed: int = 0
    files_failed: int = 0
    uptime: float = 0.0
    last_activity: datetime | None = None
    start_time: datetime | None = None
    files_monitored: int = 0
    files_in_queue: int = 0
    recent_events: list[dict] = field(default_factory=list)
    errors_count: int = 0
    preset_name: str = "default"

    def uptime_seconds(self) -> float:
        """Calculate uptime in seconds."""
        if self.start_time:
            return (datetime.now() - self.start_time).total_seconds()
        return self.uptime

    def to_dict(self) -> dict:
        """Convert status to dictionary."""
        return {
            "running": self.running,
            "folders_watched": self.folders_watched,
            "files_processing": self.files_processing,
            "files_processed": self.files_processed,
            "files_failed": self.files_failed,
            "uptime": self.uptime,
            "uptime_seconds": self.uptime_seconds(),
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "files_monitored": self.files_monitored,
            "files_in_queue": self.files_in_queue,
            "recent_events": self.recent_events,
            "errors_count": self.errors_count,
            "preset_name": self.preset_name,
        }


@dataclass
class ProcessingResult:
    """Result of processing a file."""

    success: bool
    file_path: Path
    duration: float
    error: str | None = None
    output_path: Path | None = None

    def __post_init__(self):
        """Convert paths to Path objects if they're strings."""
        if isinstance(self.file_path, str):
            self.file_path = Path(self.file_path)
        if isinstance(self.output_path, str):
            self.output_path = Path(self.output_path)
