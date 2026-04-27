from __future__ import annotations

import re

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


def classify_subtitle_variant(
    title: str | None,
    *,
    forced: bool = False,
    hearing_impaired: bool = False,
) -> str:
    raw = (title or "").strip().lower()

    if forced or _matches_any(raw, _FORCED_PATTERNS):
        return "forced"

    if hearing_impaired or _matches_any(raw, _SDH_PATTERNS):
        return "sdh"

    return "full"
