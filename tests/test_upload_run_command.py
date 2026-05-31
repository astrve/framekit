"""Regression tests for upload run command."""

from __future__ import annotations

from types import SimpleNamespace

from swirrl.commands import upload as upload_command


def test_upload_run_requires_description_in_non_interactive_mode(monkeypatch, tmp_path):
    torrent_file = tmp_path / "sample.torrent"
    torrent_file.write_bytes(b"torrent")

    class _NoTty:
        @staticmethod
        def isatty() -> bool:
            return False

    monkeypatch.setattr(upload_command.sys, "stdin", _NoTty())

    class _UploadService:
        @staticmethod
        def list_trackers():
            return [{"name": "tracker-a", "url": "https://tracker.local"}]

        @staticmethod
        def get_tracker_info(_tracker_name: str):
            return {
                "url": "https://tracker.local",
                "categories": {"Movie": 1},
                "types": {"1080p": 10},
                "resolutions": {"1920x1080": 100},
            }

        def upload(self, *_args, **_kwargs):
            raise AssertionError("upload() must not be called when description is missing")

    monkeypatch.setattr(upload_command, "UploadService", _UploadService)

    captured: dict[str, str] = {}

    def _fake_print_fatal(message: str, hint: str | None = None):
        captured["message"] = message
        if hint:
            captured["hint"] = hint

    monkeypatch.setattr(upload_command, "print_fatal", _fake_print_fatal)

    upload_command.run_command.callback(
        torrent_file=torrent_file,
        tracker="tracker-a",
        name=None,
        description=None,
        category=None,
        type=None,
        resolution=None,
        tmdb_id=None,
        imdb_id=None,
        tvdb_id=None,
        anonymous=False,
        stream=True,
        dry_run=False,
        preset=None,
    )

    assert captured["message"] == "--description is required in non-interactive mode"


