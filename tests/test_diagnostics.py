from __future__ import annotations

import json

from framekit.core.diagnostics import (
    configure_diagnostics,
    diagnostics_summary,
    log_event,
    log_exception,
    redact,
    reset_diagnostics,
)


def test_redact_masks_nested_secret_values():
    payload = {
        "metadata": {"tmdb_read_access_token": "secret", "language": "fr-FR"},
        "headers": {"Authorization": "Bearer token"},
    }

    redacted = redact(payload)

    assert redacted["metadata"]["tmdb_read_access_token"] == "********"
    assert redacted["metadata"]["language"] == "fr-FR"
    assert redacted["headers"]["Authorization"] == "********"


def test_log_event_writes_jsonl_with_redaction(tmp_path):
    reset_diagnostics()
    log_file = tmp_path / "framekit.log"
    configure_diagnostics(log_file=log_file)

    log_event("INFO", "metadata request", api_key="secret", page=1)

    entry = json.loads(log_file.read_text(encoding="utf-8").splitlines()[0])
    assert entry["level"] == "INFO"
    assert entry["message"] == "metadata request"
    assert entry["context"]["api_key"] == "********"
    assert entry["context"]["page"] == 1

    reset_diagnostics()


def test_log_exception_writes_traceback(tmp_path):
    reset_diagnostics()
    log_file = tmp_path / "framekit.log"
    configure_diagnostics(log_file=log_file)

    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        log_exception(exc, command="doctor")

    entry = json.loads(log_file.read_text(encoding="utf-8").splitlines()[0])
    assert entry["level"] == "ERROR"
    assert entry["context"]["exception_type"] == "RuntimeError"
    assert "RuntimeError: boom" in entry["context"]["traceback"]

    reset_diagnostics()


def test_diagnostics_summary_reports_state(tmp_path):
    reset_diagnostics()
    log_file = tmp_path / "framekit.log"
    configure_diagnostics(debug=True, log_file=log_file)

    summary = diagnostics_summary()

    assert summary["debug"] is True
    assert summary["log_file"] == str(log_file)

    reset_diagnostics()
