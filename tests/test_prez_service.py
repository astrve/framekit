from __future__ import annotations

from pathlib import Path

from framekit.core.i18n import get_locale, set_locale
from framekit.core.models.metadata import EpisodeMetadata, MovieMetadata, SeasonMetadata
from framekit.core.models.nfo import EpisodeNfoData, ReleaseNfoData, TrackNfoData
from framekit.modules.prez import service as prez_service
from framekit.modules.prez.service import (
    PrezBuildOptions,
    PrezService,
    available_bbcode_templates,
    available_html_templates,
    render_bbcode,
    render_html,
)


def _track(
    *,
    kind: str,
    language: str | None = "French",
    language_short: str | None = "fr",
    codec: str | None = "E-AC-3",
    channels: str | None = "5.1",
    bitrate: int | None = 768_000,
    subtitle_variant: str | None = None,
    is_default: bool = True,
    is_forced: bool = False,
) -> TrackNfoData:
    return TrackNfoData(
        display_id="#2",
        kind=kind,
        language_display=language,
        language_short=language_short,
        format_name="SRT" if kind == "subtitle" else codec,
        codec=codec,
        codec_id=None,
        channels=channels,
        channels_count=None,
        title=None,
        is_default=is_default,
        is_forced=is_forced,
        subtitle_variant=subtitle_variant,
        bitrate=bitrate,
        size_bytes=None,
        size_percent=None,
        bit_depth=None,
        frame_rate=None,
    )


def _release() -> ReleaseNfoData:
    audio = _track(
        kind="audio", language="French", language_short="fr", codec="E-AC-3", channels="5.1"
    )
    subtitle = _track(
        kind="subtitle",
        language="French",
        language_short="fr",
        codec="S_TEXT/UTF8",
        channels=None,
        bitrate=None,
        subtitle_variant="Full",
        is_default=False,
    )
    return ReleaseNfoData(
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
        audio_languages_display="French, English",
        total_size_bytes=3 * 1024 * 1024 * 1024,
        total_duration_ms=60_000,
        episodes=[
            EpisodeNfoData(
                file_path=Path("movie.mkv"),
                file_name="movie.mkv",
                episode_code=None,
                episode_label=None,
                episode_title=None,
                container="MKV",
                size_bytes=3 * 1024 * 1024 * 1024,
                duration_ms=60_000,
                overall_bitrate_kbps=None,
                resolution="1080p",
                aspect_ratio="1.778",
                aspect_ratio_display="1.778 (16/9)",
                video_codec="H.264",
                hdr_display="HDR10",
                video_bitrate=3_010_000,
                audio_summary=["fr · E-AC-3 · 5.1"],
                audio_tracks=[audio],
                subtitle_tracks=[subtitle],
            )
        ],
    )


def _metadata_context() -> dict:
    return {
        "metadata_movie": MovieMetadata(
            provider_name="tmdb",
            provider_id="123",
            imdb_id="tt1234567",
            external_url="https://www.themoviedb.org/movie/123",
            title="Movie",
            year="2024",
            overview="A compact overview.",
            genres=["Drama", "Animation"],
            runtime_minutes=96,
            original_title="Original Movie",
            release_date="2024-01-02",
            countries=["FR", "JP"],
            spoken_languages=["French", "Japanese"],
            vote_average=7.7,
            poster_url="https://image.example/poster.jpg",
            cast=["Actor One", "Actor Two"],
            crew=["Director: Person One"],
        ),
        "metadata_episode": None,
        "metadata_season": None,
        "metadata_episode_map": {},
    }


def test_available_prez_templates_are_rich_enough():
    assert len(available_html_templates()) >= 8
    assert len(available_bbcode_templates()) >= 8


def test_render_html_uses_requested_lang_attribute():
    html = render_html(_release(), locale="es")

    assert '<html lang="es">' in html


def test_render_html_omits_empty_movie_episode_fields_and_wraps_release_name():
    html = render_html(_release(), metadata_context=_metadata_context(), locale="fr")

    assert "Durée par épisode" not in html
    assert "IMDb" not in html
    assert "Source name" not in html
    assert "overflow-wrap:anywhere" in html
    assert "https://www.themoviedb.org/movie/123" in html
    assert "Screenshots" not in html


def test_render_bbcode_contains_tracker_sections_flags_and_tables():
    bbcode = render_bbcode(
        _release(),
        metadata_context=_metadata_context(),
        screenshots=("https://img.example/one.jpg",),
        mediainfo_text="General\nComplete name: movie.mkv",
    )

    assert "[h1]Movie[/h1]" in bbcode
    assert "[center][img]https://image.example/poster.jpg[/img][/center]" in bbcode
    assert "[img]https://flagcdn.com/20x15/fr.png[/img]" in bbcode
    assert "[url=https://www.themoviedb.org/movie/123]Link to the movie TMDb page[/url]" in bbcode
    assert "IMDb" not in bbcode
    assert "tt1234567" not in bbcode
    assert "[table]" in bbcode
    assert "E-AC-3" in bbcode
    assert "5.1" in bbcode
    assert "768 kb/s" in bbcode
    assert "[spoiler=MediaInfo]" in bbcode
    assert "https://img.example/one.jpg" not in bbcode
    assert "nfo_path" not in bbcode
    assert "torrent_path" not in bbcode


