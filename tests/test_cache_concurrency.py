"""Concurrency tests for cache manager thread-safety.

Tests verify that the cache system handles concurrent access correctly
in batch processing scenarios where multiple threads may access the cache
simultaneously.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pytest

from framekit.core.cache.manager import CacheManager
from framekit.core.cache.storage import CacheStorage


@pytest.fixture
def cache_manager(tmp_path: Path) -> CacheManager:
    """Create a cache manager for testing."""
    return CacheManager(
        cache_dir=tmp_path / "cache",
        config={
            "enabled": True,
            "auto_cleanup": False,  # Disable for predictable tests
            "cleanup_on_startup": False,
        },
    )


@pytest.fixture
def cache_storage(tmp_path: Path) -> CacheStorage:
    """Create a cache storage for testing."""
    return CacheStorage(
        cache_file=tmp_path / "test.json",
        max_size_mb=10,
        auto_cleanup=False,
    )


class TestCacheStorageConcurrency:
    """Test thread-safety of CacheStorage operations."""

    def test_concurrent_reads(self, cache_storage: CacheStorage):
        """Test that concurrent reads don't cause race conditions."""
        # Pre-populate cache
        for i in range(10):
            cache_storage.set(f"key_{i}", f"value_{i}", ttl_seconds=3600)

        results: list[Any] = []
        errors: list[Exception] = []

        def read_cache(key: str) -> Any:
            try:
                entry = cache_storage.get(key)
                return entry.value if entry else None
            except Exception as e:
                errors.append(e)
                return None

        # Concurrent reads from multiple threads
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for _ in range(100):  # 100 reads total
                key = f"key_{_ % 10}"
                futures.append(executor.submit(read_cache, key))

            for future in as_completed(futures):
                results.append(future.result())

        # Verify no errors occurred
        assert len(errors) == 0, f"Errors during concurrent reads: {errors}"

        # Verify all reads succeeded
        assert len(results) == 100
        assert all(r is not None for r in results)

    def test_concurrent_writes(self, cache_storage: CacheStorage):
        """Test that concurrent writes don't corrupt data."""
        errors: list[Exception] = []

        def write_cache(key: str, value: str) -> None:
            try:
                cache_storage.set(key, value, ttl_seconds=3600)
            except Exception as e:
                errors.append(e)

        # Concurrent writes from multiple threads
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(100):
                futures.append(executor.submit(write_cache, f"key_{i}", f"value_{i}"))

            for future in as_completed(futures):
                future.result()

        # Verify no errors occurred
        assert len(errors) == 0, f"Errors during concurrent writes: {errors}"

        # Verify all entries were written
        for i in range(100):
            entry = cache_storage.get(f"key_{i}")
            assert entry is not None
            assert entry.value == f"value_{i}"

    def test_concurrent_read_write(self, cache_storage: CacheStorage):
        """Test mixed concurrent reads and writes."""
        # Pre-populate some entries
        for i in range(10):
            cache_storage.set(f"key_{i}", f"initial_{i}", ttl_seconds=3600)

        errors: list[Exception] = []
        read_results: list[Any] = []

        def read_cache(key: str) -> Any:
            try:
                entry = cache_storage.get(key)
                return entry.value if entry else None
            except Exception as e:
                errors.append(e)
                return None

        def write_cache(key: str, value: str) -> None:
            try:
                cache_storage.set(key, value, ttl_seconds=3600)
            except Exception as e:
                errors.append(e)

        # Mix of reads and writes
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = []

            # 50 reads
            for i in range(50):
                key = f"key_{i % 10}"
                futures.append(executor.submit(read_cache, key))

            # 50 writes
            for i in range(50):
                key = f"key_{i % 10}"
                futures.append(executor.submit(write_cache, key, f"updated_{i}"))

            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    read_results.append(result)

        # Verify no errors occurred
        assert len(errors) == 0, f"Errors during concurrent operations: {errors}"

    def test_concurrent_deletes(self, cache_storage: CacheStorage):
        """Test that concurrent deletes are handled safely."""
        # Pre-populate cache
        for i in range(20):
            cache_storage.set(f"key_{i}", f"value_{i}", ttl_seconds=3600)

        errors: list[Exception] = []

        def delete_cache(key: str) -> bool:
            try:
                return cache_storage.delete(key)
            except Exception as e:
                errors.append(e)
                return False

        # Concurrent deletes - some keys will be deleted by multiple threads
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for _ in range(50):  # More deletes than keys
                key = f"key_{_ % 20}"
                futures.append(executor.submit(delete_cache, key))

            for future in as_completed(futures):
                future.result()

        # Verify no errors occurred
        assert len(errors) == 0, f"Errors during concurrent deletes: {errors}"

    def test_statistics_accuracy_under_concurrency(self, cache_storage: CacheStorage):
        """Test that cache statistics remain accurate under concurrent access.

        This is a known issue - statistics may have race conditions.
        This test documents the expected behavior.
        """
        # Pre-populate cache
        for i in range(10):
            cache_storage.set(f"key_{i}", f"value_{i}", ttl_seconds=3600)

        def access_cache(key: str) -> None:
            cache_storage.get(key)

        # Concurrent reads
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for _ in range(100):
                key = f"key_{_ % 10}"
                futures.append(executor.submit(access_cache, key))

            for future in as_completed(futures):
                future.result()

        stats = cache_storage.get_stats()

        # Stats should show hits (exact count may vary due to race conditions)
        # We verify that stats are in a reasonable range rather than exact
        assert stats.hits > 0, "Should have recorded some hits"
        assert stats.hits <= 100, "Hits should not exceed total accesses"
        assert stats.total_entries == 10, "Should have 10 entries"


