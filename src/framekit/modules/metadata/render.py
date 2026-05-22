from __future__ import annotations

from dataclasses import replace
from typing import Any

from framekit.core.models.metadata import EpisodeMetadata, MovieMetadata, SeasonMetadata


def _episode_code(season_number: int | None, episode_number: int | None) -> str | None:
    if season_number is None or episode_number is None:
        return None
    return f"S{season_number:02d}E{episode_number:02d}"


def _base_metadata_context() -> dict[str, Any]:
    return {
        "metadata_movie": None,
        "metadata_episode": None,
        "metadata_season": None,
        "metadata_episode_map": {},
        "metadata_season_episode_codes": (),
        "metadata_season_episode_count": 0,
        "metadata_cover_url": None,
        "metadata_cover_url_original": None,
    }


def _apply_cover(context: dict[str, Any], selected_cover: dict[str, str] | None) -> None:
    if not selected_cover:
        return
    context["metadata_cover_url"] = selected_cover.get("url")
    context["metadata_cover_url_original"] = selected_cover.get("url_original")


def _wanted_episode_codes(release) -> set[str]:
    if release is None:
        return set()
    return {episode.episode_code for episode in release.episodes if episode.episode_code}


def _season_episode_mapping(
    resolved: SeasonMetadata,
    *,
    wanted_codes: set[str],
) -> tuple[list[EpisodeMetadata], dict[str, EpisodeMetadata], list[str]]:
    episode_map: dict[str, EpisodeMetadata] = {}
    all_episode_codes: list[str] = []
    filtered_episode_summaries: list[EpisodeMetadata] = []
    for meta_episode in resolved.episode_summaries:
        code = _episode_code(meta_episode.season_number, meta_episode.episode_number)
        if code is None:
            continue
        all_episode_codes.append(code)
        if wanted_codes and code not in wanted_codes:
            continue
        filtered_episode_summaries.append(meta_episode)
        episode_map[code] = meta_episode
    return filtered_episode_summaries, episode_map, all_episode_codes


def _apply_season_context(context: dict[str, Any], resolved: SeasonMetadata, release) -> None:
    wanted_codes = _wanted_episode_codes(release)
    filtered_episode_summaries, episode_map, all_episode_codes = _season_episode_mapping(
        resolved,
        wanted_codes=wanted_codes,
    )
    filtered_season = replace(resolved, episode_summaries=filtered_episode_summaries)
    context["metadata_season"] = filtered_season
    context["metadata_episode_map"] = episode_map
    context["metadata_season_episode_codes"] = tuple(all_episode_codes)
    context["metadata_season_episode_count"] = len(all_episode_codes)


def build_metadata_context(
    resolved, release=None, selected_cover: dict[str, str] | None = None
) -> dict[str, Any]:
    """Build metadata context."""
    context: dict[str, Any] = _base_metadata_context()
    _apply_cover(context, selected_cover)

    if isinstance(resolved, MovieMetadata):
        context["metadata_movie"] = resolved
        return context

    if isinstance(resolved, EpisodeMetadata):
        context["metadata_episode"] = resolved
        code = _episode_code(resolved.season_number, resolved.episode_number)
        if code:
            context["metadata_episode_map"] = {code: resolved}
        return context

    if isinstance(resolved, SeasonMetadata):
        _apply_season_context(context, resolved, release)
        return context

    return context
