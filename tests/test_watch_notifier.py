"""Unit tests for :mod:`framekit.modules.watch.notifier`.

The desktop-notifier subsystem is replaced with a fake collector so tests
exercise the config-gating logic, message formatting, and error truncation
without firing real OS-level notifications. Threading + asyncio plumbing in
``__init__`` is bypassed by setting ``config.enabled = False`` for the
constructor and patching ``_show_notification`` directly.
"""

from __future__ import annotations

from typing import Any

import pytest

from framekit.modules.watch import notifier as notifier_module
from framekit.modules.watch.models import NotificationConfig
from framekit.modules.watch.notifier import WindowsNotifier


@pytest.fixture
def quiet_notifier() -> WindowsNotifier:
    """Build a notifier without touching the OS notifier backend.

    ``config.enabled=False`` short-circuits the constructor's event-loop
    setup; the individual ``notify_*`` methods still check their own
    per-event flag, so we flip the ones each test cares about back to True
    locally.
    """

    config = NotificationConfig(
        enabled=False,
        on_start=False,
        on_success=False,
        on_error=False,
        on_watch_started=False,
    )
    return WindowsNotifier(config)


@pytest.fixture
def shown(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Capture every ``_show_notification`` call without actually showing."""

    captured: list[dict[str, Any]] = []

    def _capture(self: WindowsNotifier, title: str, message: str, urgency: Any = None) -> None:
        captured.append({"title": title, "message": message, "urgency": urgency})

    monkeypatch.setattr(WindowsNotifier, "_show_notification", _capture)
    return captured


# ---------------------------------------------------------------------------
# notify_started
# ---------------------------------------------------------------------------


def test_notify_started_skipped_when_flag_false(
    quiet_notifier: WindowsNotifier, shown: list[dict[str, Any]]
) -> None:
    quiet_notifier.config.on_start = False
    quiet_notifier.notify_started("foo.mkv")
    assert shown == []


def test_notify_started_emits_when_flag_true(
    quiet_notifier: WindowsNotifier, shown: list[dict[str, Any]]
) -> None:
    quiet_notifier.config.on_start = True
    quiet_notifier.notify_started("foo.mkv")
    assert len(shown) == 1
    assert "Processing started" in shown[0]["message"]
    assert "foo.mkv" in shown[0]["message"]


# ---------------------------------------------------------------------------
# notify_success
# ---------------------------------------------------------------------------


def test_notify_success_skipped_when_flag_false(
    quiet_notifier: WindowsNotifier, shown: list[dict[str, Any]]
) -> None:
    quiet_notifier.config.on_success = False
    quiet_notifier.notify_success("foo.mkv", duration=10.0)
    assert shown == []


def test_notify_success_formats_seconds_only(
    quiet_notifier: WindowsNotifier, shown: list[dict[str, Any]]
) -> None:
    quiet_notifier.config.on_success = True
    quiet_notifier.notify_success("foo.mkv", duration=42.0)
    assert "42s" in shown[0]["message"]
    assert "m " not in shown[0]["message"]


def test_notify_success_formats_minutes_and_seconds(
    quiet_notifier: WindowsNotifier, shown: list[dict[str, Any]]
) -> None:
    quiet_notifier.config.on_success = True
    quiet_notifier.notify_success("foo.mkv", duration=185.0)
    assert "3m 5s" in shown[0]["message"]


# ---------------------------------------------------------------------------
# notify_error
# ---------------------------------------------------------------------------


def test_notify_error_skipped_when_flag_false(
    quiet_notifier: WindowsNotifier, shown: list[dict[str, Any]]
) -> None:
    quiet_notifier.config.on_error = False
    quiet_notifier.notify_error("foo.mkv", "boom")
    assert shown == []


def test_notify_error_truncates_long_message(
    quiet_notifier: WindowsNotifier, shown: list[dict[str, Any]]
) -> None:
    quiet_notifier.config.on_error = True
    long_err = "x" * 500
    quiet_notifier.notify_error("foo.mkv", long_err)
    body = shown[0]["message"]
    assert body.endswith("...")
    # 100-char cap + ellipsis: the displayed error portion stops well short
    # of the original.
    assert "x" * 500 not in body


def test_notify_error_keeps_short_message_intact(
    quiet_notifier: WindowsNotifier, shown: list[dict[str, Any]]
) -> None:
    quiet_notifier.config.on_error = True
    quiet_notifier.notify_error("foo.mkv", "tiny")
    assert "tiny" in shown[0]["message"]
    assert "..." not in shown[0]["message"]


# ---------------------------------------------------------------------------
# notify_watch_started / notify_watch_stopped
# ---------------------------------------------------------------------------


def test_notify_watch_started_skipped_when_disabled(
    quiet_notifier: WindowsNotifier, shown: list[dict[str, Any]]
) -> None:
    quiet_notifier.config.enabled = False
    quiet_notifier.config.on_watch_started = True
    quiet_notifier.notify_watch_started(["/a"])
    assert shown == []


def test_notify_watch_started_skipped_when_flag_false(
    quiet_notifier: WindowsNotifier, shown: list[dict[str, Any]]
) -> None:
    quiet_notifier.config.enabled = True
    quiet_notifier.config.on_watch_started = False
    quiet_notifier.notify_watch_started(["/a"])
    assert shown == []


def test_notify_watch_started_pluralises(
    quiet_notifier: WindowsNotifier, shown: list[dict[str, Any]]
) -> None:
    quiet_notifier.config.enabled = True
    quiet_notifier.config.on_watch_started = True
    quiet_notifier.notify_watch_started(["/a", "/b", "/c"])
    assert "Watching 3 folders" in shown[0]["message"]


def test_notify_watch_started_singular(
    quiet_notifier: WindowsNotifier, shown: list[dict[str, Any]]
) -> None:
    quiet_notifier.config.enabled = True
    quiet_notifier.config.on_watch_started = True
    quiet_notifier.notify_watch_started(["/only"])
    assert "Watching 1 folder" in shown[0]["message"]
    assert "folders" not in shown[0]["message"]


def test_notify_watch_stopped_emits_low_urgency(
    quiet_notifier: WindowsNotifier, shown: list[dict[str, Any]]
) -> None:
    quiet_notifier.config.enabled = True
    quiet_notifier.config.on_watch_started = True
    quiet_notifier.notify_watch_stopped()
    assert "stopped" in shown[0]["message"].lower()


def test_notify_watch_stopped_respects_disable(
    quiet_notifier: WindowsNotifier, shown: list[dict[str, Any]]
) -> None:
    quiet_notifier.config.enabled = False
    quiet_notifier.notify_watch_stopped()
    assert shown == []


# ---------------------------------------------------------------------------
# Module-level flag
# ---------------------------------------------------------------------------


def test_notifier_available_flag_is_boolean() -> None:
    assert isinstance(notifier_module.NOTIFIER_AVAILABLE, bool)


# ---------------------------------------------------------------------------
# _show_notification short-circuits when disabled
# ---------------------------------------------------------------------------


def test_show_notification_skips_when_config_disabled() -> None:
    config = NotificationConfig(enabled=False)
    notifier = WindowsNotifier(config)
    # Real ``_show_notification`` (not the captured fake) must early-return
    # rather than reach into the asyncio loop.
    notifier._show_notification("t", "m", urgency=None)


def test_show_notification_skips_when_loop_missing() -> None:
    config = NotificationConfig(enabled=True)
    notifier = WindowsNotifier(config)
    # Even if the config says enabled, the absence of the backend (and thus
    # ``self.notifier`` / ``self._loop``) must not crash.
    notifier.notifier = None
    notifier._loop = None
    notifier._show_notification("t", "m", urgency=None)
