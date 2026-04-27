from __future__ import annotations

from framekit.__main__ import _extract_diagnostics_args


def test_extract_diagnostics_args_accepts_flags_anywhere():
    cleaned, debug, log_file = _extract_diagnostics_args(
        ["cmk", "folder", "--debug", "--log-file", "framekit.log", "--dry-run"]
    )

    assert cleaned == ["cmk", "folder", "--dry-run"]
    assert debug is True
    assert log_file == "framekit.log"


def test_extract_diagnostics_args_accepts_equals_log_file():
    cleaned, debug, log_file = _extract_diagnostics_args(["--log-file=debug.jsonl", "doctor"])

    assert cleaned == ["doctor"]
    assert debug is None
    assert log_file == "debug.jsonl"
