from __future__ import annotations

from swirrl.core.diagnostics import (
    configure_diagnostics,
    get_module_log_file,
    log_event,
    reset_diagnostics,
)


def test_log_event_writes_per_module_session_log(tmp_path, monkeypatch) -> None:
    from swirrl.core import paths

    workspace = tmp_path / "workspace"
    cache_dir = tmp_path / "cache"
    config_dir = tmp_path / "config"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    monkeypatch.delenv("SWIRRL_CONFIG", raising=False)
    monkeypatch.setattr(paths, "user_cache_dir", lambda *_args: str(cache_dir))
    monkeypatch.setattr(paths, "user_config_dir", lambda *_args: str(config_dir))
    configure_diagnostics(log_file=cache_dir / "swirrl.log")

    try:
        log_event("INFO", "hello module log", module="prez", release="demo")
        module_log = get_module_log_file("prez")
        assert module_log is not None
        assert module_log.exists()
        content = module_log.read_text(encoding="utf-8")
        assert "hello module log" in content
        assert module_log.parent == cache_dir / "logs" / "modules"
        assert not (workspace / "logs").exists()
    finally:
        reset_diagnostics()
