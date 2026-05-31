"""Unit tests for :mod:`swirrl.modules.watch.service`."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from swirrl.modules.watch import service as watch_service
from swirrl.modules.watch.models import (
    ErrorHandlingConfig,
    NotificationConfig,
    ValidationConfig,
    WatchConfig,
    WatchFolder,
)
from swirrl.modules.watch.service import WatcherService


def _watch_config(tmp_path: Path) -> WatchConfig:
    watched = tmp_path / "watch"
    watched.mkdir()
    return WatchConfig(
        enabled=True,
        folders=[WatchFolder(path=watched, preset="default", enabled=True)],
        validation=ValidationConfig(stability_timeout=1, check_interval=1, min_file_size=1),
        extensions=[".mkv"],
        ignore_extensions=[".tmp"],
        error_handling=ErrorHandlingConfig(failed_folder="failed", move_on_error=True),
        notifications=NotificationConfig(enabled=False),
    )


def test_validate_configuration_rejects_missing_folders() -> None:
    service = WatcherService(WatchConfig(enabled=True, folders=[]))
    with pytest.raises(ValueError, match="No folders configured"):
        service._validate_configuration()


def test_create_folders_and_find_folder_config(tmp_path: Path) -> None:
    service = WatcherService(_watch_config(tmp_path))
    service._create_folders()

    watched = service.config.folders[0].path
    assert (watched / "failed").exists()

    target = watched / "release.mkv"
    target.write_bytes(b"x")
    found = service._find_folder_config(target)
    assert found is not None
    assert found.path == watched


def test_process_queue_success_updates_status(tmp_path: Path) -> None:
    service = WatcherService(_watch_config(tmp_path))
    target = service.config.folders[0].path / "release.mkv"
    target.write_bytes(b"payload")

    service.validator = SimpleNamespace(validate=lambda _path: (True, ""))

    def _process_file(_file_path: Path, _preset: str):
        service.stop_event.set()
        return SimpleNamespace(success=True, error=None)

    service.handler = SimpleNamespace(
        process_file=_process_file,
        handle_failed_file=lambda *_args, **_kwargs: None,
    )

    service.processing_queue.put(target)
    service._process_queue()

    assert service.status.files_processed == 1
    assert service.status.files_failed == 0


def test_process_queue_failure_calls_failed_handler(tmp_path: Path) -> None:
    service = WatcherService(_watch_config(tmp_path))
    target = service.config.folders[0].path / "release.mkv"
    target.write_bytes(b"payload")

    handled: list[tuple[Path, str]] = []
    service.validator = SimpleNamespace(validate=lambda _path: (True, ""))

    def _process_file(_file_path: Path, _preset: str):
        service.stop_event.set()
        return SimpleNamespace(success=False, error="boom")

    def _handle_failed(path: Path, error: str):
        handled.append((path, error))

    service.handler = SimpleNamespace(
        process_file=_process_file,
        handle_failed_file=_handle_failed,
    )

    service.processing_queue.put(target)
    service._process_queue()

    assert service.status.files_failed == 1
    assert handled == [(target, "boom")]


def test_read_running_watcher_pid_removes_stale_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid_file = tmp_path / ".swirrl_watch.pid"
    pid_file.write_text("12345", encoding="utf-8")
    monkeypatch.setattr(watch_service, "_pid_file_path", lambda: pid_file)
    monkeypatch.setattr(watch_service, "_pid_is_alive", lambda _pid: False)

    assert watch_service.read_running_watcher_pid() is None
    assert not pid_file.exists()


def test_stop_running_watcher_returns_false_when_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(watch_service, "read_running_watcher_pid", lambda: None)
    assert watch_service.stop_running_watcher() is False


def test_watch_folder_dispatches_created_and_modified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = WatcherService(_watch_config(tmp_path))
    events: list[tuple[str, Path]] = []

    service.handler = SimpleNamespace(
        on_created=lambda path: events.append(("created", path)),
        on_modified=lambda path: events.append(("modified", path)),
    )
    service.stop_event.set()

    target = service.config.folders[0].path / "episode.mkv"
    target.write_bytes(b"x")
    change_added = watch_service.Change.added
    change_modified = watch_service.Change.modified
    monkeypatch.setattr(
        watch_service,
        "watch",
        lambda *_args, **_kwargs: [{(change_added, str(target)), (change_modified, str(target))}],
    )

    service._watch_folder(service.config.folders[0].path)
    assert ("created", target) in events
    assert ("modified", target) in events


def test_start_and_stop_cycle_updates_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = WatcherService(_watch_config(tmp_path))

    monkeypatch.setattr(service, "_validate_configuration", lambda: None)
    monkeypatch.setattr(service, "_create_folders", lambda: None)
    monkeypatch.setattr(service, "_write_pid_file", lambda: None)
    monkeypatch.setattr(service, "_remove_pid_file", lambda: None)
    monkeypatch.setattr(service.notifier, "notify_watch_started", lambda _folders: None)
    monkeypatch.setattr(service.notifier, "notify_watch_stopped", lambda: None)

    def _fake_watch_folder(_path: Path) -> None:
        return None

    def _fake_process_queue() -> None:
        return None

    monkeypatch.setattr(service, "_watch_folder", _fake_watch_folder)
    monkeypatch.setattr(service, "_process_queue", _fake_process_queue)

    class _ImmediateThread:
        def __init__(self, target: Any, args: tuple = (), daemon: bool = False) -> None:
            self._target = target
            self._args = args
            self.daemon = daemon

        def start(self) -> None:
            self._target(*self._args)

        def join(self, timeout: float | None = None) -> None:
            _ = timeout
            return None

    monkeypatch.setattr(watch_service, "Thread", _ImmediateThread)
    monkeypatch.setattr(
        watch_service.time,
        "sleep",
        lambda _seconds: setattr(service.status, "running", False),
    )

    service.start()
    assert service.status.folders_watched
    service.status.running = True
    service.stop()
    assert service.status.running is False


def test_get_status_sets_queue_size(tmp_path: Path) -> None:
    service = WatcherService(_watch_config(tmp_path))
    service.processing_queue.put("dummy")
    status = service.get_status()
    assert status.files_in_queue == 1
