from pathlib import Path

from framekit.core.models.media import MediaFileInfo
from framekit.modules.renamer.detector import get_hdr_canonical, hdr_display_label


def _media_info(hdr_format: str) -> MediaFileInfo:
    return MediaFileInfo(
        path=Path("movie.mkv"),
        container="MKV",
        duration_ms=1,
        size_bytes=1,
        overall_bitrate=None,
        width=3840,
        height=2160,
        aspect_ratio=None,
        video_codec="H265",
        video_profile="Main 10",
        video_encoding_settings=None,
        video_library_name=None,
        video_format_name="HEVC",
        video_codec_id=None,
        video_bitrate=None,
        video_frame_rate=None,
        video_bit_depth=10,
        video_stream_size_bytes=None,
        video_stream_size_ratio=None,
        hdr_format=hdr_format,
    )


def test_hdr10plus_detected_from_st2094_metadata():
    assert get_hdr_canonical(_media_info("SMPTE ST 2094 App 4")) == "hdr10plus"
    assert hdr_display_label("hdr10plus") == "HDR10+"


def test_hdr10_detected_from_bt2020_pq_metadata():
    assert get_hdr_canonical(_media_info("BT.2020 / PQ")) == "hdr10"
