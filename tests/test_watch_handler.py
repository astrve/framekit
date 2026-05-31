"""Unit tests for :mod:`swirrl.modules.watch.handler`.

Covers event routing (``on_created`` / ``on_modified`` / ``on_moved``), the
failed-file relocation helper, status snapshot, log-event truncation and
uptime formatting. ``process_file`` is intentionally NOT exercised here —
it invokes the full pipeline and is covered by the pipeline smoke tests.
"""

from __future__ import annotations

from pathlib import Path
from queue import Queue
from typing import Any

import pytest

from swirrl.modules.watch.handler import FileHandler
from swirrl.modules.watch.models import (
    ErrorHandlingConfig,
    NotificationConfig,
    ValidationConfig,
    WatchConfig,
)
from swirrl.modules.watch.notifier import WindowsNotifier
from swirrl.modules.watch.validator import FileValidator


@pytest.fixture
def watch_config() -> WatchConfig:
    return WatchConfig(
        enabled=False,
        folders=[],
        validation=ValidationConfig(stability_timeout=4, check_interval=2, min_file_size=10),
        extensions=[".mkv", ".mp4"],
        ignore_extensions=[".tmp", ".part"],
        error_handling=ErrorHandlingConfig(failed_folder="failed", move_on_error=True),
        notifications=NotificationConfig(enabled=False),
    )


@pytest.fixture
def validator(watch_config: WatchConfig) -> FileValidator:
    return FileValidator(
        config=watch_config.validation,
        valid_extensions=watch_config.extensions,
        ignore_extensions=watch_config.ignore_extensions,
    )


@pytest.fixture
def notifier(watch_config: WatchConfig) -> WindowsNotifier:
    return WindowsNotifier(watch_config.notifications)


@pytest.fixture
def queue() -> Queue:
    return Queue()


@pytest.fixture
def handler(
    watch_config: WatchConfig,
    validator: FileValidator,
    notifier: WindowsNotifier,
    queue: Queue,
) -> FileHandler:
    return FileHandler(watch_config, validator, notifier, queue)


# ---------------------------------------------------------------------------
# on_created
# ---------------------------------------------------------------------------


def test_on_created_queues_valid_file(handler: FileHandler, tmp_path: Path) -> None:
    target = tmp_path / "release.mkv"
    target.write_bytes(b"\x00" * 1024)
    handler.on_created(target)
    assert handler.processing_queue.qsize() == 1
    assert str(target) in handler.file_timestamps
    assert any(e["type"] == "created" for e in handler.recent_events)


def test_on_created_skips_temporary(handler: FileHandler, tmp_path: Path) -> None:
    target = tmp_path / "download.tmp"
    target.write_bytes(b"\x00" * 1024)
    handler.on_created(target)
    assert handler.processing_queue.qsize() == 0
    assert str(target) not in handler.file_timestamps


def test_on_created_skips_invalid_extension(handler: FileHandler, tmp_path: Path) -> None:
    target = tmp_path / "release.avi"
    target.write_bytes(b"\x00" * 1024)
    handler.on_created(target)
    assert handler.processing_queue.qsize() == 0


# ---------------------------------------------------------------------------
# on_modified / on_moved
# ---------------------------------------------------------------------------


def test_on_modified_updates_timestamp(handler: FileHandler, tmp_path: Path) -> None:
    target = tmp_path / "release.mkv"
    target.write_bytes(b"\x00" * 1024)
    handler.on_created(target)
    before = handler.file_timestamps[str(target)]
    handler.on_modified(target)
    after = handler.file_timestamps[str(target)]
    assert after >= before


def test_on_modified_ignores_unknown_file(handler: FileHandler, tmp_path: Path) -> None:
    target = tmp_path / "ghost.mkv"
    handler.on_modified(target)
    assert str(target) not in handler.file_timestamps


def test_on_moved_queues_destination(handler: FileHandler, tmp_path: Path) -> None:
    src = tmp_path / "old.mkv"
    dst = tmp_path / "new.mkv"
    dst.write_bytes(b"\x00" * 1024)
    handler.on_moved(src, dst)
    assert handler.processing_queue.qsize() == 1
    assert str(dst) in handler.file_timestamps


