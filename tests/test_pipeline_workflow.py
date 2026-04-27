from __future__ import annotations

from pathlib import Path

from framekit.commands.pipeline import (
    _next_work_folder,
)
from framekit.core.naming import release_name_from_mkv_paths

"""
Integration tests for the pipeline payload workflow.

These tests verify that the pipeline-level helpers select the correct working
folder (payload) based on the presence of MKV files and Release folders. The
tests ensure that release folder names are sanitised consistently, that the
pipeline picks up a cleaned payload created by CleanMKV, and that ambiguous
structures are handled gracefully.
"""


def test_safe_release_folder_name_sanitises_invalid_chars() -> None:
    """release_name_from_mkv_paths should remove characters illegal on filesystems."""
    # The Path does not need to exist for release_name_from_mkv_paths to compute the name
    name = release_name_from_mkv_paths([Path("My Film:2024?/Quest!.mkv")])
    # The result should not contain colon, slash or question mark
    assert ":" not in name and "/" not in name and "?" not in name


def test_next_work_folder_picks_release_payload(tmp_path: Path) -> None:
    """When a release payload folder exists, _next_work_folder should return it."""
    # Create a root folder with a single MKV file
    mkv = tmp_path / "Movie.mkv"
    mkv.touch()
    # Compute the expected release folder name
    release_name = release_name_from_mkv_paths([mkv])
    release_dir = tmp_path / "Release" / release_name
    # Before the release directory exists, the next work folder should be the root
    assert _next_work_folder(tmp_path, {}) == tmp_path
    # Simulate that CleanMKV has produced the Release/<release> folder
    release_dir.mkdir(parents=True)
    (release_dir / mkv.name).touch()
    # Now the next work folder should be the release directory
    assert _next_work_folder(tmp_path, {}) == release_dir


def test_next_work_folder_detects_release_subfolder(tmp_path: Path) -> None:
    """
    If no MKV files remain in the root but there is exactly one Release/<release> subfolder
    containing media, _next_work_folder should return that subfolder.
    """
    # No MKV at root; create a Release/<release> folder with MKVs
    mkv_dir = tmp_path / "Release" / "Series.Name.S01"
    mkv_dir.mkdir(parents=True)
    (mkv_dir / "Series.Name.S01E01.mkv").touch()
    (mkv_dir / "Series.Name.S01E02.mkv").touch()
    # The next work folder should identify and return the only release payload subfolder
    assert _next_work_folder(tmp_path, {}) == mkv_dir