def test_upload_run_uses_preset_defaults_in_non_interactive_mode(monkeypatch, tmp_path):
    torrent_file = tmp_path / "sample.torrent"
    torrent_file.write_bytes(b"torrent")

    class _NoTty:
        @staticmethod
        def isatty() -> bool:
            return False

    monkeypatch.setattr(upload_command.sys, "stdin", _NoTty())

    class _UploadService:
        @staticmethod
        def list_trackers():
            return [{"name": "tracker-a", "url": "https://tracker.local"}]

        @staticmethod
        def get_tracker_info(_tracker_name: str):
            return {
                "url": "https://tracker.local",
                "categories": {"Movie": 1, "TV": 2},
                "types": {"WEB-DL": 10},
                "resolutions": {"2160p": 100},
            }

    monkeypatch.setattr(upload_command, "UploadService", _UploadService)
    monkeypatch.setattr(
        upload_command,
        "_load_upload_preset",
        lambda _preset: SimpleNamespace(
            description="Preset description",
            category="TV",
            type="WEB-DL",
            resolution="2160p",
        ),
    )
    monkeypatch.setattr(
        upload_command, "_apply_upload_preset", lambda metadata, *_a, **_k: metadata
    )

    captured: dict[str, object] = {}

    def _fake_preview(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(upload_command, "_render_upload_preview", _fake_preview)

    upload_command.run_command.callback(
        torrent_file=torrent_file,
        tracker="tracker-a",
        name=None,
        description=None,
        category=None,
        type=None,
        resolution=None,
        tmdb_id=None,
        imdb_id=None,
        tvdb_id=None,
        anonymous=False,
        stream=True,
        dry_run=True,
        preset="movie",
    )

    metadata = captured["metadata"]
    assert metadata.description == "Preset description"
    assert metadata.category == "TV"
    assert metadata.type == "WEB-DL"
    assert metadata.resolution == "2160p"


def test_upload_run_custom_json_api_v1_requires_nfo_in_non_interactive_mode(monkeypatch, tmp_path):
    torrent_file = tmp_path / "sample.torrent"
    torrent_file.write_bytes(b"torrent")

    class _NoTty:
        @staticmethod
        def isatty() -> bool:
            return False

    monkeypatch.setattr(upload_command.sys, "stdin", _NoTty())

    class _UploadService:
        @staticmethod
        def list_trackers():
            return [{"name": "custom_json_api_v1", "url": "https://tracker.example"}]

        @staticmethod
        def get_tracker_info(_tracker_name: str):
            return {
                "name": "custom_json_api_v1",
                "type": "custom_json_api_v1",
                "url": "https://tracker.example",
                "defaults": {
                    "custom_api_category_id": 1,
                    "custom_api_subcategory_id": 6,
                },
                "categories": {},
                "types": {},
                "resolutions": {},
            }

    monkeypatch.setattr(upload_command, "UploadService", _UploadService)

    captured: dict[str, str] = {}

    def _fake_print_fatal(message: str, hint: str | None = None):
        captured["message"] = message
        if hint:
            captured["hint"] = hint

    monkeypatch.setattr(upload_command, "print_fatal", _fake_print_fatal)

    upload_command.run_command.callback(
        torrent_file=torrent_file,
        tracker="custom_json_api_v1",
        name="Release.Name",
        description="[b]desc long enough for tests[/b]",
        category=None,
        type=None,
        resolution=None,
        tmdb_id=None,
        imdb_id=None,
        tvdb_id=None,
        anonymous=False,
        stream=True,
        dry_run=False,
        preset=None,
    )

    assert captured["message"] == "custom API requires an NFO file (--nfo or <torrent>.nfo)"


def test_upload_run_custom_json_api_v1_maps_fields_in_dry_run(monkeypatch, tmp_path):
    torrent_file = tmp_path / "sample.torrent"
    torrent_file.write_bytes(b"torrent")
    nfo_file = tmp_path / "sample.nfo"
    nfo_file.write_text("NFO", encoding="utf-8")

    class _NoTty:
        @staticmethod
        def isatty() -> bool:
            return False

    monkeypatch.setattr(upload_command.sys, "stdin", _NoTty())

    class _UploadService:
        @staticmethod
        def list_trackers():
            return [{"name": "custom_json_api_v1", "url": "https://tracker.example"}]

        @staticmethod
        def get_tracker_info(_tracker_name: str):
            return {
                "name": "custom_json_api_v1",
                "type": "custom_json_api_v1",
                "url": "https://tracker.example",
                "defaults": {},
                "categories": {},
                "types": {},
                "resolutions": {},
            }

    monkeypatch.setattr(upload_command, "UploadService", _UploadService)
    monkeypatch.setattr(
        upload_command, "_apply_upload_preset", lambda metadata, *_a, **_k: metadata
    )
    monkeypatch.setattr(upload_command, "_load_upload_preset", lambda _preset: None)

    captured: dict[str, object] = {}

    def _fake_preview(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(upload_command, "_render_upload_preview", _fake_preview)

    upload_command.run_command.callback(
        torrent_file=torrent_file,
        tracker="custom_json_api_v1",
        name="Release.Name",
        description="[b]desc long enough for tests[/b]",
        nfo_path=nfo_file,
        category=None,
        type=None,
        resolution=None,
        category_id=1,
        subcategory_id=6,
        options_json='{"1":[4],"2":10}',
        description_format="standard",
        uploader_note="note",
        tmdb_id=None,
        imdb_id=None,
        tvdb_id=None,
        anonymous=False,
        stream=True,
        dry_run=True,
        preset=None,
    )

    metadata = captured["metadata"]
    assert metadata.nfo_path == str(nfo_file)
    assert metadata.custom_api_category_id == 1
    assert metadata.custom_api_subcategory_id == 6
    assert metadata.custom_api_options == {"1": [4], "2": 10}


def test_upload_run_accepts_description_file_in_non_interactive_mode(monkeypatch, tmp_path):
    torrent_file = tmp_path / "sample.torrent"
    torrent_file.write_bytes(b"torrent")
    description_file = tmp_path / "desc.bbcode.txt"
    description_file.write_text("[b]Description from file[/b]", encoding="utf-8")

    class _NoTty:
        @staticmethod
        def isatty() -> bool:
            return False

    monkeypatch.setattr(upload_command.sys, "stdin", _NoTty())

    class _UploadService:
        @staticmethod
        def list_trackers():
            return [{"name": "tracker-a", "url": "https://tracker.local"}]

        @staticmethod
        def get_tracker_info(_tracker_name: str):
            return {
                "url": "https://tracker.local",
                "categories": {"Movie": 1},
                "types": {"1080p": 10},
                "resolutions": {"1920x1080": 100},
            }

    monkeypatch.setattr(upload_command, "UploadService", _UploadService)
    monkeypatch.setattr(
        upload_command, "_apply_upload_preset", lambda metadata, *_a, **_k: metadata
    )
    monkeypatch.setattr(upload_command, "_load_upload_preset", lambda _preset: None)

    captured: dict[str, object] = {}

    def _fake_preview(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(upload_command, "_render_upload_preview", _fake_preview)

    upload_command.run_command.callback(
        torrent_file=torrent_file,
        tracker="tracker-a",
        name="Release.Name",
        description=None,
        description_file=description_file,
        nfo_path=None,
        category=None,
        type=None,
        resolution=None,
        category_id=None,
        subcategory_id=None,
        options_json=None,
        description_format=None,
        uploader_note=None,
        tmdb_id=None,
        imdb_id=None,
        tvdb_id=None,
        anonymous=False,
        stream=True,
        dry_run=True,
        preset=None,
    )

    metadata = captured["metadata"]
    assert metadata.description == "[b]Description from file[/b]"


def test_upload_run_accepts_release_folder_and_infers_bbcode(monkeypatch, tmp_path):
    release = tmp_path / "Release"
    release.mkdir()
    torrent_file = release / "Movie.2026.torrent"
    torrent_file.write_bytes(b"torrent")
    nfo_file = release / "Movie.2026.nfo"
    nfo_file.write_text("NFO", encoding="utf-8")
    bbcode_file = release / "release.bbcode.txt"
    bbcode_file.write_text("[b]Auto description[/b]", encoding="utf-8")

    class _NoTty:
        @staticmethod
        def isatty() -> bool:
            return False

    monkeypatch.setattr(upload_command.sys, "stdin", _NoTty())

    class _UploadService:
        @staticmethod
        def list_trackers():
            return [{"name": "custom_json_api_v1", "url": "https://tracker.example"}]

        @staticmethod
        def get_tracker_info(_tracker_name: str):
            return {
                "name": "custom_json_api_v1",
                "type": "custom_json_api_v1",
                "url": "https://tracker.example",
                "defaults": {
                    "custom_api_category_id": 1,
                    "custom_api_subcategory_id": 6,
                    "custom_api_options": {"1": [4], "2": 25},
                },
                "categories": {},
                "types": {},
                "resolutions": {},
            }

    monkeypatch.setattr(upload_command, "UploadService", _UploadService)
    monkeypatch.setattr(
        upload_command, "_apply_upload_preset", lambda metadata, *_a, **_k: metadata
    )
    monkeypatch.setattr(upload_command, "_load_upload_preset", lambda _preset: None)

    captured: dict[str, object] = {}

    def _fake_preview(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(upload_command, "_render_upload_preview", _fake_preview)

    upload_command.run_command.callback(
        torrent_file=release,
        tracker="custom_json_api_v1",
        name=None,
        description=None,
        description_file=None,
        nfo_path=None,
        category=None,
        type=None,
        resolution=None,
        category_id=None,
        subcategory_id=None,
        options_json=None,
        description_format=None,
        uploader_note=None,
        tmdb_id=None,
        imdb_id=None,
        tvdb_id=None,
        anonymous=False,
        stream=True,
        dry_run=True,
        preset=None,
    )

    metadata = captured["metadata"]
    assert metadata.description == "[b]Auto description[/b]"
    assert metadata.nfo_path == str(nfo_file)


def test_upload_run_release_folder_multiple_torrents_fails_non_interactive(monkeypatch, tmp_path):
    release = tmp_path / "Release"
    release.mkdir()
    (release / "a.torrent").write_bytes(b"a")
    (release / "b.torrent").write_bytes(b"b")

    class _NoTty:
        @staticmethod
        def isatty() -> bool:
            return False

    monkeypatch.setattr(upload_command.sys, "stdin", _NoTty())

    class _UploadService:
        @staticmethod
        def list_trackers():
            return [{"name": "custom_json_api_v1", "url": "https://tracker.example"}]

        @staticmethod
        def get_tracker_info(_tracker_name: str):
            return {
                "name": "custom_json_api_v1",
                "type": "custom_json_api_v1",
                "url": "https://tracker.example",
                "defaults": {"custom_api_category_id": 1, "custom_api_subcategory_id": 6},
                "categories": {},
                "types": {},
                "resolutions": {},
            }

    monkeypatch.setattr(upload_command, "UploadService", _UploadService)

    captured: dict[str, str] = {}

    def _fake_print_fatal(message: str, hint: str | None = None):
        captured["message"] = message
        if hint:
            captured["hint"] = hint

    monkeypatch.setattr(upload_command, "print_fatal", _fake_print_fatal)

    upload_command.run_command.callback(
        torrent_file=release,
        tracker="custom_json_api_v1",
        name=None,
        description=None,
        description_file=None,
        nfo_path=None,
        category=None,
        type=None,
        resolution=None,
        category_id=None,
        subcategory_id=None,
        options_json=None,
        description_format=None,
        uploader_note=None,
        tmdb_id=None,
        imdb_id=None,
        tvdb_id=None,
        anonymous=False,
        stream=True,
        dry_run=True,
        preset=None,
    )

    assert "Multiple .torrent files found in folder" in captured["message"]


def test_upload_run_tracker_name_case_insensitive(monkeypatch, tmp_path):
    torrent_file = tmp_path / "sample.torrent"
    torrent_file.write_bytes(b"torrent")
    nfo_file = tmp_path / "sample.nfo"
    nfo_file.write_text("NFO", encoding="utf-8")

    class _NoTty:
        @staticmethod
        def isatty() -> bool:
            return False

    monkeypatch.setattr(upload_command.sys, "stdin", _NoTty())

    class _UploadService:
        @staticmethod
        def list_trackers():
            return [
                {
                    "name": "Custom JSON API",
                    "url": "https://tracker.example",
                    "type": "custom_json_api_v1",
                }
            ]

        @staticmethod
        def get_tracker_info(tracker_name: str):
            if tracker_name != "Custom JSON API":
                return None
            return {
                "name": "Custom JSON API",
                "type": "custom_json_api_v1",
                "url": "https://tracker.example",
                "defaults": {"custom_api_category_id": 1, "custom_api_subcategory_id": 6},
                "categories": {},
                "types": {},
                "resolutions": {},
            }

    monkeypatch.setattr(upload_command, "UploadService", _UploadService)
    monkeypatch.setattr(
        upload_command, "_apply_upload_preset", lambda metadata, *_a, **_k: metadata
    )
    monkeypatch.setattr(upload_command, "_load_upload_preset", lambda _preset: None)

    captured: dict[str, object] = {}

    def _fake_preview(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(upload_command, "_render_upload_preview", _fake_preview)

    upload_command.run_command.callback(
        torrent_file=torrent_file,
        tracker="custom_json_api_v1",
        name="Release.Name",
        description="[b]desc long enough for tests[/b]",
        description_file=None,
        nfo_path=nfo_file,
        category=None,
        type=None,
        resolution=None,
        category_id=None,
        subcategory_id=None,
        options_json=None,
        description_format=None,
        uploader_note=None,
        tmdb_id=None,
        auto_tmdb=False,
        imdb_id=None,
        tvdb_id=None,
        anonymous=False,
        stream=True,
        dry_run=True,
        preset=None,
    )

    assert captured["tracker"] == "Custom JSON API"
    assert captured["tracker_url"] == "https://tracker.example"


def test_upload_run_auto_tmdb_populates_metadata(monkeypatch, tmp_path):
    torrent_file = tmp_path / "Gone.Baby.Gone.2007.1080p.WEB-DL.x264-GRP.torrent"
    torrent_file.write_bytes(b"torrent")

    class _NoTty:
        @staticmethod
        def isatty() -> bool:
            return False

    monkeypatch.setattr(upload_command.sys, "stdin", _NoTty())

    class _UploadService:
        @staticmethod
        def list_trackers():
            return [{"name": "tracker-a", "url": "https://tracker.local", "type": "unit3d"}]

        @staticmethod
        def get_tracker_info(_tracker_name: str):
            return {
                "url": "https://tracker.local",
                "categories": {"Movie": 1},
                "types": {"1080p": 10},
                "resolutions": {"1920x1080": 100},
            }

    monkeypatch.setattr(upload_command, "UploadService", _UploadService)
    monkeypatch.setattr(upload_command, "_try_auto_tmdb_id", lambda _path: 4771)
    monkeypatch.setattr(
        upload_command, "_apply_upload_preset", lambda metadata, *_a, **_k: metadata
    )
    monkeypatch.setattr(upload_command, "_load_upload_preset", lambda _preset: None)

    captured: dict[str, object] = {}

    def _fake_preview(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(upload_command, "_render_upload_preview", _fake_preview)

    upload_command.run_command.callback(
        torrent_file=torrent_file,
        tracker="tracker-a",
        name=None,
        description="[b]desc long enough for tests[/b]",
        description_file=None,
        nfo_path=None,
        category=None,
        type=None,
        resolution=None,
        category_id=None,
        subcategory_id=None,
        options_json=None,
        description_format=None,
        uploader_note=None,
        tmdb_id=None,
        auto_tmdb=True,
        imdb_id=None,
        tvdb_id=None,
        anonymous=False,
        stream=True,
        dry_run=True,
        preset=None,
    )

    metadata = captured["metadata"]
    assert metadata.tmdb_id == 4771
