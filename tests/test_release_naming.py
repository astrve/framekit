from pathlib import Path

from framekit.core.naming import release_name_from_mkv_paths, torrent_name_from_payload
from framekit.ui.progress import _format_bytes


def test_release_name_single_file_keeps_stem():
    assert (
        release_name_from_mkv_paths([Path("Movie.Name.2024.1080p.mkv")]) == "Movie.Name.2024.1080p"
    )


def test_release_name_season_pack_removes_episode_token():
    result = release_name_from_mkv_paths(
        [
            Path("Show.Name.S04E01.1080p.mkv"),
            Path("Show.Name.S04E02.1080p.mkv"),
        ]
    )
    assert result == "Show.Name.S04.1080p"


def test_torrent_name_for_file_removes_mkv_suffix(tmp_path):
    payload = tmp_path / "Movie.Name.mkv"
    payload.write_bytes(b"x")
    assert torrent_name_from_payload(payload) == "Movie.Name"


def test_progress_byte_format_uses_correct_scale():
    assert _format_bytes(14.49 * 1024**3).endswith("GB")
    assert "TB" not in _format_bytes(14.49 * 1024**3)
