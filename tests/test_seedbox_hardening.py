from __future__ import annotations

from click.testing import CliRunner

from framekit.commands.main import cli
from framekit.commands.seedbox import (
    _get_default_seedbox,
    _destination_path_for_source,
    _list_seedboxes,
    _resolve_local_payload,
    _resolve_local_payloads,
    _resolve_remote_path,
)


def test_seedbox_list_treats_null_seedboxes_as_empty() -> None:
    assert _list_seedboxes({"seedbox": {"seedboxes": None}}) == []


def test_seedbox_default_prefers_profile_mapping() -> None:
    settings = {
        "seedbox": {
            "default": "global",
            "default_by_profile": {"anime": "anime-box"},
            "seedboxes": [
                {"name": "global", "rclone_remote": "r1", "remote_base_path": "/"},
                {"name": "anime-box", "rclone_remote": "r2", "remote_base_path": "/"},
            ],
        }
    }
    sb = _get_default_seedbox(settings, profile_name="anime")
    assert sb is not None
    assert sb.get("name") == "anime-box"


def test_seedbox_push_requires_path_or_cwd(tmp_path, monkeypatch) -> None:
    settings_file = tmp_path / "framekit.yaml"
    settings_file.write_text(
        "\n".join(
            [
                "seedbox:",
                "  default: box",
                "  history_enabled: true",
                "  max_concurrent_uploads: 3",
                "  seedboxes:",
                "    - name: box",
                "      rclone_remote: remote",
                "      remote_base_path: /data",
                "      max_concurrent_uploads: 4",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("FRAMEKIT_CONFIG", str(settings_file))

    result = CliRunner().invoke(cli, ["seedbox", "push", "--dry-run"])

    assert result.exit_code == 0
    assert "Refusing implicit current-directory upload" in result.output


def test_seedbox_doctor_handles_missing_rclone_as_warning(tmp_path, monkeypatch) -> None:
    settings_file = tmp_path / "framekit.yaml"
    settings_file.write_text("seedbox:\n  seedboxes: []\n", encoding="utf-8")
    monkeypatch.setenv("FRAMEKIT_CONFIG", str(settings_file))
    monkeypatch.setattr("framekit.commands.seedbox._find_rclone", lambda: None)

    result = CliRunner().invoke(cli, ["seedbox", "doctor"])

    assert result.exit_code == 0
    assert "rclone not found" in result.output


def test_seedbox_detects_final_release_payload_folder(tmp_path) -> None:
    root = tmp_path / "Messy.Movie.2024.1080p.WEB-GRP"
    final = root / "Release" / "MESSY.MOVIE.2024.1080P.WEB-GRP"
    final.mkdir(parents=True)
    (root / "MESSY.MOVIE.2024.1080P.WEB-GRP.mkv").write_bytes(b"old")
    (final / "MESSY.MOVIE.2024.1080P.WEB-GRP.mkv").write_bytes(b"new")
    (final / "MESSY.MOVIE.2024.1080P.WEB-GRP.nfo").write_text("nfo", encoding="utf-8")

    selected, category = _resolve_local_payload(root)

    assert selected == final
    assert category == "movies"


def test_seedbox_detects_multiple_payloads_from_batch_parent(tmp_path) -> None:
    parent = tmp_path / "ready"
    movie_final = parent / "movie" / "Release" / "MOVIE.ONE.2024.1080P.WEB-GRP"
    series_final = parent / "series" / "Release" / "SHOW.NAME.S01E01.1080P.WEB-GRP"
    for final in (movie_final, series_final):
        final.mkdir(parents=True)
        (final / f"{final.name}.mkv").write_bytes(b"mkv")
        (final / f"{final.name}.nfo").write_text("nfo", encoding="utf-8")

    payloads = _resolve_local_payloads(parent)

    assert payloads == [(movie_final, "movies"), (series_final, "series")]


def test_seedbox_absolute_category_path_is_not_joined_to_base() -> None:
    sb = {
        "remote_base_path": "/downloads/releases/transfer",
        "category_paths": {"movies": "/downloads/releases/movies"},
    }

    assert (
        _resolve_remote_path(sb, remote_path=None, category="movies")
        == "/downloads/releases/movies"
    )


def test_seedbox_directory_push_preserves_release_folder_name(tmp_path) -> None:
    release = tmp_path / "Movie.2024.1080p.WEB-GRP"
    release.mkdir()

    assert (
        _destination_path_for_source("/downloads/releases/movies", release)
        == "/downloads/releases/movies/Movie.2024.1080p.WEB-GRP"
    )


def test_seedbox_directory_push_does_not_duplicate_explicit_release_folder(tmp_path) -> None:
    release = tmp_path / "Movie.2024.1080p.WEB-GRP"
    release.mkdir()

    assert (
        _destination_path_for_source("/downloads/releases/movies/Movie.2024.1080p.WEB-GRP", release)
        == "/downloads/releases/movies/Movie.2024.1080p.WEB-GRP"
    )


def test_seedbox_push_uploads_each_payload_from_batch_parent(tmp_path, monkeypatch) -> None:
    settings_file = tmp_path / "framekit.yaml"
    settings_file.write_text(
        "\n".join(
            [
                "seedbox:",
                "  default: box",
                "  history_enabled: false",
                "  max_concurrent_uploads: 2",
                "  seedboxes:",
                "    - name: box",
                "      rclone_remote: remote",
                "      remote_base_path: /downloads/releases",
                "      max_concurrent_uploads: 5",
                "      disk_check_enabled: false",
                "      category_paths:",
                "        movies: movies",
                "        series: series",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("FRAMEKIT_CONFIG", str(settings_file))

    parent = tmp_path / "ready"
    movie_final = parent / "movie" / "Release" / "MOVIE.ONE.2024.1080P.WEB-GRP"
    series_final = parent / "series" / "Release" / "SHOW.NAME.S01E01.1080P.WEB-GRP"
    for final in (movie_final, series_final):
        final.mkdir(parents=True)
        (final / f"{final.name}.mkv").write_bytes(b"mkv")
        (final / f"{final.name}.nfo").write_text("nfo", encoding="utf-8")

    calls: list[tuple[list[str], bool, bool]] = []

    def fake_rclone(args: list[str], *, dry_run: bool = False, verbose: bool = False) -> int:
        calls.append((args, dry_run, verbose))
        return 0

    monkeypatch.setattr("framekit.commands.seedbox._run_rclone", fake_rclone)

    result = CliRunner().invoke(cli, ["seedbox", "push", str(parent), "--dry-run"])

    assert result.exit_code == 0
    assert len(calls) == 2
    destinations = [args[2] for args, _, _ in calls]
    assert "remote:/downloads/releases/movies/MOVIE.ONE.2024.1080P.WEB-GRP" in destinations
    assert "remote:/downloads/releases/series/SHOW.NAME.S01E01.1080P.WEB-GRP" in destinations
    assert all("--transfers" in args for args, _, _ in calls)
    assert all(args[args.index("--transfers") + 1] == "5" for args, _, _ in calls)
    assert all(dry_run for _, dry_run, _ in calls)


def test_seedbox_use_profile_binding_updates_settings(tmp_path, monkeypatch) -> None:
    settings_file = tmp_path / "framekit.yaml"
    settings_file.write_text(
        "\n".join(
            [
                "seedbox:",
                "  default: box",
                "  seedboxes:",
                "    - name: box",
                "      rclone_remote: remote",
                "      remote_base_path: /data",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("FRAMEKIT_CONFIG", str(settings_file))

    result = CliRunner().invoke(cli, ["seedbox", "use", "box", "--profile", "anime"])

    assert result.exit_code == 0
    content = settings_file.read_text(encoding="utf-8")
    assert "default_by_profile" in content
    assert "anime" in content
    assert "box" in content
