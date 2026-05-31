from __future__ import annotations

import re
from pathlib import Path

from swirrl.core.mediainfo import probe_media_file
from swirrl.core.models.media import MediaFileInfo

MediaInfoSource = Path | MediaFileInfo
_EAC3_FORMATS = {"E-AC-3", "EAC3"}
_AC3_FORMATS = {"AC-3", "AC3"}
_HDR_DV_MARKERS = ("DOLBYVISION", "DVHE")
_HDR10PLUS_MARKERS = ("HDR10PLUS", "HDR10P", "ST2094", "SMPTEST2094")
_HDR_HLG_MARKERS = ("HLG", "ARIBSTDB67")
_HDR10_MARKERS = ("HDR10", "SMPTEST2084", "BT2020", "PQ")
_HDR10PLUS_TEXT_MARKERS = ("HDR10+",)


def _info(source: MediaInfoSource) -> MediaFileInfo:
    if isinstance(source, MediaFileInfo):
        return source
    return probe_media_file(source)


def _has_any_marker(value: str, markers: tuple[str, ...]) -> bool:
    return any(marker in value for marker in markers)


def _hdr_parts(info: MediaFileInfo) -> tuple[str, str]:
    hdr = " ".join(
        str(value or "")
        for value in (
            info.hdr_format,
            getattr(info, "video_profile", None),
            getattr(info, "video_format_name", None),
        )
    ).upper()
    compact = hdr.replace(" ", "").replace("_", "").replace("-", "")
    return hdr, compact


def _detect_hdr10plus(hdr_text: str, compact: str) -> bool:
    return _has_any_marker(hdr_text, _HDR10PLUS_TEXT_MARKERS) or _has_any_marker(
        compact, _HDR10PLUS_MARKERS
    )


def _detect_hdr10(compact: str) -> bool:
    return _has_any_marker(compact, _HDR10_MARKERS)


def _format_audio_tag(codec: str, channels: str) -> str:
    if codec in _EAC3_FORMATS:
        return f"EAC3.{channels}" if channels else "EAC3"
    if codec in _AC3_FORMATS:
        return f"AC3.{channels}" if channels else "AC3"
    if codec == "AAC":
        return f"AAC.{channels}" if channels else "AAC"
    return f"{codec}.{channels}" if codec and channels else codec


def get_preferred_video_tag(source: MediaInfoSource) -> str:
    """Return the preferred video tag."""
    info = _info(source)

    if not info.video_codec:
        return ""

    codec = info.video_codec
    has_encoding_settings = bool(info.video_encoding_settings)

    if codec == "H264":
        return "x264" if has_encoding_settings else "H264"

    if codec == "H265":
        return "x265" if has_encoding_settings else "H265"

    return codec


def get_preferred_audio_tag(source: MediaInfoSource) -> str:
    """Return the preferred audio tag."""
    info = _info(source)

    if not info.audio_tracks:
        return ""

    track = info.audio_tracks[0]
    fmt = (track.codec or "").upper()
    channels = track.channels or ""
    return _format_audio_tag(fmt, channels)


def get_preferred_resolution(source: MediaInfoSource) -> str:
    """Return the preferred resolution."""
    info = _info(source)

    if not info.height:
        return ""

    height = info.height
    if height >= 2160:
        return "2160P"
    if height >= 1080:
        return "1080P"
    if height >= 720:
        return "720P"
    return "480P"


def get_hdr_canonical(source: MediaInfoSource) -> str:
    """Detect the primary HDR format from media info.

    Returns a single canonical HDR format identifier.
    For multiple HDR formats, use get_all_hdr_formats().
    """
    info = _info(source)
    hdr, compact = _hdr_parts(info)
    if not hdr:
        return ""
    if _has_any_marker(compact, _HDR_DV_MARKERS):
        return "dolby_vision"
    if _detect_hdr10plus(hdr, compact):
        return "hdr10plus"
    if _has_any_marker(compact, _HDR_HLG_MARKERS):
        return "hlg"
    if _detect_hdr10(compact):
        return "hdr10"
    return ""


def get_all_hdr_formats(source: MediaInfoSource) -> list[str]:
    """Detect all HDR formats present in the media.

    Returns a list of canonical HDR format identifiers.
    Useful for files with multiple HDR formats (e.g., Dolby Vision + HDR10).
    """
    info = _info(source)
    hdr, compact = _hdr_parts(info)
    if not hdr:
        return []
    formats: list[str] = []
    if _has_any_marker(compact, _HDR_DV_MARKERS):
        formats.append("dolby_vision")
    if _detect_hdr10plus(hdr, compact):
        formats.append("hdr10plus")
    elif _detect_hdr10(compact):
        formats.append("hdr10")
    if _has_any_marker(compact, _HDR_HLG_MARKERS):
        formats.append("hlg")
    return formats


def hdr_release_label(value: str) -> str:
    """Handle hdr release label."""
    mapping = {
        "dolby_vision": "DV",
        "hdr10plus": "HDR10PLUS",
        "hdr10": "HDR10",
        "hlg": "HLG",
    }
    return mapping.get(value, "")


def hdr_display_label(value: str) -> str:
    """Handle hdr display label."""
    mapping = {
        "dolby_vision": "Dolby Vision",
        "hdr10plus": "HDR10+",
        "hdr10": "HDR10",
        "hlg": "HLG",
    }
    return mapping.get(value, "")


def hdr_display_label_all(source: MediaInfoSource) -> str:
    """Get a display label for all HDR formats present in the media.

    Returns formats separated by " + " (e.g., "Dolby Vision + HDR10+").
    """
    formats = get_all_hdr_formats(source)
    if not formats:
        return ""
    labels = [hdr_display_label(fmt) for fmt in formats]
    return " + ".join(label for label in labels if label)


def infer_source_from_name(name: str) -> str:
    """Handle infer source from name."""
    upper = name.upper()

    if "WEBRIP" in upper:
        return "WEBRip"
    if "WEB-DL" in upper or re.search(r"(?<![A-Z])WEB(?![A-Z])", upper):
        return "WEB"
    if "BLURAY" in upper or "BDRIP" in upper or "REMUX" in upper:
        return "BLURAY"

    return ""
