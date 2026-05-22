"""Regression tests for pipeline upload step behavior."""

from __future__ import annotations

from types import SimpleNamespace

from framekit.commands import pipeline_steps


def _make_release_parse_result():
    return SimpleNamespace(
        resolution="1080p",
        source="WEB",
        codec="x264",
        audio="AAC",
        hdr=None,
    )


def _make_context(torrent_path):
    return SimpleNamespace(
        torrent_path=torrent_path,
        nfo_path=None,
        metadata_context=None,
        release=None,
        prez_outputs=[],
        dry_run=False,
    )


def test_upload_step_returns_failure_when_all_uploads_fail(monkeypatch, tmp_path):
    torrent_path = tmp_path / "release.torrent"
    torrent_path.write_bytes(b"torrent-bytes")

    import framekit.modules.upload.metadata_extractor as metadata_extractor
    import framekit.modules.upload.service as upload_service

    monkeypatch.setattr(
        metadata_extractor.ReleaseParser,
        "parse",
        staticmethod(lambda _name: _make_release_parse_result()),
    )

    class _UploadService:
        def upload_to_multiple(self, *_args, **_kwargs):
            return {"tracker-a": SimpleNamespace(success=False)}

    monkeypatch.setattr(upload_service, "UploadService", _UploadService)

    settings = {
        "upload": {
            "enabled": True,
            "auto_upload": True,
            "trackers": [{"name": "tracker-a"}],
            "max_parallel_uploads": 2,
        }
    }
    code = pipeline_steps._upload_step(
        work_folder=tmp_path,
        context=_make_context(torrent_path),
        settings=settings,
    )
    assert code == 1


def test_upload_step_returns_success_when_at_least_one_upload_succeeds(monkeypatch, tmp_path):
    torrent_path = tmp_path / "release.torrent"
    torrent_path.write_bytes(b"torrent-bytes")

    import framekit.modules.upload.metadata_extractor as metadata_extractor
    import framekit.modules.upload.service as upload_service

    monkeypatch.setattr(
        metadata_extractor.ReleaseParser,
        "parse",
        staticmethod(lambda _name: _make_release_parse_result()),
    )

    class _UploadService:
        def upload_to_multiple(self, *_args, **_kwargs):
            return {
                "tracker-a": SimpleNamespace(success=False),
                "tracker-b": SimpleNamespace(success=True),
            }

    monkeypatch.setattr(upload_service, "UploadService", _UploadService)

    settings = {
        "upload": {
            "enabled": True,
            "auto_upload": True,
            "trackers": [{"name": "tracker-a"}, {"name": "tracker-b"}],
            "max_parallel_uploads": 2,
        }
    }
    code = pipeline_steps._upload_step(
        work_folder=tmp_path,
        context=_make_context(torrent_path),
        settings=settings,
    )
    assert code == 0


def test_resolve_pipeline_upload_description_reads_bbcode_txt(tmp_path):
    bbcode_path = tmp_path / "release.bbcode.txt"
    bbcode_path.write_text("[b]Description[/b]", encoding="utf-8")
    context = SimpleNamespace(prez_outputs=[bbcode_path])

    description = pipeline_steps._resolve_pipeline_upload_description(
        context=context,
        image_urls=[],
        inject_images_into_bbcode_fn=lambda text, _urls: text,
    )

    assert description == "[b]Description[/b]"


def test_upload_pipeline_screenshots_discovers_from_work_folder(tmp_path):
    screens_dir = tmp_path / "screens"
    screens_dir.mkdir()
    shot1 = screens_dir / "shot1.png"
    shot2 = tmp_path / "screenshot_02.jpg"
    shot1.write_bytes(b"a")
    shot2.write_bytes(b"b")

    class _ImageHostService:
        def __init__(self, *_args):
            pass

        def upload_batch(self, screenshots):
            return [(path, f"https://img.local/{path.name}") for path in screenshots]

    image_urls = pipeline_steps._upload_pipeline_screenshots(
        work_folder=tmp_path,
        context=SimpleNamespace(prez_outputs=[]),
        image_host="imgbb",
        image_host_api_key="key",
        image_host_service_cls=_ImageHostService,
    )

    assert image_urls == [
        "https://img.local/shot1.png",
        "https://img.local/screenshot_02.jpg",
    ]


