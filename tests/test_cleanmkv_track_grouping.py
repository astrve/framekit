"""Tests for cleanmkv track grouping logic."""

from __future__ import annotations

from pathlib import Path

from swirrl.core.models.cleanmkv import MkvFileScan, TrackInfo
from swirrl.modules.cleanmkv.tracks import (
    track_display_grouping_key,
    track_grouped_label,
    track_reference_key,
)
from swirrl.modules.cleanmkv.wizard import _expand_grouped_refs, _track_display_groups


def _audio(
    track_id: int,
    *,
    codec: str,
    language: str = "french",
    channels: str = "5.1",
    bitrate: int = 768_000,
    subtitle_variant: str | None = None,
    title: str | None = None,
) -> TrackInfo:
    """Create a mock audio TrackInfo for testing."""
    return TrackInfo(
        track_id=track_id,
        kind="audio",
        codec=codec,
        language=language,
        language_variant=None,
        subtitle_variant=subtitle_variant,
        title=title,
        is_default=False,
        is_forced=False,
        channels=channels,
        bitrate=bitrate,
    )


def test_display_grouping_key_groups_same_language_different_codecs():
    """Audio tracks with same language but different codecs should have the same display grouping key."""
    aac = _audio(1, codec="AAC", language="french")
    ac3 = _audio(2, codec="AC3", language="french")
    dts = _audio(3, codec="DTS", language="french")

    aac_key = track_display_grouping_key(aac)
    ac3_key = track_display_grouping_key(ac3)
    dts_key = track_display_grouping_key(dts)

    # All should have the same display grouping key (language+channels, not codec)
    assert aac_key == ac3_key == dts_key


def test_display_grouping_key_separates_different_languages():
    """Audio tracks with different languages should have different display grouping keys."""
    french = _audio(1, codec="AAC", language="french")
    english = _audio(2, codec="AAC", language="english")

    french_key = track_display_grouping_key(french)
    english_key = track_display_grouping_key(english)

    assert french_key != english_key


def test_display_grouping_key_separates_ad_from_normal():
    """Audio description tracks should be separate from normal tracks."""
    normal = _audio(1, codec="AAC", language="french", subtitle_variant=None)
    ad = _audio(2, codec="AAC", language="french", subtitle_variant="ad")

    normal_key = track_display_grouping_key(normal)
    ad_key = track_display_grouping_key(ad)

    # AD tracks should have different grouping key than normal tracks
    assert normal_key != ad_key


def test_display_grouping_key_separates_different_channels():
    """Audio tracks with different channel layouts should be separate."""
    stereo = _audio(1, codec="AAC", language="french", channels="2.0")
    surround = _audio(2, codec="AAC", language="french", channels="5.1")

    stereo_key = track_display_grouping_key(stereo)
    surround_key = track_display_grouping_key(surround)

    assert stereo_key != surround_key


def test_reference_key_keeps_tracks_distinct():
    """Track reference keys should still distinguish between different codecs."""
    aac = _audio(1, codec="AAC", language="french")
    ac3 = _audio(2, codec="AC3", language="french")

    aac_ref = track_reference_key(aac)
    ac3_ref = track_reference_key(ac3)

    # Reference keys should be different (includes codec)
    assert aac_ref != ac3_ref


def test_grouped_label_shows_multiple_codecs():
    """Grouped label should show all codecs separated by slashes."""
    aac = _audio(1, codec="AAC", language="french", bitrate=128_000)
    ac3 = _audio(2, codec="AC3", language="french", bitrate=640_000)
    dts = _audio(3, codec="DTS", language="french", bitrate=1_536_000)

    label = track_grouped_label([aac, ac3, dts])

    # Should contain all codecs
    assert "AAC" in label
    assert "AC3" in label
    assert "DTS" in label
    # Should use slash separator
    assert "AAC/AC3/DTS" in label
    # Should contain language
    assert "fr" in label
    # Should contain channels
    assert "5.1" in label


