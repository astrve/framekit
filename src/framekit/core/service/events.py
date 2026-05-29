"""In-process service events bus with in-memory ring + persisted NDJSON history."""

from __future__ import annotations

import json
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from threading import Condition
from typing import Any

_DEFAULT_MAX_EVENTS = 500
_DEFAULT_MAX_FILE_BYTES = 50 * 1024 * 1024
_DEFAULT_MAX_ROTATIONS = 3


def _parse_event_id(raw: str | None) -> int:
    if raw is None:
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _service_events_path() -> Path:
    from framekit.core.paths import get_service_dir

    return get_service_dir() / "events.ndjson"


def _service_events_rotated_path(index: int) -> Path:
    return _service_events_path().with_name(f"events.ndjson.{index}")


def _recent_events_from_files(limit: int) -> list[dict[str, Any]]:
    bounded = max(1, int(limit))
    lines: deque[str] = deque(maxlen=bounded)
    paths = [_service_events_path(), *(_service_events_rotated_path(i) for i in range(1, _DEFAULT_MAX_ROTATIONS + 1))]
    for path in reversed(paths):
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as fh:
                for raw in fh:
                    line = raw.strip()
                    if line:
                        lines.append(line)
        except OSError:
            continue
    result: list[dict[str, Any]] = []
    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            result.append(payload)
    return result[-bounded:]


class _ServiceEventBus:
    def __init__(self, max_events: int = _DEFAULT_MAX_EVENTS) -> None:
        self._max_events = max(1, int(max_events))
        self._events: deque[dict[str, Any]] = deque(maxlen=self._max_events)
        self._next_id = 1
        self._condition = Condition()
        self._metrics: dict[str, int] = {
            "queued": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "retried": 0,
        }
        self._load_from_history()

    def _load_from_history(self) -> None:
        tail = _recent_events_from_files(self._max_events)
        max_id = 0
        for item in tail:
            if isinstance(item, dict):
                self._events.append(dict(item))
                max_id = max(max_id, _parse_event_id(str(item.get("id"))))
        if max_id > 0:
            self._next_id = max_id + 1

    def _rotate_if_needed(self) -> None:
        events_path = _service_events_path()
        try:
            size = events_path.stat().st_size if events_path.exists() else 0
        except OSError:
            return
        if size <= _DEFAULT_MAX_FILE_BYTES:
            return
        for index in range(_DEFAULT_MAX_ROTATIONS, 0, -1):
            src = _service_events_rotated_path(index)
            dst = _service_events_rotated_path(index + 1)
            if src.exists():
                if index == _DEFAULT_MAX_ROTATIONS:
                    try:
                        src.unlink()
                    except OSError:
                        pass
                else:
                    try:
                        src.replace(dst)
                    except OSError:
                        pass
        if events_path.exists():
            try:
                events_path.replace(_service_events_rotated_path(1))
            except OSError:
                pass

    def _append_to_history(self, payload: dict[str, Any]) -> None:
        events_path = _service_events_path()
        try:
            events_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            return
        self._rotate_if_needed()
        try:
            with events_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False))
                fh.write("\n")
        except OSError:
            return

    def _bump_metrics(self, event_type: str) -> None:
        if event_type == "job.queued":
            self._metrics["queued"] += 1
        elif event_type == "job.started":
            self._metrics["running"] += 1
        elif event_type == "job.completed":
            self._metrics["completed"] += 1
        elif event_type == "job.failed":
            self._metrics["failed"] += 1
        elif event_type == "job.retry_scheduled":
            self._metrics["retried"] += 1

    def emit(
        self,
        event_type: str,
        *,
        level: str,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._condition:
            event_id = str(self._next_id)
            self._next_id += 1
            payload: dict[str, Any] = {
                "id": event_id,
                "ts": datetime.now(UTC).isoformat(),
                "type": event_type,
                "level": level,
                "message": message,
            }
            if data:
                payload["data"] = dict(data)
            self._events.append(payload)
            self._append_to_history(payload)
            self._bump_metrics(event_type)
            self._condition.notify_all()
            return dict(payload)

    def recent(self, limit: int) -> list[dict[str, Any]]:
        bounded = max(1, int(limit))
        with self._condition:
            in_memory = [dict(item) for item in list(self._events)[-bounded:]]
        if len(in_memory) >= bounded:
            return in_memory[-bounded:]

        disk = _recent_events_from_files(bounded)
        by_id: dict[str, dict[str, Any]] = {}
        for item in disk:
            key = str(item.get("id", ""))
            if key:
                by_id[key] = dict(item)
        for item in in_memory:
            key = str(item.get("id", ""))
            if key:
                by_id[key] = dict(item)
        merged = sorted(by_id.values(), key=lambda item: _parse_event_id(str(item.get("id"))))
        return merged[-bounded:]

    def metrics(self) -> dict[str, int]:
        with self._condition:
            return dict(self._metrics)

    def wait_for_newer_than(
        self,
        *,
        after_id: str | None,
        timeout_s: float,
    ) -> list[dict[str, Any]]:
        after = _parse_event_id(after_id)
        timeout = max(0.0, float(timeout_s))

        with self._condition:
            ready = [
                dict(item)
                for item in self._events
                if _parse_event_id(str(item.get("id"))) > after
            ]
            if ready:
                return ready

            self._condition.wait(timeout=timeout)
            return [
                dict(item)
                for item in self._events
                if _parse_event_id(str(item.get("id"))) > after
            ]


_EVENT_BUS = _ServiceEventBus()


def emit_service_event(
    event_type: str,
    *,
    level: str = "info",
    message: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Emit one service event into ring buffer and persisted history."""
    return _EVENT_BUS.emit(event_type, level=level, message=message, data=data)


def list_service_events_recent(limit: int = 100) -> list[dict[str, Any]]:
    """Return recent service events, oldest->newest, from memory+history."""
    return _EVENT_BUS.recent(limit)


def get_service_event_metrics() -> dict[str, int]:
    """Return in-memory service event counters."""
    return _EVENT_BUS.metrics()


def wait_for_service_events(
    *,
    after_id: str | None,
    timeout_s: float = 15.0,
) -> list[dict[str, Any]]:
    """Block up to timeout and return events newer than after_id."""
    return _EVENT_BUS.wait_for_newer_than(after_id=after_id, timeout_s=timeout_s)


__all__ = [
    "emit_service_event",
    "get_service_event_metrics",
    "list_service_events_recent",
    "wait_for_service_events",
]
