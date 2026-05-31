"""Singleton ``SettingsStore`` with mtime-based cache invalidation."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from swirrl.core.settings import SettingsStore


class SettingsSingleton:
    """Process-wide cache for the ``SettingsStore`` instance and its data.

    The store itself is cheap to recreate, but each ``load()`` re-reads the
    YAML file and re-runs validation. This singleton tracks the file mtime so
    that callers requesting the parsed dict only pay the I/O cost when the
    file actually changed on disk.

    The cache is thread-safe via two locks:

    * ``_lock`` guards instance creation (double-checked locking).
    * ``_cache_lock`` guards the per-instance state (store + cached data +
      mtime). All public methods take it for the full read-then-update window.
    """

    _instance: SettingsSingleton | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._store: SettingsStore | None = None
        self._data: dict[str, Any] | None = None
        self._config_path: Path | None = None
        self._last_mtime: float | None = None
        self._cache_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> SettingsSingleton:
        """Return the instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Drop the singleton (test helper)."""
        with cls._lock:
            cls._instance = None

    def _current_path(self) -> Path:
        from swirrl.core.paths import get_settings_path

        return get_settings_path()

    def _needs_reload(self, current_path: Path) -> bool:
        if self._store is None or self._data is None:
            return True
        if self._config_path != current_path:
            return True
        if not current_path.exists():
            return self._last_mtime is not None
        return current_path.stat().st_mtime != self._last_mtime

    def _refresh(self, current_path: Path) -> None:
        self._store = SettingsStore(current_path)
        self._data = self._store.load()
        self._config_path = current_path
        self._last_mtime = current_path.stat().st_mtime if current_path.exists() else None

    def get_settings(self) -> SettingsStore:
        """Return the settings."""
        with self._cache_lock:
            current_path = self._current_path()
            if self._needs_reload(current_path):
                self._refresh(current_path)
            assert self._store is not None  # nosec B101
            return self._store

    def get_data(self) -> dict[str, Any]:
        """Return the cached parsed settings dict.

        Re-reads disk only when the file's mtime changed (or the file was
        moved/replaced). The returned dict is a fresh deep copy so callers
        that mutate it cannot corrupt the cache for everyone else.
        """
        with self._cache_lock:
            current_path = self._current_path()
            if self._needs_reload(current_path):
                self._refresh(current_path)
            assert self._data is not None  # nosec B101
            return _deepcopy_settings(self._data)

    def invalidate(self) -> None:
        """Force a reload on the next call."""
        with self._cache_lock:
            self._last_mtime = None
            self._data = None


def _deepcopy_settings(data: dict[str, Any]) -> dict[str, Any]:
    from copy import deepcopy

    return deepcopy(data)


def get_settings() -> SettingsStore:
    """Return the cached ``SettingsStore`` instance."""
    return SettingsSingleton.get_instance().get_settings()


def get_settings_data() -> dict[str, Any]:
    """Return a fresh copy of the cached parsed settings dict."""
    return SettingsSingleton.get_instance().get_data()
