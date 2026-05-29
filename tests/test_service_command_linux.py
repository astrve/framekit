"""Linux command-dispatch tests for ``ouro service`` CLI."""

from __future__ import annotations

import sys
from unittest.mock import patch

from click.testing import CliRunner

from ouro.commands.service import service_group


def test_install_auto_uses_systemd_on_linux(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    runner = CliRunner()
    with patch(
        "ouro.core.service.linux.install_systemd_user",
        return_value=(True, "installed"),
    ) as install_mock:
        result = runner.invoke(service_group, ["install", "--mode", "auto"])
    assert result.exit_code == 0
    assert "installed" in result.output
    install_mock.assert_called_once_with(host="127.0.0.1", port=8000)


def test_install_rejects_windows_mode_on_linux(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    runner = CliRunner()
    result = runner.invoke(service_group, ["install", "--mode", "task"])
    assert result.exit_code != 0
    assert "use --mode=systemd" in result.output


def test_start_auto_uses_systemd_on_linux(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    runner = CliRunner()
    with patch(
        "ouro.core.service.linux.start_systemd_user",
        return_value=(True, "started"),
    ) as start_mock:
        result = runner.invoke(service_group, ["start", "--mode", "auto"])
    assert result.exit_code == 0
    assert "started" in result.output
    start_mock.assert_called_once_with()


def test_uninstall_systemd_on_linux(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    runner = CliRunner()
    with patch(
        "ouro.core.service.linux.uninstall_systemd_user",
        return_value=(True, "removed"),
    ) as uninstall_mock:
        result = runner.invoke(service_group, ["uninstall", "--mode", "systemd", "--yes"])
    assert result.exit_code == 0
    assert "removed" in result.output
    uninstall_mock.assert_called_once_with()


def test_logs_linux_uses_journal(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    runner = CliRunner()
    with patch(
        "ouro.core.service.linux.journal_logs",
        return_value=(True, "line1\nline2"),
    ) as logs_mock:
        result = runner.invoke(service_group, ["logs", "-n", "2"])
    assert result.exit_code == 0
    assert "line1" in result.output
    logs_mock.assert_called_once_with(lines=2, follow=False)


def test_status_linux_json_includes_systemd_block(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    runner = CliRunner()
    with patch(
        "ouro.core.service.linux.query_http_status",
        return_value=None,
    ), patch(
        "ouro.core.service.linux.read_service_state",
        return_value=None,
    ), patch(
        "ouro.core.service.linux.query_systemd_status",
        return_value={"state": "ACTIVE", "mainpid": "123"},
    ), patch(
        "ouro.core.paths.get_service_dir",
        return_value=tmp_path,
    ):
        result = runner.invoke(service_group, ["status", "--json"])
    assert result.exit_code == 0
    assert '"systemd"' in result.output
    assert '"ACTIVE"' in result.output