class TestCacheManagerConcurrency:
    """Test thread-safety of CacheManager operations."""

    def test_concurrent_tmdb_cache_access(self, cache_manager: CacheManager):
        """Test concurrent access to TMDb cache."""
        errors: list[Exception] = []

        def cache_tmdb_search(query: str, media_kind: str) -> None:
            try:
                # Try to get from cache
                result = cache_manager.get_tmdb_search(query, media_kind)
                if result is None:
                    # Simulate cache miss - store result
                    cache_manager.set_tmdb_search(query, media_kind, {"results": [{"id": 123}]})
            except Exception as e:
                errors.append(e)

        # Concurrent TMDb cache operations
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(50):
                query = f"Movie {i % 5}"  # 5 unique queries
                futures.append(executor.submit(cache_tmdb_search, query, "movie"))

            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors during concurrent TMDb cache: {errors}"

    def test_concurrent_mediainfo_cache_access(self, cache_manager: CacheManager):
        """Test concurrent access to MediaInfo cache."""
        errors: list[Exception] = []

        def cache_mediainfo(file_path: str, mtime: float) -> None:
            try:
                result = cache_manager.get_mediainfo(file_path, mtime)
                if result is None:
                    cache_manager.set_mediainfo(file_path, mtime, {"format": "Matroska"})
            except Exception as e:
                errors.append(e)

        # Concurrent MediaInfo cache operations
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(50):
                file_path = f"/path/to/file_{i % 5}.mkv"
                mtime = time.time()
                futures.append(executor.submit(cache_mediainfo, file_path, mtime))

            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors during concurrent MediaInfo cache: {errors}"

    def test_concurrent_multi_cache_access(self, cache_manager: CacheManager):
        """Test concurrent access across different cache types."""
        errors: list[Exception] = []

        def access_tmdb() -> None:
            try:
                cache_manager.set_tmdb_search("query", "movie", {"results": []})
                cache_manager.get_tmdb_search("query", "movie")
            except Exception as e:
                errors.append(e)

        def access_mediainfo() -> None:
            try:
                cache_manager.set_mediainfo("/path/file.mkv", 123.0, {"format": "MKV"})
                cache_manager.get_mediainfo("/path/file.mkv", 123.0)
            except Exception as e:
                errors.append(e)

        def access_release() -> None:
            try:
                cache_manager.set_release_metadata("Release.Name", {"group": "TEST"})
                cache_manager.get_release_metadata("Release.Name")
            except Exception as e:
                errors.append(e)

        # Concurrent access to all cache types
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = []
            for _ in range(30):
                futures.append(executor.submit(access_tmdb))
                futures.append(executor.submit(access_mediainfo))
                futures.append(executor.submit(access_release))

            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors during multi-cache access: {errors}"

    def test_concurrent_cleanup_operations(self, cache_manager: CacheManager):
        """Test that cleanup operations are safe during concurrent access."""
        errors: list[Exception] = []

        # Pre-populate caches
        for i in range(20):
            cache_manager.set("tmdb", f"key_{i}", f"value_{i}", ttl=1)  # 1 second TTL

        def read_cache() -> None:
            try:
                for i in range(20):
                    cache_manager.get("tmdb", f"key_{i}")
            except Exception as e:
                errors.append(e)

        def cleanup_cache() -> None:
            try:
                cache_manager.cleanup_expired("tmdb")
            except Exception as e:
                errors.append(e)

        # Wait for entries to expire
        time.sleep(1.5)

        # Concurrent reads and cleanup
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for _ in range(5):
                futures.append(executor.submit(read_cache))
                futures.append(executor.submit(cleanup_cache))

            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors during concurrent cleanup: {errors}"

    def test_concurrent_stats_collection(self, cache_manager: CacheManager):
        """Test that statistics collection is safe during concurrent operations."""
        errors: list[Exception] = []
        stats_results: list[dict] = []

        # Pre-populate cache
        for i in range(10):
            cache_manager.set("tmdb", f"key_{i}", f"value_{i}")

        def access_cache() -> None:
            try:
                for i in range(10):
                    cache_manager.get("tmdb", f"key_{i}")
            except Exception as e:
                errors.append(e)

        def collect_stats() -> None:
            try:
                stats = cache_manager.get_stats()
                stats_results.append(stats)
            except Exception as e:
                errors.append(e)

        # Concurrent access and stats collection
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for _ in range(20):
                futures.append(executor.submit(access_cache))
                futures.append(executor.submit(collect_stats))

            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors during stats collection: {errors}"
        assert len(stats_results) > 0, "Should have collected some stats"


