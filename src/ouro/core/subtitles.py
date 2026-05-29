from __future__ import annotations

import re

_AD_TITLE_PATTERNS = (
    r"\baudio.?descri",
    r"\baudio.?desc\b",
    r"\b(?:AD|VA)\b",
    r"\bvisually.?impaired\b",
    r"\bdescriptive\b",
)

_FORCED_PATTERNS = (
    r"\bforced\b",
    r"\bforcé\b",
    r"\bforce\b",
)

_SDH_PATTERNS = (
    r"\bsdh\b",
    r"\bhi\b",
    r"hearing impaired",
    r"malentendant",
    r"sourd",
)


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def is_audio_description_track(title: str | None, *, flag_visual_impaired: bool = False) -> bool:
    """Return True if the audio track is an audio description (AD) track.

    Checks the mkvmerge/MediaInfo flag_visual_impaired property and common
    title patterns: "Audio Description", "AD", "VA", "Visually Impaired", etc.
    """
    if flag_visual_impaired:
        return True
    return _matches_any((title or "").strip(), _AD_TITLE_PATTERNS)


def classify_subtitle_variant(
    title: str | None,
    *,
    forced: bool = False,
    hearing_impaired: bool = False,
) -> str:
    """Handle classify subtitle variant."""
    raw = (title or "").strip().lower()

    if forced or _matches_any(raw, _FORCED_PATTERNS):
        return "forced"

    if hearing_impaired or _matches_any(raw, _SDH_PATTERNS):
        return "sdh"

    return "full"
