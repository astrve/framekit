"""Cache entry models for the intelligent caching system."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CacheEntry:
    """Represents a single cache entry with metadata.

    Attributes:
        key: Unique identifier for the cache entry
        value: The cached data (can be any JSON-serializable type)
        created_at: Unix timestamp when the entry was created
        expires_at: Unix timestamp when the entry expires
        access_count: Number of times this entry has been accessed
        last_accessed: Unix timestamp of the last access
        metadata: Optional metadata about the cached entry
    """

    key: str
    value: Any
    created_at: float
    expires_at: float
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        return time.time() > self.expires_at

    def touch(self) -> None:
        """Update access statistics."""
        self.access_count += 1
        self.last_accessed = time.time()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "key": self.key,
            "value": self.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CacheEntry:
        """Create from dictionary."""
        return cls(
            key=data["key"],
            value=data["value"],
            created_at=data["created_at"],
            expires_at=data["expires_at"],
            access_count=data.get("access_count", 0),
            last_accessed=data.get("last_accessed", data["created_at"]),
            metadata=data.get("metadata", {}),
        )


@dataclass
class CacheStats:
    """Statistics about cache usage.

    Attributes:
        hits: Number of successful cache retrievals
        misses: Number of cache misses
        total_entries: Total number of entries in cache
        total_size_bytes: Total size of cache in bytes
        expired_entries: Number of expired entries
        cache_type: Type of cache (tmdb, mediainfo, release)
    """

    hits: int = 0
    misses: int = 0
    total_entries: int = 0
    total_size_bytes: int = 0
    expired_entries: int = 0
    cache_type: str = ""

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate as a percentage."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return (self.hits / total) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "total_entries": self.total_entries,
            "total_size_bytes": self.total_size_bytes,
            "expired_entries": self.expired_entries,
            "cache_type": self.cache_type,
            "hit_rate": self.hit_rate,
        }
