from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from swirrl.core.mediainfo import probe_media_file
from swirrl.core.models.renamer import RenamePlanItem
from swirrl.modules.renamer.detector import (
    MediaInfoSource,
    get_hdr_canonical,
    get_preferred_audio_tag,
    get_preferred_resolution,
    get_preferred_video_tag,
    hdr_display_label,
    hdr_release_label,
)
from swirrl.modules.renamer.profiles import (
    LanguageTagProfile,
    RenamerProfile,
    infer_language_tag,
    language_tags_for_profile,
)
from swirrl.modules.renamer.rules import (
    DEFAULT_LANG,
    SINGLE_LANG_TAGS,
    VIDEO_EXTENSIONS,
    extract_existing_language_tag_with_candidates,
    normalize_name_part,
    split_team,
)


class _RenameContext(NamedTuple):
    inferred_video_tag: str
    inferred_audio_tag: str
    inferred_resolution: str
    hdr_canonical: str
    hdr_release: str
    hdr_display: str
    existing_language_tag: str | None
    resulting_language_tag: str | None
    calculated_language_tag: str | None
    parsed_episode_code: str | None
    parsed_episode_title: str | None
    normalized_name: str
    multi_language_detected: bool
    language_tag_conflict: bool
    resolution_conflict: bool


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


def _insert_after_token(
    name: str,
    insert_after_pairs: tuple[tuple[str, str], ...],
    missing_tokens: set[str],
) -> str:
    """Insert terms after existing tokens in the filename.

    Args:
        name: The filename to modify
        insert_after_pairs: Tuples of (existing_token, term_to_add)
        missing_tokens: Set to collect tokens that were not found

    Returns:
        Modified filename with inserted terms
    """
    result = name
    for existing_token, term_to_add in insert_after_pairs:
        existing = existing_token.strip()
        to_add = term_to_add.strip()
        if not existing or not to_add:
            continue

        # Create a pattern to find the existing token
        pattern = _term_pattern(existing)

        # Check if the token exists in the name
        if not pattern.search(result):
            missing_tokens.add(existing)
            continue

        # Insert the new term after the existing token
        # We need to preserve the separator style (. or space)
        def replacer(match: re.Match[str], val: str = to_add) -> str:
            matched_text = match.group(0)
            # Add the new term with a dot separator
            return f"{matched_text}.{val}"

        result = pattern.sub(replacer, result, count=1)

    return result


def _collect_media_files(folder: Path) -> list[Path]:
    return sorted(
        file_path
        for file_path in folder.iterdir()
        if file_path.is_file() and file_path.suffix.lower() in VIDEO_EXTENSIONS
    )


def _resolve_original_stem(
    file_path: Path,
    insert_after_pairs: tuple[tuple[str, str], ...],
    missing_tokens: set[str],
) -> str:
    stem = file_path.stem
    if not insert_after_pairs:
        return stem
    return _insert_after_token(stem, insert_after_pairs, missing_tokens)


def _detect_multi_language(info: MediaInfoSource) -> bool:
    """Return True when the media file has more than one audio track."""
    from swirrl.core.models.media import MediaFileInfo

    if isinstance(info, MediaFileInfo):
        return len(info.audio_tracks) > 1
    return len(probe_media_file(info).audio_tracks) > 1


def _audio_languages(info: MediaInfoSource) -> list[tuple[str | None, str | None]]:
    from swirrl.core.models.media import MediaFileInfo

    media_info = info if isinstance(info, MediaFileInfo) else probe_media_file(info)
    return [
        (getattr(track, "language", None), getattr(track, "language_variant", None))
        for track in media_info.audio_tracks
    ]


def _existing_resolution_token(stem: str) -> str | None:
    for token in stem.replace("_", ".").split("."):
        upper = token.upper()
        if upper in {"2160P", "1440P", "1080P", "720P", "480P"}:
            return upper
        if upper == "HD":
            return upper
        if re.fullmatch(r"\d{3,4}P", upper):
            return upper
    return None


def _is_non_bucket_resolution(token: str) -> bool:
    upper = token.upper()
    if upper == "HD":
        return True
    if re.fullmatch(r"\d{3,4}P", upper) and upper not in {"2160P", "1080P", "720P", "480P"}:
        return True
    return False


