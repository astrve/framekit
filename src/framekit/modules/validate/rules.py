"""Predefined validation rules for common tracker types."""

from __future__ import annotations

from .service import ValidationRules


def default_rules() -> ValidationRules:
    """Standard validation rules."""
    return ValidationRules()


def strict_rules() -> ValidationRules:
    """Strict rules for quality-focused trackers."""
    return ValidationRules(
        require_nfo=True,
        require_torrent=False,
        allowed_video_codecs=["HEVC", "AVC", "x264", "x265", "H.264", "H.265"],
        allowed_audio_codecs=["AC-3", "E-AC-3", "DTS", "DTS-HD", "FLAC", "TrueHD", "Opus", "AAC"],
        min_video_bitrate_kbps=1000,
        max_file_size_gb=100,
        require_language_tags=True,
        allowed_containers=[".mkv"],
        require_subs=False,
        min_resolution_width=1280,
    )


def anime_rules() -> ValidationRules:
    """Rules for anime trackers."""
    return ValidationRules(
        require_nfo=False,
        allowed_video_codecs=["HEVC", "AVC", "x264", "x265", "H.264", "H.265"],
        allowed_audio_codecs=["AAC", "FLAC", "Opus", "AC-3", "E-AC-3"],
        allowed_containers=[".mkv"],
        require_subs=True,
        min_resolution_width=720,
    )


def music_video_rules() -> ValidationRules:
    """Rules for music video content."""
    return ValidationRules(
        require_nfo=False,
        allowed_video_codecs=["HEVC", "AVC", "x264", "x265", "H.264", "H.265"],
        allowed_containers=[".mkv", ".mp4"],
        min_resolution_width=720,
    )


BUILTIN_RULESETS: dict[str, ValidationRules] = {
    "default": default_rules(),
    "strict": strict_rules(),
    "anime": anime_rules(),
    "music-video": music_video_rules(),
}
