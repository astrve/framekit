from __future__ import annotations

import re
from pathlib import Path

from framekit.core.mediainfo import probe_media_file
from framekit.core.models.renamer import RenamePlanItem
from framekit.modules.renamer.detector import (
    get_hdr_canonical,
    get_preferred_audio_tag,
    get_preferred_resolution,
    get_preferred_video_tag,
    hdr_display_label,
    hdr_release_label,
)
from framekit.modules.renamer.rules import (
    DEFAULT_LANG,
    VIDEO_EXTENSIONS,
    normalize_name_part,
    split_team,
)


def _clean_removed_term_separators(value: str) -> str:
    value = re.sub(r"[. _-]{2,}", ".", value)
    value = re.sub(r"\.{2,}", ".", value)
    return value.strip(" ._-")


def _term_pattern(raw: str) -> re.Pattern[str]:
    escaped = re.escape(raw.strip())
    return re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", re.IGNORECASE)


def _remove_terms_from_stem(stem: str, remove_terms: tuple[str, ...]) -> str:
    result = stem
    for term in remove_terms:
        raw = term.strip()
        if not raw:
            continue
        result = _term_pattern(raw).sub("", result)
    result = _clean_removed_term_separators(result)
    return result or stem


def _remove_terms_from_normalized_name(name: str, remove_terms: tuple[str, ...]) -> str:
    result = name
    for term in remove_terms:
        raw = term.strip()
        if not raw:
            continue
        result = _term_pattern(raw).sub("", result)
    result = _clean_removed_term_separators(result)
    return result or name


def build_rename_plan(
    folder: Path,
    *,
    default_lang: str = DEFAULT_LANG,
    force_lang: bool = False,
    remove_terms: tuple[str, ...] = (),
) -> list[RenamePlanItem]:
    plan: list[RenamePlanItem] = []
    reserved_targets: dict[str, Path] = {}

    media_files = sorted(
        file_path
        for file_path in folder.iterdir()
        if file_path.is_file() and file_path.suffix.lower() in VIDEO_EXTENSIONS
    )

    for file_path in media_files:
        info = probe_media_file(file_path)
        stem, team = split_team(_remove_terms_from_stem(file_path.stem, remove_terms))

        inferred_video_tag = get_preferred_video_tag(info)
        inferred_audio_tag = get_preferred_audio_tag(info)
        inferred_resolution = get_preferred_resolution(info)

        hdr_canonical = get_hdr_canonical(info)
        hdr_release = hdr_release_label(hdr_canonical)
        hdr_display = hdr_display_label(hdr_canonical)

        (
            normalized,
            existing_language_tag,
            resulting_language_tag,
            parsed_episode_code,
            parsed_episode_title,
        ) = normalize_name_part(
            stem,
            preferred_video_tag=inferred_video_tag,
            preferred_audio_tag=inferred_audio_tag,
            preferred_resolution=inferred_resolution,
            preferred_hdr=hdr_release,
            default_lang=default_lang,
            force_lang=force_lang,
        )

        normalized = _remove_terms_from_normalized_name(normalized, remove_terms)

        if team:
            normalized = f"{normalized}-{team}"

        normalized = _remove_terms_from_normalized_name(normalized, remove_terms)

        target = file_path.with_name(f"{normalized}{file_path.suffix}")

        source_name_lower = file_path.name.lower()
        target_name_lower = target.name.lower()

        changed = file_path.name != target.name
        case_only = changed and source_name_lower == target_name_lower

        collision = False
        reserved_key = str(target).lower()

        if (
            changed
            and reserved_key in reserved_targets
            and reserved_targets[reserved_key] != file_path
        ):
            collision = True

        if (
            changed
            and target.exists()
            and target.resolve() != file_path.resolve()
            and not case_only
        ):
            collision = True

        reserved_targets[reserved_key] = file_path

        plan.append(
            RenamePlanItem(
                source=file_path,
                target=target,
                reason="normalized",
                changed=changed,
                case_only=case_only,
                collision=collision,
                inferred_video_tag=inferred_video_tag or None,
                inferred_audio_tag=inferred_audio_tag or None,
                inferred_source=None,
                inferred_resolution=inferred_resolution or None,
                hdr_canonical=hdr_canonical or None,
                hdr_release_label=hdr_release or None,
                hdr_display_label=hdr_display or None,
                existing_language_tag=existing_language_tag,
                resulting_language_tag=resulting_language_tag,
                parsed_episode_code=parsed_episode_code,
                parsed_episode_title=parsed_episode_title,
            )
        )

    return plan
