"""Term selector for the Renamer.

This module extracts release-name tokens from a folder of `.mkv` files,
groups them by category (episode codes, language, resolution, source, video
codec, audio codec, HDR, team, free-form / other), and exposes the result so
the CLI can present an interactive "terms to keep" picker. Tokens that the
normalizer already controls (resolution, codec, language, …) are reported as
locked: they are always kept and cannot be unticked. Only the *free-form*
tokens — the ones that survive normalization untouched (release labels, scene
markers, "INTERNAL", "PROPER", platform tags …) — are toggleable.

Unticking a free-form term adds it to the `remove_terms` tuple consumed by the
existing Renamer plan-builder.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ouro.modules.renamer.rules import (
    COMPOUND_RESTORE,
    COMPOUND_TOKENS,
    LANGUAGE_TAGS,
    RAW_REPLACEMENTS,
    REMOVE_TOKENS,
    VIDEO_EXTENSIONS,
    extract_episode_code,
    split_team,
)

# Tokens that are part of the structured grammar already handled by
# `normalize_name_part`. They are displayed in the selector but locked
# (always kept) — unticking them would not be honoured anyway, since the
# renamer rewrites tech tags from MediaInfo.
_RESOLUTION_TOKENS = {"480P", "720P", "1080P", "1440P", "2160P", "4320P"}
_VIDEO_CODEC_TOKENS = {
    "H264",
    "H265",
    "X264",
    "X265",
    "HEVC",
    "AVC",
    "AV1",
    "VP9",
    "MPEG2",
    "MPEG4",
}
_AUDIO_CODEC_PREFIXES = (
    "EAC3",
    "AC3",
    "AAC",
    "DTS",
    "TRUEHD",
    "FLAC",
    "OPUS",
    "MP3",
    "DDP",
)
_SOURCE_TOKENS = {
    "WEB",
    "WEBDL",
    "WEB-DL",
    "WEBRIP",
    "BLURAY",
    "BDRIP",
    "BRRIP",
    "HDRIP",
    "DVDRIP",
    "REMUX",
    "HDTV",
}
_HDR_TOKENS = {"HDR", "HDR10", "HDR10PLUS", "HDR10+", "DV", "DOLBYVISION", "HLG", "PQ"}
_LANGUAGE_COMPACT = {item.replace(".", "") for item in LANGUAGE_TAGS}
_SOURCE_COMPACT = {item.replace("-", "") for item in _SOURCE_TOKENS}
_HDR_COMPACT = {"HDR10PLUS", "DOLBYVISION"}

# Categories — preserved in this exact order in the selector UI. The first
# value of each tuple is the canonical category id used in code; the second
# is whether the category is selectable (True) or locked (False).
LOCKED_CATEGORIES = (
    "episode_code",
    "year",
    "language",
    "resolution",
    "source",
    "video_codec",
    "audio_codec",
    "hdr",
)
SELECTABLE_CATEGORIES = ("team", "other")
ALL_CATEGORIES = LOCKED_CATEGORIES + SELECTABLE_CATEGORIES


# Year tokens like "2023" / "1998" are kept as informational locked entries —
# they are part of the title context and should never be removed via the
# selector (the user can still pass `--remove-term 2023` explicitly).
_YEAR_PATTERN = re.compile(r"^(19|20)\d{2}$")
_EPISODE_PATTERN = re.compile(r"^S\d{2}(E\d{2})?$", re.IGNORECASE)


@dataclass(slots=True)
class TermEntry:
    """A single term extracted from one or more file names.

    `category` is one of `ALL_CATEGORIES`. `value` is the normalized,
    upper-cased token. `originals` keeps the verbatim spellings as they
    appeared in source files (for display). `count` is how many files contain
    the term. `locked` is True for categories whose tokens are rewritten by
    the renamer itself; locked entries are shown but cannot be toggled off.
    `selected_by_default` is True by default for every entry (selector is a
    "terms to keep" picker — unticking removes).
    """

    category: str
    value: str
    originals: tuple[str, ...] = field(default_factory=tuple)
    count: int = 0
    locked: bool = True
    selected_by_default: bool = True


@dataclass(slots=True)
class EpisodeCodeGroup:
    """Compact representation of a contiguous range of episode codes for display.

    Example: `S01E01`, `S01E02`, …, `S01E10` → `("S01E01..S01E10", 10)`.
    """

    label: str
    count: int
    codes: tuple[str, ...]


def _classify_token(token: str) -> str | None:
    """Return the category for a *non-team*, *non-episode* token.

    Returns ``None`` if the token is purely informational and should be filed
    under ``"other"``.
    """
    if not token:
        return None

    upper = token.upper()
    compact = upper.replace(".", "").replace("-", "").replace("_", "")
    checks = (
        ("language", upper in LANGUAGE_TAGS or compact in _LANGUAGE_COMPACT),
        ("resolution", upper in _RESOLUTION_TOKENS),
        ("source", upper in _SOURCE_TOKENS or compact in _SOURCE_COMPACT),
        ("video_codec", upper in _VIDEO_CODEC_TOKENS),
        ("hdr", upper in _HDR_TOKENS or compact in _HDR_COMPACT),
    )
    for category, matches in checks:
        if matches:
            return category
    if any(upper.startswith(prefix) for prefix in _AUDIO_CODEC_PREFIXES):
        return "audio_codec"
    return None


def _media_files(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )


def _token_counter_key(token: str) -> tuple[str, str] | None:
    upper = token.upper()
    if upper in REMOVE_TOKENS or _EPISODE_PATTERN.match(upper):
        return None
    category = _classify_token(token)
    if category is not None:
        return category, upper
    if _YEAR_PATTERN.match(upper):
        return "year", upper
    return "other", upper


def _collect_file_terms(
    file_path: Path,
    counters: dict[tuple[str, str], list[str]],
    episode_codes: list[str],
) -> None:
    stem, team = split_team(file_path.stem)
    if team:
        counters.setdefault(("team", team.upper()), []).append(team)

    ep_code = extract_episode_code(stem)
    if ep_code:
        episode_codes.append(ep_code)

    tokens = _collect_compound_tokens(_split_stem_into_tokens(stem))
    for token in tokens:
        key = _token_counter_key(token)
        if key is not None:
            counters.setdefault(key, []).append(token)


def _build_term_entries(counters: dict[tuple[str, str], list[str]]) -> list[TermEntry]:
    entries: list[TermEntry] = []
    for category in ALL_CATEGORIES:
        if category == "episode_code":
            continue
        category_items = sorted(
            (key for key in counters if key[0] == category),
            key=lambda pair: pair[1],
        )
        for _, value in category_items:
            originals = tuple(counters[(category, value)])
            entries.append(
                TermEntry(
                    category=category,
                    value=value,
                    originals=originals,
                    count=len(originals),
                    locked=category not in SELECTABLE_CATEGORIES,
                    selected_by_default=True,
                )
            )
    return entries


def _split_stem_into_tokens(stem: str) -> list[str]:
    """Tokenize a release stem **using the same pipeline as the renamer**.

    The previous implementation split on `.` / `_` and then tried to
    re-stitch known compounds (`WEB-DL`, `MULTI.VFF`, audio codec layouts)
    by walking the resulting token list with hard-coded rules. That is
    fragile: any time the renamer learns a new compound (a new audio
    layout, a new language alias, a new HDR family), we would have to
    duplicate the rule here — and a divergence between the two pipelines
    means the picker shows fragments the renamer never sees in isolation
    (e.g. `VFF` alone), so unticking them silently does nothing.

    Instead we mirror the *first half* of
    :func:`ouro.modules.renamer.rules.normalize_name_part` exactly:
    apply :data:`RAW_REPLACEMENTS`, collapse separators to ``.``, swap
    every entry of :data:`COMPOUND_TOKENS` for an opaque sentinel so it
    survives the split, then split on ``.`` and restore. Whatever the
    renamer treats as one atom, the picker also treats as one atom.
    """
    base = stem.replace("_", ".")
    for pattern, repl in RAW_REPLACEMENTS:
        base = re.sub(pattern, repl, base)

    base = re.sub(r"[.\-]+", ".", base)
    base = re.sub(r"\.+", ".", base).strip(".")

    for canonical, sentinel in COMPOUND_TOKENS.items():
        base = base.replace(canonical, sentinel)

    parts = [COMPOUND_RESTORE.get(part, part) for part in base.split(".") if part]
    return [part for part in parts if part]


def _collect_compound_tokens(tokens: list[str]) -> list[str]:
    """Backward-compatible no-op shim for the legacy compound-token pipeline.

    Kept so external callers that used the older two-step
    ``_split_stem_into_tokens`` → ``_collect_compound_tokens`` pipeline keep
    working. Compounds are now restored *inside* ``_split_stem_into_tokens``
    itself (single source of truth, mirrored from the renamer), so this
    function is now a no-op.
    """
    return tokens


def _episode_code_label(codes: list[str]) -> EpisodeCodeGroup:
    """Render a compact label for a list of episode codes.

    - Single code → exact code.
    - Multiple codes from the same season → `S01E01..S01E10` (count).
    - Mixed seasons → `S01E01..S02E03` (count).
    - All-season tokens (`S01`) → `S01..S03` if multiple seasons.
    """
    unique = sorted({code.upper() for code in codes})
    if not unique:
        return EpisodeCodeGroup(label="", count=0, codes=())
    if len(unique) == 1:
        return EpisodeCodeGroup(label=unique[0], count=1, codes=tuple(unique))
    return EpisodeCodeGroup(
        label=f"{unique[0]}..{unique[-1]}",
        count=len(unique),
        codes=tuple(unique),
    )


@dataclass(slots=True)
class TermInventory:
    """Result of :func:`collect_terms`.

    Provides per-category access plus a flat ``entries`` list ordered by
    ``ALL_CATEGORIES`` membership.
    """

    entries: list[TermEntry] = field(default_factory=list)
    episode_codes: EpisodeCodeGroup = field(default_factory=lambda: EpisodeCodeGroup("", 0, ()))
    files: tuple[str, ...] = field(default_factory=tuple)

    def by_category(self, category: str) -> list[TermEntry]:
        """Handle by category."""
        return [entry for entry in self.entries if entry.category == category]

    def selectable(self) -> list[TermEntry]:
        """Handle selectable."""
        return [entry for entry in self.entries if not entry.locked]

    def is_empty(self) -> bool:
        """Return ``True`` if is empty."""
        return not self.entries


def collect_terms(folder: Path) -> TermInventory:
    """Scan a folder of ``.mkv`` files and return a categorized term inventory.

    Tokens that look like episode codes are folded into a single grouped
    entry so a 26-episode season does not produce 26 lines in the selector.
    Unknown / free-form tokens (release labels, scene markers, year, …) end
    up under the ``other`` category and are the only ones the user can untick.
    """
    media_files = _media_files(folder)
    file_names = tuple(item.name for item in media_files)

    counters: dict[tuple[str, str], list[str]] = {}
    episode_codes: list[str] = []

    for file_path in media_files:
        _collect_file_terms(file_path, counters, episode_codes)

    return TermInventory(
        entries=_build_term_entries(counters),
        episode_codes=_episode_code_label(episode_codes),
        files=file_names,
    )


def derive_remove_terms(
    inventory: TermInventory,
    kept_values: set[str],
) -> tuple[str, ...]:
    """Compute the ``remove_terms`` tuple to feed to the renamer.

    From a ``TermInventory`` and the set of values the user kept, return the
    ``remove_terms`` tuple. Locked entries are always kept regardless of
    whether they appear in ``kept_values``. Selectable entries that are
    *not* in ``kept_values`` are treated as removed.
    """
    removed: list[str] = []
    for entry in inventory.entries:
        if entry.locked:
            continue
        if entry.value in kept_values:
            continue
        # Use the first verbatim spelling so case-insensitive removal still
        # works while looking natural in logs/dry-run previews.
        removed.append(entry.originals[0] if entry.originals else entry.value)
    return tuple(removed)


def category_label(category: str) -> str:
    """Human-readable category label, deferred to i18n at the call site.

    Returned key follows the `renamer.term_selector.category.<id>` namespace.
    """
    return f"renamer.term_selector.category.{category}"
