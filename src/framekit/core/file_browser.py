"""File browser engine for interactive file selection.

This module provides the core engine for browsing and selecting files
in an interactive terminal interface. It handles directory navigation,
file filtering, and selection state management.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from framekit.core.path_validation import validate_directory_path


@dataclass(frozen=True, slots=True)
class FileEntry:
    """Represents a file or directory entry in the browser.

    Attributes:
        path: Full path to the file or directory
        name: Display name (filename or directory name)
        is_directory: Whether this entry is a directory
        size: File size in bytes (0 for directories)
        extension: File extension (empty for directories)
    """

    path: Path
    name: str
    is_directory: bool
    size: int
    extension: str


@dataclass(slots=True)
class BrowserConfig:
    """Configuration for file browser behavior.

    Attributes:
        start_directory: Initial directory to browse
        filter_extensions: List of allowed extensions (e.g., ['.mkv', '.mp4'])
        filter_pattern: Glob pattern for filtering files
        multi_select: Enable multi-file selection
        show_hidden: Show hidden files (starting with .)
        directories_only: Show only directories
    """

    start_directory: Path = field(default_factory=Path.cwd)
    filter_extensions: list[str] | None = None
    filter_pattern: str | None = None
    multi_select: bool = False
    show_hidden: bool = False
    directories_only: bool = False


@dataclass(slots=True)
class FileBrowserState:
    """Current state of the file browser.

    Attributes:
        current_dir: Current directory being browsed
        entries: List of file/directory entries in current directory
        cursor_index: Index of currently highlighted entry
        selected_indices: Set of selected entry indices
    """

    current_dir: Path
    entries: list[FileEntry]
    cursor_index: int = 0
    selected_indices: set[int] = field(default_factory=set)


class FileBrowserEngine:
    """Core engine for file browser functionality.

    Handles directory navigation, file filtering, and selection state.
    Uses path validation for security.
    """

    def __init__(self, config: BrowserConfig) -> None:
        """Initialize the file browser engine.

        Args:
            config: Browser configuration
        """
        self.config = config

        # Validate and resolve start directory
        try:
            validated_dir = validate_directory_path(
                config.start_directory, must_exist=True, strict=False
            )
        except Exception as e:
            logger.warning(f"Invalid start directory, using cwd: {e}")
            validated_dir = Path.cwd()

        # Initialize state
        self.state = FileBrowserState(
            current_dir=validated_dir, entries=[], cursor_index=0, selected_indices=set()
        )

        # Load initial directory
        self._load_directory()

    def _load_directory(self) -> None:
        """Load entries from current directory with filtering."""
        try:
            entries = self._collect_entries()
            self._apply_loaded_entries(entries)

        except PermissionError:
            logger.warning(f"Permission denied accessing directory: {self.state.current_dir}")
            self.state.entries = []
        except Exception as e:
            logger.error(f"Error loading directory: {e}")
            self.state.entries = []

    def _collect_entries(self) -> list[FileEntry]:
        entries: list[FileEntry] = []
        for item in self.state.current_dir.iterdir():
            entry = self._build_entry(item)
            if entry is not None:
                entries.append(entry)
        entries.sort(key=lambda current: (not current.is_directory, current.name.lower()))
        return entries

    def _build_entry(self, item: Path) -> FileEntry | None:
        if self._should_skip_hidden(item):
            return None

        is_directory = item.is_dir()
        if self.config.directories_only and not is_directory:
            return None

        if is_directory:
            return FileEntry(path=item, name=item.name, is_directory=True, size=0, extension="")

        file_size, extension = self._read_file_metadata(item)
        if file_size is None:
            return None
        if not self._matches_filters(item, extension):
            return None
        return FileEntry(
            path=item,
            name=item.name,
            is_directory=False,
            size=file_size,
            extension=extension,
        )

    def _should_skip_hidden(self, item: Path) -> bool:
        return not self.config.show_hidden and item.name.startswith(".")

    def _read_file_metadata(self, item: Path) -> tuple[int | None, str]:
        try:
            return item.stat().st_size, item.suffix.lower()
        except OSError:
            return None, ""

    def _matches_filters(self, item: Path, extension: str) -> bool:
        if self.config.filter_extensions and extension not in self.config.filter_extensions:
            return False
        if self.config.filter_pattern and not item.match(self.config.filter_pattern):
            return False
        return True

    def _apply_loaded_entries(self, entries: list[FileEntry]) -> None:
        self.state.entries = entries
        self.state.cursor_index = 0
        self.state.selected_indices.clear()

    def navigate_into(self) -> None:
        """Navigate into the currently selected directory.

        Does nothing if current selection is not a directory.
        """
        if not self.state.entries:
            return

        if self.state.cursor_index >= len(self.state.entries):
            return

        current_entry = self.state.entries[self.state.cursor_index]

        # Only navigate if it's a directory
        if not current_entry.is_directory:
            return

        try:
            # Validate the target directory
            validated_dir = validate_directory_path(
                current_entry.path, must_exist=True, strict=False
            )

            self.state.current_dir = validated_dir
            self._load_directory()

        except Exception as e:
            logger.warning(f"Cannot navigate to directory: {e}")

    def navigate_up(self) -> None:
        """Navigate to parent directory.

        Does nothing if already at root or filesystem boundary.
        """
        parent = self.state.current_dir.parent

        # Don't navigate if we're at the root
        if parent == self.state.current_dir:
            return

        try:
            # Validate parent directory
            validated_dir = validate_directory_path(parent, must_exist=True, strict=False)

            self.state.current_dir = validated_dir
            self._load_directory()

        except Exception as e:
            logger.warning(f"Cannot navigate to parent directory: {e}")

    def move_cursor(self, delta: int) -> None:
        """Move cursor by delta positions with wrapping.

        Args:
            delta: Number of positions to move (positive or negative)
        """
        if not self.state.entries:
            return

        new_index = (self.state.cursor_index + delta) % len(self.state.entries)
        self.state.cursor_index = new_index

    def toggle_selection(self) -> None:
        """Toggle selection of current entry.

        In single-select mode, replaces previous selection.
        In multi-select mode, toggles the current entry.
        """
        if not self.state.entries:
            return

        if self.state.cursor_index >= len(self.state.entries):
            return

        idx = self.state.cursor_index

        if self.config.multi_select:
            # Multi-select: toggle current entry
            if idx in self.state.selected_indices:
                self.state.selected_indices.remove(idx)
            else:
                self.state.selected_indices.add(idx)
        else:
            # Single-select: replace selection
            self.state.selected_indices = {idx}

    def get_selected_paths(self) -> list[Path]:
        """Get list of selected file paths.

        Returns:
            List of Path objects for selected entries
        """
        selected_paths: list[Path] = []

        for idx in sorted(self.state.selected_indices):
            if idx < len(self.state.entries):
                selected_paths.append(self.state.entries[idx].path)

        return selected_paths

    def refresh(self) -> None:
        """Refresh the current directory contents.

        Preserves cursor position if possible.
        """
        old_cursor_name = None
        if self.state.entries and self.state.cursor_index < len(self.state.entries):
            old_cursor_name = self.state.entries[self.state.cursor_index].name

        self._load_directory()

        # Try to restore cursor to same file
        if old_cursor_name:
            for i, entry in enumerate(self.state.entries):
                if entry.name == old_cursor_name:
                    self.state.cursor_index = i
                    break
