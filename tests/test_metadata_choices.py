from pathlib import Path

from framekit.core.models.metadata import MetadataCandidate
from framekit.core.models.nfo import EpisodeNfoData, ReleaseNfoData
from framekit.modules.metadata.choices import MetadataChoiceStore, build_release_signature


def test_build_release_signature_movie():
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

    signature = build_release_signature(release)
    assert signature == "movie | moonlight | 2016"


def test_build_release_signature_single_episode():
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
                size_bytes=1,
                duration_ms=1,
                overall_bitrate_kbps=1,
                resolution="1080P",
                aspect_ratio="1.778",
                aspect_ratio_display="1.778 (16/9)",
                video_codec="H264",
                hdr_display=None,
            )
        ],
    )

    signature = build_release_signature(release)
    assert signature == "single_episode | les simpson | 1989 | S08E04"


def test_metadata_choice_store_roundtrip(tmp_path: Path):
    store = MetadataChoiceStore(tmp_path / "metadata_choices.json")

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

    candidate = MetadataCandidate(
        provider_name="tmdb",
        provider_id="123",
        kind="movie",
        title="Moonlight",
        year="2016",
        confidence=0.95,
    )

    store.set(release, candidate)
    loaded = store.get(release)

    assert loaded is not None
    assert loaded.provider_name == "tmdb"
    assert loaded.provider_id == "123"
    assert loaded.kind == "movie"
