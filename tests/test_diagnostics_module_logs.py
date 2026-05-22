from __future__ import annotations

from framekit.core.diagnostics import (
    configure_diagnostics,
    get_module_log_file,
    log_event,
    reset_diagnostics,
)


def test_log_event_writes_per_module_session_log(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    configure_diagnostics(log_file=tmp_path / "framekit.log")

    try:
        log_event("INFO", "hello module log", module="prez", release="demo")
        module_log = get_module_log_file("prez")
        assert module_log is not None
        assert module_log.exists()
        content = module_log.read_text(encoding="utf-8")
        assert "hello module log" in content
        assert (tmp_path / "logs").is_dir()
    finally:
        reset_diagnostics()
