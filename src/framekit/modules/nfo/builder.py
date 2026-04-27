from __future__ import annotations

import re
from pathlib import Path

from framekit.core.models.nfo import EpisodeNfoData, ReleaseNfoData
from framekit.modules.renamer.detector import infer_source_from_name
from framekit.modules.renamer.rules import split_team

YEAR_PATTERN = re.compile(r"\b(19\d{2}|20\d{2})\b")
SEASON_EPISODE_PATTERN = re.compile(r"\b(S\d{2})E\d{2}\b", flags=re.IGNORECASE)

TECH_MARKERS = {
    "MULTI",
    "VFF",
    "VFQ",
    "VOSTFR",
    "WEB",
    "WEBRIP",
    "WEB-DL",
    "BLURAY",
    "BDRIP",
    "REMUX",
    "DVDRIP",
    "HDRIP",
    "H264",
    "H265",
    "X264",
    "X265",
    "AAC",
    "AC3",
    "EAC3",
    "DDP5",
    "DDP5.1",
    "DDP",
    "TRUEHD",
    "DTS",
    "ATMOS",
    "HDR",
    "HDR10",
    "HDR10+",
    "DV",
    "DOLBY",
    "VISION",
}


def _safe_sum(values: list[int | None]) -> int | None:
    cleaned = [value for value in values if value is not None]
    if not cleaned:
        return None
    return sum(cleaned)


def _extract_year(text: str | None) -> str | None:
    if not text:
        return None
    match = YEAR_PATTERN.search(text)
    return match.group(1) if match else None


