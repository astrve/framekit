from __future__ import annotations

# Lightweight integration tests for the CleanMKV → Release/{release} → NFO/Prez/Torrent workflow.
#
# These tests verify that the pipeline correctly picks the sanitized release folder
# after CleanMKV has prepared the payload and that subsequent steps operate on
# that payload folder. The tests use monkeypatching to avoid invoking the real
# CleanMKV, NFO, Prez and Torrent implementations. Instead, they simulate the
# creation of a cleaned payload and record the folders passed to each step. Converting
# this module-level documentation to comments ensures that imports remain at the top
# of the file, satisfying the Ruff E402 rule without suppressing it.

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


def test_pipeline_uses_sanitised_release_folder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    temp_settings_store: SettingsStore,
) -> None:
    """
    When a root folder contains an MKV whose name includes illegal filesystem
    characters, the pipeline should sanitise the release name using the central
    helper and operate on the cleaned payload folder created by CleanMKV.

    This test creates a single MKV file with characters that require sanitisation
    (colon, question mark, exclamation mark). The CleanMKV step is monkeypatched
    to create a Release/<sanitised> subfolder containing a copy of the MKV file.
    The test asserts that NFO, Torrent and Prez steps are invoked with the
    sanitised release folder and not with the root folder.
    """
    # Create a file with characters that need to be sanitised in the release name
    mkv = tmp_path / "Movie:Quest?!.mkv"
    mkv.touch()
    # Precompute the sanitised release name using the naming helper
    sanitised = release_name_from_mkv_paths([mkv])

    # Prepare a dictionary to record which folders each pipeline step uses
    calls: dict[str, str] = {}

    # Patch the SettingsStore used by the pipeline to ensure a temporary store is used
    monkeypatch.setattr(
        pipeline_command_module, "SettingsStore", _StoreFactory(temp_settings_store)
    )

    # Patch the Renamer step to record the folder name and succeed
    def fake_renamer(folder: Path, remove_terms: tuple[str, ...] = ()) -> int:
        calls["renamer"] = folder.name
        return 0

    monkeypatch.setattr(pipeline_command_module, "_renamer_step", fake_renamer)

    # Patch the CleanMKV step to simulate output in Release/{sanitised}
    def fake_cleanmkv(folder: Path) -> int:
        calls["cleanmkv"] = folder.name
        # Simulate CleanMKV creating Release/<sanitised> and copying the MKV
        release_dir = folder / "Release" / sanitised
        release_dir.mkdir(parents=True)
        # Copy the original MKV into the cleaned payload
        (release_dir / mkv.name).touch()
        return 0

    monkeypatch.setattr(pipeline_command_module, "_cleanmkv_step", fake_cleanmkv)

    # Patch the NFO step to record the folder it operates on
    def fake_nfo(folder: Path, locale: str | None, *args: object) -> int:
        calls["nfo"] = folder.name
        return 0

    monkeypatch.setattr(pipeline_command_module, "_nfo_step", fake_nfo)

    # Patch the Torrent step to record the folder it operates on
    def fake_torrent(folder: Path, announce: str | None, *args: object) -> int:
        calls["torrent"] = folder.name
        return 0

    monkeypatch.setattr(pipeline_command_module, "_torrent_step", fake_torrent)

    # Patch the Prez step to record the folder it operates on
    def fake_prez(folder: Path, locale: str | None, *args: object) -> int:
        calls["prez"] = folder.name
        return 0

    monkeypatch.setattr(pipeline_command_module, "_prez_step", fake_prez)

    # Run the pipeline; provide a dummy announce URL to avoid validation errors
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

    # The pipeline should succeed
    assert exit_code == 0
    # Renamer and CleanMKV should operate on the root folder
    assert calls["renamer"] == tmp_path.name
    assert calls["cleanmkv"] == tmp_path.name
    # NFO, Torrent and Prez should operate on the sanitised release folder
    assert calls["nfo"] == sanitised
    assert calls["torrent"] == sanitised
    assert calls["prez"] == sanitised