def test_render_bbcode_keeps_missing_fields_readable_without_empty_sections():
    release = _release()
    bbcode = render_bbcode(release, metadata_context=None)

    assert "[b]TMDb" not in bbcode
    assert "Screenshots" not in bbcode
    assert "[table]" in bbcode


def test_prez_service_uses_output_locale_and_restores_previous_locale(monkeypatch, tmp_path):
    release = _release()
    monkeypatch.setattr(prez_service, "scan_nfo_folder", lambda folder: release.episodes)
    monkeypatch.setattr(prez_service, "build_release_nfo", lambda folder, episodes: release)

    set_locale("en")
    output_dir = tmp_path / "out"
    _report, result = PrezService().build(
        tmp_path,
        options=PrezBuildOptions(formats=("html",), output_dir=output_dir, locale="fr"),
        write=True,
    )

    html = result.outputs[0].read_text(encoding="utf-8")
    assert '<html lang="fr">' in html
    assert "Movie" in html
    assert get_locale() == "en"


def test_prez_service_can_generate_mediainfo_only(monkeypatch, tmp_path):
    release = _release()
    monkeypatch.setattr(prez_service, "scan_nfo_folder", lambda folder: release.episodes)
    monkeypatch.setattr(prez_service, "build_release_nfo", lambda folder, episodes: release)
    monkeypatch.setattr(prez_service, "_generate_mediainfo_text", lambda release: "FULL MEDIAINFO")

    _report, result = PrezService().build(
        tmp_path,
        options=PrezBuildOptions(formats=(), mediainfo_mode="only"),
        write=True,
    )

    assert result.outputs[0].name.endswith(".mediainfo.txt")
    assert result.outputs[0].read_text(encoding="utf-8") == "FULL MEDIAINFO"


def _episode(
    code: str,
    *,
    duration_ms: int = 24 * 60_000,
    video_bitrate: int = 3_010_000,
    subtitles: list[TrackNfoData] | None = None,
) -> EpisodeNfoData:
    audio = _track(
        kind="audio",
        language="French",
        language_short="fr",
        codec="E-AC-3",
        channels="5.1",
    )
    return EpisodeNfoData(
        file_path=Path(f"show.{code}.mkv"),
        file_name=f"show.{code}.mkv",
        episode_code=code,
        episode_label=code,
        episode_title=f"Episode {code[-2:]}",
        container="MKV",
        size_bytes=1_000_000_000,
        duration_ms=duration_ms,
        overall_bitrate_kbps=None,
        resolution="1080p",
        aspect_ratio="1.778",
        aspect_ratio_display="1.778 (16/9)",
        video_codec="H.264",
        hdr_display=None,
        video_bitrate=video_bitrate,
        audio_summary=["fr · E-AC-3 · 5.1"],
        audio_tracks=[audio],
        subtitle_tracks=subtitles or [],
    )


def _season_release() -> ReleaseNfoData:
    fr_full = _track(
        kind="subtitle",
        language="French",
        language_short="fr",
        codec="S_TEXT/UTF8",
        channels=None,
        bitrate=None,
        subtitle_variant="Full",
        is_default=False,
    )
    en_full = _track(
        kind="subtitle",
        language="English",
        language_short="en",
        codec="S_TEXT/UTF8",
        channels=None,
        bitrate=None,
        subtitle_variant="Full",
        is_default=False,
    )
    en_sdh = _track(
        kind="subtitle",
        language="English",
        language_short="en",
        codec="S_TEXT/UTF8",
        channels=None,
        bitrate=None,
        subtitle_variant="SDH",
        is_default=False,
    )
    episodes = [
        _episode(
            "S04E01",
            duration_ms=22 * 60_000,
            video_bitrate=2_000_000,
            subtitles=[fr_full, en_full],
        ),
        _episode(
            "S04E02",
            duration_ms=24 * 60_000,
            video_bitrate=4_000_000,
            subtitles=[fr_full, en_full],
        ),
        _episode(
            "S04E09",
            duration_ms=26 * 60_000,
            video_bitrate=6_000_000,
            subtitles=[fr_full, en_full, en_sdh],
        ),
    ]
    return ReleaseNfoData(
        media_kind="season_pack",
        release_title="The.Simpsons.S04.1080p.WEB-DL",
        title_display="The Simpsons",
        series_title="The Simpsons",
        year="1992",
        source="WEB-DL",
        resolution="1080p",
        video_tag="H.264",
        audio_tag="E-AC-3",
        language_tag="MULTI",
        audio_languages_display="French",
        total_size_bytes=3_000_000_000,
        total_duration_ms=72 * 60_000,
        episodes=episodes,
    )


