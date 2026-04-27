from pathlib import Path

import pytest

from framekit.modules.torrent.payload import resolve_torrent_payload


def test_torrent_resolver_single_file(tmp_path: Path) -> None:
    """
    Resolving a single MKV file should return a payload containing only that file and
    exclude any sidecar files in the same folder.
    """
    mkv = tmp_path / "Movie.mkv"
    mkv.touch()
    sidecar = tmp_path / "Movie.nfo"
    sidecar.touch()
    payload = resolve_torrent_payload(mkv, content_mode="auto")
    assert payload.files == (mkv,)
    # The sidecar file should not be part of the payload
    assert sidecar not in payload.files


def test_torrent_resolver_release_subfolder(tmp_path: Path) -> None:
    """
    When MKV files reside under a Release/<release> subfolder, the resolver should
    automatically select that subfolder as the payload in auto/media modes, and ignore
    sidecar files within it.
    """
    release_dir = tmp_path / "Release" / "MyMovie"
    release_dir.mkdir(parents=True)
    mkv = release_dir / "MyMovie.mkv"
    mkv.touch()
    sidecar = release_dir / "MyMovie.nfo"
    sidecar.touch()
    payload = resolve_torrent_payload(tmp_path, content_mode="auto")
    assert payload.path == release_dir
    assert payload.files == (mkv,)
    # Ensure sidecar is ignored
    assert sidecar not in payload.files


def test_torrent_resolver_excludes_sidecars(tmp_path: Path) -> None:
    """
    The resolver must exclude non-media sidecar files (nfo, txt, html, bbcode, screenshots)
    from the selected payload in auto/media modes.
    """
    mkv = tmp_path / "Film.mkv"
    mkv.touch()
    # Create various sidecar files and folders
    (tmp_path / "Film.nfo").touch()
    (tmp_path / "Film.txt").touch()
    (tmp_path / "Film.html").touch()
    (tmp_path / "Film.bbcode").touch()
    screenshots = tmp_path / "screenshots"
    screenshots.mkdir()
    (screenshots / "1.png").touch()

    payload = resolve_torrent_payload(tmp_path, content_mode="auto")
    assert payload.files == (mkv,)
    # None of the sidecar files or images should be included
    for sidecar in [
        tmp_path / "Film.nfo",
        tmp_path / "Film.txt",
        tmp_path / "Film.html",
        tmp_path / "Film.bbcode",
        screenshots / "1.png",
    ]:
        assert sidecar not in payload.files


def test_torrent_resolver_ambiguous_release_subfolders(tmp_path: Path) -> None:
    """
    When multiple Release/<release> subfolders each contain media files, auto/media modes
    should raise a ValueError due to ambiguity.
    """
    base = tmp_path / "Release"
    (base / "MovieA").mkdir(parents=True)
    (base / "MovieB").mkdir(parents=True)
    (base / "MovieA" / "MovieA.mkv").touch()
    (base / "MovieB" / "MovieB.mkv").touch()

    with pytest.raises(ValueError):
        resolve_torrent_payload(tmp_path, content_mode="auto")
    with pytest.raises(ValueError):
        resolve_torrent_payload(tmp_path, content_mode="media")


def test_torrent_resolver_ambiguous_root_and_release(tmp_path: Path) -> None:
    """
    When both the root folder and a Release subfolder contain media files, auto/media modes
    should raise a ValueError to signal ambiguity.
    """
    # Root-level media
    mkv_root = tmp_path / "Root.mkv"
    mkv_root.touch()
    # Subfolder media
    release_sub = tmp_path / "Release" / "Inner"
    release_sub.mkdir(parents=True)
    (release_sub / "Inner.mkv").touch()

    with pytest.raises(ValueError):
        resolve_torrent_payload(tmp_path, content_mode="auto")
    with pytest.raises(ValueError):
        resolve_torrent_payload(tmp_path, content_mode="media")


def test_torrent_resolver_folder_mode_includes_all_files(tmp_path: Path) -> None:
    """
    In folder content mode, all files except .torrent should be included in the payload.
    This mode is useful when the user explicitly requests to include sidecar files.
    """
    mkv = tmp_path / "Film.mkv"
    mkv.touch()
    nfo = tmp_path / "Film.nfo"
    nfo.touch()
    txt = tmp_path / "Film.txt"
    txt.touch()

    payload = resolve_torrent_payload(tmp_path, content_mode="folder")
    # The payload should include the MKV and both sidecar files
    assert set(payload.files) == {mkv, nfo, txt}
