from __future__ import annotations


def test_pipeline_auto_mode_skips_interactive_preset_selection(monkeypatch) -> None:
    from swirrl.commands import pipeline

    called = False

    def _fail_select():
        nonlocal called
        called = True
        raise AssertionError("selector should not run in --auto mode")

    monkeypatch.setattr(pipeline, "_select_pipeline_preset", _fail_select)

    selected, _preview, auto_mode, _metadata = pipeline._resolve_module_selection(
        {"modules": {"pipeline": {"enabled_modules": ["renamer"]}}},
        None,
        None,
        True,
        None,
        None,
    )

    assert selected == {"renamer"}
    assert auto_mode is True
    assert called is False