def _strip_year(text: str | None) -> str | None:
    if not text:
        return None

    cleaned = YEAR_PATTERN.sub("", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ._-")
    return cleaned or None


def _detect_media_kind(episodes: list[EpisodeNfoData]) -> str:
    codes = [episode.episode_code for episode in episodes if episode.episode_code]

    if not codes:
        return "movie"

    if len(episodes) == 1:
        return "single_episode"

    if all(code.upper().startswith("S00E") for code in codes):
        return "special_pack"

    return "season_pack"


def _common_series_title(episodes: list[EpisodeNfoData]) -> str | None:
    candidates: list[str] = []

    for episode in episodes:
        stem, _team = split_team(Path(episode.file_name).stem)
        episode_code = episode.episode_code
        if not episode_code:
            continue

        prefix = stem.split(episode_code, 1)[0]
        prefix = prefix.strip(" ._-").replace(".", " ").replace("_", " ").strip()
        if prefix:
            prefix = re.sub(r"\s+", " ", prefix)
            prefix = _strip_year(prefix) or prefix
            candidates.append(prefix)

    if not candidates:
        return None

    first = candidates[0]
    if all(item == first for item in candidates):
        return first
    return first


def _common_year(episodes: list[EpisodeNfoData]) -> str | None:
    years: list[str] = []

    for episode in episodes:
        stem, _team = split_team(Path(episode.file_name).stem)
        episode_code = episode.episode_code
        if not episode_code:
            continue

        prefix = stem.split(episode_code, 1)[0]
        prefix = prefix.strip(" ._-").replace(".", " ").replace("_", " ").strip()
        year = _extract_year(prefix)
        if year:
            years.append(year)

    if not years:
        return None

    first = years[0]
    if all(item == first for item in years):
        return first
    return first


def _movie_title_and_year_from_release(release_title: str) -> tuple[str | None, str | None]:
    stem, _team = split_team(release_title)
    tokens = re.split(r"[.\s_-]+", stem)

    title_tokens: list[str] = []
    year: str | None = None

    for token in tokens:
        if not token:
            continue

        upper = token.upper()

        if YEAR_PATTERN.fullmatch(token):
            year = token
            break

        if upper in TECH_MARKERS or re.fullmatch(r"\d{3,4}P", upper):
            break

        title_tokens.append(token)

    title_display = " ".join(title_tokens).strip() or None
    return title_display, year


def _release_title_from_episodes(episodes: list[EpisodeNfoData]) -> str | None:
    if not episodes:
        return None

    first_stem = Path(episodes[0].file_name).stem

    match = SEASON_EPISODE_PATTERN.search(first_stem)
    if match:
        season_code = match.group(1).upper()
        return SEASON_EPISODE_PATTERN.sub(season_code, first_stem, count=1)

    if episodes[0].episode_code:
        return first_stem.replace(episodes[0].episode_code, "").replace("..", ".").strip(" ._-")

    return first_stem


def _release_title(folder: Path, episodes: list[EpisodeNfoData], media_kind: str) -> str:
    if media_kind in {"movie", "single_episode"} and episodes:
        return Path(episodes[0].file_name).stem

    derived = _release_title_from_episodes(episodes)
    if derived:
        return derived

    return folder.name


def _first_match_or_none(values: list[str | None]) -> str | None:
    for value in values:
        if value:
            return value
    return None


def _common_team_from_episodes(episodes: list[EpisodeNfoData]) -> str | None:
    teams: list[str] = []

    for episode in episodes:
        stem = Path(episode.file_name).stem
        _before, team = split_team(stem)
        if team:
            teams.append(team)

    if not teams:
        return None

    first = teams[0]
    if all(item == first for item in teams):
        return first
    return None


def _common_source_from_episodes(episodes: list[EpisodeNfoData]) -> str | None:
    sources: list[str] = []

    for episode in episodes:
        source = infer_source_from_name(episode.file_name)
        if source:
            sources.append(source)

    if not sources:
        return None

    first = sources[0]
    if all(item == first for item in sources):
        return first

    return first


def _audio_languages_display(episodes: list[EpisodeNfoData]) -> str | None:
    if not episodes:
        return None

    first = episodes[0]
    labels: list[str] = []

    for track in first.audio_tracks:
        if track.language_display and track.language_display not in labels:
            labels.append(track.language_display)

    if not labels:
        return None

    return " / ".join(labels)


def _language_tag_display(episodes: list[EpisodeNfoData]) -> str | None:
    if not episodes:
        return None

    first = episodes[0]
    short_labels: list[str] = []

    for track in first.audio_tracks:
        if track.language_short and track.language_short.upper() not in short_labels:
            short_labels.append(track.language_short.upper())

    if not short_labels:
        return None

    if len(short_labels) == 1:
        lang = first.audio_tracks[0].language_display
        return lang or short_labels[0]

    return f"MULTI ({', '.join(short_labels)})"


def _subtitle_summary_lines(episodes: list[EpisodeNfoData]) -> list[str]:
    if not episodes:
        return []

    first = episodes[0]
    grouped: dict[str, list[str]] = {}

    for track in first.subtitle_tracks:
        label = track.language_display or "Unknown"
        variant = track.subtitle_variant or "Unknown"

        grouped.setdefault(label, [])
        if variant not in grouped[label]:
            grouped[label].append(variant)

    return [
        f"{language_label}: {', '.join(variants)}" for language_label, variants in grouped.items()
    ]


def _subtitle_summary_by_episode(episodes: list[EpisodeNfoData]) -> list[str]:
    blocks: list[str] = []

    for episode in episodes:
        label = episode.episode_code or Path(episode.file_name).stem

        if not episode.subtitle_tracks:
            blocks.append(f"{label}\n  - No subtitles")
            continue

        grouped: dict[str, list[str]] = {}
        for track in episode.subtitle_tracks:
            language = track.language_display or "Unknown"
            variant = track.subtitle_variant or "Unknown"

            grouped.setdefault(language, [])
            if variant not in grouped[language]:
                grouped[language].append(variant)

        lines = [label]
        for language, variants in grouped.items():
            lines.append(f"  - {language}: {', '.join(variants)}")

        blocks.append("\n".join(lines))

    return blocks


def build_release_nfo(folder: Path, episodes: list[EpisodeNfoData]) -> ReleaseNfoData:
    media_kind = _detect_media_kind(episodes)
    release_title = _release_title(folder, episodes, media_kind)

    source = _common_source_from_episodes(episodes)
    resolution = _first_match_or_none([episode.resolution for episode in episodes])
    video_tag = _first_match_or_none([episode.video_codec for episode in episodes])
    hdr_display = _first_match_or_none([episode.hdr_display for episode in episodes])

    audio_tag = None
    if episodes and episodes[0].audio_tracks:
        first_audio = episodes[0].audio_tracks[0]
        if first_audio.codec and first_audio.channels:
            audio_tag = f"{first_audio.codec}.{first_audio.channels}"
        elif first_audio.codec:
            audio_tag = first_audio.codec

    title_display = None
    series_title = None
    year = None

    if media_kind == "movie":
        title_display, year = _movie_title_and_year_from_release(release_title)
    else:
        series_title = _common_series_title(episodes)
        title_display = series_title
        year = _common_year(episodes)

    subtitle_summary_by_episode = _subtitle_summary_by_episode(episodes)
    if media_kind in {"movie", "single_episode"}:
        subtitle_summary_by_episode = []

    return ReleaseNfoData(
        media_kind=media_kind,
        release_title=release_title,
        title_display=title_display,
        series_title=series_title,
        year=year,
        source=source,
        resolution=resolution,
        video_tag=video_tag,
        audio_tag=audio_tag,
        language_tag=_language_tag_display(episodes),
        audio_languages_display=_audio_languages_display(episodes),
        subtitle_summary_lines=_subtitle_summary_lines(episodes),
        subtitle_summary_by_episode=subtitle_summary_by_episode,
        hdr_display=hdr_display,
        team=_common_team_from_episodes(episodes),
        total_size_bytes=sum(item.size_bytes for item in episodes),
        total_duration_ms=_safe_sum([item.duration_ms for item in episodes]),
        episodes=episodes,
    )
