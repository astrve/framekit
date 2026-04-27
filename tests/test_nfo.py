from pathlib import Path

from framekit.core.models.nfo import EpisodeNfoData, ReleaseNfoData, TrackNfoData
from framekit.modules.nfo.builder import build_release_nfo
from framekit.modules.nfo.service import NfoService
from framekit.modules.nfo.templates import list_all_templates


def _track(
    display_id: str,
    kind: str,
    language_display: str | None,
    language_short: str | None,
    format_name: str | None,
    codec: str | None,
    codec_id: str | None,
    channels: str | None,
    channels_count: int | None,
    title: str | None,
    is_default: bool,
    is_forced: bool,
    subtitle_variant: str | None,
    bitrate: int | None,
    size_bytes: int | None,
    size_percent: float | None,
    bit_depth: int | None,
    frame_rate: float | None,
) -> TrackNfoData:
    return TrackNfoData(
        display_id=display_id,
        kind=kind,
        language_display=language_display,
        language_short=language_short,
        format_name=format_name,
        codec=codec,
        codec_id=codec_id,
        channels=channels,
        channels_count=channels_count,
        title=title,
        is_default=is_default,
        is_forced=is_forced,
        subtitle_variant=subtitle_variant,
        bitrate=bitrate,
        size_bytes=size_bytes,
        size_percent=size_percent,
        bit_depth=bit_depth,
        frame_rate=frame_rate,
    )


def test_list_templates_has_default():
    data = list_all_templates()

    assert "movie_default" in data["builtin"]
    assert "movie_detailed" in data["builtin"]
    assert "single_episode_default" in data["builtin"]
    assert "single_episode_detailed" in data["builtin"]
    assert "series_default" in data["builtin"]
    assert "series_detailed" in data["builtin"]

    assert "_macros" not in data["builtin"]


def test_build_release_nfo_movie_kind():
    folder = Path("MovieFolder")
    episodes = [
        EpisodeNfoData(
            file_path=Path("MOONLIGHT.2016.MULTI.VFF.1080P.WEB.EAC3.5.1.H264-ACKER.mkv"),
            file_name="MOONLIGHT.2016.MULTI.VFF.1080P.WEB.EAC3.5.1.H264-ACKER.mkv",
            episode_code=None,
            episode_label=None,
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
            audio_summary=["English (US) / E-AC-3.5.1", "French / E-AC-3.5.1"],
            subtitle_summary=["English (US) / Full", "English (US) / SDH", "French / Full"],
            video_tracks=[],
            audio_tracks=[],
            subtitle_tracks=[],
        )
    ]

    release = build_release_nfo(folder, episodes)

    assert release.media_kind == "movie"
    assert release.title_display == "MOONLIGHT"
    assert release.year == "2016"
    assert release.series_title is None
    assert release.subtitle_summary_by_episode == []


def test_build_release_nfo_single_episode_kind():
    folder = Path("EpisodeFolder")
    episodes = [
        EpisodeNfoData(
            file_path=Path("LES.SIMPSON.1989.S08E04.MULTI.VFF.1080P.WEB.AAC.2.0.H264-ACKER.mkv"),
            file_name="LES.SIMPSON.1989.S08E04.MULTI.VFF.1080P.WEB.AAC.2.0.H264-ACKER.mkv",
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
            audio_summary=["French / AAC.2.0", "English / E-AC-3.5.1"],
            subtitle_summary=["French / Forced", "English / SDH"],
            video_tracks=[],
            audio_tracks=[],
            subtitle_tracks=[],
        )
    ]

    release = build_release_nfo(folder, episodes)

    assert release.media_kind == "single_episode"
    assert release.series_title == "LES SIMPSON"
    assert release.title_display == "LES SIMPSON"
    assert release.subtitle_summary_by_episode == []


