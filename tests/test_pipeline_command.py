from __future__ import annotations

from framekit.commands import pipeline as pipeline_command_module
from framekit.core.settings import SettingsStore


class _StoreFactory:
    def __init__(self, store: SettingsStore) -> None:
        self.store = store

    def __call__(self) -> SettingsStore:
        return self.store


def test_pipeline_runs_steps_in_order_and_uses_clean_folder(
    monkeypatch, tmp_path, temp_settings_store
):
    root = tmp_path / "Release"
    clean = root / "clean"
    clean.mkdir(parents=True)

    temp_settings_store.set("modules.pipeline.stop_on_error", True)
    monkeypatch.setattr(
        pipeline_command_module, "SettingsStore", _StoreFactory(temp_settings_store)
    )

    calls: list[tuple[str, str | None]] = []
    monkeypatch.setattr(
        pipeline_command_module,
        "_renamer_step",
        lambda folder: calls.append(("renamer", folder.name)) or 0,
    )
    monkeypatch.setattr(
        pipeline_command_module,
        "_cleanmkv_step",
        lambda folder: calls.append(("cleanmkv", folder.name)) or 0,
    )
    monkeypatch.setattr(
        pipeline_command_module,
        "_nfo_step",
        lambda folder, locale, *args: calls.append(("nfo", f"{folder.name}:{locale}")) or 0,
    )
    monkeypatch.setattr(
        pipeline_command_module,
        "_torrent_step",
        lambda folder, announce, *args: calls.append(("torrent", f"{folder.name}:{announce}")) or 0,
    )
    monkeypatch.setattr(
        pipeline_command_module,
        "_prez_step",
        lambda folder, locale, *args: calls.append(("prez", f"{folder.name}:{locale}")) or 0,
    )

    assert (
        pipeline_command_module.run_pipeline_command(
            path=str(root),
            nfo_locale="es",
            announce="https://tracker.example/announce",
            skip_renamer=False,
            skip_cleanmkv=False,
            skip_nfo=False,
            skip_torrent=False,
            skip_prez=False,
        )
        == 0
    )

    assert calls == [
        ("renamer", "Release"),
        ("cleanmkv", "Release"),
        ("nfo", "clean:es"),
        ("torrent", "clean:https://tracker.example/announce"),
        ("prez", "clean:es"),
    ]
    assert temp_settings_store.get("modules.pipeline.last_folder") == str(root)


def test_pipeline_respects_skip_flags(monkeypatch, tmp_path, temp_settings_store):
    root = tmp_path / "Release"
    root.mkdir()
    monkeypatch.setattr(
        pipeline_command_module, "SettingsStore", _StoreFactory(temp_settings_store)
    )

    calls: list[str] = []
    monkeypatch.setattr(
        pipeline_command_module, "_renamer_step", lambda folder: calls.append("renamer") or 0
    )
    monkeypatch.setattr(
        pipeline_command_module, "_cleanmkv_step", lambda folder: calls.append("cleanmkv") or 0
    )
    monkeypatch.setattr(
        pipeline_command_module, "_nfo_step", lambda folder, locale, *args: calls.append("nfo") or 0
    )
    monkeypatch.setattr(
        pipeline_command_module,
        "_torrent_step",
        lambda folder, announce, *args: calls.append("torrent") or 0,
    )
    monkeypatch.setattr(
        pipeline_command_module,
        "_prez_step",
        lambda folder, locale, *args: calls.append("prez") or 0,
    )

    assert (
        pipeline_command_module.run_pipeline_command(
            path=str(root),
            nfo_locale=None,
            announce=None,
            skip_renamer=True,
            skip_cleanmkv=False,
            skip_nfo=True,
            skip_torrent=False,
            skip_prez=True,
        )
        == 0
    )

    assert calls == ["cleanmkv", "torrent"]


def test_pipeline_stops_on_first_failure_when_configured(
    monkeypatch, tmp_path, temp_settings_store
):
    root = tmp_path / "Release"
    root.mkdir()
    temp_settings_store.set("modules.pipeline.stop_on_error", True)
    monkeypatch.setattr(
        pipeline_command_module, "SettingsStore", _StoreFactory(temp_settings_store)
    )

    calls: list[str] = []
    monkeypatch.setattr(
        pipeline_command_module, "_renamer_step", lambda folder: calls.append("renamer") or 2
    )
    monkeypatch.setattr(
        pipeline_command_module, "_cleanmkv_step", lambda folder: calls.append("cleanmkv") or 0
    )

    assert (
        pipeline_command_module.run_pipeline_command(
            path=str(root),
            nfo_locale=None,
            announce=None,
            skip_renamer=False,
            skip_cleanmkv=False,
            skip_nfo=True,
            skip_torrent=True,
            skip_prez=True,
        )
        == 2
    )
    assert calls == ["renamer"]


def test_pipeline_can_continue_after_failure(monkeypatch, tmp_path, temp_settings_store):
    root = tmp_path / "Release"
    root.mkdir()
    temp_settings_store.set("modules.pipeline.stop_on_error", False)
    monkeypatch.setattr(
        pipeline_command_module, "SettingsStore", _StoreFactory(temp_settings_store)
    )

    calls: list[str] = []
    monkeypatch.setattr(
        pipeline_command_module, "_renamer_step", lambda folder: calls.append("renamer") or 1
    )
    monkeypatch.setattr(
        pipeline_command_module, "_cleanmkv_step", lambda folder: calls.append("cleanmkv") or 0
    )

    assert (
        pipeline_command_module.run_pipeline_command(
            path=str(root),
            nfo_locale=None,
            announce=None,
            skip_renamer=False,
            skip_cleanmkv=False,
            skip_nfo=True,
            skip_torrent=True,
            skip_prez=True,
        )
        == 1
    )
    assert calls == ["renamer", "cleanmkv"]


