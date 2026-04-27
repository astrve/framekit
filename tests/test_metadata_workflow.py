from pathlib import Path

from framekit.core.models.metadata import MetadataCandidate
from framekit.core.models.nfo import EpisodeNfoData, ReleaseNfoData
from framekit.modules.metadata.base import MetadataProvider
from framekit.modules.metadata.workflow import run_metadata_workflow


class DummyProvider(MetadataProvider):
    name = "tmdb"

    def search(self, request):
        return [
            MetadataCandidate(
                provider_name="tmdb",
                provider_id="123",
                kind=request.media_kind,
                title=request.title or "Unknown",
                year=request.year,
                season_number=request.season_number,
                episode_number=request.episode_number,
                confidence=0.95,
                reasons=["dummy"],
            )
        ]

    def fetch_movie(self, candidate):
        from framekit.core.models.metadata import MovieMetadata

        return MovieMetadata(
            provider_name="tmdb",
            provider_id="123",
            imdb_id="tt0000001",
            external_url="https://example.com",
            title=candidate.title,
            year=candidate.year,
            overview="Movie overview",
        )

    def fetch_episode(self, candidate):
        from framekit.core.models.metadata import EpisodeMetadata

        return EpisodeMetadata(
            provider_name="tmdb",
            provider_id="123",
            imdb_id="tt0000002",
            external_url="https://example.com",
            series_title=candidate.title,
            series_year=candidate.year,
            season_number=candidate.season_number,
            episode_number=candidate.episode_number,
            episode_title="Episode title",
            overview="Episode overview",
        )

    def fetch_season(self, candidate):
        from framekit.core.models.metadata import SeasonMetadata

        return SeasonMetadata(
            provider_name="tmdb",
            provider_id="123",
            imdb_id="tt0000003",
            external_url="https://example.com",
            series_title=candidate.title,
            series_year=candidate.year,
            season_number=candidate.season_number,
            overview="Season overview",
        )


def test_run_metadata_workflow_missing_credentials():
    release = ReleaseNfoData(
        media_kind="movie",
        release_title="MOONLIGHT.2016.MULTI.VFF.1080P.WEB.H264-ACKER",
        title_display="MOONLIGHT",
        series_title=None,
        year="2016",
        source="WEB",
        resolution="1080P",
        video_tag="H264",
        audio_tag="E-AC-3.5.1",
        language_tag="MULTI (EN, FR)",
        audio_languages_display="English / French",
        episodes=[],
    )

    result = run_metadata_workflow(
        release,
        {"metadata": {}},
        auto_accept=True,
        show_ui=False,
        env={},
    )
    assert result.status == "missing_credentials"


def test_run_metadata_workflow_resolved(monkeypatch):
    release = ReleaseNfoData(
        media_kind="single_episode",
        release_title="LES.SIMPSON.1989.S08E04.MULTI.VFF.1080P.WEB.H264-ACKER",
        title_display="LES SIMPSON",
        series_title="LES SIMPSON",
        year="1989",
        source="WEB",
        resolution="1080P",
        video_tag="H264",
        audio_tag="AAC.2.0",
        language_tag="MULTI (FR-FR, EN, ES)",
        audio_languages_display="French (France) / English / Spanish",
        episodes=[
            EpisodeNfoData(
                file_path=Path("dummy.mkv"),
                file_name="dummy.mkv",
                episode_code="S08E04",
                episode_label="Season/Episode",
                episode_title=None,
                container="MATROSKA",
                size_bytes=1000,
                duration_ms=100,
                overall_bitrate_kbps=8000,
                resolution="1080P",
                aspect_ratio="1.778",
                aspect_ratio_display="1.778 (16/9)",
                video_codec="H264",
                hdr_display=None,
            )
        ],
    )

    monkeypatch.setattr(
        "framekit.modules.metadata.workflow.build_metadata_provider",
        lambda settings, **kwargs: DummyProvider(),
    )

    settings = {
        "metadata": {
            "tmdb_read_access_token": "dummy.valid.token",
            "interactive_confirmation": False,
        }
    }

    result = run_metadata_workflow(
        release,
        settings,
        auto_accept=True,
        show_ui=False,
        env={},
    )

    assert result.status == "resolved"
    assert result.resolved is not None
    assert "metadata_episode" in result.context


def test_run_metadata_workflow_passes_language_override_to_provider(monkeypatch):
    release = ReleaseNfoData(
        media_kind="movie",
        release_title="MOONLIGHT.2016.MULTI.VFF.1080P.WEB.H264-ACKER",
        title_display="MOONLIGHT",
        series_title=None,
        year="2016",
        source="WEB",
        resolution="1080P",
        video_tag="H264",
        audio_tag="E-AC-3.5.1",
        language_tag="MULTI (EN, FR)",
        audio_languages_display="English / French",
        episodes=[],
    )

    captured = {}

    def fake_build_metadata_provider(settings, **kwargs):
        captured["language"] = kwargs["config"].language
        return DummyProvider()

    monkeypatch.setattr(
        "framekit.modules.metadata.workflow.build_metadata_provider",
        fake_build_metadata_provider,
    )

    result = run_metadata_workflow(
        release,
        {
            "metadata": {
                "tmdb_read_access_token": "dummy.valid.token",
                "interactive_confirmation": False,
                "language": "fr-FR",
            }
        },
        auto_accept=True,
        show_ui=False,
        env={"FRAMEKIT_METADATA_LANGUAGE": "en-US"},
        language_override="es-ES",
    )

    assert result.status == "resolved"
    assert captured["language"] == "es-ES"
