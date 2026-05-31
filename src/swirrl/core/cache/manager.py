"""Main cache manager for intelligent caching system."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from swirrl.core.cache.models import CacheStats
from swirrl.core.cache.storage import CacheStorage
from swirrl.core.cache.strategies import generate_cache_key


class CacheManager:
    """Main cache manager coordinating multiple cache types.

    Manages TMDb metadata cache, MediaInfo cache, and release metadata cache.

    Thread-Safety Guarantees:
    -------------------------
    This class is thread-safe for concurrent access in batch processing:

    1. **Delegated Thread-Safety**: All cache operations are delegated to
       CacheStorage instances, which are thread-safe by design.

    2. **Independent Cache Types**: Each cache type (tmdb, mediainfo, release)
       has its own CacheStorage instance with independent locking, allowing
       concurrent access to different cache types without contention.

    3. **No Shared Mutable State**: The CacheManager itself maintains no
       mutable state that requires synchronization. All state is managed
       by the underlying CacheStorage instances.

    Usage in Concurrent Scenarios:
    ------------------------------
    Multiple threads can safely:
    - Access different cache types simultaneously
    - Access the same cache type simultaneously
    - Mix operations across cache types
    - Perform cleanup and statistics collection

    Example:
        # Safe to use from multiple threads
        cache_manager = CacheManager(cache_dir)

        # Thread 1
        cache_manager.set_tmdb_search("query1", "movie", results1)

        # Thread 2 (concurrent)
        cache_manager.get_mediainfo("/path/file.mkv", mtime)

        # Thread 3 (concurrent)
        stats = cache_manager.get_stats()
    """

    def __init__(
        self,
        cache_dir: Path,
        config: dict[str, Any] | None = None,
    ):
        """Initialize cache manager.

        Args:
            cache_dir: Directory for cache files
            config: Cache configuration dictionary
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Parse configuration
        config = config or {}
        self.enabled = config.get("enabled", True)

        # Initialize storage backends for each cache type
        tmdb_config = config.get("tmdb", {})
        self.tmdb_storage = CacheStorage(
            cache_file=self.cache_dir / "tmdb.json",
            max_size_mb=tmdb_config.get("max_size_mb", 50),
            auto_cleanup=config.get("auto_cleanup", True),
        )

        tvdb_config = config.get("tvdb", {})
        self.tvdb_storage = CacheStorage(
            cache_file=self.cache_dir / "tvdb.json",
            max_size_mb=tvdb_config.get("max_size_mb", 50),
            auto_cleanup=config.get("auto_cleanup", True),
        )

        anilist_config = config.get("anilist", {})
        self.anilist_storage = CacheStorage(
            cache_file=self.cache_dir / "anilist.json",
            max_size_mb=anilist_config.get("max_size_mb", 50),
            auto_cleanup=config.get("auto_cleanup", True),
        )

        trakt_config = config.get("trakt", {})
        self.trakt_storage = CacheStorage(
            cache_file=self.cache_dir / "trakt.json",
            max_size_mb=trakt_config.get("max_size_mb", 50),
            auto_cleanup=config.get("auto_cleanup", True),
        )

        mediainfo_config = config.get("mediainfo", {})
        self.mediainfo_storage = CacheStorage(
            cache_file=self.cache_dir / "mediainfo.json",
            max_size_mb=mediainfo_config.get("max_size_mb", 50),
            auto_cleanup=config.get("auto_cleanup", True),
        )

        release_config = config.get("release", {})
        self.release_storage = CacheStorage(
            cache_file=self.cache_dir / "release.json",
            max_size_mb=release_config.get("max_size_mb", 50),
            auto_cleanup=config.get("auto_cleanup", True),
        )

        # TTL configurations (in days, converted to seconds)
        self.tmdb_ttl = tmdb_config.get("ttl_days", 7) * 86400
        self.tvdb_ttl = tvdb_config.get("ttl_days", 7) * 86400
        self.anilist_ttl = anilist_config.get("ttl_days", 7) * 86400
        self.trakt_ttl = trakt_config.get("ttl_days", 7) * 86400
        self.mediainfo_ttl = mediainfo_config.get("ttl_days", 30) * 86400
        self.release_ttl = release_config.get("ttl_days", 7) * 86400

        # Cleanup on startup if configured
        if config.get("cleanup_on_startup", True):
            self.cleanup_expired()

    def _get_storage(self, cache_type: str) -> CacheStorage:
        """Get storage backend for cache type.

        Args:
            cache_type: One of 'tmdb', 'tvdb', 'anilist', 'trakt', 'mediainfo', 'release'

        Returns:
            CacheStorage instance

        Raises:
            ValueError: If cache type is unknown
        """
        if cache_type == "tmdb":
            return self.tmdb_storage
        elif cache_type == "tvdb":
            return self.tvdb_storage
        elif cache_type == "anilist":
            return self.anilist_storage
        elif cache_type == "trakt":
            return self.trakt_storage
        elif cache_type == "mediainfo":
            return self.mediainfo_storage
        elif cache_type == "release":
            return self.release_storage
        else:
            raise ValueError(f"Unknown cache type: {cache_type}")

    def _get_ttl(self, cache_type: str) -> int:
        """Get TTL for cache type in seconds.

        Args:
            cache_type: One of 'tmdb', 'tvdb', 'anilist', 'trakt', 'mediainfo', 'release'

        Returns:
            TTL in seconds
        """
        return {
            "tmdb": self.tmdb_ttl,
            "tvdb": self.tvdb_ttl,
            "anilist": self.anilist_ttl,
            "trakt": self.trakt_ttl,
            "mediainfo": self.mediainfo_ttl,
            "release": self.release_ttl,
        }.get(cache_type, 7 * 86400)

    def get(self, cache_type: str, key: str) -> Any | None:
        """Retrieve a cached value.

        Args:
            cache_type: Type of cache ('tmdb', 'tvdb', 'anilist', 'trakt', 'mediainfo', 'release')
            key: Cache key

        Returns:
            Cached value if found and not expired, None otherwise
        """
        if not self.enabled:
            return None

        storage = self._get_storage(cache_type)
        entry = storage.get(key)

        if entry is None:
            return None

        return entry.value

    def set(
        self,
        cache_type: str,
        key: str,
        value: Any,
        ttl: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store a value in cache.

        Args:
            cache_type: Type of cache ('tmdb', 'mediainfo', 'release')
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl: Time-to-live in seconds (uses default if None)
            metadata: Optional metadata to store with the entry
        """
        if not self.enabled:
            return

        storage = self._get_storage(cache_type)
        ttl_seconds = ttl if ttl is not None else self._get_ttl(cache_type)
        storage.set(key, value, ttl_seconds, metadata)

    def delete(self, cache_type: str, key: str) -> bool:
        """Delete a cache entry.

        Args:
            cache_type: Type of cache ('tmdb', 'mediainfo', 'release')
            key: Cache key

        Returns:
            True if entry was deleted, False if not found
        """
        storage = self._get_storage(cache_type)
        return storage.delete(key)

    def clear(self, cache_type: str | None = None) -> None:
        """Clear cache entries.

        Args:
            cache_type: Type of cache to clear, or None to clear all
        """
        if cache_type is None:
            # Clear all caches
            self.tmdb_storage.clear()
            self.mediainfo_storage.clear()
            self.release_storage.clear()
        else:
            storage = self._get_storage(cache_type)
            storage.clear()

    def cleanup_expired(self, cache_type: str | None = None) -> dict[str, int]:
        """Remove expired entries.

        Args:
            cache_type: Type of cache to cleanup, or None to cleanup all

        Returns:
            Dictionary mapping cache type to number of entries removed
        """
        results = {}

        if cache_type is None:
            # Cleanup all caches
            results["tmdb"] = self.tmdb_storage.clear_expired()
            results["mediainfo"] = self.mediainfo_storage.clear_expired()
            results["release"] = self.release_storage.clear_expired()
        else:
            storage = self._get_storage(cache_type)
            results[cache_type] = storage.clear_expired()

        return results

    def invalidate_pattern(
        self,
        cache_type: str,
        pattern: str,
    ) -> int:
        """Remove entries matching a pattern.

        Args:
            cache_type: Type of cache ('tmdb', 'mediainfo', 'release')
            pattern: String pattern to match in keys

        Returns:
            Number of entries removed
        """
        storage = self._get_storage(cache_type)
        return storage.invalidate_pattern(pattern)

    def get_stats(self, cache_type: str | None = None) -> dict[str, CacheStats]:
        """Get cache statistics.

        Args:
            cache_type: Type of cache, or None to get stats for all

        Returns:
            Dictionary mapping cache type to CacheStats
        """
        if cache_type is None:
            # Get stats for all caches
            return {
                "tmdb": self.tmdb_storage.get_stats(),
                "mediainfo": self.mediainfo_storage.get_stats(),
                "release": self.release_storage.get_stats(),
            }
        else:
            storage = self._get_storage(cache_type)
            return {cache_type: storage.get_stats()}

    # Convenience methods for TMDb cache

    def get_tmdb_search(self, query: str, media_kind: str, language: str = "en-US") -> Any | None:
        """Get cached TMDb search results.

        Args:
            query: Search query
            media_kind: Media kind (movie, single_episode, season_pack)
            language: Language code

        Returns:
            Cached search results or None
        """
        key = generate_cache_key("search", query, media_kind, language)
        return self.get("tmdb", key)

    def set_tmdb_search(
        self,
        query: str,
        media_kind: str,
        results: Any,
        language: str = "en-US",
    ) -> None:
        """Cache TMDb search results.

        Args:
            query: Search query
            media_kind: Media kind (movie, single_episode, season_pack)
            results: Search results to cache
            language: Language code
        """
        key = generate_cache_key("search", query, media_kind, language)
        self.set("tmdb", key, results)

    def get_tmdb_details(
        self, tmdb_id: str, media_kind: str, language: str = "en-US"
    ) -> Any | None:
        """Get cached TMDb details.

        Args:
            tmdb_id: TMDb ID
            media_kind: Media kind (movie, tv)
            language: Language code

        Returns:
            Cached details or None
        """
        key = generate_cache_key("details", media_kind, tmdb_id, language)
        return self.get("tmdb", key)

    def set_tmdb_details(
        self,
        tmdb_id: str,
        media_kind: str,
        details: Any,
        language: str = "en-US",
    ) -> None:
        """Cache TMDb details.

        Args:
            tmdb_id: TMDb ID
            media_kind: Media kind (movie, tv)
            details: Details to cache
            language: Language code
        """
        key = generate_cache_key("details", media_kind, tmdb_id, language)
        self.set("tmdb", key, details)

    def get_tmdb_posters(self, tmdb_id: str, media_kind: str) -> Any | None:
        """Get cached TMDb posters.

        Args:
            tmdb_id: TMDb ID
            media_kind: Media kind (movie, tv)

        Returns:
            Cached posters or None
        """
        key = generate_cache_key("posters", media_kind, tmdb_id)
        return self.get("tmdb", key)

    def set_tmdb_posters(
        self,
        tmdb_id: str,
        media_kind: str,
        posters: Any,
    ) -> None:
        """Cache TMDb posters.

        Args:
            tmdb_id: TMDb ID
            media_kind: Media kind (movie, tv)
            posters: Posters to cache
        """
        key = generate_cache_key("posters", media_kind, tmdb_id)
        self.set("tmdb", key, posters)

    # Convenience methods for MediaInfo cache

    def get_mediainfo(self, file_path: str | Path, mtime: float) -> Any | None:
        """Get cached MediaInfo scan results.

        Args:
            file_path: Path to media file
            mtime: File modification time

        Returns:
            Cached MediaInfo results or None
        """
        path_str = str(Path(file_path).resolve())
        key = generate_cache_key("file", path_str, str(mtime))
        return self.get("mediainfo", key)

    def set_mediainfo(
        self,
        file_path: str | Path,
        mtime: float,
        mediainfo_data: Any,
    ) -> None:
        """Cache MediaInfo scan results.

        Args:
            file_path: Path to media file
            mtime: File modification time
            mediainfo_data: MediaInfo data to cache
        """
        path_str = str(Path(file_path).resolve())
        key = generate_cache_key("file", path_str, str(mtime))
        metadata = {
            "file_path": path_str,
            "mtime": mtime,
        }
        self.set("mediainfo", key, mediainfo_data, metadata=metadata)

    # Convenience methods for release metadata cache

    def get_release_metadata(self, release_name: str) -> Any | None:
        """Get cached release metadata.

        Args:
            release_name: Release name

        Returns:
            Cached metadata or None
        """
        key = hashlib.sha256(release_name.encode("utf-8")).hexdigest()
        return self.get("release", key)

    def set_release_metadata(self, release_name: str, metadata: Any) -> None:
        """Cache release metadata.

        Args:
            release_name: Release name
            metadata: Metadata to cache
        """
        key = hashlib.sha256(release_name.encode("utf-8")).hexdigest()
        self.set("release", key, metadata)
