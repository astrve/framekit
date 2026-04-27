from pathlib import Path

from framekit.core.languages import (
    language_filter_short_label,
    match_language_filter,
    normalize_language,
)
from framekit.core.models.cleanmkv import CleanPreset, MkvFileScan, TrackInfo
from framekit.modules.cleanmkv.planner import build_remux_plan, get_builtin_preset
from framekit.modules.cleanmkv.presets import (
    load_preset_file,
    preset_from_dict,
    save_preset_file,
    validate_preset,
)


def test_get_builtin_preset_anime():
    preset = get_builtin_preset("anime")
    assert preset.name == "anime"
    assert "french" in preset.keep_audio_filters


def test_build_remux_plan_filters_tracks():
    scan = MkvFileScan(
        path=Path("test.mkv"),
        audio_tracks=[
            TrackInfo(
                track_id=0,
                kind="audio",
                codec="AAC",
                language="french",
                language_variant=None,
                subtitle_variant=None,
                title=None,
                is_default=True,
                is_forced=False,
            ),
            TrackInfo(
                track_id=1,
                kind="audio",
                codec="AAC",
                language="japanese",
                language_variant=None,
                subtitle_variant=None,
                title=None,
                is_default=False,
                is_forced=False,
            ),
            TrackInfo(
                track_id=2,
                kind="audio",
                codec="AAC",
                language="spanish",
                language_variant="latam",
                subtitle_variant=None,
                title=None,
                is_default=False,
                is_forced=False,
            ),
        ],
        subtitle_tracks=[
            TrackInfo(
                track_id=3,
                kind="subtitle",
                codec="SRT",
                language="french",
                language_variant=None,
                subtitle_variant="full",
                title=None,
                is_default=False,
                is_forced=False,
            ),
            TrackInfo(
                track_id=4,
                kind="subtitle",
                codec="SRT",
                language="english",
                language_variant="uk",
                subtitle_variant="sdh",
                title=None,
                is_default=False,
                is_forced=False,
            ),
            TrackInfo(
                track_id=5,
                kind="subtitle",
                codec="SRT",
                language="spanish",
                language_variant="latam",
                subtitle_variant="full",
                title=None,
                is_default=False,
                is_forced=False,
            ),
        ],
    )

    preset = get_builtin_preset("anime")
    plan = build_remux_plan(scan, preset=preset, output_dir_name="clean")

    assert plan.keep_audio_track_ids == [0, 1]
    assert plan.keep_subtitle_track_ids == [3, 4]
    assert plan.default_audio_track_id == 0


def test_build_remux_plan_selects_vostfr_defaults():
    scan = MkvFileScan(
        path=Path("test.mkv"),
        audio_tracks=[
            TrackInfo(
                track_id=0,
                kind="audio",
                codec="AAC",
                language="japanese",
                language_variant=None,
                subtitle_variant=None,
                title=None,
                is_default=False,
                is_forced=False,
            ),
            TrackInfo(
                track_id=1,
                kind="audio",
                codec="AAC",
                language="english",
                language_variant="us",
                subtitle_variant=None,
                title=None,
                is_default=True,
                is_forced=False,
            ),
        ],
        subtitle_tracks=[
            TrackInfo(
                track_id=3,
                kind="subtitle",
                codec="SRT",
                language="french",
                language_variant=None,
                subtitle_variant="full",
                title=None,
                is_default=False,
                is_forced=False,
            ),
            TrackInfo(
                track_id=4,
                kind="subtitle",
                codec="SRT",
                language="french",
                language_variant="canada",
                subtitle_variant="forced",
                title=None,
                is_default=False,
                is_forced=False,
            ),
        ],
    )

    preset = get_builtin_preset("vostfr")
    plan = build_remux_plan(scan, preset=preset, output_dir_name="clean")

    assert plan.keep_audio_track_ids == [0]
    assert plan.default_audio_track_id == 0
    assert plan.default_subtitle_track_id == 3