def _season_metadata_context() -> dict:
    episode = EpisodeMetadata(
        provider_name="tmdb",
        provider_id="4009",
        imdb_id=None,
        external_url="https://www.themoviedb.org/tv/456/season/4/episode/9",
        series_title="The Simpsons",
        series_year="1989",
        season_number=4,
        episode_number=9,
        episode_title="Itchy & Scratchy: The Movie",
        overview="A TV family season.",
        air_date="1992-11-03",
        runtime_minutes=24,
        series_provider_id="456",
        series_url="https://www.themoviedb.org/tv/456",
        episode_url="https://www.themoviedb.org/tv/456/season/4/episode/9",
    )
    season = SeasonMetadata(
        provider_name="tmdb",
        provider_id="456",
        imdb_id=None,
        external_url="https://www.themoviedb.org/tv/456",
        series_title="The Simpsons",
        series_year="1989",
        season_number=4,
        overview="A TV family season.",
        air_date="1992-09-24",
        first_air_date="1989-12-17",
        poster_url="https://image.example/season4.jpg",
        series_provider_id="456",
        series_url="https://www.themoviedb.org/tv/456",
        season_url="https://www.themoviedb.org/tv/456/season/4",
        episode_summaries=[episode],
    )
    return {
        "metadata_movie": None,
        "metadata_episode": None,
        "metadata_season": season,
        "metadata_episode_map": {},
        "metadata_season_episode_codes": ("S04E01", "S04E02", "S04E09"),
        "metadata_season_episode_count": 3,
    }


def test_render_bbcode_deduplicates_season_subtitles_and_uses_average_runtime():
    bbcode = render_bbcode(
        _season_release(),
        metadata_context=_season_metadata_context(),
        locale="fr",
        template_name="tracker",
    )

    assert "[h1]The Simpsons (1989)[/h1]" in bbcode
    assert "[h2]S04 (Saison complète)[/h2]" in bbcode
    assert "[h3]S04E01-S04E09[/h3]" in bbcode
    assert (
        bbcode.index("[h1]The Simpsons (1989)[/h1]")
        < bbcode.index("[h2]S04 (Saison complète)[/h2]")
        < bbcode.index("[h3]S04E01-S04E09[/h3]")
        < bbcode.index("[center][img]https://image.example/season4.jpg[/img][/center]")
    )
    assert "S04E01-S04E09 (Saison complète)" in bbcode
    assert "4.00 Mb/s" in bbcode
    assert "3.01 Mb/s" not in bbcode
    assert "Durée moyenne par épisode" in bbcode
    assert "24 min" in bbcode
    assert "Durée par épisode" not in bbcode
    assert "[/img][/center]\n[hr]" not in bbcode
    assert "[hr]\n\n[hr]" not in bbcode
    assert bbcode.count("French[/td][td]Full") == 1
    assert bbcode.count("English[/td][td]Full") == 1
    assert bbcode.count("English (E09)[/td][td]SDH") == 1
    assert "Lien vers la fiche TMDb de la série" in bbcode
    assert "https://www.themoviedb.org/tv/456" in bbcode
    assert "IMDb" not in bbcode


def test_render_bbcode_does_not_mark_incomplete_tmdb_season_complete():
    context = _season_metadata_context()
    context["metadata_season_episode_codes"] = (
        "S04E01",
        "S04E02",
        "S04E03",
        "S04E09",
    )

    bbcode = render_bbcode(
        _season_release(),
        metadata_context=context,
        locale="fr",
        template_name="tracker",
    )

    assert "Saison complète" not in bbcode
    assert "[h2]S04[/h2]" in bbcode


def test_render_html_marks_complete_season_and_uses_timeline_template():
    html = render_html(
        _season_release(),
        metadata_context=_season_metadata_context(),
        locale="fr",
        template_name="timeline",
    )

    assert "The Simpsons (1989)" in html
    assert "S04 (Saison complète)" in html
    assert "S04E01-S04E09" in html
    assert "S04E01-S04E09 (Saison complète)" in html
    assert "4.00 Mb/s" in html
    assert "3.01 Mb/s" not in html
    assert "timeline" in html


def test_render_bbcode_uses_series_then_episode_title_for_single_episode():
    release = _season_release()
    release.media_kind = "single_episode"
    release.release_title = "The.Simpsons.S04E09.1080p.WEB-DL"
    release.episodes = [release.episodes[-1]]
    metadata = _season_metadata_context()["metadata_season"].episode_summaries[0]
    context = {
        "metadata_movie": None,
        "metadata_episode": metadata,
        "metadata_season": None,
        "metadata_episode_map": {},
    }

    bbcode = render_bbcode(release, metadata_context=context, template_name="tracker")

    assert "[h1]The Simpsons[/h1]" in bbcode
    assert "[h2]Itchy & Scratchy: The Movie[/h2]" in bbcode
    assert "S04E09" in bbcode
    assert "Link to the series TMDb page" in bbcode
    assert "Link to the episode TMDb page" in bbcode
    assert "https://www.themoviedb.org/tv/456/season/4/episode/9" in bbcode


def test_render_bbcode_formats_release_date_in_locale():
    bbcode = render_bbcode(_release(), metadata_context=_metadata_context(), locale="fr")
    assert "2 janvier 2024" in bbcode