# ---------------------------------------------------------------------------
# handle_failed_file
# ---------------------------------------------------------------------------


def test_handle_failed_file_moves_to_failed_folder(handler: FileHandler, tmp_path: Path) -> None:
    target = tmp_path / "broken.mkv"
    target.write_bytes(b"\x00" * 1024)
    handler.handle_failed_file(target, "boom")
    failed = tmp_path / "failed" / "broken.mkv"
    assert failed.exists()
    assert not target.exists()


def test_handle_failed_file_renames_on_collision(handler: FileHandler, tmp_path: Path) -> None:
    failed_folder = tmp_path / "failed"
    failed_folder.mkdir()
    pre_existing = failed_folder / "broken.mkv"
    pre_existing.write_bytes(b"original")

    target = tmp_path / "broken.mkv"
    target.write_bytes(b"new")
    handler.handle_failed_file(target, "boom")

    assert pre_existing.exists()
    assert pre_existing.read_bytes() == b"original"
    assert (failed_folder / "broken_1.mkv").exists()


def test_handle_failed_file_skipped_when_disabled(handler: FileHandler, tmp_path: Path) -> None:
    handler.config.error_handling.move_on_error = False
    target = tmp_path / "still-here.mkv"
    target.write_bytes(b"\x00")
    handler.handle_failed_file(target, "boom")
    assert target.exists()
    assert not (tmp_path / "failed").exists()


def test_handle_failed_file_swallows_move_errors(
    handler: FileHandler, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A filesystem error must not raise out of ``handle_failed_file``."""

    target = tmp_path / "release.mkv"
    target.write_bytes(b"\x00")

    def _raise(self: Path, *args: Any, **kwargs: Any) -> None:
        raise PermissionError("simulated denial")

    monkeypatch.setattr(Path, "rename", _raise)
    # Must not raise.
    handler.handle_failed_file(target, "boom")


# ---------------------------------------------------------------------------
# Status / log event
# ---------------------------------------------------------------------------


def test_log_event_caps_recent_events(handler: FileHandler, tmp_path: Path) -> None:
    target = tmp_path / "release.mkv"
    target.write_bytes(b"\x00")
    for _ in range(75):
        handler.log_event("created", target)
    # Cap is 50.
    assert len(handler.recent_events) == 50


def test_get_current_status_reports_queue_and_processed(
    handler: FileHandler, tmp_path: Path
) -> None:
    target = tmp_path / "release.mkv"
    target.write_bytes(b"\x00")
    handler.on_created(target)
    handler.files_processed = 4
    status = handler.get_current_status()
    assert status.files_in_queue == 1
    assert status.files_processed == 4
    assert status.running is True


# ---------------------------------------------------------------------------
# _format_uptime
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (5, "5s"),
        (65, "1m 5s"),
        (3665, "1h 1m 5s"),
        (90061, "1d 1h 1m 1s"),
        (0, "0s"),
    ],
)
def test_format_uptime(handler: FileHandler, seconds: float, expected: str) -> None:
    assert handler._format_uptime(seconds) == expected


# ---------------------------------------------------------------------------
# Periodic status timer
# ---------------------------------------------------------------------------


def test_start_periodic_status_creates_timer(
    handler: FileHandler, monkeypatch: pytest.MonkeyPatch
) -> None:
    started: list[bool] = []

    class _FakeTimer:
        def __init__(self, interval: float, fn: Any) -> None:
            self.interval = interval
            self.fn = fn
            self.daemon = False

        def start(self) -> None:
            started.append(True)

        def cancel(self) -> None:
            started.append(False)

    import threading as _threading

    monkeypatch.setattr(_threading, "Timer", _FakeTimer)
    handler.start_periodic_status()
    assert started == [True]
    assert handler.status_timer is not None


def test_stop_periodic_status_cancels(handler: FileHandler) -> None:
    cancelled: list[bool] = []

    class _Timer:
        def cancel(self) -> None:
            cancelled.append(True)

    handler.status_timer = _Timer()  # type: ignore[assignment]
    handler.stop_periodic_status()
    assert cancelled == [True]
    assert handler.status_timer is None
