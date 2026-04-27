from __future__ import annotations

from dataclasses import replace

from framekit.core.models.metadata import EpisodeMetadata, MovieMetadata, SeasonMetadata


def _episode_code(season_number: int | None, episode_number: int | None) -> str | None:
    if season_number is None or episode_number is None:
        return None
    return f"S{season_number:02d}E{episode_number:02d}"


def build_metadata_context(resolved, release=None) -> dict:
    context = {
        "metadata_movie": None,
        "metadata_episode": None,
        "metadata_season": None,
        "metadata_episode_map": {},
        "metadata_season_episode_codes": (),
        "metadata_season_episode_count": 0,
    }

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
        episode_map: dict[str, EpisodeMetadata] = {}

        if release is not None:
            wanted_codes = {
                episode.episode_code for episode in release.episodes if episode.episode_code
            }
        else:
            wanted_codes = set()

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

        filtered_season = replace(
            resolved,
            episode_summaries=filtered_episode_summaries,
        )

        context["metadata_season"] = filtered_season
        context["metadata_episode_map"] = episode_map
        context["metadata_season_episode_codes"] = tuple(all_episode_codes)
        context["metadata_season_episode_count"] = len(all_episode_codes)
        return context

    return context
