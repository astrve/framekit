from __future__ import annotations

import sys

import click

import framekit.commands.main as command_main_module
import framekit.commands.setup as setup_command_module
from framekit import __main__ as main_module
from framekit.core.diagnostics import (
    configure_diagnostics,
    get_log_file,
    is_debug_enabled,
    reset_diagnostics,
)


def test_extract_diagnostics_args_removes_global_flags():
    args, debug, log_file = main_module._extract_diagnostics_args(
        ["--debug", "--log-file", "debug.jsonl", "nfo", "Release"]
    )

    assert args == ["nfo", "Release"]
    assert debug is True
    assert log_file == "debug.jsonl"


def test_extract_diagnostics_args_supports_equals_and_no_debug():
    args, debug, log_file = main_module._extract_diagnostics_args(
        ["--no-debug", "--log-file=debug.jsonl", "doctor"]
    )

    assert args == ["doctor"]
    assert debug is False
    assert log_file == "debug.jsonl"


def test_extract_diagnostics_args_keeps_incomplete_log_file_flag_for_click_error():
    args, debug, log_file = main_module._extract_diagnostics_args(["--log-file"])

    assert args == ["--log-file"]
    assert debug is None
    assert log_file is None


def test_print_traceback_if_debug_only_prints_when_enabled(monkeypatch, tmp_path):
    reset_diagnostics()
    calls = []

    class _Console:
        def print_exception(self, *, show_locals: bool) -> None:
            calls.append(show_locals)

    monkeypatch.setattr(main_module, "console", _Console())

    configure_diagnostics(debug=False, log_file=tmp_path / "normal.log")
    main_module._print_traceback_if_debug(RuntimeError("normal"))
    assert calls == []

    configure_diagnostics(debug=True, log_file=tmp_path / "debug.log")
    main_module._print_traceback_if_debug(RuntimeError("debug"))
    assert calls == [False]

    reset_diagnostics()


def test_main_configures_debug_and_log_file_before_running_cli(monkeypatch, tmp_path):
    log_file = tmp_path / "framekit.jsonl"

    monkeypatch.setattr(sys, "argv", ["fk", "--debug", "--log-file", str(log_file), "doctor"])
    monkeypatch.setattr(main_module, "_load_locale_from_settings", lambda: None)

    monkeypatch.setattr(setup_command_module, "maybe_offer_first_time_setup", lambda: None)

    class _Cli:
        def main(self, *, args, prog_name, standalone_mode):
            assert args == ["doctor"]
            assert prog_name == "framekit"
            assert standalone_mode is False
            return 0

    monkeypatch.setattr(command_main_module, "cli", _Cli())

    assert main_module.main() == 0
    assert is_debug_enabled() is True
    assert get_log_file() == log_file
    assert log_file.exists()

    reset_diagnostics()


def test_main_handles_click_exception_without_traceback(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["fk", "bad"])
    monkeypatch.setattr(main_module, "_load_locale_from_settings", lambda: None)
    monkeypatch.setattr(main_module, "print_error", lambda message: None)
    monkeypatch.setattr(setup_command_module, "maybe_offer_first_time_setup", lambda: None)

    class _Cli:
        def main(self, *, args, prog_name, standalone_mode):
            raise click.UsageError("bad command")

    monkeypatch.setattr(command_main_module, "cli", _Cli())

    assert main_module.main() == 2