def test_build_release_nfo_basic():
    folder = Path("Testmkv")
    episodes = [
        EpisodeNfoData(
            file_path=Path("Les.Simpson.1989.S00E01.Test.mkv"),
            file_name="Les.Simpson.1989.S00E01.MULTi.VFF.1080P.WEB.DDP5.1.H.264-ACKER.mkv",
            episode_code="S00E01",
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
            audio_summary=["French / E-AC-3.5.1", "English / E-AC-3.5.1"],
            subtitle_summary=["French / Forced", "English / SDH"],
            video_tracks=[
                _track(
                    "#1",
                    "video",
                    None,
                    None,
                    "AVC",
                    "H264",
                    None,
                    None,
                    None,
                    None,
                    True,
                    False,
                    None,
                    5000,
                    700,
                    70.0,
                    10,
                    23.976,
                ),
            ],
            audio_tracks=[
                _track(
                    "#2",
                    "audio",
                    "French",
                    "fr",
                    "E-AC-3",
                    "E-AC-3",
                    None,
                    "5.1",
                    None,
                    None,
                    True,
                    False,
                    None,
                    640,
                    200,
                    20.0,
                    None,
                    None,
                ),
                _track(
                    "#3",
                    "audio",
                    "English",
                    "en",
                    "E-AC-3",
                    "E-AC-3",
                    None,
                    "5.1",
                    None,
                    None,
                    False,
                    False,
                    None,
                    640,
                    80,
                    8.0,
                    None,
                    None,
                ),
            ],
            subtitle_tracks=[
                _track(
                    "#4",
                    "subtitle",
                    "French",
                    "fr",
                    "UTF-8",
                    "UTF-8",
                    None,
                    None,
                    None,
                    None,
                    False,
                    True,
                    "Forced",
                    10,
                    5,
                    0.5,
                    None,
                    None,
                ),
                _track(
                    "#5",
                    "subtitle",
                    "English",
                    "en",
                    "UTF-8",
                    "UTF-8",
                    None,
                    None,
                    None,
                    None,
                    False,
                    False,
                    "SDH",
                    12,
                    5,
                    0.5,
                    None,
                    None,
                ),
            ],
        ),
        EpisodeNfoData(
            file_path=Path("Les.Simpson.1989.S00E02.Test.mkv"),
            file_name="Les.Simpson.1989.S00E02.MULTi.VFF.1080P.WEB.DDP5.1.H.264-ACKER.mkv",
            episode_code="S00E02",
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
            audio_summary=["French / E-AC-3.5.1", "English / E-AC-3.5.1"],
            subtitle_summary=["French / Forced"],
            video_tracks=[],
            audio_tracks=[
                _track(
                    "#2",
                    "audio",
                    "French",
                    "fr",
                    "E-AC-3",
                    "E-AC-3",
                    None,
                    "5.1",
                    None,
                    None,
                    True,
                    False,
                    None,
                    640,
                    200,
                    20.0,
                    None,
                    None,
                ),
                _track(
                    "#3",
                    "audio",
                    "English",
                    "en",
                    "E-AC-3",
                    "E-AC-3",
                    None,
                    "5.1",
                    None,
                    None,
                    False,
                    False,
                    None,
                    640,
                    80,
                    8.0,
                    None,
                    None,
                ),
            ],
            subtitle_tracks=[
                _track(
                    "#4",
                    "subtitle",
                    "French",
                    "fr",
                    "UTF-8",
                    "UTF-8",
                    None,
                    None,
                    None,
                    None,
                    False,
                    True,
                    "Forced",
                    10,
                    5,
                    0.5,
                    None,
                    None,
                ),
            ],
        ),
    ]

    release = build_release_nfo(folder, episodes)

    assert release.release_title == "Les.Simpson.1989.S00.MULTi.VFF.1080P.WEB.DDP5.1.H.264-ACKER"
    assert release.series_title == "Les Simpson"
    assert release.year == "1989"
    assert release.source == "WEB"
    assert release.video_tag == "H264"
    assert release.audio_tag == "E-AC-3.5.1"
    assert release.team == "ACKER"
    assert release.language_tag == "MULTI (FR, EN)"
    assert release.audio_languages_display == "French / English"
    assert "French: Forced" in release.subtitle_summary_lines[0]
    assert release.subtitle_summary_by_episode[1].startswith("S00E02")
    assert "French: Forced" in release.subtitle_summary_by_episode[1]
    assert episodes[0].aspect_ratio_display == "1.778 (16/9)"
    assert release.subtitle_summary_by_episode[0].startswith("S00E01")
    assert release.subtitle_summary_by_episode[1].startswith("S00E02")


def test_nfo_service_write_rendered(tmp_path: Path):
    service = NfoService()

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

    report, path = service.write_rendered(
        tmp_path,
        release=release,
        rendered="hello world",
        template_name="movie_detailed",
    )

    assert path.exists()
    assert path.read_text(encoding="utf-8") == "hello world"
    assert report.modified == 1


def _minimal_render_context():
    from types import SimpleNamespace

    release = SimpleNamespace(
        title_display="Moonlight",
        year="2016",
        team="ACKER",
        source="WEB",
        resolution="1080P",
        video_tag="H264",
        audio_tag="EAC3.5.1",
        language_tag="MULTI.VFF",
        audio_languages_display="French | English",
        hdr_display=None,
        release_title="MOONLIGHT.2016.MULTI.VFF.1080P.WEB.EAC3.5.1.H264-ACKER",
        total_size_bytes=1000,
        total_duration_ms=1000,
        subtitle_summary_lines=[],
        series_title="The Series",
        subtitle_summary_by_episode=[],
        episodes=[],
    )
    return {
        "release": release,
        "episodes": [],
        "logo_text": None,
        "metadata_movie": None,
        "metadata_episode": None,
        "metadata_season": None,
        "metadata_episode_map": {},
    }


def test_list_templates_collapses_localized_builtin_variants():
    data = list_all_templates()

    assert "movie_default" in data["builtin"]
    assert "movie_default.fr" not in data["builtin"]
    assert "movie_default.es" not in data["builtin"]


def test_render_template_uses_requested_locale():
    from framekit.modules.nfo.templates import render_template

    rendered_fr = render_template("movie_default", _minimal_render_context(), locale="fr")
    rendered_es = render_template("movie_default", _minimal_render_context(), locale="es")

    assert "GÉNÉRAL" in rendered_fr
    assert "Titre" in rendered_fr
    assert "GENERAL" in rendered_es
    assert "Título" in rendered_es


def test_aspect_ratio_display_handles_two_to_one():
    from framekit.modules.nfo.scanner import _aspect_ratio_display

    assert _aspect_ratio_display("2.000") == "2.000 (2:1)"