def _build_rename_context(
    stem: str,
    *,
    default_lang: str,
    force_lang: bool,
    remove_terms: tuple[str, ...],
    info: MediaInfoSource,
    profile: RenamerProfile | None,
    language_profile: LanguageTagProfile | None = None,
) -> _RenameContext:
    inferred_video_tag = get_preferred_video_tag(info)
    inferred_audio_tag = get_preferred_audio_tag(info)
    inferred_resolution = get_preferred_resolution(info)

    hdr_canonical = get_hdr_canonical(info)
    hdr_release = hdr_release_label(hdr_canonical)
    hdr_display = hdr_display_label(hdr_canonical)

    inferred_lang_tag = (
        infer_language_tag(language_profile, _audio_languages(info))
        if language_profile is not None
        else default_lang
    )

    additional_language_tags: tuple[str, ...] = ()
    if language_profile is not None:
        additional_language_tags = tuple(language_tags_for_profile(language_profile))

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
        default_lang=inferred_lang_tag or default_lang,
        force_lang=force_lang,
        profile=profile,
        additional_language_tags=additional_language_tags,
    )

    normalized = _remove_terms_from_normalized_name(normalized, remove_terms)
    if existing_language_tag is None and additional_language_tags:
        existing_language_tag = extract_existing_language_tag_with_candidates(
            stem.replace("_", ".").split("."),
            candidates=set(additional_language_tags),
        )

    language_tag_conflict = bool(
        existing_language_tag
        and inferred_lang_tag
        and existing_language_tag.upper() != inferred_lang_tag.upper()
    )
    multi_detected = (
        _detect_multi_language(info) and (existing_language_tag or "") in SINGLE_LANG_TAGS
    )
    existing_resolution = _existing_resolution_token(stem)
    resolution_conflict = bool(
        (
            existing_resolution
            and inferred_resolution
            and existing_resolution != inferred_resolution
        )
        or (existing_resolution and not inferred_resolution and _is_non_bucket_resolution(existing_resolution))
    )
    return _RenameContext(
        inferred_video_tag=inferred_video_tag,
        inferred_audio_tag=inferred_audio_tag,
        inferred_resolution=inferred_resolution,
        hdr_canonical=hdr_canonical,
        hdr_release=hdr_release,
        hdr_display=hdr_display,
        existing_language_tag=existing_language_tag,
        resulting_language_tag=resulting_language_tag,
        calculated_language_tag=inferred_lang_tag or None,
        parsed_episode_code=parsed_episode_code,
        parsed_episode_title=parsed_episode_title,
        normalized_name=normalized,
        multi_language_detected=multi_detected,
        language_tag_conflict=language_tag_conflict,
        resolution_conflict=resolution_conflict,
    )


def _build_target_name(
    normalized_name: str,
    team: str | None,
    *,
    remove_terms: tuple[str, ...],
) -> str:
    name = normalized_name
    if team:
        name = f"{name}-{team}"
    return _remove_terms_from_normalized_name(name, remove_terms)


def _detect_collision(
    source: Path,
    target: Path,
    *,
    changed: bool,
    case_only: bool,
    reserved_targets: dict[str, Path],
) -> tuple[bool, str]:
    reserved_key = str(target).lower()

    if changed and reserved_key in reserved_targets and reserved_targets[reserved_key] != source:
        return True, reserved_key

    if changed and target.exists() and target.resolve() != source.resolve() and not case_only:
        return True, reserved_key

    return False, reserved_key


def _warn_missing_tokens(missing_tokens: set[str]) -> None:
    if not missing_tokens:
        return
    from swirrl.core.i18n import tr
    from swirrl.ui.console import print_warning

    for token in sorted(missing_tokens):
        print_warning(
            tr(
                "renamer.warning.insert_after_token_not_found",
                default="Token not found for insertion: {token}",
                token=token,
            )
        )


def build_rename_plan(
    folder: Path,
    *,
    default_lang: str = DEFAULT_LANG,
    force_lang: bool = False,
    remove_terms: tuple[str, ...] = (),
    insert_after_pairs: tuple[tuple[str, str], ...] = (),
    profile: RenamerProfile | None = None,
    language_profile: LanguageTagProfile | None = None,
) -> list[RenamePlanItem]:
    """Build rename plan."""
    plan: list[RenamePlanItem] = []
    reserved_targets: dict[str, Path] = {}
    missing_tokens: set[str] = set()
    profile_terms = profile.junk_terms if profile else ()
    effective_remove_terms = tuple(dict.fromkeys((*profile_terms, *remove_terms)))
    media_files = _collect_media_files(folder)

    for file_path in media_files:
        info = probe_media_file(file_path)
        original_stem = _resolve_original_stem(file_path, insert_after_pairs, missing_tokens)
        stem, team = split_team(_remove_terms_from_stem(original_stem, effective_remove_terms))
        context = _build_rename_context(
            stem,
            default_lang=default_lang,
            force_lang=force_lang,
            remove_terms=effective_remove_terms,
            info=info,
            profile=profile,
            language_profile=language_profile,
        )
        normalized = _build_target_name(
            context.normalized_name,
            team,
            remove_terms=effective_remove_terms,
        )
        target = file_path.with_name(f"{normalized}{file_path.suffix}")

        source_name_lower = file_path.name.lower()
        target_name_lower = target.name.lower()

        changed = file_path.name != target.name
        case_only = changed and source_name_lower == target_name_lower
        collision, reserved_key = _detect_collision(
            file_path,
            target,
            changed=changed,
            case_only=case_only,
            reserved_targets=reserved_targets,
        )
        reserved_targets[reserved_key] = file_path

        plan.append(
            RenamePlanItem(
                source=file_path,
                target=target,
                reason="normalized",
                changed=changed,
                case_only=case_only,
                collision=collision,
                inferred_video_tag=context.inferred_video_tag or None,
                inferred_audio_tag=context.inferred_audio_tag or None,
                inferred_source=None,
                inferred_resolution=context.inferred_resolution or None,
                hdr_canonical=context.hdr_canonical or None,
                hdr_release_label=context.hdr_release or None,
                hdr_display_label=context.hdr_display or None,
                existing_language_tag=context.existing_language_tag,
                resulting_language_tag=context.resulting_language_tag,
                calculated_language_tag=context.calculated_language_tag,
                parsed_episode_code=context.parsed_episode_code,
                parsed_episode_title=context.parsed_episode_title,
                multi_language_detected=context.multi_language_detected,
                language_tag_conflict=context.language_tag_conflict,
                resolution_conflict=context.resolution_conflict,
            )
        )

    _warn_missing_tokens(missing_tokens)
    return plan