def test_apply_c411_metadata_mapping_infers_film_animation(monkeypatch, tmp_path):
    torrent_path = tmp_path / "release.torrent"
    torrent_path.write_bytes(b"torrent")
    context = _make_context(torrent_path)
    context.release = SimpleNamespace(
        media_kind="movie",
        language_tag="MULTI",
        audio_languages_display="French",
    )
    context.metadata_context = {
        "metadata_movie": SimpleNamespace(genres=["Animation"]),
    }
    parsed = SimpleNamespace(
        source="WEB-DL",
        resolution="2160p",
        season=None,
        episode=None,
        title="Foo",
        codec="x265",
        audio="DTS",
        hdr="HDR10",
    )
    nfo_data = SimpleNamespace(genre=[], tmdb_id=None, imdb_id=None, tvdb_id=None)

    metadata = pipeline_steps._build_pipeline_upload_metadata(
        context=context,
        release_name="Movie.2024",
        parsed=parsed,
        nfo_data=nfo_data,
        description="[b]desc[/b]",
    )
    mapped = pipeline_steps._apply_c411_metadata_mapping(
        settings={"upload": {"trackers": [{"name": "c411", "type": "c411", "defaults": {}}]}},
        tracker_names=["c411"],
        context=context,
        parsed=parsed,
        nfo_data=nfo_data,
        metadata=metadata,
    )

    assert mapped.c411_category_id == 1
    assert mapped.c411_subcategory_id == 1
    assert mapped.c411_options["2"] == 26
    assert mapped.c411_options["1"] == [4]


def test_apply_c411_metadata_mapping_infers_tv_episode(monkeypatch, tmp_path):
    torrent_path = tmp_path / "release.torrent"
    torrent_path.write_bytes(b"torrent")
    context = _make_context(torrent_path)
    context.release = SimpleNamespace(
        media_kind="single_episode",
        language_tag="VOSTFR",
        audio_languages_display="English",
    )
    context.metadata_context = {
        "metadata_episode": SimpleNamespace(genres=["Drama"]),
    }
    parsed = SimpleNamespace(
        source="WEB-DL",
        resolution="1080p",
        season=1,
        episode=2,
        title="Show",
        codec="x264",
        audio="DD+",
        hdr=None,
    )
    nfo_data = SimpleNamespace(genre=[], tmdb_id=None, imdb_id=None, tvdb_id=None)

    metadata = pipeline_steps._build_pipeline_upload_metadata(
        context=context,
        release_name="Show.S01E02",
        parsed=parsed,
        nfo_data=nfo_data,
        description="[b]desc[/b]",
    )
    mapped = pipeline_steps._apply_c411_metadata_mapping(
        settings={"upload": {"trackers": [{"name": "c411", "type": "c411", "defaults": {}}]}},
        tracker_names=["c411"],
        context=context,
        parsed=parsed,
        nfo_data=nfo_data,
        metadata=metadata,
    )

    assert mapped.c411_category_id == 1
    assert mapped.c411_subcategory_id == 7
    assert mapped.c411_options["2"] == 25
    assert mapped.c411_options["1"] == [8]
    assert mapped.c411_options["7"] == 121
    assert mapped.c411_options["6"] == 98


def test_torrent_step_uses_folder_mode_for_pipeline_upload(tmp_path, monkeypatch):
    work_folder = tmp_path / "release"
    work_folder.mkdir()
    (work_folder / "movie.mkv").write_bytes(b"mkv")
    context = SimpleNamespace(dry_run=False, torrent_path=None)
    called: dict[str, object] = {}

    def _fake_run_torrent_command(**kwargs):
        called.update(kwargs)
        return 0

    monkeypatch.setattr(pipeline_steps, "run_torrent_command", _fake_run_torrent_command)

    code = pipeline_steps._torrent_step(
        work_folder=work_folder,
        announce="https://tracker.example/announce",
        context=context,
        output_folder=tmp_path,
        settings={},
    )

    assert code == 0
    assert called["content_mode"] == "folder"
