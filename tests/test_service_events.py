from __future__ import annotations

from threading import Thread
from time import sleep

from framekit.core.service.events import (
    emit_service_event,
    list_service_events_recent,
    wait_for_service_events,
)


def test_service_events_recent_includes_emitted_event() -> None:
    emitted = emit_service_event(
        "test.event.recent",
        message="Recent event test",
        data={"marker": "recent-1"},
    )
    recent = list_service_events_recent(20)
    assert any(item["id"] == emitted["id"] for item in recent)
    matching = next(item for item in recent if item["id"] == emitted["id"])
    assert matching["type"] == "test.event.recent"
    assert matching["message"] == "Recent event test"
    assert matching["data"]["marker"] == "recent-1"


def test_wait_for_service_events_returns_new_events() -> None:
    latest = list_service_events_recent(1)
    after_id = latest[-1]["id"] if latest else "0"

    emitted: dict[str, str] = {}

    def _emit_later() -> None:
        sleep(0.05)
        event = emit_service_event(
            "test.event.wait",
            message="Wait event test",
            data={"marker": "wait-1"},
        )
        emitted["id"] = str(event["id"])

    t = Thread(target=_emit_later, daemon=True)
    t.start()
    batch = wait_for_service_events(after_id=after_id, timeout_s=0.5)
    t.join(timeout=0.5)

    assert emitted.get("id")
    assert any(item["id"] == emitted["id"] for item in batch)

