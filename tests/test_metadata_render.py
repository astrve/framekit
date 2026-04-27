from pathlib import Path

from framekit.core.models.metadata import EpisodeMetadata, SeasonMetadata
from framekit.core.models.nfo import EpisodeNfoData, ReleaseNfoData
from framekit.modules.metadata.render import build_metadata_context


def test_build_metadata_context_filters_season_to_folder_episodes():
    release = ReleaseNfoData(
        media_kind="season_pack",
        release_title="LES.SIMPSON.1989.S12.MULTI.VFF.1080P.WEB.H264-ACKER",
        title_display="LES SIMPSON",
        series_title="LES SIMPSON",
        year="1989",
        source="WEB",
        resolution="1080P",
        video_tag="H264",
        audio_tag="E-AC-3.5.1",
        language_tag="MULTI (FR, EN, ES)",
        audio_languages_display="French / English / Spanish",
        episodes=[
            EpisodeNfoData(
                file_path=Path("e1.mkv"),
                file_name="e1.mkv",
                episode_code="S12E01",
                episode_label="Season/Episode",
                episode_title=None,
                container="MATROSKA",
                size_bytes=1,
                duration_ms=1,
                overall_bitrate_kbps=1,
                resolution="1080P",
                aspect_ratio="1.778",
                aspect_ratio_display="1.778 (16/9)",
                video_codec="H264",
                hdr_display=None,
            ),
            EpisodeNfoData(
                file_path=Path("e2.mkv"),
                file_name="e2.mkv",
                episode_code="S12E02",
                episode_label="Season/Episode",
                episode_title=None,
                container="MATROSKA",
                size_bytes=1,
                duration_ms=1,
                overall_bitrate_kbps=1,
                resolution="1080P",
                aspect_ratio="1.778",
                aspect_ratio_display="1.778 (16/9)",
                video_codec="H264",
                hdr_display=None,
            ),
        ],
    )

    season = SeasonMetadata(
        provider_name="tmdb",
        provider_id="123",
        imdb_id="tt0096697",
        external_url="https://example.com",
        series_title="The Simpsons",
        series_year="1989",
        season_number=12,
        overview="Season overview",
        episode_summaries=[
            EpisodeMetadata(
                provider_name="tmdb",
                provider_id="1",
                imdb_id=None,
                external_url=None,
                series_title="The Simpsons",
                series_year="1989",
                season_number=12,
                episode_number=1,
                episode_title="Episode One",
                overview="Overview 1",
                air_date="2000-01-01",
            ),
            EpisodeMetadata(
                provider_name="tmdb",
                provider_id="2",
                imdb_id=None,
                external_url=None,
                series_title="The Simpsons",
                series_year="1989",
                season_number=12,
                episode_number=2,
                episode_title="Episode Two",
                overview="Overview 2",
                air_date="2000-01-08",
            ),
            EpisodeMetadata(
                provider_name="tmdb",
                provider_id="3",
                imdb_id=None,
                external_url=None,
                series_title="The Simpsons",
                series_year="1989",
                season_number=12,
                episode_number=3,
                episode_title="Episode Three",
                overview="Overview 3",
                air_date="2000-01-15",
            ),
        ],
    )

    context = build_metadata_context(season, release)
    filtered = context["metadata_season"]
    episode_map = context["metadata_episode_map"]

    assert filtered is not None
    assert len(filtered.episode_summaries) == 2
    assert "S12E01" in episode_map
    assert "S12E02" in episode_map
    assert "S12E03" not in episode_map
