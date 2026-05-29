from __future__ import annotations

import json
from threading import Thread
from time import sleep

from ouro.core.service.events import (
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


def test_service_events_persisted_history_and_fallback(monkeypatch, tmp_path) -> None:
    import ouro.core.service.events as service_events

    history_path = tmp_path / "events.ndjson"
    monkeypatch.setattr(service_events, "_service_events_path", lambda: history_path)
    monkeypatch.setattr(service_events, "_service_events_rotated_path", lambda index: tmp_path / f"events.ndjson.{index}")

    emitted = emit_service_event(
        "test.event.persist",
        message="Persisted event test",
        data={"marker": "persist-1"},
    )
    assert history_path.exists()
    lines = history_path.read_text(encoding="utf-8").strip().splitlines()
    assert lines
    parsed = json.loads(lines[-1])
    assert parsed["id"] == emitted["id"]

    # Clear in-memory ring to force disk fallback.
    with service_events._EVENT_BUS._condition:  # noqa: SLF001 - test-only access
        service_events._EVENT_BUS._events.clear()  # noqa: SLF001 - test-only access
    recent = list_service_events_recent(1)
    assert recent
    assert recent[-1]["id"] == emitted["id"]