def test_grouped_label_single_track():
    """Grouped label should work with a single track."""
    aac = _audio(1, codec="AAC", language="french")

    label = track_grouped_label([aac])

    assert "fr" in label
    assert "AAC" in label
    assert "5.1" in label


def test_expand_grouped_refs_with_single_refs():
    """Expand function should pass through single references unchanged."""
    refs = ("ref1", "ref2", "ref3")
    expanded = _expand_grouped_refs(refs)

    assert expanded == refs


def test_expand_grouped_refs_with_grouped_refs():
    """Expand function should split comma-separated grouped references."""
    refs = ("ref1,ref2,ref3", "ref4", "ref5,ref6")
    expanded = _expand_grouped_refs(refs)

    assert expanded == ("ref1", "ref2", "ref3", "ref4", "ref5", "ref6")


def test_expand_grouped_refs_empty():
    """Expand function should handle empty tuple."""
    refs = ()
    expanded = _expand_grouped_refs(refs)

    assert expanded == ()


def test_track_display_groups_groups_same_language_different_codecs():
    """Display groups should group tracks with same language but different codecs."""
    aac = _audio(1, codec="AAC", language="french")
    ac3 = _audio(2, codec="AC3", language="french")
    dts = _audio(3, codec="DTS", language="french")

    scan = MkvFileScan(
        path=Path("movie.mkv"),
        audio_tracks=[aac, ac3, dts],
        subtitle_tracks=[],
    )

    groups = _track_display_groups([scan], kind="audio")

    # Should have only one group (all same language)
    assert len(groups) == 1

    # The group should contain all three track references
    group_key = next(iter(groups.keys()))
    track_refs, tracks, _paths = groups[group_key]
    assert len(track_refs) == 3
    assert len(tracks) == 3


def test_track_display_groups_separates_ad_tracks():
    """Display groups should keep AD tracks separate from normal tracks."""
    normal_aac = _audio(1, codec="AAC", language="french", subtitle_variant=None)
    normal_ac3 = _audio(2, codec="AC3", language="french", subtitle_variant=None)
    ad_aac = _audio(3, codec="AAC", language="french", subtitle_variant="ad")
    ad_ac3 = _audio(4, codec="AC3", language="french", subtitle_variant="ad")

    scan = MkvFileScan(
        path=Path("movie.mkv"),
        audio_tracks=[normal_aac, normal_ac3, ad_aac, ad_ac3],
        subtitle_tracks=[],
    )

    groups = _track_display_groups([scan], kind="audio")

    # Should have two groups: one for normal, one for AD
    assert len(groups) == 2

    # Each group should have 2 tracks (AAC and AC3)
    for track_refs, tracks, _paths in groups.values():
        assert len(track_refs) == 2
        assert len(tracks) == 2


def test_track_display_groups_separates_different_languages():
    """Display groups should keep different languages separate."""
    french_aac = _audio(1, codec="AAC", language="french")
    french_ac3 = _audio(2, codec="AC3", language="french")
    english_aac = _audio(3, codec="AAC", language="english")
    english_ac3 = _audio(4, codec="AC3", language="english")

    scan = MkvFileScan(
        path=Path("movie.mkv"),
        audio_tracks=[french_aac, french_ac3, english_aac, english_ac3],
        subtitle_tracks=[],
    )

    groups = _track_display_groups([scan], kind="audio")

    # Should have two groups: one for French, one for English
    assert len(groups) == 2

    # Each group should have 2 tracks (AAC and AC3)
    for track_refs, tracks, _paths in groups.values():
        assert len(track_refs) == 2
        assert len(tracks) == 2


