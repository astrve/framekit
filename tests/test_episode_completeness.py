from pathlib import Path

from framekit.core.models.nfo import EpisodeNfoData, ReleaseNfoData
from framekit.core.release_inspection import inspect_release_completeness


def _episode(code: str) -> EpisodeNfoData:
    return EpisodeNfoData(
        file_path=Path(f"/tmp/{code}.mkv"),
        file_name=f"{code}.mkv",
        episode_code=code,
        episode_label=None,
        episode_title=None,
        container="MKV",
        size_bytes=1,
        duration_ms=1,
        overall_bitrate_kbps=None,
        resolution="1080p",
        aspect_ratio=None,
        aspect_ratio_display=None,
        video_codec="H.264",
        hdr_display=None,
    )


def _release(*codes: str) -> ReleaseNfoData:
    return ReleaseNfoData(
        media_kind="season_pack",
        release_title="Example",
        title_display="Example",
        series_title="Example",
        year="2024",
        source="WEB",
        resolution="1080p",
        video_tag="H264",
        audio_tag="AAC",
        language_tag="MULTI",
        audio_languages_display="MULTI",
        team="TEAM",
        episodes=[_episode(code) for code in codes],
    )


def test_episode_completeness_detects_complete_range():
    result = inspect_release_completeness(_release("S01E01", "S01E02", "S01E03"))

    assert result.status == "complete"
    assert result.expected == 3
    assert result.missing_codes == ()


def test_episode_completeness_detects_missing_middle_episode():
    result = inspect_release_completeness(_release("S01E01", "S01E03"))

    assert result.status == "incomplete"
    assert result.missing_codes == ("S01E02",)
