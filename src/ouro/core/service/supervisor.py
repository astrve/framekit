"""Service supervisor: exclusive lock, PID file, heartbeat state.

Lifecycle:
    supervisor = ServiceSupervisor(get_service_dir())
    supervisor.acquire()   # raises RuntimeError if another process holds the lock
    try:
        run_server()
    finally:
        supervisor.release()

Files written under service_dir:
    service.lock        — filelock held exclusively while running
    service.pid         — plain-text PID of the running process
    service.state.json  — heartbeat JSON: status, pid, started_at, heartbeat_at
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from time import time
from typing import Any

from loguru import logger


class ServiceSupervisor:
    """Manages service.lock, service.pid, and service.state.json heartbeat."""

    HEARTBEAT_INTERVAL_S: float = 10.0

    def __init__(self, service_dir: Path) -> None:
        self._dir = service_dir
        self._lock_path = service_dir / "service.lock"
        self._pid_path = service_dir / "service.pid"
        self._state_path = service_dir / "service.state.json"
        self._filelock: Any = None
        self._heartbeat_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._started_at: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def acquire(self) -> None:
        """Acquire exclusive service lock.

        Raises:
            RuntimeError: if another process already holds the lock.
        """
        from filelock import FileLock, Timeout

        self._dir.mkdir(parents=True, exist_ok=True)
        lock = FileLock(str(self._lock_path), timeout=0)
        try:
            lock.acquire()
        except Timeout:
            raise RuntimeError(
                f"Another Ouro service is already running "
                f"(lock held: {self._lock_path}). "
                "Stop the other instance or remove the lock file if it is stale."
            ) from None

        self._filelock = lock
        self._started_at = time()
        self._write_pid()
        self._write_state("starting")
        self._start_heartbeat()
        self._write_state("running")
        logger.info("Service supervisor acquired lock (pid={})", os.getpid())

    def release(self) -> None:
        """Release lock, stop heartbeat thread, clean up PID file."""
        self._stop_event.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=3.0)
        self._write_state("stopped")
        try:
            self._pid_path.unlink(missing_ok=True)
        except OSError:
            pass
        if self._filelock is not None:
            try:
                self._filelock.release()
            except Exception:
                pass
        logger.info("Service supervisor released lock (pid={})", os.getpid())

    def read_state(self) -> dict[str, Any] | None:
        """Return the last written state dict, or None if unavailable."""
        try:
            text = self._state_path.read_text(encoding="utf-8")
            return json.loads(text)
        except (OSError, json.JSONDecodeError):
            return None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _write_pid(self) -> None:
        try:
            self._pid_path.write_text(str(os.getpid()), encoding="utf-8")
        except OSError as exc:
            logger.warning("Failed to write service PID file: {}", exc)

    def _write_state(self, status: str) -> None:
        state: dict[str, Any] = {
            "status": status,
            "pid": os.getpid(),
            "started_at": self._started_at,
            "heartbeat_at": time(),
        }
        try:
            self._state_path.write_text(
                json.dumps(state, indent=2), encoding="utf-8"
            )
        except OSError as exc:
            logger.warning("Failed to write service state: {}", exc)

    def _start_heartbeat(self) -> None:
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
            name="ouro-service-heartbeat",
        )
        self._heartbeat_thread.start()

    def _heartbeat_loop(self) -> None:
        while not self._stop_event.wait(timeout=self.HEARTBEAT_INTERVAL_S):
            self._write_state("running")
