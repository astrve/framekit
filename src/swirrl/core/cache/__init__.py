"""Intelligent caching system for TMDb and MediaInfo data."""

from swirrl.core.cache.manager import CacheManager
from swirrl.core.cache.models import CacheEntry, CacheStats
from swirrl.core.cache.storage import CacheStorage
from swirrl.core.cache.strategies import (
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
