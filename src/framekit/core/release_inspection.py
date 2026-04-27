from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from framekit.core.models.nfo import ReleaseNfoData

EPISODE_CODE_RE = re.compile(r"^S(?P<season>\d{2})E(?P<episode>\d{2})$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class EpisodeCompleteness:
    status: str
    found: int
    expected: int | None
    missing_codes: tuple[str, ...] = ()
    detected_range: str | None = None

    @property
    def is_complete(self) -> bool:
        return self.status == "complete"

    @property
    def label(self) -> str:
        if self.status == "complete" and self.expected is not None:
            return f"Complete ({self.found}/{self.expected})"
        if self.status == "incomplete" and self.expected is not None:
            missing = ", ".join(self.missing_codes) if self.missing_codes else "?"
            return f"Incomplete ({self.found}/{self.expected}) · Missing: {missing}"
        if self.status == "partial":
            if self.detected_range:
                return f"Partial/unknown ({self.found}) · Range: {self.detected_range}"
            return f"Partial/unknown ({self.found})"
        return "N/A"


def _episode_code_numbers(codes: Iterable[str]) -> list[tuple[int, int, str]]:
    items: list[tuple[int, int, str]] = []
    for code in codes:
        match = EPISODE_CODE_RE.match((code or "").strip())
        if not match:
            continue
        season = int(match.group("season"))
        episode = int(match.group("episode"))
        items.append((season, episode, f"S{season:02d}E{episode:02d}"))
    return items


def inspect_release_completeness(release: ReleaseNfoData) -> EpisodeCompleteness:
    if release.media_kind not in {"season_pack", "special_pack", "single_episode"}:
        return EpisodeCompleteness(status="n/a", found=len(release.episodes), expected=None)

    items = _episode_code_numbers(
        episode.episode_code for episode in release.episodes if episode.episode_code
    )
    if not items:
        return EpisodeCompleteness(status="partial", found=len(release.episodes), expected=None)

    seasons = {season for season, _episode, _code in items}
    if len(seasons) != 1:
        return EpisodeCompleteness(status="partial", found=len(items), expected=None)

    season = items[0][0]
    found_codes = tuple(dict.fromkeys(code for _season, _episode, code in items))
    episode_numbers = sorted({episode for _season, episode, _code in items})
    min_ep = episode_numbers[0]
    max_ep = episode_numbers[-1]
    expected_codes = tuple(f"S{season:02d}E{number:02d}" for number in range(min_ep, max_ep + 1))
    missing = tuple(code for code in expected_codes if code not in found_codes)
    return EpisodeCompleteness(
        status="complete" if not missing else "incomplete",
        found=len(found_codes),
        expected=len(expected_codes),
        missing_codes=missing,
        detected_range=f"S{season:02d}E{min_ep:02d}-S{season:02d}E{max_ep:02d}",
    )


def completeness_label(release: ReleaseNfoData) -> str:
    return inspect_release_completeness(release).label


def missing_episode_codes(release: ReleaseNfoData) -> tuple[str, ...]:
    return inspect_release_completeness(release).missing_codes
