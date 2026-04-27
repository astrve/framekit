from __future__ import annotations

from framekit.modules.torrent.service import TorrentBuildOptions, TorrentService, _auto_piece_length


def test_torrent_service_dry_run_reports_output_without_writing(tmp_path):
    payload = tmp_path / "Release"
    payload.mkdir()
    (payload / "movie.mkv").write_bytes(b"a" * 1024)

    output = tmp_path / "out" / "release.torrent"
    report, result = TorrentService().build(
        payload,
        options=TorrentBuildOptions(
            announce="https://tracker.example/announce",
            output_path=output,
            piece_length=512,
        ),
        write=False,
    )

    assert result.files_count == 1
    assert result.pieces_count == 2
    assert result.output_path == output
    assert report.modified == 0
    assert not output.exists()


def test_torrent_service_write_creates_output_parent(tmp_path):
    payload = tmp_path / "Release"
    payload.mkdir()
    (payload / "movie.mkv").write_bytes(b"a" * 1024)

    output = tmp_path / "nested" / "release.torrent"
    report, result = TorrentService().build(
        payload,
        options=TorrentBuildOptions(
            announce="https://tracker.example/announce",
            output_path=output,
            piece_length=512,
        ),
        write=True,
    )

    assert result.output_path == output
    assert output.exists()
    assert output.read_bytes().startswith(b"d")
    assert report.modified == 1


def test_torrent_service_requires_announce(tmp_path):
    payload = tmp_path / "Release"
    payload.mkdir()
    (payload / "movie.mkv").write_bytes(b"a")

    try:
        TorrentService().build(payload, options=TorrentBuildOptions(announce=""), write=False)
    except ValueError as exc:
        assert "announce" in str(exc).lower()
    else:
        raise AssertionError("missing announce should fail")


def test_auto_piece_length_uses_tracker_thresholds():
    gib = 1024 * 1024 * 1024
    mib = 1024 * 1024

    cases = [
        (gib - 1, 1 * mib),
        (gib, 2 * mib),
        (2 * gib, 4 * mib),
        (3 * gib, 8 * mib),
        (8 * gib, 16 * mib),
    ]

    for size, expected_piece_length in cases:
        assert _auto_piece_length(size) == expected_piece_length


def test_torrent_announce_url_validation():
    from framekit.modules.torrent.service import is_valid_announce_url

    assert is_valid_announce_url("https://tracker.example/announce")
    assert is_valid_announce_url("udp://tracker.example:6969/announce")
    assert not is_valid_announce_url("tracker.example/announce")
    assert not is_valid_announce_url("ftp://tracker.example/announce")


def test_torrent_payload_auto_ignores_sidecars(tmp_path):
    from framekit.modules.torrent.payload import resolve_torrent_payload

    (tmp_path / "Movie.2024.1080p.mkv").write_bytes(b"a")
    (tmp_path / "Movie.2024.1080p.nfo").write_text("nfo")
    (tmp_path / "notes.txt").write_text("notes")

    payload = resolve_torrent_payload(tmp_path, content_mode="auto")

    assert payload.name == "Movie.2024.1080p"
    assert [path.name for path in payload.files] == ["Movie.2024.1080p.mkv"]
    assert sorted(path.name for path in payload.ignored_files) == [
        "Movie.2024.1080p.nfo",
        "notes.txt",
    ]


def test_torrent_payload_auto_detects_release_subfolder(tmp_path):
    release = tmp_path / "Release"
    release.mkdir()
    payload_dir = release / "Show.S01"
    payload_dir.mkdir()
    (payload_dir / "Show.S01E01.mkv").write_bytes(b"a")
    (payload_dir / "Show.S01E02.mkv").write_bytes(b"b")
    (release / "Show.S01.nfo").write_text("nfo")

    from framekit.modules.torrent.payload import resolve_torrent_payload

    payload = resolve_torrent_payload(release, content_mode="auto")

    assert payload.path == payload_dir
    assert payload.name == "Show.S01"
    assert len(payload.files) == 2


def test_torrent_payload_auto_refuses_multiple_root_groups(tmp_path):
    from framekit.modules.torrent.payload import resolve_torrent_payload

    (tmp_path / "Movie.A.2024.mkv").write_bytes(b"a")
    (tmp_path / "Movie.B.2023.mkv").write_bytes(b"b")

    try:
        resolve_torrent_payload(tmp_path, content_mode="auto")
    except ValueError as exc:
        assert "multiple media groups" in str(exc).lower()
    else:
        raise AssertionError("auto mode should refuse ambiguous root media groups")


def test_torrent_service_can_use_resolved_media_subset(tmp_path):
    payload_dir = tmp_path / "Release"
    payload_dir.mkdir()
    mkv = payload_dir / "Movie.2024.1080p.mkv"
    mkv.write_bytes(b"a" * 1024)
    (payload_dir / "Movie.2024.1080p.nfo").write_text("nfo")

    output = tmp_path / "Movie.2024.1080p.torrent"
    report, result = TorrentService().build(
        payload_dir,
        options=TorrentBuildOptions(
            announce="https://tracker.example/announce",
            output_path=output,
            piece_length=512,
            payload_files=(mkv,),
            payload_name="Movie.2024.1080p",
        ),
        write=False,
    )

    assert result.files_count == 1
    assert result.output_path == output
    assert report.details[0].before["files"] == 1
