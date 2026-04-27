from pathlib import Path

from framekit.core.models.metadata import MetadataCandidate
from framekit.core.models.nfo import EpisodeNfoData, ReleaseNfoData
from framekit.modules.metadata.cache import MetadataCache
from framekit.modules.metadata.matcher import build_lookup_request


def test_build_lookup_request_movie():
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

    request = build_lookup_request(release)
    assert request.media_kind == "movie"
    assert request.title == "MOONLIGHT"
    assert request.year == "2016"


def test_build_lookup_request_single_episode():
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

    request = build_lookup_request(release)
    assert request.media_kind == "single_episode"
    assert request.title == "LES SIMPSON"
    assert request.season_number == 8
    assert request.episode_number == 4


def test_metadata_cache_roundtrip(tmp_path: Path):
    cache = MetadataCache(tmp_path / "metadata_cache.json")

    from framekit.core.models.metadata import MetadataLookupRequest

    request = MetadataLookupRequest(
        media_kind="movie",
        title="MOONLIGHT",
        year="2016",
    )

    candidates = [
        MetadataCandidate(
            provider_name="tmdb",
            provider_id="123",
            kind="movie",
            title="Moonlight",
            year="2016",
            confidence=0.95,
        )
    ]

    cache.set("tmdb", request, candidates)
    loaded = cache.get("tmdb", request, ttl_hours=168)

    assert loaded is not None
    assert len(loaded) == 1
    assert loaded[0].title == "Moonlight"
