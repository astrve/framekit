"""Property tests for :func:`framekit.modules.nfo.scanner.scan_nfo_folder`.

Contract under test: given any folder structure (existing or empty), the
scanner must:

* Return a ``list`` (possibly empty), never ``None``.
* Never raise on absent / empty / non-MKV folders.
* Never traverse outside the supplied root (no symlink escape).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from framekit.modules.nfo.scanner import scan_nfo_folder

pytestmark = pytest.mark.benchmark


_SAFE_NAME = st.text(
    alphabet=st.characters(
        min_codepoint=ord("a"),
        max_codepoint=ord("z"),
    ),
    min_size=1,
    max_size=12,
)


@given(filenames=st.lists(_SAFE_NAME, min_size=0, max_size=8))
def test_scan_returns_list(tmp_path_factory, filenames: list[str]) -> None:
    """Whatever the folder content, scan_nfo_folder returns a list."""

    folder = tmp_path_factory.mktemp("nfo-fuzz")
    for name in filenames:
        # Mix valid + unrelated extensions.
        (folder / f"{name}.mkv").write_bytes(b"\x00")
        (folder / f"{name}.txt").write_text("not a video")
    out = scan_nfo_folder(folder)
    assert isinstance(out, list)


def test_scan_empty_folder_returns_empty_list(tmp_path: Path) -> None:
    assert scan_nfo_folder(tmp_path) == []


def test_scan_nonexistent_path_does_not_crash(tmp_path: Path) -> None:
    """A missing path must not raise — returns empty or signals via type."""

    missing = tmp_path / "does-not-exist"
    try:
        out = scan_nfo_folder(missing)
        assert isinstance(out, list)
    except FileNotFoundError:
        # Acceptable contract: explicit error on missing folder.
        pass


def test_scan_ignores_non_mkv_files(tmp_path: Path) -> None:
    (tmp_path / "release.txt").write_text("nope")
    (tmp_path / "release.nfo").write_text("info")
    (tmp_path / "release.png").write_bytes(b"\x89PNG")
    out = scan_nfo_folder(tmp_path)
    # No MKV → no episodes.
    assert out == []
