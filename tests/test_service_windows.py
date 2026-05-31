"""Tests for swirrl.core.service.windows — Windows service management helpers.

Most functions call external binaries (nssm, sc, schtasks) or make HTTP requests.
All external calls are mocked so tests run on any platform.

Platform-guarded functions (those that call _windows_only()) are tested in two
variants: the non-Windows early-return path, and the mocked-Windows execution path.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _import_windows():
    """Import the module under test."""
    from swirrl.core.service import windows
    return windows


# ---------------------------------------------------------------------------
# _run
# ---------------------------------------------------------------------------


class TestRun:
    def test_success(self):
        w = _import_windows()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="ok\n", stderr=""
            )
            ok, out = w._run(["echo", "hello"])
        assert ok is True
        assert "ok" in out

    def test_failure_nonzero(self):
        w = _import_windows()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", stderr="permission denied"
            )
            ok, out = w._run(["sc", "create", "Swirrl"])
        assert ok is False
        assert "permission denied" in out

    def test_file_not_found(self):
        w = _import_windows()
        with patch("subprocess.run", side_effect=FileNotFoundError("no such file")):
            ok, out = w._run(["nonexistent_binary"])
        assert ok is False
        assert "not found" in out.lower()

    def test_timeout_returns_false(self):
        import subprocess
        w = _import_windows()
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="x", timeout=1)):
            ok, out = w._run(["slow_cmd"], timeout=1.0)
        assert ok is False
        assert "timed out" in out.lower()


# ---------------------------------------------------------------------------
# _windows_only
# ---------------------------------------------------------------------------


class TestWindowsOnly:
    def test_non_windows_returns_error(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        w = _import_windows()
        result = w._windows_only()
        assert result is not None
        ok, msg = result
        assert ok is False
        assert "Windows" in msg

    def test_windows_returns_none(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        w = _import_windows()
        result = w._windows_only()
        assert result is None


# ---------------------------------------------------------------------------
# _find_nssm
# ---------------------------------------------------------------------------


class TestFindNssm:
    def test_found(self):
        w = _import_windows()
        with patch("shutil.which", return_value=r"C:\nssm\nssm.exe"):
            result = w._find_nssm()
        assert result == r"C:\nssm\nssm.exe"

    def test_not_found(self):
        w = _import_windows()
        with patch("shutil.which", return_value=None):
            result = w._find_nssm()
        assert result is None


# ---------------------------------------------------------------------------
# install_nssm
# ---------------------------------------------------------------------------


class TestInstallNssm:
    def test_all_steps_succeed(self):
        w = _import_windows()
        with patch.object(w, "_run", return_value=(True, "ok")) as mock_run:
            ok, msg = w.install_nssm(
                nssm=r"C:\nssm.exe",
                python_exe=r"C:\python.exe",
                host="127.0.0.1",
                port=8000,
                log_out=r"C:\service\service.out.log",
                log_err=r"C:\service\service.err.log",
            )
        assert ok is True
        assert "installed" in msg.lower()
        # 11 install steps defined in windows.py
        assert mock_run.call_count == 11

    def test_first_step_fails(self):
        w = _import_windows()
        with patch.object(w, "_run", return_value=(False, "Access denied")) as mock_run:
            ok, msg = w.install_nssm(
                nssm=r"C:\nssm.exe",
                python_exe=r"C:\python.exe",
                host="127.0.0.1",
                port=8000,
                log_out=r"C:\logs\out.log",
                log_err=r"C:\logs\err.log",
            )
        assert ok is False
        assert "install service" in msg
        assert "Access denied" in msg
        # Stops at first failure
        assert mock_run.call_count == 1

    def test_later_step_fails(self):
        w = _import_windows()
        call_count = [0]

        def side_effect(args, **kwargs):
            call_count[0] += 1
            if call_count[0] > 5:
                return False, "Write error"
            return True, "ok"

        with patch.object(w, "_run", side_effect=side_effect):
            ok, msg = w.install_nssm(
                nssm="nssm",
                python_exe="python",
                host="127.0.0.1",
                port=8000,
                log_out="/out.log",
                log_err="/err.log",
            )
        assert ok is False
        assert call_count[0] == 6


# ---------------------------------------------------------------------------
# install_sc
# ---------------------------------------------------------------------------


class TestInstallSc:
    def test_non_windows_guard(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        w = _import_windows()
        ok, msg = w.install_sc("python", "127.0.0.1", 8000)
        assert ok is False
        assert "Windows" in msg

    def test_sc_create_fails(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        w = _import_windows()
        with patch.object(w, "_run", return_value=(False, "Access denied")):
            ok, msg = w.install_sc("python", "127.0.0.1", 8000)
        assert ok is False
        assert "sc create failed" in msg

    def test_success(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        w = _import_windows()
        with patch.object(w, "_run", return_value=(True, "")):
            ok, msg = w.install_sc("python", "127.0.0.1", 8000)
        assert ok is True
        assert "installed" in msg.lower()


# ---------------------------------------------------------------------------
# install_task
# ---------------------------------------------------------------------------


class TestInstallTask:
    def test_non_windows_guard(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        w = _import_windows()
        ok, msg = w.install_task("python", "127.0.0.1", 8000)
        assert ok is False

    def test_no_rl_highest_in_command(self, monkeypatch, tmp_path):
        """/RL HIGHEST must NOT be passed — it requires admin and breaks no-admin mode."""
        monkeypatch.setattr(sys, "platform", "win32")
        w = _import_windows()
        captured: list[list[str]] = []

        def capture(args, **kw):
            captured.append(list(args))
            return True, "SUCCESS"

        with patch.object(w, "_run", side_effect=capture):
            ok, _ = w.install_task("python", "127.0.0.1", 8000, service_dir=tmp_path)

        assert ok is True
        assert captured, "Expected _run to be called"
        cmd_args = captured[0]
        assert "/RL" not in cmd_args, "/RL should not appear — no elevation flag"
        assert "HIGHEST" not in cmd_args, "HIGHEST run-level requires admin; must be absent"

    def test_onlogon_trigger_present(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "platform", "win32")
        w = _import_windows()
        captured: list[list[str]] = []

        def capture(args, **kw):
            captured.append(list(args))
            return True, "SUCCESS"

        with patch.object(w, "_run", side_effect=capture):
            w.install_task("python", "127.0.0.1", 8000, service_dir=tmp_path)

        cmd_args = captured[0]
        assert "ONLOGON" in cmd_args
        assert "/SC" in cmd_args
        assert "/F" in cmd_args   # overwrite existing task without prompt

    def test_schtasks_generic_failure(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "platform", "win32")
        w = _import_windows()
        with patch.object(w, "_run", return_value=(False, "Some other error")):
            ok, msg = w.install_task("python", "127.0.0.1", 8000, service_dir=tmp_path)
        assert ok is False
        assert "schtasks" in msg

    def test_access_denied_english_gives_guidance(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "platform", "win32")
        w = _import_windows()
        with patch.object(w, "_run", return_value=(False, "ERROR: Access is denied.")):
            ok, msg = w.install_task("python", "127.0.0.1", 8000, service_dir=tmp_path)
        assert ok is False
        # Must explain the non-elevated terminal fix
        assert "non-elevated" in msg or "non-admin" in msg or "normal" in msg.lower()
        assert "--mode=sc" in msg or "mode=sc" in msg

    def test_access_denied_french_gives_guidance(self, monkeypatch, tmp_path):
        """'Accès refusé' (French locale) must trigger the same guidance."""
        monkeypatch.setattr(sys, "platform", "win32")
        w = _import_windows()
        with patch.object(w, "_run", return_value=(False, "ERREUR : Accès refusé.")):
            ok, msg = w.install_task("python", "127.0.0.1", 8000, service_dir=tmp_path)
        assert ok is False
        assert "Access denied" in msg    # normalised English header
        assert "--mode=sc" in msg or "mode=sc" in msg

    def test_success(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "platform", "win32")
        w = _import_windows()
        with patch.object(w, "_run", return_value=(True, "SUCCESS")):
            ok, msg = w.install_task("python", "127.0.0.1", 8000, service_dir=tmp_path)
        assert ok is True
        assert "ONLOGON" in msg

    def test_bat_file_written(self, monkeypatch, tmp_path):
        """install_task writes a bat wrapper to service_dir."""
        monkeypatch.setattr(sys, "platform", "win32")
        w = _import_windows()
        with patch.object(w, "_run", return_value=(True, "SUCCESS")):
            w.install_task("python", "127.0.0.1", 8000, service_dir=tmp_path)
        assert (tmp_path / "swirrl-serve.bat").exists(), "bat must be written"

    def test_bat_file_has_log_redirection(self, monkeypatch, tmp_path):
        """Bat file must redirect stdout and stderr to the log files."""
        monkeypatch.setattr(sys, "platform", "win32")
        w = _import_windows()
        with patch.object(w, "_run", return_value=(True, "SUCCESS")):
            w.install_task("python", "127.0.0.1", 8000, service_dir=tmp_path)
        content = (tmp_path / "swirrl-serve.bat").read_bytes().decode("utf-8")
        assert ">>" in content, "stdout redirect must appear"
        assert "2>>" in content, "stderr redirect must appear"
        assert "service.out.log" in content
        assert "service.err.log" in content

    def test_bat_python_exe_with_spaces_is_quoted(self, monkeypatch, tmp_path):
        """python_exe path with spaces must be quoted inside the bat file."""
        monkeypatch.setattr(sys, "platform", "win32")
        w = _import_windows()
        python_with_spaces = r"C:\Program Files\Python\python.exe"
        with patch.object(w, "_run", return_value=(True, "SUCCESS")):
            w.install_task(python_with_spaces, "127.0.0.1", 8000, service_dir=tmp_path)
        content = (tmp_path / "swirrl-serve.bat").read_bytes().decode("utf-8")
        assert f'"{python_with_spaces}"' in content


# ---------------------------------------------------------------------------
# _build_task_tr
# ---------------------------------------------------------------------------


class TestBuildTaskTr:
    def test_path_without_spaces(self):
        w = _import_windows()
        bat_path = Path(r"C:\service\swirrl-serve.bat")
        tr = w._build_task_tr(bat_path)
        assert tr == r'cmd.exe /c "C:\service\swirrl-serve.bat"'

    def test_path_with_spaces(self):
        """Paths with spaces use CMD.EXE double-outer-quote convention."""
        w = _import_windows()
        bat_path = Path(r"E:\Swirrl Folder\service\swirrl-serve.bat")
        tr = w._build_task_tr(bat_path)
        assert tr == r'cmd.exe /c ""E:\Swirrl Folder\service\swirrl-serve.bat""'


# ---------------------------------------------------------------------------
# uninstall_nssm / uninstall_sc / uninstall_task
# ---------------------------------------------------------------------------


class TestUninstall:
    def test_uninstall_nssm_success(self):
        w = _import_windows()
        with patch.object(w, "_run", return_value=(True, "ok")):
            ok, msg = w.uninstall_nssm(nssm="nssm")
        assert ok is True
        assert "removed" in msg.lower()

    def test_uninstall_nssm_remove_fails(self):
        w = _import_windows()
        calls = [0]

        def side(args, **kw):
            calls[0] += 1
            if calls[0] == 1:
                return True, "stopped"
            return False, "remove error"

        with patch.object(w, "_run", side_effect=side):
            ok, msg = w.uninstall_nssm(nssm="nssm")
        assert ok is False
        assert "remove error" in msg

    def test_uninstall_sc_non_windows(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        w = _import_windows()
        ok, msg = w.uninstall_sc()
        assert ok is False

    def test_uninstall_sc_success(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        w = _import_windows()
        with patch.object(w, "_run", return_value=(True, "")):
            ok, msg = w.uninstall_sc()
        assert ok is True

    def test_uninstall_task_non_windows(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        w = _import_windows()
        ok, msg = w.uninstall_task()
        assert ok is False

    def test_uninstall_task_success(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        w = _import_windows()
        with patch.object(w, "_run", return_value=(True, "SUCCESS")):
            ok, msg = w.uninstall_task()
        assert ok is True


# ---------------------------------------------------------------------------
# start / stop
# ---------------------------------------------------------------------------


class TestStartStop:
    def test_start_service_sc_non_windows(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        w = _import_windows()
        ok, msg = w.start_service_sc()
        assert ok is False

    def test_start_service_sc_success(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        w = _import_windows()
        with patch.object(w, "_run", return_value=(True, "START_PENDING")):
            ok, msg = w.start_service_sc()
        assert ok is True

    def test_stop_service_sc_success(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        w = _import_windows()
        with patch.object(w, "_run", return_value=(True, "STOP_PENDING")):
            ok, msg = w.stop_service_sc()
        assert ok is True

    def test_start_task_non_windows(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        w = _import_windows()
        ok, msg = w.start_task()
        assert ok is False

    def test_start_task_success(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        w = _import_windows()
        with patch.object(w, "_run", return_value=(True, "SUCCESS")):
            ok, msg = w.start_task()
        assert ok is True

    def test_stop_task_reads_pid_file(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "platform", "win32")
        w = _import_windows()
        pid_path = tmp_path / "service.pid"
        pid_path.write_text("12345")

        run_calls: list[list] = []

        def capture_run(args, **kw):
            run_calls.append(list(args))
            return True, ""

        with patch.object(w, "_run", side_effect=capture_run):
            ok, msg = w.stop_task(pid_path=pid_path)

        assert ok is True
        # taskkill /PID 12345 should have been called first
        taskkill_calls = [c for c in run_calls if c and c[0] == "taskkill"]
        assert taskkill_calls, "Expected taskkill call with PID"
        assert "12345" in taskkill_calls[0]

    def test_stop_task_missing_pid_file(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "platform", "win32")
        w = _import_windows()
        pid_path = tmp_path / "service.pid"  # does not exist

        with patch.object(w, "_run", return_value=(True, "")) as mock_run:
            ok, msg = w.stop_task(pid_path=pid_path)

        assert ok is True
        assert mock_run.call_count >= 1


# ---------------------------------------------------------------------------
# query_sc_status
# ---------------------------------------------------------------------------


class TestQueryScStatus:
    SC_RUNNING_OUTPUT = (
        "SERVICE_NAME: Swirrl\n"
        "        TYPE               : 10  WIN32_OWN_PROCESS\n"
        "        STATE              : 4  RUNNING\n"
        "                                (STOPPABLE, NOT_PAUSABLE, ACCEPTS_SHUTDOWN)\n"
        "        WIN32_EXIT_CODE    : 0  (0x0)\n"
        "        SERVICE_EXIT_CODE  : 0  (0x0)\n"
        "        CHECKPOINT         : 0x0\n"
        "        WAIT_HINT          : 0x0\n"
    )

    SC_STOPPED_OUTPUT = (
        "SERVICE_NAME: Swirrl\n"
        "        STATE              : 1  STOPPED\n"
    )

    def test_running_state_parsed(self):
        w = _import_windows()
        with patch.object(w, "_run", return_value=(True, self.SC_RUNNING_OUTPUT)):
            result = w.query_sc_status()
        assert result.get("state") == "RUNNING"

    def test_stopped_state_parsed(self):
        w = _import_windows()
        with patch.object(w, "_run", return_value=(True, self.SC_STOPPED_OUTPUT)):
            result = w.query_sc_status()
        assert result.get("state") == "STOPPED"

    def test_sc_failure_returns_error(self):
        w = _import_windows()
        with patch.object(w, "_run", return_value=(False, "The specified service does not exist")):
            result = w.query_sc_status()
        assert "error" in result


# ---------------------------------------------------------------------------
# query_task_status
# ---------------------------------------------------------------------------


class TestQueryTaskStatus:
    TASK_LIST_OUTPUT = (
        "TaskName:                             Swirrl\n"
        "Status:                               Ready\n"
        "Next Run Time:                        N/A\n"
        "Last Run Time:                        N/A\n"
        "Last Result:                          0\n"
    )

    def test_status_parsed(self):
        w = _import_windows()
        with patch.object(w, "_run", return_value=(True, self.TASK_LIST_OUTPUT)):
            result = w.query_task_status()
        assert "status" in result
        assert "ready" in result["status"].lower()

    def test_task_not_found(self):
        w = _import_windows()
        with patch.object(w, "_run", return_value=(False, "ERROR: The system cannot find the path")):
            result = w.query_task_status()
        assert "error" in result


# ---------------------------------------------------------------------------
# query_http_status
# ---------------------------------------------------------------------------


class TestQueryHttpStatus:
    def test_success(self):
        w = _import_windows()
        payload = {"status": "running", "pid": 1234, "uptime_seconds": 3600}

        class FakeResponse:
            def read(self):
                return json.dumps(payload).encode()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        with patch("urllib.request.urlopen", return_value=FakeResponse()):
            result = w.query_http_status()

        assert result is not None
        assert result["status"] == "running"
        assert result["pid"] == 1234

    def test_connection_refused_returns_none(self):
        import urllib.error
        w = _import_windows()
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ):
            result = w.query_http_status()
        assert result is None

    def test_json_parse_error_returns_none(self):
        w = _import_windows()

        class BadResponse:
            def read(self):
                return b"not json {"

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        with patch("urllib.request.urlopen", return_value=BadResponse()):
            result = w.query_http_status()
        assert result is None

    def test_401_returns_auth_required(self):
        import urllib.error
        w = _import_windows()
        err = urllib.error.HTTPError(
            url="http://127.0.0.1:8000/api/v1/service/status",
            code=401,
            msg="Unauthorized",
            hdrs=None,  # type: ignore[arg-type]
            fp=None,
        )
        with patch("urllib.request.urlopen", side_effect=err):
            result = w.query_http_status()
        assert result is not None
        assert result.get("auth_required") is True
        assert result.get("status") == "running"

    def test_403_returns_auth_required(self):
        import urllib.error
        w = _import_windows()
        err = urllib.error.HTTPError(
            url="http://127.0.0.1:8000/api/v1/service/status",
            code=403,
            msg="Forbidden",
            hdrs=None,  # type: ignore[arg-type]
            fp=None,
        )
        with patch("urllib.request.urlopen", side_effect=err):
            result = w.query_http_status()
        assert result is not None
        assert result.get("auth_required") is True

    def test_500_returns_none(self):
        import urllib.error
        w = _import_windows()
        err = urllib.error.HTTPError(
            url="http://127.0.0.1:8000/api/v1/service/status",
            code=500,
            msg="Internal Server Error",
            hdrs=None,  # type: ignore[arg-type]
            fp=None,
        )
        with patch("urllib.request.urlopen", side_effect=err):
            result = w.query_http_status()
        assert result is None


# ---------------------------------------------------------------------------
# read_service_state
# ---------------------------------------------------------------------------


class TestReadServiceState:
    def test_reads_valid_state(self, tmp_path):
        w = _import_windows()
        state = {
            "status": "running",
            "pid": 9999,
            "started_at": 1748000000.0,
            "heartbeat_at": 1748000010.0,
        }
        (tmp_path / "service.state.json").write_text(
            json.dumps(state), encoding="utf-8"
        )
        result = w.read_service_state(tmp_path)
        assert result is not None
        assert result["status"] == "running"
        assert result["pid"] == 9999

    def test_missing_file_returns_none(self, tmp_path):
        w = _import_windows()
        result = w.read_service_state(tmp_path)
        assert result is None

    def test_corrupt_json_returns_none(self, tmp_path):
        w = _import_windows()
        (tmp_path / "service.state.json").write_text("{{bad json", encoding="utf-8")
        result = w.read_service_state(tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# tail_file
# ---------------------------------------------------------------------------


class TestTailFile:
    def test_returns_last_n_lines(self, tmp_path):
        w = _import_windows()
        log = tmp_path / "service.out.log"
        lines = [f"line {i}" for i in range(100)]
        log.write_text("\n".join(lines))
        result = w.tail_file(log, 20)
        assert len(result) == 20
        assert result[-1] == "line 99"
        assert result[0] == "line 80"

    def test_returns_all_when_fewer_than_n(self, tmp_path):
        w = _import_windows()
        log = tmp_path / "service.out.log"
        log.write_text("line 1\nline 2\nline 3")
        result = w.tail_file(log, 50)
        assert result == ["line 1", "line 2", "line 3"]

    def test_missing_file_returns_empty(self, tmp_path):
        w = _import_windows()
        result = w.tail_file(tmp_path / "nonexistent.log")
        assert result == []

    def test_empty_file_returns_empty(self, tmp_path):
        w = _import_windows()
        log = tmp_path / "service.out.log"
        log.write_text("")
        result = w.tail_file(log)
        assert result == []


# ---------------------------------------------------------------------------
# follow_file
# ---------------------------------------------------------------------------


class TestFollowFile:
    def test_yields_existing_lines(self, tmp_path):
        """follow_file yields lines already in the file."""
        w = _import_windows()
        log = tmp_path / "service.out.log"
        log.write_text("first\nsecond\nthird\n")

        gen = w.follow_file(log, poll_interval=0.01)
        collected: list[str] = []

        def consume():
            for line in gen:
                collected.append(line)
                if len(collected) >= 3:
                    gen.close()
                    break

        t = threading.Thread(target=consume)
        t.start()
        t.join(timeout=2.0)

        assert "first" in collected
        assert "second" in collected
        assert "third" in collected

    def test_yields_appended_lines(self, tmp_path):
        """follow_file yields lines appended after the generator starts."""
        w = _import_windows()
        log = tmp_path / "service.out.log"
        log.write_text("")

        gen = w.follow_file(log, poll_interval=0.02)
        collected: list[str] = []

        def consume():
            for line in gen:
                collected.append(line)
                if len(collected) >= 2:
                    gen.close()
                    break

        t = threading.Thread(target=consume)
        t.start()

        time.sleep(0.05)
        with log.open("a") as fh:
            fh.write("appended1\nappended2\n")

        t.join(timeout=2.0)

        assert "appended1" in collected
        assert "appended2" in collected

    def test_waits_for_file_creation(self, tmp_path):
        """follow_file blocks until the log file exists."""
        w = _import_windows()
        log = tmp_path / "new.log"

        gen = w.follow_file(log, poll_interval=0.02)
        collected: list[str] = []

        def consume():
            for line in gen:
                collected.append(line)
                if line == "created":
                    gen.close()
                    break

        t = threading.Thread(target=consume)
        t.start()

        time.sleep(0.05)
        log.write_text("created\n")

        t.join(timeout=2.0)
        assert "created" in collected