def test_track_display_groups_tracks_file_availability():
    """Display groups should track which files contain each group."""
    aac = _audio(1, codec="AAC", language="french")
    ac3 = _audio(2, codec="AC3", language="french")

    scan1 = MkvFileScan(
        path=Path("movie1.mkv"),
        audio_tracks=[aac, ac3],
        subtitle_tracks=[],
    )
    scan2 = MkvFileScan(
        path=Path("movie2.mkv"),
        audio_tracks=[aac],  # Only AAC in this file
        subtitle_tracks=[],
    )

    groups = _track_display_groups([scan1, scan2], kind="audio")

    # Should have one group (same language)
    assert len(groups) == 1

    group_key = next(iter(groups.keys()))
    _track_refs, _tracks, paths = groups[group_key]

    # Should track both files
    assert len(paths) == 2
    assert str(Path("movie1.mkv")) in paths
    assert str(Path("movie2.mkv")) in paths


def test_grouped_label_shows_file_count_for_multi_codec_groups():
    """Grouped label should show file count for multi-codec groups."""
    aac = _audio(1, codec="AAC", language="french")
    ac3 = _audio(2, codec="AC3", language="french")
    dts = _audio(3, codec="DTS", language="french")

    # Multiple codecs with file count info
    label = track_grouped_label([aac, ac3, dts], available_count=8, total_count=10)

    # Should contain all codecs
    assert "AAC/AC3/DTS" in label
    # Should contain file count
    assert "8/10" in label
    assert "available in" in label or "files" in label


def test_grouped_label_no_file_count_for_single_codec():
    """Grouped label should NOT show file count for single-codec groups."""
    aac = _audio(1, codec="AAC", language="french")

    # Single codec - should not show file count even if provided
    label = track_grouped_label([aac], available_count=8, total_count=10)

    # Should NOT contain file count
    assert "8/10" not in label
    assert "available in" not in label


def test_grouped_label_no_file_count_when_not_provided():
    """Grouped label should work without file count parameters."""
    aac = _audio(1, codec="AAC", language="french")
    ac3 = _audio(2, codec="AC3", language="french")

    # Multiple codecs but no file count provided
    label = track_grouped_label([aac, ac3])

    # Should contain codecs but no file count
    assert "AAC/AC3" in label
    assert "8/10" not in label
    assert "available in" not in label


def test_track_display_groups_with_partial_availability():
    """Display groups should correctly track partial file availability."""
    aac = _audio(1, codec="AAC", language="french")
    ac3 = _audio(2, codec="AC3", language="french")
    dts = _audio(3, codec="DTS", language="french")

    # File 1: has all three codecs
    scan1 = MkvFileScan(
        path=Path("movie1.mkv"),
        audio_tracks=[aac, ac3, dts],
        subtitle_tracks=[],
    )
    # File 2: has only AAC and AC3
    scan2 = MkvFileScan(
        path=Path("movie2.mkv"),
        audio_tracks=[aac, ac3],
        subtitle_tracks=[],
    )
    # File 3: has only AAC
    scan3 = MkvFileScan(
        path=Path("movie3.mkv"),
        audio_tracks=[aac],
        subtitle_tracks=[],
    )

    groups = _track_display_groups([scan1, scan2, scan3], kind="audio")

    # Should have one group (all same language)
    assert len(groups) == 1

    group_key = next(iter(groups.keys()))
    _track_refs, _tracks, paths = groups[group_key]

    # Should track all three files (union of files containing any track in the group)
    assert len(paths) == 3
    assert str(Path("movie1.mkv")) in paths
    assert str(Path("movie2.mkv")) in paths
    assert str(Path("movie3.mkv")) in paths


def test_grouped_label_file_count_format():
    """Grouped label should format file count correctly."""
    aac = _audio(1, codec="AAC", language="french", channels="5.1")
    ac3 = _audio(2, codec="AC3", language="french", channels="5.1")

    label = track_grouped_label([aac, ac3], available_count=5, total_count=10)

    # Should have proper format: "French · AAC/AC3 · 5.1 (available in 5/10 files)"
    assert "fr" in label or "French" in label.lower()
    assert "AAC/AC3" in label
    assert "5.1" in label
    assert "(available in 5/10 files)" in label or "(5/10" in label
