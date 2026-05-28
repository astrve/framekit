"""In-process service events bus with bounded in-memory retention.

Event shape:
    {
      "id": "1",
      "ts": "2026-05-28T16:31:00.000000+00:00",
      "type": "job.started",
      "level": "info",
      "message": "Job started",
      "data": {...}  # optional
    }
"""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from threading import Condition
from typing import Any

_DEFAULT_MAX_EVENTS = 500


def _parse_event_id(raw: str | None) -> int:
    if raw is None:
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


class _ServiceEventBus:
    def __init__(self, max_events: int = _DEFAULT_MAX_EVENTS) -> None:
        self._max_events = max(1, int(max_events))
        self._events: deque[dict[str, Any]] = deque(maxlen=self._max_events)
        self._next_id = 1
        self._condition = Condition()

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
            self._condition.notify_all()
            return dict(payload)

    def recent(self, limit: int) -> list[dict[str, Any]]:
        bounded = min(max(1, int(limit)), self._max_events)
        with self._condition:
            tail = list(self._events)[-bounded:]
            return [dict(item) for item in tail]

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
    """Emit one service event into the in-process ring buffer."""
    return _EVENT_BUS.emit(event_type, level=level, message=message, data=data)


def list_service_events_recent(limit: int = 100) -> list[dict[str, Any]]:
    """Return recent service events, oldest->newest, bounded by ring size."""
    return _EVENT_BUS.recent(limit)


def wait_for_service_events(
    *,
    after_id: str | None,
    timeout_s: float = 15.0,
) -> list[dict[str, Any]]:
    """Block up to timeout and return events newer than after_id."""
    return _EVENT_BUS.wait_for_newer_than(after_id=after_id, timeout_s=timeout_s)


__all__ = [
    "emit_service_event",
    "list_service_events_recent",
    "wait_for_service_events",
]

