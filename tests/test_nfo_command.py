from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from framekit.commands import nfo as nfo_command_module
from framekit.core.reporting import OperationReport
from framekit.core.settings import SettingsStore


class _StoreFactory:
    def __init__(self, store: SettingsStore) -> None:
        self.store = store

    def __call__(self) -> SettingsStore:
        return self.store


def _release(folder: Path) -> SimpleNamespace:
    return SimpleNamespace(
        media_kind="movie",
        release_title="Movie.2024.1080p.WEB-DL",
        title_display="Movie",
        series_title=None,
        year="2024",
        source="WEB-DL",
        resolution="1080p",
        video_tag="H.264",
        audio_tag="E-AC-3",
        language_tag="MULTI",
        audio_languages_display="French",
        hdr_display=None,
        team="FRAME",
        episodes=[SimpleNamespace(file_path=folder / "movie.mkv")],
        total_size_bytes=1024,
        total_duration_ms=60_000,
    )


def test_resolve_metadata_context_handles_statuses(monkeypatch, tmp_path):
    release = _release(tmp_path)

    for status, expected_fragment in [
        ("missing_credentials", "credentials"),
        ("unsupported_specials", "Special"),
        ("no_candidates", "No metadata"),
        ("cancelled", "cancelled"),
        ("failed", "failed"),
    ]:
        monkeypatch.setattr(
            nfo_command_module,
            "run_metadata_workflow",
            lambda *args, status=status, **kwargs: SimpleNamespace(
                status=status,
                context={"ignored": True},
                message=None,
            ),
        )

        context, message = nfo_command_module._resolve_metadata_context(
            release,
            {},
            auto_accept=False,
            metadata_language="fr-FR",
        )

        assert context == {}
        assert expected_fragment.lower() in (message or "").lower()


def test_resolve_metadata_context_returns_resolved_context_and_passes_language(
    monkeypatch, tmp_path
):
    release = _release(tmp_path)
    captured = {}

    def fake_workflow(release_arg, settings, *, auto_accept, show_ui, language_override=None):
        captured["release"] = release_arg
        captured["auto_accept"] = auto_accept
        captured["show_ui"] = show_ui
        captured["language_override"] = language_override
        return SimpleNamespace(
            status="resolved", context={"tmdb": {"title": "Movie"}}, message=None
        )

    monkeypatch.setattr(nfo_command_module, "run_metadata_workflow", fake_workflow)

    context, message = nfo_command_module._resolve_metadata_context(
        release,
        {"metadata": {"provider": "tmdb"}},
        auto_accept=True,
        metadata_language="es-ES",
    )

    assert context == {"tmdb": {"title": "Movie"}}
    assert message is None
    assert captured == {
        "release": release,
        "auto_accept": True,
        "show_ui": True,
        "language_override": "es-ES",
    }


def test_run_nfo_command_maps_output_locale_to_metadata_language(
    monkeypatch, tmp_path, temp_settings_store
):
    folder = tmp_path / "Release"
    folder.mkdir()
    release = _release(folder)
    output = folder / "Release.nfo"

    monkeypatch.setattr(nfo_command_module, "SettingsStore", _StoreFactory(temp_settings_store))
    monkeypatch.setattr(nfo_command_module, "_build_release_from_folder", lambda folder: release)
    monkeypatch.setattr(
        nfo_command_module,
        "_resolve_template_choice",
        lambda template, settings, media_kind: SimpleNamespace(
            template_name="default",
            source="builtin",
            display_name="Default",
            scope="universal",
        ),
    )
    monkeypatch.setattr(nfo_command_module, "_print_nfo_summary", lambda release: None)
    monkeypatch.setattr(nfo_command_module, "_print_nfo_preflight", lambda **kwargs: None)

    captured = {}

    def fake_metadata_context(release_arg, settings, auto_accept, metadata_language=None):
        captured["metadata_language"] = metadata_language
        return {"tmdb": {"title": "Movie"}}, None

    monkeypatch.setattr(nfo_command_module, "_resolve_metadata_context", fake_metadata_context)

    class _Service:
        def build(self, folder_path, *, template_name, logo_path, template_locale, extra_context):
            captured["template_locale"] = template_locale
            captured["extra_context"] = extra_context
            return OperationReport(tool="nfo", scanned=1, processed=1), release, "rendered"

        def write_rendered(
            self,
            folder_path,
            *,
            release,
            rendered,
            template_name,
            template_locale,
        ):
            captured["write_locale"] = template_locale
            return OperationReport(tool="nfo", scanned=1, processed=1, modified=1), output

    monkeypatch.setattr(nfo_command_module, "NfoService", _Service)

    assert (
        nfo_command_module.run_nfo_command(
            path=str(folder),
            template="default",
            nfo_locale="es",
            write_requested=True,
            with_metadata=True,
            metadata_auto_accept=True,
            list_templates=False,
            import_template=None,
            import_name=None,
            import_scope=None,
            import_location=None,
            import_logo=None,
            logo_name=None,
            set_logo=None,
            list_logos=False,
            clear_logo=False,
        )
        == 0
    )

    assert captured["metadata_language"] == "es-ES"
    assert captured["template_locale"] == "es"
    assert captured["write_locale"] == "es"
    assert captured["extra_context"] == {"tmdb": {"title": "Movie"}}
    assert temp_settings_store.get("modules.nfo.last_folder") == str(folder)


def test_run_nfo_command_requires_explicit_folder_for_write(monkeypatch, temp_settings_store):
    monkeypatch.setattr(nfo_command_module, "SettingsStore", _StoreFactory(temp_settings_store))

    assert (
        nfo_command_module.run_nfo_command(
            path=None,
            template=None,
            nfo_locale=None,
            write_requested=True,
            with_metadata=False,
            metadata_auto_accept=False,
            list_templates=False,
            import_template=None,
            import_name=None,
            import_scope=None,
            import_location=None,
            import_logo=None,
            logo_name=None,
            set_logo=None,
            list_logos=False,
            clear_logo=False,
        )
        == 1
    )
