from __future__ import annotations

import re
from pathlib import Path

from framekit.core.mediainfo import probe_media_file
from framekit.core.models.media import MediaFileInfo

MediaInfoSource = Path | MediaFileInfo


def _info(source: MediaInfoSource) -> MediaFileInfo:
    if isinstance(source, MediaFileInfo):
        return source
    return probe_media_file(source)


def get_preferred_video_tag(source: MediaInfoSource) -> str:
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
    info = _info(source)

    if not info.audio_tracks:
        return ""

    track = info.audio_tracks[0]
    fmt = (track.codec or "").upper()
    channels = track.channels or ""

    if fmt in {"E-AC-3", "EAC3"}:
        return f"EAC3.{channels}" if channels else "EAC3"
    if fmt in {"AC-3", "AC3"}:
        return f"AC3.{channels}" if channels else "AC3"
    if fmt == "AAC":
        return f"AAC.{channels}" if channels else "AAC"

    return f"{fmt}.{channels}" if fmt and channels else fmt


def get_preferred_resolution(source: MediaInfoSource) -> str:
    info = _info(source)

    if not info.height:
        return ""

    height = info.height
    if height >= 2160:
        return "2160P"
    if height >= 1440:
        return "1440P"
    if height >= 1080:
        return "1080P"
    if height >= 720:
        return "720P"
    if height >= 480:
        return "480P"
    return f"{height}P"


def get_hdr_canonical(source: MediaInfoSource) -> str:
    info = _info(source)
    hdr = " ".join(
        str(value or "")
        for value in (
            info.hdr_format,
            getattr(info, "video_profile", None),
            getattr(info, "video_format_name", None),
        )
    ).upper()

    if not hdr:
        return ""

    compact = hdr.replace(" ", "").replace("_", "").replace("-", "")
    if "DOLBYVISION" in compact or "DVHE" in compact:
        return "dolby_vision"
    if "HDR10+" in hdr or "HDR10PLUS" in compact or "ST2094" in compact or "SMPTEST2094" in compact:
        return "hdr10plus"
    if "HLG" in compact or "ARIBSTDB67" in compact:
        return "hlg"
    if "HDR10" in compact or "SMPTEST2084" in compact or "BT2020" in compact or "PQ" in compact:
        return "hdr10"

    return ""


def hdr_release_label(value: str) -> str:
    mapping = {
        "dolby_vision": "DV",
        "hdr10plus": "HDR10Plus",
        "hdr10": "HDR10",
        "hlg": "HLG",
    }
    return mapping.get(value, "")


def hdr_display_label(value: str) -> str:
    mapping = {
        "dolby_vision": "Dolby Vision",
        "hdr10plus": "HDR10+",
        "hdr10": "HDR10",
        "hlg": "HLG",
    }
    return mapping.get(value, "")


def infer_source_from_name(name: str) -> str:
    upper = name.upper()

    if "WEBRIP" in upper:
        return "WEBRip"
    if "WEB-DL" in upper or re.search(r"(?<![A-Z])WEB(?![A-Z])", upper):
        return "WEB"
    if "BLURAY" in upper or "BDRIP" in upper or "REMUX" in upper:
        return "BLURAY"

    return ""
