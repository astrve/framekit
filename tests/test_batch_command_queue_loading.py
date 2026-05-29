from __future__ import annotations

from ouro.commands import batch as batch_module


def test_batch_command_uses_fresh_queue_for_explicit_path(monkeypatch, tmp_path) -> None:
    captured: dict[str, bool] = {}

    class DummyService:
        def __init__(self, auto_load: bool = False) -> None:
            captured["auto_load"] = auto_load

    monkeypatch.setattr(batch_module, "BatchService", DummyService)
    monkeypatch.setattr(batch_module, "print_module_banner", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        batch_module,
        "_handle_non_processing_actions",
        lambda *_args, **_kwargs: 0,
    )

    exit_code = batch_module.batch_command.callback(
        path_parts=(str(tmp_path),),
        add_folder_path=None,
        add_release_path=None,
        list_queue=False,
        clear_queue_flag=False,
        remove_index=None,
        save_queue_path=None,
        load_queue_path=None,
        retry_failed=False,
        remove_completed=False,
        auto=True,
        manual=False,
        use_dashboard=None,
        pipeline_preset=None,
        enabled_modules_option=None,
        nfo_locale=None,
        announce=None,
        skip_renamer=False,
        skip_cleanmkv=False,
        skip_encoder=False,
        skip_nfo=False,
        skip_torrent=False,
        skip_prez=False,
        preset=None,
        with_metadata=None,
        nfo_mode=None,
    )

    assert exit_code == 0
    assert captured["auto_load"] is False


def test_batch_command_keeps_default_queue_without_explicit_source(monkeypatch) -> None:
    captured: dict[str, bool] = {}

    class DummyService:
        def __init__(self, auto_load: bool = False) -> None:
            captured["auto_load"] = auto_load

    monkeypatch.setattr(batch_module, "BatchService", DummyService)
    monkeypatch.setattr(batch_module, "print_module_banner", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        batch_module,
        "_handle_non_processing_actions",
        lambda *_args, **_kwargs: 0,
    )

    exit_code = batch_module.batch_command.callback(
        path_parts=(),
        add_folder_path=None,
        add_release_path=None,
        list_queue=False,
        clear_queue_flag=False,
        remove_index=None,
        save_queue_path=None,
        load_queue_path=None,
        retry_failed=False,
        remove_completed=False,
        auto=False,
        manual=False,
        use_dashboard=None,
        pipeline_preset=None,
        enabled_modules_option=None,
        nfo_locale=None,
        announce=None,
        skip_renamer=False,
        skip_cleanmkv=False,
        skip_encoder=False,
        skip_nfo=False,
        skip_torrent=False,
        skip_prez=False,
        preset=None,
        with_metadata=None,
        nfo_mode=None,
    )

    assert exit_code == 0
    assert captured["auto_load"] is True


def test_batch_command_skips_default_queue_when_custom_queue_is_loaded(monkeypatch) -> None:
    captured: dict[str, bool] = {}

    class DummyService:
        def __init__(self, auto_load: bool = False) -> None:
            captured["auto_load"] = auto_load

    monkeypatch.setattr(batch_module, "BatchService", DummyService)
    monkeypatch.setattr(batch_module, "print_module_banner", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        batch_module,
        "_handle_non_processing_actions",
        lambda *_args, **_kwargs: 0,
    )

    exit_code = batch_module.batch_command.callback(
        path_parts=(),
        add_folder_path=None,
        add_release_path=None,
        list_queue=False,
        clear_queue_flag=False,
        remove_index=None,
        save_queue_path=None,
        load_queue_path="custom-queue.json",
        retry_failed=False,
        remove_completed=False,
        auto=False,
        manual=False,
        use_dashboard=None,
        pipeline_preset=None,
        enabled_modules_option=None,
        nfo_locale=None,
        announce=None,
        skip_renamer=False,
        skip_cleanmkv=False,
        skip_encoder=False,
        skip_nfo=False,
        skip_torrent=False,
        skip_prez=False,
        preset=None,
        with_metadata=None,
        nfo_mode=None,
    )

    assert exit_code == 0
    assert captured["auto_load"] is False
