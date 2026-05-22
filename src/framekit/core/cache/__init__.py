"""Intelligent caching system for TMDb and MediaInfo data."""

from framekit.core.cache.manager import CacheManager
from framekit.core.cache.models import CacheEntry, CacheStats
from framekit.core.cache.storage import CacheStorage
from framekit.core.cache.strategies import (
    CompositeStrategy,
    FileModificationStrategy,
    TTLStrategy,
    generate_cache_key,
    generate_file_cache_key,
)

__all__ = [
    "CacheEntry",
    "CacheManager",
    "CacheStats",
    "CacheStorage",
    "CompositeStrategy",
    "FileModificationStrategy",
    "TTLStrategy",
    "generate_cache_key",
    "generate_file_cache_key",
]
