from __future__ import annotations

from pathlib import Path

from framekit.core.models.cleanmkv import CleanPreset, MkvFileScan, TrackInfo
from framekit.modules.cleanmkv.planner import build_remux_plan
from framekit.modules.cleanmkv.tracks import track_reference_key, track_reference_label


def _audio(
    track_id: int,
    *,
    codec: str,
    channels: str,
    bitrate: int,
    default: bool = False,
) -> TrackInfo:
    return TrackInfo(
        track_id=track_id,
        kind="audio",
        codec=codec,
        language="french",
        language_variant=None,
        subtitle_variant=None,
        title=None,
        is_default=default,
        is_forced=False,
        channels=channels,
        bitrate=bitrate,
    )


def test_track_reference_label_includes_codec_channels_and_bitrate():
    track = _audio(1, codec="E-AC-3", channels="5.1", bitrate=768_000)

    label = track_reference_label(track)

    assert "fr" in label
    assert "E-AC-3" in label
    assert "5.1" in label
    assert "768 kb/s" in label


def test_selector_style_preset_uses_track_refs_without_language_filters():
    eac3 = _audio(1, codec="E-AC-3", channels="5.1", bitrate=768_000, default=True)
    aac = _audio(2, codec="AAC", channels="2.0", bitrate=128_000)
    scan = MkvFileScan(path=Path("movie.mkv"), audio_tracks=[eac3, aac], subtitle_tracks=[])

    preset = CleanPreset(
        name="selector",
        keep_audio_filters=(),
        default_audio_filter=None,
        keep_subtitle_filters=(),
        keep_subtitle_variants=(),
        default_subtitle_filter=None,
        default_subtitle_variant=None,
        keep_audio_track_refs=(track_reference_key(eac3), track_reference_key(aac)),
        default_audio_track_ref=track_reference_key(eac3),
    )

    plan = build_remux_plan(scan, preset=preset, output_dir_name="clean")

    assert plan.keep_audio_track_ids == [1, 2]
    assert plan.default_audio_track_id == 1


def test_track_refs_keep_similar_same_language_tracks_distinct():
    eac3 = _audio(1, codec="E-AC-3", channels="5.1", bitrate=768_000)
    aac = _audio(2, codec="AAC", channels="2.0", bitrate=128_000)
    scan = MkvFileScan(path=Path("movie.mkv"), audio_tracks=[eac3, aac], subtitle_tracks=[])

    preset = CleanPreset(
        name="selector",
        keep_audio_filters=(),
        default_audio_filter=None,
        keep_subtitle_filters=(),
        keep_subtitle_variants=(),
        default_subtitle_filter=None,
        default_subtitle_variant=None,
        keep_audio_track_refs=(track_reference_key(aac),),
        default_audio_track_ref=track_reference_key(aac),
    )

    plan = build_remux_plan(scan, preset=preset, output_dir_name="clean")

    assert plan.keep_audio_track_ids == [2]
    assert plan.default_audio_track_id == 2