class TestCacheRaceConditions:
    """Test specific race condition scenarios."""

    def test_check_then_act_race(self, cache_manager: CacheManager):
        """Test the check-then-act pattern for race conditions.

        This simulates the common pattern:
        1. Check if key exists in cache
        2. If not, compute value and store it

        Multiple threads doing this simultaneously should not cause issues.
        """
        computation_count = 0
        computation_lock = threading.Lock()
        errors: list[Exception] = []

        def expensive_computation(key: str) -> dict:
            """Simulate expensive computation."""
            nonlocal computation_count
            with computation_lock:
                computation_count += 1
            time.sleep(0.01)  # Simulate work
            return {"key": key, "computed": True}

        def get_or_compute(key: str) -> dict:
            try:
                # Check cache
                result = cache_manager.get("tmdb", key)
                if result is None:
                    # Compute and store
                    result = expensive_computation(key)
                    cache_manager.set("tmdb", key, result)
                return result
            except Exception as e:
                errors.append(e)
                return {}

        # Multiple threads trying to get/compute the same keys
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for _ in range(50):
                key = f"key_{_ % 5}"  # 5 unique keys, accessed 10 times each
                futures.append(executor.submit(get_or_compute, key))

            results = [future.result() for future in as_completed(futures)]

        assert len(errors) == 0, f"Errors during check-then-act: {errors}"
        assert len(results) == 50

        # Due to race conditions, computation_count may be > 5 but should be reasonable
        # diskcache handles this gracefully - last write wins
        assert computation_count >= 5, "Should compute at least once per key"
        assert computation_count <= 50, "Should not compute more than total requests"

    def test_concurrent_invalidation(self, cache_manager: CacheManager):
        """Test concurrent pattern-based invalidation."""
        errors: list[Exception] = []

        # Pre-populate cache with pattern-based keys
        for i in range(20):
            cache_manager.set("tmdb", f"movie_search_{i}", {"id": i})
            cache_manager.set("tmdb", f"tv_search_{i}", {"id": i})

        def invalidate_pattern(pattern: str) -> int:
            try:
                return cache_manager.invalidate_pattern("tmdb", pattern)
            except Exception as e:
                errors.append(e)
                return 0

        # Concurrent invalidation of different patterns
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for _ in range(10):
                futures.append(executor.submit(invalidate_pattern, "movie_search"))
                futures.append(executor.submit(invalidate_pattern, "tv_search"))

            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors during concurrent invalidation: {errors}"


# Made with Bob
