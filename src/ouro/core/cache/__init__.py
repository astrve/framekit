"""Intelligent caching system for TMDb and MediaInfo data."""

from ouro.core.cache.manager import CacheManager
from ouro.core.cache.models import CacheEntry, CacheStats
from ouro.core.cache.storage import CacheStorage
from ouro.core.cache.strategies import (
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
