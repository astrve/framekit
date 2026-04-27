from __future__ import annotations

from types import SimpleNamespace

from framekit.commands import cleanmkv as cleanmkv_command_module
from framekit.core.models.cleanmkv import CleanPreset
from framekit.core.reporting import OperationReport
from framekit.core.settings import SettingsStore


class _StoreFactory:
    def __init__(self, store: SettingsStore) -> None:
        self.store = store

    def __call__(self) -> SettingsStore:
        return self.store


def _preset(name: str = "selector") -> CleanPreset:
    return CleanPreset(
        name=name,
        keep_audio_filters=(),
        default_audio_filter=None,
        keep_subtitle_filters=(),
        keep_subtitle_variants=(),
        default_subtitle_filter=None,
        default_subtitle_variant=None,
        keep_audio_track_refs=("audio|fr||||e-ac-3||5.1|768000|",),
        default_audio_track_ref="audio|fr||||e-ac-3||5.1|768000|",
    )


def test_cleanmkv_base_command_uses_track_selector_and_applies_after_confirmation(
    monkeypatch, tmp_path, temp_settings_store
):
    folder = tmp_path / "Release"
    folder.mkdir()
    monkeypatch.setattr(
        cleanmkv_command_module, "SettingsStore", _StoreFactory(temp_settings_store)
    )

    scans = [SimpleNamespace(path=folder / "movie.mkv")]
    preset = _preset()
    monkeypatch.setattr(cleanmkv_command_module, "scan_folder", lambda folder, registry: scans)
    monkeypatch.setattr(
        cleanmkv_command_module, "run_cleanmkv_track_selector", lambda scans_arg: preset
    )
    monkeypatch.setattr(cleanmkv_command_module, "confirm_choice", lambda **kwargs: True)

    calls = []

    class _Service:
        def run(
            self,
            folder_arg,
            *,
            preset,
            output_dir_name,
            apply_changes,
            registry,
            copy_unchanged_files,
            scans,
        ):
            calls.append((apply_changes, preset.name, scans))
            return OperationReport(tool="cleanmkv", scanned=1, processed=1, modified=1), []

    monkeypatch.setattr(cleanmkv_command_module, "CleanMkvService", _Service)

    assert (
        cleanmkv_command_module.run_cleanmkv_command(
            path=str(folder),
            apply_changes=False,
            dry_run=False,
            preset_name=None,
            preset_file=None,
            external_preset=None,
            wizard=False,
            save_preset=None,
            list_presets=False,
        )
        == 0
    )

    assert calls == [(False, "selector", scans), (True, "selector", scans)]
    assert temp_settings_store.get("modules.cleanmkv.last_folder") == str(folder)


def test_cleanmkv_base_command_can_preview_without_applying(
    monkeypatch, tmp_path, temp_settings_store
):
    folder = tmp_path / "Release"
    folder.mkdir()
    monkeypatch.setattr(
        cleanmkv_command_module, "SettingsStore", _StoreFactory(temp_settings_store)
    )

    monkeypatch.setattr(cleanmkv_command_module, "scan_folder", lambda folder, registry: [object()])
    monkeypatch.setattr(
        cleanmkv_command_module, "run_cleanmkv_track_selector", lambda scans: _preset()
    )
    monkeypatch.setattr(cleanmkv_command_module, "confirm_choice", lambda **kwargs: False)

    calls = []

    class _Service:
        def run(
            self,
            folder_arg,
            *,
            preset,
            output_dir_name,
            apply_changes,
            registry,
            copy_unchanged_files,
            scans,
        ):
            calls.append(apply_changes)
            return OperationReport(tool="cleanmkv", scanned=1, processed=1), []

    monkeypatch.setattr(cleanmkv_command_module, "CleanMkvService", _Service)

    assert (
        cleanmkv_command_module.run_cleanmkv_command(
            path=str(folder),
            apply_changes=False,
            dry_run=False,
            preset_name=None,
            preset_file=None,
            external_preset=None,
            wizard=False,
            save_preset=None,
            list_presets=False,
        )
        == 0
    )

    assert calls == [False]


def test_cleanmkv_dry_run_uses_configured_preset_without_selector(
    monkeypatch, tmp_path, temp_settings_store
):
    folder = tmp_path / "Release"
    folder.mkdir()
    monkeypatch.setattr(
        cleanmkv_command_module, "SettingsStore", _StoreFactory(temp_settings_store)
    )

    monkeypatch.setattr(cleanmkv_command_module, "get_builtin_preset", lambda name: _preset(name))
    monkeypatch.setattr(
        cleanmkv_command_module,
        "scan_folder",
        lambda folder, registry: (_ for _ in ()).throw(AssertionError("selector not expected")),
    )

    calls = []

    class _Service:
        def run(
            self,
            folder_arg,
            *,
            preset,
            output_dir_name,
            apply_changes,
            registry,
            copy_unchanged_files,
            scans,
        ):
            calls.append((preset.name, apply_changes, scans))
            return OperationReport(tool="cleanmkv", scanned=1, processed=1), []

    monkeypatch.setattr(cleanmkv_command_module, "CleanMkvService", _Service)

    assert (
        cleanmkv_command_module.run_cleanmkv_command(
            path=str(folder),
            apply_changes=False,
            dry_run=True,
            preset_name="multi",
            preset_file=None,
            external_preset=None,
            wizard=False,
            save_preset=None,
            list_presets=False,
        )
        == 0
    )

    assert calls == [("multi", False, None)]


def test_cleanmkv_rejects_apply_and_dry_run():
    assert (
        cleanmkv_command_module.run_cleanmkv_command(
            path=None,
            apply_changes=True,
            dry_run=True,
            preset_name=None,
            preset_file=None,
            external_preset=None,
            wizard=False,
            save_preset=None,
            list_presets=False,
        )
        == 1
    )
