"""Tests for cleanmkv command module."""

from __future__ import annotations

from types import SimpleNamespace

from ouro.commands import cleanmkv as cleanmkv_command_module
from ouro.core.models.cleanmkv import CleanPreset
from ouro.core.reporting import OperationReport
from ouro.core.settings import SettingsStore


class _StoreFactory:
    """Mock settings store factory for testing."""

    def __init__(self, store: SettingsStore) -> None:
        self.store = store

    def __call__(self) -> SettingsStore:
        return self.store


def _preset(name: str = "selector") -> CleanPreset:
    """Create a mock CleanPreset for testing."""
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
    """Test that cleanmkv command uses track selector and applies changes after confirmation."""
    folder = tmp_path / "Release"
    folder.mkdir()
    monkeypatch.setattr(
        cleanmkv_command_module, "SettingsStore", _StoreFactory(temp_settings_store)
    )

    scans = [SimpleNamespace(path=folder / "movie.mkv")]
    preset = _preset()
    monkeypatch.setattr(cleanmkv_command_module, "scan_folder", lambda folder, registry: scans)
    monkeypatch.setattr(
        cleanmkv_command_module, "run_cleanmkv_track_selector", lambda _scans: preset
    )
    monkeypatch.setattr(cleanmkv_command_module, "confirm_choice", lambda **kwargs: True)

    calls = []

    class _Service:
        def run(
            self,
            _folder,
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


def test_cleanmkv_base_command_can_preview_without_applying(
    monkeypatch, tmp_path, temp_settings_store
):
    """Test that cleanmkv command can preview without applying changes."""
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
            _folder,
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
    """Test that cleanmkv dry run uses configured preset without selector."""
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
            _folder,
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
    """Test that cleanmkv rejects both apply_changes and dry_run flags together."""
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