def test_build_remux_plan_copy_only_when_nothing_changes():
    scan = MkvFileScan(
        path=Path("test.mkv"),
        audio_tracks=[
            TrackInfo(
                track_id=0,
                kind="audio",
                codec="AAC",
                language="french",
                language_variant=None,
                subtitle_variant=None,
                title=None,
                is_default=True,
                is_forced=False,
            ),
            TrackInfo(
                track_id=1,
                kind="audio",
                codec="AAC",
                language="english",
                language_variant=None,
                subtitle_variant=None,
                title=None,
                is_default=False,
                is_forced=False,
            ),
            TrackInfo(
                track_id=2,
                kind="audio",
                codec="AAC",
                language="japanese",
                language_variant=None,
                subtitle_variant=None,
                title=None,
                is_default=False,
                is_forced=False,
            ),
        ],
        subtitle_tracks=[
            TrackInfo(
                track_id=3,
                kind="subtitle",
                codec="SRT",
                language="french",
                language_variant=None,
                subtitle_variant="full",
                title=None,
                is_default=False,
                is_forced=False,
            ),
            TrackInfo(
                track_id=4,
                kind="subtitle",
                codec="SRT",
                language="english",
                language_variant=None,
                subtitle_variant="sdh",
                title=None,
                is_default=False,
                is_forced=False,
            ),
        ],
    )

    preset = CleanPreset(
        name="copy_case",
        keep_audio_filters=("french", "english", "japanese"),
        default_audio_filter="french",
        keep_subtitle_filters=("french", "english"),
        keep_subtitle_variants=("full", "sdh"),
        default_subtitle_filter=None,
        default_subtitle_variant=None,
    )

    plan = build_remux_plan(scan, preset=preset, output_dir_name="clean")
    assert plan.copy_only is True


def test_language_filter_short_labels_for_variants():
    assert language_filter_short_label("french:canada") == "fr-CA"
    assert language_filter_short_label("english:us") == "en-US"
    assert language_filter_short_label("english:uk") == "en-GB"
    assert language_filter_short_label("spanish:latam") == "es-419"


def test_match_language_filter_with_variants():
    assert match_language_filter("french", "canada", "french:canada") is True
    assert match_language_filter("english", "us", "english:us") is True
    assert match_language_filter("english", "uk", "english:uk") is True
    assert match_language_filter("spanish", "latam", "spanish:latam") is True
    assert match_language_filter("english", "uk", "english:us") is False


def test_preset_from_dict_and_validate():
    preset = preset_from_dict(
        {
            "name": "custom",
            "keep_audio_filters": ["french:canada", "english:uk"],
            "default_audio_filter": "french:canada",
            "keep_subtitle_filters": ["french", "english:uk"],
            "keep_subtitle_variants": ["forced", "full"],
            "default_subtitle_filter": "french",
            "default_subtitle_variant": "full",
        }
    )

    assert validate_preset(preset).name == "custom"
    assert preset.keep_audio_filters == ("french:canada", "english:uk")


def test_save_and_load_preset_file(tmp_path: Path):
    preset = preset_from_dict(
        {
            "name": "my_preset",
            "keep_audio_filters": ["english:us"],
            "default_audio_filter": "english:us",
            "keep_subtitle_filters": ["french", "spanish:latam"],
            "keep_subtitle_variants": ["full"],
            "default_subtitle_filter": "french",
            "default_subtitle_variant": "full",
        }
    )

    path = tmp_path / "my_preset.json"
    save_preset_file(preset, path)

    loaded = load_preset_file(path)
    assert loaded.name == "my_preset"
    assert loaded.keep_audio_filters == ("english:us",)
    assert loaded.keep_subtitle_filters == ("french", "spanish:latam")


def test_invalid_preset_rejected():
    try:
        preset_from_dict(
            {
                "name": "bad",
                "keep_audio_filters": ["english:moon"],
                "default_audio_filter": "english:moon",
                "keep_subtitle_filters": ["french"],
                "keep_subtitle_variants": ["full"],
                "default_subtitle_filter": None,
                "default_subtitle_variant": None,
            }
        )
    except ValueError as exc:
        assert "Invalid audio filter" in str(exc)
    else:
        raise AssertionError("Expected invalid preset to raise ValueError")


def test_normalize_language_variants():
    assert normalize_language("fr-CA") == ("french", "canada")
    assert normalize_language("en-US") == ("english", "us")
    assert normalize_language("en-GB") == ("english", "uk")
    assert normalize_language("es-419") == ("spanish", "latam")


def test_build_remux_plan_not_copy_only_when_default_flags_need_cleanup():
    scan = MkvFileScan(
        path=Path("test.mkv"),
        audio_tracks=[
            TrackInfo(
                track_id=0,
                kind="audio",
                codec="AAC",
                language="french",
                language_variant=None,
                subtitle_variant=None,
                title=None,
                is_default=True,
                is_forced=False,
            ),
            TrackInfo(
                track_id=1,
                kind="audio",
                codec="AAC",
                language="english",
                language_variant=None,
                subtitle_variant=None,
                title=None,
                is_default=True,
                is_forced=False,
            ),
        ],
        subtitle_tracks=[],
    )

    preset = CleanPreset(
        name="flag_cleanup",
        keep_audio_filters=("french", "english"),
        default_audio_filter="french",
        keep_subtitle_filters=(),
        keep_subtitle_variants=(),
        default_subtitle_filter=None,
        default_subtitle_variant=None,
    )

    plan = build_remux_plan(scan, preset=preset, output_dir_name="clean")
    assert plan.keep_audio_track_ids == [0, 1]
    assert plan.default_audio_track_id == 0
    assert plan.copy_only is False
