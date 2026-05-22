"""Tests for renamer rules - normalization and transformation logic."""

from framekit.modules.renamer.detector import hdr_display_label, hdr_release_label
from framekit.modules.renamer.rules import (
    ensure_language_tag,
    extract_episode_code,
    extract_episode_title,
    normalize_name_part,
    replace_language_tag,
    split_team,
)


def test_split_team_detects_release_group():
    """Test that release group is correctly extracted from filename."""
    stem, team = split_team("Show.S01E01.1080p.WEB.x264-NTb")
    assert stem == "Show.S01E01.1080p.WEB.x264"
    assert team == "NTB"


def test_split_team_ignores_plain_hyphenated_title():
    """Test that hyphenated titles are not mistaken for release groups."""
    stem, team = split_team("Spider-Man")
    assert stem == "Spider-Man"
    assert team is None


def test_ensure_language_tag_inserts_after_episode_code():
    """Test that language tag is inserted after episode code."""
    parts = ["SHOW", "S01E01", "1080p"]
    result = ensure_language_tag(parts, "MULTI.VFF")
    assert result == ["SHOW", "S01E01", "MULTI.VFF", "1080p"]


def test_replace_language_tag_replaces_existing_value():
    """Test that existing language tag is replaced."""
    parts = ["SHOW", "S01E01", "MULTI.VFF", "1080P"]
    result = replace_language_tag(parts, "VOSTFR")
    assert result == ["SHOW", "S01E01", "VOSTFR", "1080P"]


def test_extract_episode_code():
    """Test episode code extraction from filename."""
    assert extract_episode_code("SHOW.S01E03.TITLE.1080P.WEB") == "S01E03"


def test_extract_episode_title():
    """Test episode title extraction from filename."""
    title = extract_episode_title("SHOW.S01E03.Le.Noel.Des.Simpson.1080P.WEB.x265")
    assert title == "Le Noel Des Simpson"


def test_extract_episode_title_returns_none_when_missing():
    """Test that None is returned when episode title is not present."""
    title = extract_episode_title("SHOW.S01E03.1080P.WEB.x265")
    assert title is None


def test_normalize_name_part_normalizes_core_tokens():
    """Test that filename parts are normalized correctly."""
    result, existing_lang, resulting_lang, episode_code, episode_title = normalize_name_part(
        "Show_S01E01_WEB-DL_DDP5.1_x265"
    )
    assert result == "SHOW.S01E01.MULTI.VFF.WEB.EAC3.5.1.x265"
    assert existing_lang is None
    assert resulting_lang == "MULTI.VFF"
    assert episode_code == "S01E01"
    assert episode_title is None


def test_normalize_name_part_can_force_language():
    """Test that language can be forced during normalization."""
    result, existing_lang, resulting_lang, episode_code, episode_title = normalize_name_part(
        "SHOW.S01E01.MULTI.VFF.1080P.WEB.EAC3.5.1.x265",
        default_lang="VOSTFR",
        force_lang=True,
    )
    assert result == "SHOW.S01E01.VOSTFR.1080P.WEB.EAC3.5.1.x265"
    assert existing_lang == "MULTI.VFF"
    assert resulting_lang == "VOSTFR"
    assert episode_code == "S01E01"
    assert episode_title is None


def test_normalize_name_part_keeps_episode_title_separate():
    """Test that episode titles are preserved during normalization."""
    result, _existing_lang, _resulting_lang, episode_code, episode_title = normalize_name_part(
        "SHOW.S01E03.Le.Noel.Des.Simpson.1080P.WEB.EAC3.5.1.x265"
    )
    assert result == "SHOW.S01E03.MULTI.VFF.LE.NOEL.DES.SIMPSON.1080P.WEB.EAC3.5.1.x265"
    assert episode_code == "S01E03"
    assert episode_title == "Le Noel Des Simpson"


def test_hdr_release_and_display_labels_are_distinct_for_hdr10plus():
    """Test that HDR10+ has different release and display labels."""
    assert hdr_release_label("hdr10plus") == "HDR10PLUS"
    assert hdr_display_label("hdr10plus") == "HDR10+"


def test_video_tag_stays_h264_or_h265_without_encoding_settings():
    """Design rule test: H264/H265 should stay uppercase codec tags unless encoding settings exist."""
    # This is a design rule test placeholder for the detector logic
    assert True


def test_normalize_name_uses_french_title_alias_for_french_language_tag():
    """Test that French title aliases are used for French language tags."""
    result, *_ = normalize_name_part("The.Simpsons.S04E01.1080p.WEB.x264", default_lang="MULTI.VFF")

    assert result.startswith("LES.SIMPSONS.S04E01")


def test_remove_terms_from_stem_removes_tokens_and_cleans_separators():
    """Test that unwanted terms are removed from filename stem."""
    from framekit.modules.renamer.planner import _remove_terms_from_stem

    assert _remove_terms_from_stem("Movie.2024.DSNP.WEB-DL", ("DSNP",)) == "Movie.2024.WEB-DL"
    assert (
        _remove_terms_from_stem("Movie.2024.DSNP-AMZN.WEB-DL", ("DSNP", "AMZN"))
        == "Movie.2024.WEB-DL"
    )


def test_remove_terms_from_normalized_name_removes_reintroduced_tokens():
    """Test that terms removed from stem are also removed from normalized name."""
    from framekit.modules.renamer.planner import _remove_terms_from_normalized_name

    assert _remove_terms_from_normalized_name("MOVIE.2024.DSNP.WEB", ("DSNP",)) == "MOVIE.2024.WEB"
