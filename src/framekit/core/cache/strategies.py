"""Cache invalidation strategies for intelligent cache management."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Protocol


class InvalidationStrategy(Protocol):
    """Protocol for cache invalidation strategies."""

    def should_invalidate(self, entry_metadata: dict, **kwargs) -> bool:
        """Determine if a cache entry should be invalidated.

        Args:
            entry_metadata: Metadata stored with the cache entry
            **kwargs: Additional context for invalidation decision

        Returns:
            True if the entry should be invalidated, False otherwise
        """
        ...


class TTLStrategy:
    """Time-To-Live based invalidation strategy."""

    def should_invalidate(self, entry_metadata: dict, **kwargs) -> bool:
        """Invalidate if entry has expired based on TTL."""
        expires_at = entry_metadata.get("expires_at", 0)
        return time.time() > expires_at


class FileModificationStrategy:
    """File modification time based invalidation strategy.

    Used for MediaInfo cache - invalidates if file has been modified.
    """

    def should_invalidate(self, entry_metadata: dict, **kwargs) -> bool:
        """Invalidate if file modification time has changed.

        Args:
            entry_metadata: Must contain 'file_path' and 'mtime'
            **kwargs: Not used

        Returns:
            True if file has been modified or doesn't exist
        """
        file_path = entry_metadata.get("file_path")
        cached_mtime = entry_metadata.get("mtime")

        if not file_path or cached_mtime is None:
            return True

        path = Path(file_path)
        if not path.exists():
            return True

        try:
            current_mtime = path.stat().st_mtime
            return current_mtime != cached_mtime
        except OSError:
            return True


class CompositeStrategy:
    """Combines multiple invalidation strategies.

    Entry is invalidated if ANY strategy returns True.
    """

    def __init__(self, *strategies: InvalidationStrategy):
        """Initialize with multiple strategies.

        Args:
            *strategies: Variable number of invalidation strategies
        """
        self.strategies = strategies

    def should_invalidate(self, entry_metadata: dict, **kwargs) -> bool:
        """Invalidate if any strategy returns True."""
        return any(
            strategy.should_invalidate(entry_metadata, **kwargs) for strategy in self.strategies
        )


def generate_cache_key(*parts: str) -> str:
    """Generate a consistent cache key from multiple parts.

    Args:
        *parts: Variable number of string parts to combine

    Returns:
        SHA256 hash of the combined parts
    """
    combined = "|".join(str(part) for part in parts)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def generate_file_cache_key(file_path: str | Path, mtime: float) -> str:
    """Generate a cache key for file-based caching.

    Includes file path and modification time to ensure cache invalidation
    when file changes.

    Args:
        file_path: Path to the file
        mtime: File modification time

    Returns:
        Cache key string
    """
    path_str = str(Path(file_path).resolve())
    return generate_cache_key("file", path_str, str(mtime))
