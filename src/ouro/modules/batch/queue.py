"""Queue management for batch processing."""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path

from loguru import logger

from ouro.core.paths import get_cache_dir
from ouro.modules.batch.models import BatchItem, BatchQueueStats


class BatchQueue:
    """Manages a queue of batch items with thread-safe operations."""

    QUEUE_FILE_NAME = ".ouro_batch_queue.json"

    def __init__(self, queue_file: Path | None = None) -> None:
        """Initialize an empty batch queue.

        Args:
            queue_file: Optional path to queue persistence file
        """
        self._items: list[BatchItem] = []
        self._queue_file = queue_file or get_cache_dir() / "batch" / self.QUEUE_FILE_NAME
        self._version = "1.0"
        self._lock = threading.Lock()  # Thread-safe operations

    @property
    def queue_file(self) -> Path:
        return self._queue_file

    def add(self, item: BatchItem) -> None:
        """Add an item to the queue.

        Args:
            item: The batch item to add
        """
        self._items.append(item)

    def add_path(self, path: Path, display_name: str | None = None) -> BatchItem:
        """Add a path to the queue, creating a BatchItem.

        Args:
            path: Path to the release folder
            display_name: Optional display name (defaults to folder name)

        Returns:
            The created BatchItem
        """
        item = BatchItem(
            path=path,
            display_name=display_name or path.name,
        )
        self.add(item)
        return item

    def remove(self, item: BatchItem) -> None:
        """Remove an item from the queue.

        Args:
            item: The batch item to remove
        """
        if item in self._items:
            self._items.remove(item)

    def remove_at(self, index: int) -> BatchItem | None:
        """Remove an item at a specific index.

        Args:
            index: Index of the item to remove

        Returns:
            The removed item, or None if index is invalid
        """
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def clear(self) -> None:
        """Clear all items from the queue."""
        self._items.clear()

    def get_items(self) -> list[BatchItem]:
        """Get all items in the queue.

        Returns:
            List of all batch items
        """
        return self._items.copy()

    def get_item(self, index: int) -> BatchItem | None:
        """Get an item at a specific index.

        Args:
            index: Index of the item

        Returns:
            The batch item, or None if index is invalid
        """
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def contains_path(self, path: Path) -> bool:
        """Check if a path is already in the queue.

        Args:
            path: Path to check

        Returns:
            True if the path is in the queue
        """
        return any(item.path == path for item in self._items)

    def get_status(self) -> BatchQueueStats:
        """Get statistics about the queue.

        Returns:
            Queue statistics
        """
        return BatchQueueStats.from_items(self._items)

    def __len__(self) -> int:
        """Get the number of items in the queue."""
        return len(self._items)

    def __bool__(self) -> bool:
        """Check if the queue has any items."""
        return len(self._items) > 0

    def __iter__(self):
        """Iterate over items in the queue."""
        return iter(self._items)

    def __getitem__(self, index: int) -> BatchItem:
        """Get an item by index."""
        return self._items[index]

    def save(self, path: Path | None = None) -> bool:
        """Save queue to JSON file.

        Args:
            path: Optional custom path (defaults to queue_file)

        Returns:
            True if saved successfully, False otherwise
        """
        save_path = path or self._queue_file

        try:
            data = {
                "version": self._version,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "items": [item.to_dict() for item in self._items],
            }

            # Ensure parent directory exists
            save_path.parent.mkdir(parents=True, exist_ok=True)

            # Write to file
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            return True

        except Exception as e:
            logger.warning(f"Failed to save queue state to {save_path}: {e}")
            return False

    def load(self, path: Path | None = None) -> bool:
        """Load queue from JSON file.

        Args:
            path: Optional custom path (defaults to queue_file)

        Returns:
            True if loaded successfully, False otherwise
        """
        load_path = path or self._queue_file

        if not load_path.exists():
            return False

        try:
            with open(load_path, encoding="utf-8") as f:
                data = json.load(f)

            # Validate version
            if data.get("version") != self._version:
                return False

            # Load items
            self._items.clear()
            for item_data in data.get("items", []):
                item = BatchItem.from_dict(item_data)
                self._items.append(item)

            return True

        except Exception:
            return False

    def auto_save(self) -> None:
        """Automatically save queue after modifications."""
        self.save()

    def queue_file_exists(self) -> bool:
        """Check if queue file exists."""
        return self._queue_file.exists()

    def delete_queue_file(self) -> bool:
        """Delete the queue file.

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            if self._queue_file.exists():
                self._queue_file.unlink()
            return True
        except Exception:
            return False

    def get_selected_items(self) -> list[BatchItem]:
        """Get all selected items from the queue.

        Returns:
            List of selected batch items
        """
        return [item for item in self._items if item.selected]

    def select_all(self) -> None:
        """Select all items in the queue."""
        for item in self._items:
            item.selected = True

    def deselect_all(self) -> None:
        """Deselect all items in the queue."""
        for item in self._items:
            item.selected = False

    def remove_selected(self) -> int:
        """Remove all selected items from the queue.

        Returns:
            Number of items removed
        """
        selected = self.get_selected_items()
        for item in selected:
            self.remove(item)
        return len(selected)

    def toggle_enabled_for_selected(self) -> int:
        """Toggle enabled/disabled status for all selected items.

        Returns:
            Number of items toggled
        """
        selected = self.get_selected_items()
        for item in selected:
            item.enabled = not item.enabled
        return len(selected)

    def get_items_safe(self) -> list[BatchItem]:
        """Thread-safe method to get all items in the queue.

        Returns:
            List of all batch items
        """
        with self._lock:
            return self._items.copy()

    def add_safe(self, item: BatchItem) -> None:
        """Thread-safe method to add an item to the queue.

        Args:
            item: The batch item to add
        """
        with self._lock:
            self._items.append(item)

    def remove_safe(self, item: BatchItem) -> None:
        """Thread-safe method to remove an item from the queue.

        Args:
            item: The batch item to remove
        """
        with self._lock:
            if item in self._items:
                self._items.remove(item)

    def clear_safe(self) -> None:
        """Thread-safe method to clear all items from the queue."""
        with self._lock:
            self._items.clear()

    def get_status_safe(self) -> BatchQueueStats:
        """Thread-safe method to get statistics about the queue.

        Returns:
            Queue statistics
        """
        with self._lock:
            return BatchQueueStats.from_items(self._items)
