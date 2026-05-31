"""Local disk-backed cache backend (pickle-free).

Provides the subset of the old ``diskcache.Cache`` API used by Swirrl.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def _json_default(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"__swirrl_type__": "bytes", "hex": value.hex()}
    return str(value)


def _json_object_hook(value: dict[str, Any]) -> Any:
    if value.get("__swirrl_type__") == "bytes":
        try:
            return bytes.fromhex(str(value.get("hex", "")))
        except ValueError:
            return b""
    return value


class Cache:
    """SQLite-backed cache with a diskcache-compatible surface."""

    def __init__(self, directory: str, size_limit: int | None = None) -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self._dir / "cache.sqlite3"
        self._size_limit = int(size_limit or 0)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cache_entries (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                expires_at REAL,
                updated_at REAL NOT NULL
            )
            """
        )
        self._conn.commit()

    def __iter__(self) -> Iterator[str]:
        with self._lock:
            self._purge_expired_locked()
            rows = self._conn.execute("SELECT key FROM cache_entries").fetchall()
        for (key,) in rows:
            yield str(key)

    def __len__(self) -> int:
        with self._lock:
            self._purge_expired_locked()
            (count,) = self._conn.execute("SELECT COUNT(*) FROM cache_entries").fetchone() or (0,)
        return int(count)

    def _dump(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, default=_json_default, separators=(",", ":"))

    def _load(self, payload: str) -> Any:
        return json.loads(payload, object_hook=_json_object_hook)

    def _purge_expired_locked(self) -> None:
        now = time.time()
        self._conn.execute(
            "DELETE FROM cache_entries WHERE expires_at IS NOT NULL AND expires_at <= ?",
            (now,),
        )
        self._conn.commit()

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self._conn.execute(
                "SELECT value_json, expires_at FROM cache_entries WHERE key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return default
            value_json, expires_at = row
            if expires_at is not None and float(expires_at) <= time.time():
                self._conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                self._conn.commit()
                return default
            try:
                return self._load(str(value_json))
            except json.JSONDecodeError:
                return default

    def set(self, key: str, value: Any, expire: int | None = None) -> None:
        payload = self._dump(value)
        now = time.time()
        expires_at = now + int(expire) if expire is not None else None
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO cache_entries(key, value_json, expires_at, updated_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    expires_at = excluded.expires_at,
                    updated_at = excluded.updated_at
                """,
                (key, payload, expires_at, now),
            )
            self._conn.commit()
            if self._size_limit > 0 and self.volume() > self._size_limit:
                self.cull()

    def delete(self, key: str) -> bool:
        with self._lock:
            cursor = self._conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
            self._conn.commit()
        return cursor.rowcount > 0

    def clear(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM cache_entries")
            self._conn.commit()

    def cull(self) -> int:
        if self._size_limit <= 0:
            return 0
        removed = 0
        with self._lock:
            self._purge_expired_locked()
            while self.volume() > self._size_limit:
                row = self._conn.execute(
                    "SELECT key FROM cache_entries ORDER BY updated_at ASC LIMIT 1"
                ).fetchone()
                if row is None:
                    break
                self._conn.execute("DELETE FROM cache_entries WHERE key = ?", (row[0],))
                removed += 1
            self._conn.commit()
        return removed

    def volume(self) -> int:
        total = self._db_path.stat().st_size if self._db_path.exists() else 0
        wal_path = self._db_path.with_name(self._db_path.name + "-wal")
        shm_path = self._db_path.with_name(self._db_path.name + "-shm")
        if wal_path.exists():
            total += wal_path.stat().st_size
        if shm_path.exists():
            total += shm_path.stat().st_size
        return total
