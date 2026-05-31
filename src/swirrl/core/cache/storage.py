"""Storage backend for the intelligent caching system."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, cast

from swirrl.core.cache.backend import Cache
from swirrl.core.cache.models import CacheEntry, CacheStats


class CacheStorage:
    """Disk-backed storage backend for cache entries.

    Provides efficient disk-based caching with automatic cleanup.

    Thread-Safety Guarantees:
    -------------------------
    This class is designed to be thread-safe for concurrent access in batch
    processing scenarios:

    1. **Cache Operations**: All cache read/write/delete operations use the
       local cache backend with SQLite and explicit locking.

    2. **Statistics Tracking**: Cache statistics (hits, misses, expired entries)
       are protected by a threading.Lock to prevent race conditions when multiple
       threads access the cache simultaneously.

    3. **Atomic Updates**: Statistics are updated atomically within lock-protected
       critical sections to ensure consistency.

    4. **Safe Reads**: The get_stats() method returns a copy of statistics to
       prevent external modification of internal state.

    Usage in Concurrent Scenarios:
    ------------------------------
    Multiple threads can safely:
    - Read from cache simultaneously
    - Write to cache simultaneously
    - Mix reads and writes
    - Collect statistics
    - Perform cleanup operations

    The underlying backend handles persistence while this class adds
    thread-level locking for in-memory statistics tracking.
    """

    def __init__(
        self,
        cache_file: Path,
        max_size_mb: int = 50,
        auto_cleanup: bool = True,
    ):
        """Initialize cache storage.

        Args:
            cache_file: Path to the cache file (used to derive cache directory)
            max_size_mb: Maximum size of cache in MB
            auto_cleanup: Whether to automatically cleanup expired entries
        """
        # Use cache_file stem as subdirectory name (e.g., tmdb.json -> tmdb/)
        cache_dir = cache_file.parent / cache_file.stem
        cache_dir.mkdir(parents=True, exist_ok=True)

        self.cache_file = cache_file  # Keep for compatibility
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.auto_cleanup = auto_cleanup

        # Initialize disk-backed cache
        self._cache = Cache(
            str(cache_dir),
            size_limit=self.max_size_bytes,
        )

        # Statistics tracking with thread-safe lock
        self._stats = CacheStats(cache_type=cache_file.stem)
        self._stats_lock = threading.Lock()

        # Cleanup expired entries on init if configured
        if auto_cleanup:
            self.clear_expired()

    def get(self, key: str) -> CacheEntry | None:
        """Retrieve a cache entry by key.

        Args:
            key: Cache key

        Returns:
            CacheEntry if found and not expired, None otherwise
        """
        entry_data = self._cache.get(key)

        if entry_data is None:
            with self._stats_lock:
                self._stats.misses += 1
            return None

        try:
            entry = CacheEntry.from_dict(cast(dict[str, Any], entry_data))
        except (KeyError, TypeError, ValueError):
            with self._stats_lock:
                self._stats.misses += 1
            return None

        if entry.is_expired():
            with self._stats_lock:
                self._stats.misses += 1
                self._stats.expired_entries += 1
            # Remove expired entry
            self._cache.delete(key)
            return None

        # Update access statistics (in-memory only, no disk write on read)
        entry.touch()
        # Note: We don't persist the touch() update to avoid disk I/O on every cache hit
        # The entry will be persisted on next set() or during cleanup

        with self._stats_lock:
            self._stats.hits += 1
        return entry

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store a cache entry.

        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl_seconds: Time-to-live in seconds
            metadata: Optional metadata to store with the entry
        """
        now = time.time()
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=now,
            expires_at=now + ttl_seconds,
            access_count=0,
            last_accessed=now,
            metadata=metadata or {},
        )

        # Store with expiration
        self._cache.set(key, entry.to_dict(), expire=ttl_seconds)

        # Trigger cleanup if cache is getting full
        if self.auto_cleanup and len(self._cache) > 1000:
            self._cache.cull()

    def delete(self, key: str) -> bool:
        """Delete a cache entry.

        Args:
            key: Cache key

        Returns:
            True if entry was deleted, False if not found
        """
        return self._cache.delete(key)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        with self._stats_lock:
            self._stats = CacheStats(cache_type=self.cache_file.stem)

    def clear_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries removed
        """
        # Get all keys and check for expired entries
        count = 0
        for key in list(self._cache):
            entry_data = self._cache.get(key)
            if entry_data is not None:
                try:
                    entry = CacheEntry.from_dict(cast(dict[str, Any], entry_data))
                    if entry.is_expired():
                        self._cache.delete(key)
                        count += 1
                except (KeyError, TypeError, ValueError):
                    # Invalid entry, remove it
                    self._cache.delete(key)
                    count += 1

        return count

    def invalidate_pattern(self, pattern: str) -> int:
        """Remove entries matching a pattern.

        Args:
            pattern: String pattern to match in keys

        Returns:
            Number of entries removed
        """
        count = 0
        for key in list(self._cache):
            if pattern in key:
                self._cache.delete(key)
                count += 1

        return count

    def get_stats(self) -> CacheStats:
        """Get cache statistics.

        Returns:
            CacheStats object with current statistics
        """
        # Count total entries
        total = len(self._cache)

        # Get cache size from backend
        cache_size = self._cache.volume()

        # Count expired entries
        expired = 0
        for key in list(self._cache):
            entry_data = self._cache.get(key)
            if entry_data is not None:
                try:
                    entry = CacheEntry.from_dict(cast(dict[str, Any], entry_data))
                    if entry.is_expired():
                        expired += 1
                except (KeyError, TypeError, ValueError):
                    pass

        # Update stats atomically
        with self._stats_lock:
            self._stats.total_entries = total
            self._stats.total_size_bytes = cache_size
            self._stats.expired_entries = expired
            # Return a copy to prevent external modification
            return CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                total_entries=self._stats.total_entries,
                total_size_bytes=self._stats.total_size_bytes,
                expired_entries=self._stats.expired_entries,
                cache_type=self._stats.cache_type,
            )
