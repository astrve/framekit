from __future__ import annotations

import re

from framekit.core.models.metadata import MetadataCandidate, MetadataLookupRequest
from framekit.core.models.nfo import ReleaseNfoData

SEASON_EPISODE_RE = re.compile(r"^S(?P<season>\d{2})E(?P<episode>\d{2})$", flags=re.IGNORECASE)


def _parse_episode_code(code: str | None) -> tuple[int | None, int | None]:
    if not code:
        return None, None

    match = SEASON_EPISODE_RE.match(code.strip())
    if not match:
        return None, None

    return int(match.group("season")), int(match.group("episode"))


def build_lookup_request(release: ReleaseNfoData) -> MetadataLookupRequest:
    if release.media_kind == "movie":
        return MetadataLookupRequest(
            media_kind="movie",
            title=release.title_display,
            year=release.year,
            release_title=release.release_title,
        )

    if release.media_kind == "single_episode":
        first_episode = release.episodes[0] if release.episodes else None
        season_number, episode_number = _parse_episode_code(
            first_episode.episode_code if first_episode else None
        )

        return MetadataLookupRequest(
            media_kind="single_episode",
            title=release.series_title,
            year=release.year,
            season_number=season_number,
            episode_number=episode_number,
            release_title=release.release_title,
        )

    if release.media_kind == "season_pack":
        first_episode = release.episodes[0] if release.episodes else None
        season_number, _episode_number = _parse_episode_code(
            first_episode.episode_code if first_episode else None
        )

        return MetadataLookupRequest(
            media_kind="season_pack",
            title=release.series_title,
            year=release.year,
            season_number=season_number,
            release_title=release.release_title,
        )

    raise ValueError(f"Unsupported metadata lookup media kind: {release.media_kind}")


def sort_candidates(candidates: list[MetadataCandidate]) -> list[MetadataCandidate]:
    return sorted(candidates, key=lambda item: item.confidence, reverse=True)
