from pathlib import Path

from framekit.core.models.metadata import (
    EpisodeMetadata,
    MetadataCandidate,
    MovieMetadata,
    SeasonMetadata,
)
from framekit.core.models.nfo import EpisodeNfoData, ReleaseNfoData
from framekit.modules.metadata.base import MetadataProvider
from framekit.modules.metadata.service import MetadataService


class DummyProvider(MetadataProvider):
    name = "dummy"

    def search(self, request):
        return [
            MetadataCandidate(
                provider_name="dummy",
                provider_id="123",
                kind=request.media_kind,
                title=request.title or "Unknown",
                year=request.year,
                season_number=request.season_number,
                episode_number=request.episode_number,
                confidence=0.95,
            )
        ]

    def fetch_movie(self, candidate):
        return MovieMetadata(
            provider_name="dummy",
            provider_id=candidate.provider_id,
            imdb_id=None,
            external_url=None,
            title=candidate.title,
            year=candidate.year,
            overview=None,
        )

    def fetch_episode(self, candidate):
        return EpisodeMetadata(
            provider_name="dummy",
            provider_id=candidate.provider_id,
            imdb_id=None,
            external_url=None,
            series_title=candidate.title,
            series_year=candidate.year,
            season_number=candidate.season_number,
            episode_number=candidate.episode_number,
            episode_title=None,
            overview=None,
        )

    def fetch_season(self, candidate):
        return SeasonMetadata(
            provider_name="dummy",
            provider_id=candidate.provider_id,
            imdb_id=None,
            external_url=None,
            series_title=candidate.title,
            series_year=candidate.year,
            season_number=candidate.season_number,
            overview=None,
        )


def test_metadata_service_search_and_resolve_movie():
    provider = DummyProvider()
    service = MetadataService(provider)

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

    _request, candidates = service.search(release)
    result = service.resolve_candidate(candidates[0])

    assert isinstance(result, MovieMetadata)
    assert result.title == "MOONLIGHT"
    assert result.year == "2016"


def test_metadata_service_search_and_resolve_single_episode():
    provider = DummyProvider()
    service = MetadataService(provider)

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

    _request, candidates = service.search(release)
    result = service.resolve_candidate(candidates[0])

    assert isinstance(result, EpisodeMetadata)
    assert result.series_title == "LES SIMPSON"
    assert result.season_number == 8
    assert result.episode_number == 4


def test_metadata_service_merges_stored_choice_with_candidates(tmp_path: Path):
    provider = DummyProvider()
    from framekit.modules.metadata.choices import MetadataChoiceStore

    choice_store = MetadataChoiceStore(tmp_path / "metadata_choices.json")
    service = MetadataService(provider, choice_store=choice_store)

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

    stored = MetadataCandidate(
        provider_name="dummy",
        provider_id="999",
        kind="movie",
        title="Stored Moonlight",
        year="2016",
        confidence=1.0,
    )
    service.store_choice(release, stored)

    _request, candidates = service.search(release)

    assert len(candidates) >= 1
    assert candidates[0].provider_id == "999"
    assert "stored choice" in candidates[0].reasons
