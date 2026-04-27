from __future__ import annotations

# Lightweight integration tests for the CleanMKV → Release/{release} → NFO/Prez/Torrent workflow.
#
# These tests verify that the pipeline correctly picks the release payload folder
# after CleanMKV has prepared it and that subsequent steps operate on that payload
# folder. The tests use monkeypatching to avoid invoking the real CleanMKV, NFO,
# Prez and Torrent implementations.
from pathlib import Path

import pytest

from framekit.commands import pipeline as pipeline_command_module
from framekit.core.naming import release_name_from_mkv_paths
from framekit.core.settings import SettingsStore


class _StoreFactory:
    """Small helper to supply a temporary SettingsStore into the pipeline."""

    def __init__(self, store: SettingsStore) -> None:
        self.store = store

    def __call__(self) -> SettingsStore:
        return self.store


def test_release_name_from_mkv_paths_sanitises_invalid_chars() -> None:
    """The naming helper should sanitise characters illegal on common filesystems."""
    release_name = release_name_from_mkv_paths([Path("Movie:Quest?!.mkv")])

    assert release_name == "Movie_Quest_!"
    assert ":" not in release_name
    assert "?" not in release_name


def test_pipeline_uses_cleanmkv_release_payload_folder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    temp_settings_store: SettingsStore,
) -> None:
    """
    After CleanMKV creates Release/<release>, NFO, Torrent and Prez should operate
    on that cleaned payload folder instead of the original source root.
    """
    # Use a Windows-safe filename for the real filesystem operation.
    mkv = tmp_path / "Movie.Quest.mkv"
    mkv.touch()

    release_name = release_name_from_mkv_paths([mkv])
    calls: dict[str, str] = {}

    monkeypatch.setattr(
        pipeline_command_module, "SettingsStore", _StoreFactory(temp_settings_store)
    )

    def fake_renamer(folder: Path, remove_terms: tuple[str, ...] = ()) -> int:
        calls["renamer"] = folder.name
        return 0

    monkeypatch.setattr(pipeline_command_module, "_renamer_step", fake_renamer)

    def fake_cleanmkv(folder: Path) -> int:
        calls["cleanmkv"] = folder.name

        release_dir = folder / "Release" / release_name
        release_dir.mkdir(parents=True)
        (release_dir / mkv.name).touch()

        return 0

    monkeypatch.setattr(pipeline_command_module, "_cleanmkv_step", fake_cleanmkv)

    def fake_nfo(folder: Path, locale: str | None, *args: object) -> int:
        calls["nfo"] = folder.name
        return 0

    monkeypatch.setattr(pipeline_command_module, "_nfo_step", fake_nfo)

    def fake_torrent(folder: Path, announce: str | None, *args: object) -> int:
        calls["torrent"] = folder.name
        return 0

    monkeypatch.setattr(pipeline_command_module, "_torrent_step", fake_torrent)

    def fake_prez(folder: Path, locale: str | None, *args: object) -> int:
        calls["prez"] = folder.name
        return 0

    monkeypatch.setattr(pipeline_command_module, "_prez_step", fake_prez)

    exit_code = pipeline_command_module.run_pipeline_command(
        path=str(tmp_path),
        nfo_locale="en",
        announce="https://tracker.example/announce",
        skip_renamer=False,
        skip_cleanmkv=False,
        skip_nfo=False,
        skip_torrent=False,
        skip_prez=False,
    )

    assert exit_code == 0

    # Renamer and CleanMKV operate on the source root.
    assert calls["renamer"] == tmp_path.name
    assert calls["cleanmkv"] == tmp_path.name

    # Output steps operate on the CleanMKV payload folder.
    assert calls["nfo"] == release_name
    assert calls["torrent"] == release_name
    assert calls["prez"] == release_name
