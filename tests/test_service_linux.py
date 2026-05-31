"""Tests for swirrl.core.service.linux — Linux systemd user-service helpers."""

from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock, patch


def _import_linux():
    """Import module under test."""
    from swirrl.core.service import linux

    return linux


class TestLinuxOnly:
    def test_non_linux_returns_error(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        svc = _import_linux()
        result = svc._linux_only()
        assert result is not None
        ok, msg = result
        assert ok is False
        assert "Linux" in msg

    def test_linux_returns_none(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        svc = _import_linux()
        assert svc._linux_only() is None


class TestBuildUnit:
    def test_build_exec_start_uses_swirrl_binary_when_found(self):
        svc = _import_linux()
        with patch("shutil.which", return_value="/usr/local/bin/swirrl"):
            cmd = svc._build_exec_start("127.0.0.1", 8000)
        assert cmd.startswith("/usr/local/bin/swirrl serve")
        assert "--host 127.0.0.1 --port 8000" in cmd

    def test_build_exec_start_falls_back_to_python_module(self):
        svc = _import_linux()
        with patch("shutil.which", return_value=None), patch.object(
            sys, "executable", "/opt/python/bin/python3"
        ):
            cmd = svc._build_exec_start("127.0.0.1", 8000)
        assert "/opt/python/bin/python3 -m swirrl serve" in cmd

    def test_build_unit_text_contains_systemd_sections(self):
        svc = _import_linux()
        with patch("shutil.which", return_value="/usr/bin/swirrl"):
            text = svc._build_unit_text("127.0.0.1", 8000)
        assert "[Unit]" in text
        assert "[Service]" in text
        assert "[Install]" in text
        assert "ExecStart=/usr/bin/swirrl serve --host 127.0.0.1 --port 8000" in text


class TestInstallSystemdUser:
    def test_non_linux_guard(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        svc = _import_linux()
        ok, msg = svc.install_systemd_user("127.0.0.1", 8000)
        assert ok is False
        assert "Linux" in msg

    def test_missing_systemctl(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        svc = _import_linux()
        with patch.object(svc, "_find_systemctl", return_value=None):
            ok, msg = svc.install_systemd_user("127.0.0.1", 8000)
        assert ok is False
        assert "systemctl not found" in msg

    def test_success_writes_unit_and_runs_reload_enable(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "platform", "linux")
        svc = _import_linux()
        with patch.object(svc, "_find_systemctl", return_value="/bin/systemctl"), patch.object(
            svc, "_run", return_value=(True, "ok")
        ) as mock_run:
            ok, msg = svc.install_systemd_user("127.0.0.1", 8000, unit_dir=tmp_path)
        assert ok is True
        assert "Installed user unit" in msg
        assert (tmp_path / "swirrl.service").exists()
        assert mock_run.call_count == 2

    def test_daemon_reload_failure(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "platform", "linux")
        svc = _import_linux()
        with patch.object(svc, "_find_systemctl", return_value="/bin/systemctl"), patch.object(
            svc, "_run", side_effect=[(False, "dbus down")]
        ):
            ok, msg = svc.install_systemd_user("127.0.0.1", 8000, unit_dir=tmp_path)
        assert ok is False
        assert "daemon-reload" in msg


class TestUninstallSystemdUser:
    def test_success_even_when_unit_missing(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "platform", "linux")
        svc = _import_linux()
        with patch.object(svc, "_find_systemctl", return_value="/bin/systemctl"), patch.object(
            svc,
            "_run",
            side_effect=[
                (False, "Unit swirrl.service could not be found."),
                (True, "ok"),
            ],
        ):
            ok, msg = svc.uninstall_systemd_user(unit_dir=tmp_path)
        assert ok is True
        assert "Removed user unit" in msg

    def test_disable_failure_bubbles(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "platform", "linux")
        svc = _import_linux()
        with patch.object(svc, "_find_systemctl", return_value="/bin/systemctl"), patch.object(
            svc, "_run", return_value=(False, "permission denied")
        ):
            ok, msg = svc.uninstall_systemd_user(unit_dir=tmp_path)
        assert ok is False
        assert "disable --now failed" in msg


class TestLifecycleCommands:
    def test_start_stop_restart_success(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        svc = _import_linux()
        with patch.object(svc, "_find_systemctl", return_value="/bin/systemctl"), patch.object(
            svc, "_run", return_value=(True, "")
        ):
            assert svc.start_systemd_user()[0] is True
            assert svc.stop_systemd_user()[0] is True
            assert svc.restart_systemd_user()[0] is True


class TestQuerySystemdStatus:
    def test_parses_active_state(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        svc = _import_linux()
        output = (
            "LoadState=loaded\n"
            "ActiveState=active\n"
            "SubState=running\n"
            "UnitFileState=enabled\n"
            "MainPID=1234\n"
        )
        with patch.object(svc, "_find_systemctl", return_value="/bin/systemctl"), patch.object(
            svc, "_run", return_value=(True, output)
        ):
            status = svc.query_systemd_status()
        assert status.get("state") == "ACTIVE"
        assert status.get("mainpid") == "1234"

    def test_not_found_unit_sets_error(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        svc = _import_linux()
        output = "LoadState=not-found\nActiveState=inactive\nMainPID=0\n"
        with patch.object(svc, "_find_systemctl", return_value="/bin/systemctl"), patch.object(
            svc, "_run", return_value=(True, output)
        ):
            status = svc.query_systemd_status()
        assert "error" in status


class TestStateAndHttp:
    def test_read_service_state(self, tmp_path):
        svc = _import_linux()
        state = {
            "status": "running",
            "pid": 42,
            "started_at": 1.0,
            "heartbeat_at": 2.0,
        }
        (tmp_path / "service.state.json").write_text(json.dumps(state), encoding="utf-8")
        loaded = svc.read_service_state(tmp_path)
        assert loaded is not None
        assert loaded["pid"] == 42

    def test_query_http_status_success(self):
        svc = _import_linux()
        payload = {"status": "running", "pid": 99}

        class FakeResponse:
            def read(self):
                return json.dumps(payload).encode()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

        with patch("urllib.request.urlopen", return_value=FakeResponse()):
            out = svc.query_http_status()
        assert out is not None
        assert out["pid"] == 99


class TestJournalLogs:
    def test_non_follow_uses_run(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        svc = _import_linux()
        with patch.object(svc, "_find_journalctl", return_value="/bin/journalctl"), patch.object(
            svc, "_run", return_value=(True, "line1\nline2")
        ) as mock_run:
            ok, out = svc.journal_logs(lines=2, follow=False)
        assert ok is True
        assert "line1" in out
        assert mock_run.call_count == 1

    def test_follow_runs_subprocess(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        svc = _import_linux()
        with patch.object(svc, "_find_journalctl", return_value="/bin/journalctl"), patch(
            "subprocess.run", return_value=MagicMock(returncode=0)
        ) as mock_run:
            ok, out = svc.journal_logs(lines=10, follow=True)
        assert ok is True
        assert out == ""
        assert mock_run.call_count == 1