def test_pipeline_missing_folder_returns_error(monkeypatch, tmp_path, temp_settings_store):
    monkeypatch.setattr(
        pipeline_command_module, "SettingsStore", _StoreFactory(temp_settings_store)
    )

    assert (
        pipeline_command_module.run_pipeline_command(
            path=str(tmp_path / "missing"),
            nfo_locale=None,
            announce=None,
            skip_renamer=True,
            skip_cleanmkv=True,
            skip_nfo=True,
            skip_torrent=True,
            skip_prez=True,
        )
        == 1
    )


def test_pipeline_context_reuses_release_and_metadata(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from framekit.core.models.nfo import EpisodeNfoData, ReleaseNfoData
    from framekit.core.reporting import OperationReport
    from framekit.modules.prez.service import PrezBuildResult

    episode = EpisodeNfoData(
        file_path=tmp_path / "movie.mkv",
        file_name="movie.mkv",
        episode_code=None,
        episode_label=None,
        episode_title=None,
        container="MKV",
        size_bytes=1,
        duration_ms=60_000,
        overall_bitrate_kbps=None,
        resolution="1080p",
        aspect_ratio=None,
        aspect_ratio_display=None,
        video_codec="H.264",
        hdr_display=None,
    )
    release = ReleaseNfoData(
        media_kind="movie",
        release_title="Movie.2024.1080p.WEB-DL",
        title_display="Movie",
        series_title=None,
        year="2024",
        source="WEB-DL",
        resolution="1080p",
        video_tag="H.264",
        audio_tag=None,
        language_tag=None,
        audio_languages_display=None,
        episodes=[episode],
    )
    settings = {
        "general": {"locale": "en"},
        "modules": {"nfo": {"locale": "en"}, "prez": {"format": "bbcode"}},
    }
    calls = {"scan": 0, "build": 0, "metadata": 0}

    def fake_scan(folder):
        calls["scan"] += 1
        return [episode]

    def fake_build(folder, episodes):
        calls["build"] += 1
        return release

    def fake_metadata(release_arg, settings_arg, **kwargs):
        calls["metadata"] += 1
        assert release_arg is release
        return SimpleNamespace(status="resolved", context={"metadata_movie": None})

    class FakeNfoService:
        def build_from_release(self, folder, **kwargs):
            assert kwargs["release"] is release
            assert kwargs["extra_context"] == {"metadata_movie": None}
            report = OperationReport(tool="nfo")
            report.add_detail(
                file=None,
                action="nfo",
                status="built",
                after={"template": "movie_default"},
            )
            return report, release, "NFO"

        def write_rendered(self, folder, **kwargs):
            return OperationReport(tool="nfo"), tmp_path / "Movie.en.nfo"

    class FakePrezService:
        def build(self, folder, *, options, write):
            assert options.release is release
            assert options.metadata_context == {"metadata_movie": None}
            return OperationReport(tool="prez"), PrezBuildResult(
                release=release, outputs=(tmp_path / "Movie.tracker.bbcode.txt",)
            )

    monkeypatch.setattr(pipeline_command_module, "scan_nfo_folder", fake_scan)
    monkeypatch.setattr(pipeline_command_module, "build_release_nfo", fake_build)
    monkeypatch.setattr(pipeline_command_module, "run_metadata_workflow", fake_metadata)
    monkeypatch.setattr(pipeline_command_module, "NfoService", FakeNfoService)
    monkeypatch.setattr(pipeline_command_module, "PrezService", FakePrezService)

    context = pipeline_command_module.PipelineContext()

    assert pipeline_command_module._nfo_step(tmp_path, "en", context, settings) == 0
    assert pipeline_command_module._prez_step(tmp_path, "en", context, settings, "tracker") == 0

    assert calls == {"scan": 1, "build": 1, "metadata": 1}
    assert context.release is release
    assert context.metadata_context == {"metadata_movie": None}
    assert context.nfo_path == tmp_path / "Movie.en.nfo"
    assert context.prez_outputs == (tmp_path / "Movie.tracker.bbcode.txt",)


def test_pipeline_passes_remove_terms_to_renamer(monkeypatch, tmp_path, temp_settings_store):
    root = tmp_path / "Release"
    root.mkdir()
    monkeypatch.setattr(
        pipeline_command_module, "SettingsStore", _StoreFactory(temp_settings_store)
    )

    captured = {}

    def fake_renamer(folder, remove_terms=()):
        captured["folder"] = folder
        captured["remove_terms"] = remove_terms
        return 0

    monkeypatch.setattr(pipeline_command_module, "_renamer_step", fake_renamer)

    assert (
        pipeline_command_module.run_pipeline_command(
            path=str(root),
            nfo_locale=None,
            announce=None,
            skip_renamer=False,
            skip_cleanmkv=True,
            skip_nfo=True,
            skip_torrent=True,
            skip_prez=True,
            remove_terms=("DSNP",),
        )
        == 0
    )

    assert captured["folder"] == root
    assert captured["remove_terms"] == ("DSNP",)
