from __future__ import annotations

import re
from collections.abc import Callable

VIDEO_EXTENSIONS = {".mkv"}

REMOVE_TOKENS = {"PMTP", "CP", "CR", "AMZN"}

LANGUAGE_TAGS = {"MULTI.VFF", "MULTI.VF2", "VFF", "VFI", "VFQ", "VF2", "VOSTFR"}

# Tags that indicate a single-language track; if multiple audio tracks are
# detected in the media file, these should be upgraded to MULTI.<tag>.
SINGLE_LANG_TAGS = {"VFF", "VFI", "VFQ", "VF2", "VOSTFR"}

DEFAULT_LANG = "MULTI.VFF"

FRENCH_TITLE_ALIASES = {
    "THE.SIMPSONS": "LES.SIMPSONS",
    "THE.SIMPSON": "LES.SIMPSON",
}

COMPOUND_TOKENS: dict[str, str] = {
    "WEBRip": "__WEBRIP__",
    "EAC3.2.0": "__EAC3_2_0__",
    "EAC3.5.1": "__EAC3_5_1__",
    "EAC3.7.1": "__EAC3_7_1__",
    "AC3.2.0": "__AC3_2_0__",
    "AC3.5.1": "__AC3_5_1__",
    "AC3.7.1": "__AC3_7_1__",
    "AAC.2.0": "__AAC_2_0__",
    "AAC.5.1": "__AAC_5_1__",
    "AAC.7.1": "__AAC_7_1__",
    "MULTI.VFF": "__MULTI_VFF__",
    "MULTI.VF2": "__MULTI_VF2__",
}

COMPOUND_RESTORE: dict[str, str] = {v: k for k, v in COMPOUND_TOKENS.items()}

RAW_REPLACEMENTS: list[tuple[str, str]] = [
    (r"(?i)\bS(\d{2})E(\d{2})\b", r"S\1E\2"),
    (r"(?i)\bH[ ._-]?264\b", "H264"),
    (r"(?i)\bH[ ._-]?265\b", "H265"),
    (r"(?i)\bX[ ._-]?264\b", "x264"),
    (r"(?i)\bX[ ._-]?265\b", "x265"),
    (r"(?i)\bAAC[ ._-]?2[ ._-]?0\b", "AAC.2.0"),
    (r"(?i)\bAAC[ ._-]?5[ ._-]?1\b", "AAC.5.1"),
    (r"(?i)\bAAC[ ._-]?7[ ._-]?1\b", "AAC.7.1"),
    (r"(?i)\bDDP[ ._-]?2[ ._-]?0\b", "EAC3.2.0"),
    (r"(?i)\bDDP[ ._-]?5[ ._-]?1\b", "EAC3.5.1"),
    (r"(?i)\bDDP[ ._-]?7[ ._-]?1\b", "EAC3.7.1"),
    (r"(?i)\bAC3[ ._-]?2[ ._-]?0\b", "AC3.2.0"),
    (r"(?i)\bAC3[ ._-]?5[ ._-]?1\b", "AC3.5.1"),
    (r"(?i)\bAC3[ ._-]?7[ ._-]?1\b", "AC3.7.1"),
    (r"(?i)\bWEB[ ._-]?DL\b", "WEB"),
    (r"(?i)\bWEB[ ._-]?RIP\b", "WEBRip"),
    # Normalize HDR10+ variants → canonical token HDR10PLUS.
    # Longer patterns first to avoid partial replacement.
    (r"(?i)(?<![A-Za-z0-9])HDR10Plus(?![A-Za-z0-9])", "HDR10PLUS"),
    (r"(?i)(?<![A-Za-z0-9])HDR10P(?![A-Za-z0-9])", "HDR10PLUS"),
    (r"(?i)(?<![A-Za-z0-9])HDR10\+", "HDR10PLUS"),
]

EPISODE_TITLE_STOP_TOKENS = {
    "MULTI",
    "VFF",
    "VFI",
    "VFQ",
    "VF2",
    "VOSTFR",
    "2160P",
    "1440P",
    "1080P",
    "720P",
    "480P",
    "WEB",
    "WEBRIP",
    "WEB-DL",
    "WEBDL",
    "BLURAY",
    "HDR",
    "HDR10",
    "HDR10PLUS",
    "DV",
    "HLG",
    "EAC3",
    "AC3",
    "AAC",
    "DTS",
    "TRUEHD",
    "FLAC",
    "X264",
    "X265",
    "H264",
    "H265",
}

EPISODE_TITLE_STOP_PREFIXES = ("DDP", "EAC3", "AC3", "AAC", "DTS", "TRUEHD", "FLAC")


def split_team(stem: str) -> tuple[str, str | None]:
    """Handle split team."""
    match = re.search(r"-(?P<team>[A-Za-z0-9]{2,10})$", stem)
    if not match:
        return stem, None

    before = stem[: match.start()]
    if "." not in before:
        return stem, None

    return before, match.group("team").upper()


def extract_existing_language_tag(parts: list[str]) -> str | None:
    """Handle extract existing language tag."""
    for part in parts:
        if part in LANGUAGE_TAGS:
            return part
    return None


def replace_language_tag(parts: list[str], lang_tag: str) -> list[str]:
    """Handle replace language tag."""
    if not lang_tag:
        # Empty tag means remove any existing language tag
        return [p for p in parts if p not in LANGUAGE_TAGS]

    replaced = False
    new_parts: list[str] = []

    for part in parts:
        if part in LANGUAGE_TAGS:
            if not replaced:
                new_parts.append(lang_tag)
                replaced = True
            continue
        new_parts.append(part)

    if replaced:
        return new_parts

    return ensure_language_tag(new_parts, lang_tag)


def ensure_language_tag(parts: list[str], default_lang: str) -> list[str]:
    """Ensure language tag."""
    if not default_lang:
        return parts
    if any(part in LANGUAGE_TAGS for part in parts):
        return parts

    for index, part in enumerate(parts):
        if re.fullmatch(r"S\d{2}E\d{2}", part) or re.fullmatch(r"S\d{2}", part):
            return [*parts[: index + 1], default_lang, *parts[index + 1 :]]

    return [default_lang, *parts]


def _language_prefers_french_title(lang_tag: str | None) -> bool:
    return bool(lang_tag and lang_tag.upper() in LANGUAGE_TAGS)


def _apply_localized_title_alias(text: str, lang_tag: str | None) -> str:
    if not _language_prefers_french_title(lang_tag):
        return text
    for source, target in FRENCH_TITLE_ALIASES.items():
        if text == source or text.startswith(source + "."):
            return target + text[len(source) :]
    return text


def extract_episode_code(text: str) -> str | None:
    """Handle extract episode code."""
    normalized = text.replace("_", ".")
    normalized = re.sub(r"\.+", ".", normalized).strip(".")

    match = re.search(r"(^|\.)(S\d{2}E\d{2})(\.|$)", normalized, flags=re.IGNORECASE)
    if match:
        return match.group(2).upper()

    match = re.search(r"(^|\.)(S\d{2})(\.|$)", normalized, flags=re.IGNORECASE)
    if match:
        return match.group(2).upper()

    return None


def extract_episode_title(base: str) -> str | None:
    """Handle extract episode title."""
    normalized = base.replace("_", ".")
    normalized = re.sub(r"\.+", ".", normalized).strip(".")

    parts = [part for part in normalized.split(".") if part]
    if not parts:
        return None

    episode_code = extract_episode_code(normalized)
    if not episode_code:
        return None

    code_index = _episode_code_index(parts, episode_code)
    if code_index is None:
        return None

    title_parts: list[str] = []
    for part in parts[code_index + 1 :]:
        if _is_episode_title_stop_token(part):
            break
        title_parts.append(part)

    if not title_parts:
        return None

    return " ".join(title_parts).strip() or None


def _episode_code_index(parts: list[str], episode_code: str) -> int | None:
    for index, part in enumerate(parts):
        if part.upper() == episode_code.upper():
            return index
    return None


def _is_episode_title_stop_token(part: str) -> bool:
    upper = part.upper()
    if upper in EPISODE_TITLE_STOP_TOKENS:
        return True
    if upper.startswith(EPISODE_TITLE_STOP_PREFIXES):
        return True
    if re.fullmatch(r"(X264|X265|H264|H265)", upper):
        return True
    return bool(re.fullmatch(r"\d+", upper))


def _apply_raw_replacements(base: str) -> str:
    value = base.replace("_", ".")
    for pattern, repl in RAW_REPLACEMENTS:
        value = re.sub(pattern, repl, value)
    value = re.sub(r"[.\-]+", ".", value)
    return re.sub(r"\.+", ".", value).strip(".")


def _protect_compound_tokens(base: str) -> str:
    value = base
    for canonical, sentinel in COMPOUND_TOKENS.items():
        value = value.replace(canonical, sentinel)
    return value


def _split_restored_parts(base: str) -> list[str]:
    return [COMPOUND_RESTORE.get(part, part) for part in base.split(".") if part]


def _remove_tokens(parts: list[str]) -> list[str]:
    return [part for part in parts if part.upper() not in REMOVE_TOKENS]


def _merge_multi_language_tokens(parts: list[str]) -> list[str]:
    merged: list[str] = []
    index = 0
    while index < len(parts):
        token = parts[index]
        if token.upper() != "MULTI":
            merged.append(token)
            index += 1
            continue

        next_token = parts[index + 1].upper() if index + 1 < len(parts) else ""
        if next_token in {"VFF", "VFQ", "VF2"}:
            merged.append(f"MULTI.{next_token}")
            index += 2
            continue
        merged.append("MULTI.VFF")
        index += 1
    return merged


def _apply_language_rules(
    parts: list[str], *, default_lang: str, force_lang: bool
) -> tuple[list[str], str | None, str | None]:
    existing_language_tag = extract_existing_language_tag(parts)
    if force_lang:
        updated_parts = replace_language_tag(parts, default_lang)
    else:
        updated_parts = ensure_language_tag(parts, default_lang)
    resulting_language_tag = extract_existing_language_tag(updated_parts)
    return updated_parts, existing_language_tag, resulting_language_tag


def _replace_first_matching(
    parts: list[str], predicate: Callable[[str], bool], replacement: str
) -> list[str]:
    replaced = False
    result: list[str] = []
    for part in parts:
        if not replaced and predicate(part):
            result.append(replacement)
            replaced = True
        else:
            result.append(part)
    return result


def _apply_preferred_resolution(parts: list[str], preferred_resolution: str) -> list[str]:
    if not preferred_resolution:
        return parts
    resolution_tokens = {"2160P", "1440P", "1080P", "720P", "480P"}
    return _replace_first_matching(
        parts,
        lambda part: part.upper() in resolution_tokens,
        preferred_resolution,
    )


def _apply_preferred_audio(parts: list[str], preferred_audio_tag: str) -> list[str]:
    if not preferred_audio_tag:
        return parts
    audio_prefixes = ("EAC3", "AC3", "AAC", "DTS", "TRUEHD", "FLAC")
    return _replace_first_matching(
        parts,
        lambda part: part.upper().startswith(audio_prefixes),
        preferred_audio_tag,
    )


def _apply_preferred_video(parts: list[str], preferred_video_tag: str) -> list[str]:
    if not preferred_video_tag:
        return parts
    video_tokens = {"X264", "X265", "H264", "H265", "x264", "x265"}
    return _replace_first_matching(
        parts,
        lambda part: part in video_tokens,
        preferred_video_tag,
    )


def _apply_preferred_hdr(parts: list[str], preferred_hdr: str) -> list[str]:
    if not preferred_hdr:
        return parts
    hdr_tokens = {"HDR", "HDR10", "HDR10PLUS", "DV", "HLG"}
    if any(part.upper() in hdr_tokens for part in parts):
        return parts
    return [*parts, preferred_hdr]


def _finalize_text(parts: list[str], resulting_language_tag: str | None) -> str:
    text = ".".join(parts).upper()
    text = text.replace("WEBRIP", "WEBRip")
    text = text.replace("X264", "x264")
    text = text.replace("X265", "x265")
    text = _apply_localized_title_alias(text, resulting_language_tag)
    return re.sub(r"\.+", ".", text).strip(".")


def _metadata_source_text(original_for_metadata: str) -> str:
    metadata_source = original_for_metadata.replace("_", ".")
    return re.sub(r"\.+", ".", metadata_source).strip(".")


def normalize_name_part(
    base: str,
    preferred_video_tag: str = "",
    preferred_audio_tag: str = "",
    preferred_resolution: str = "",
    preferred_hdr: str = "",
    default_lang: str = DEFAULT_LANG,
    force_lang: bool = False,
) -> tuple[str, str | None, str | None, str | None, str | None]:
    """Normalise name part."""
    original_for_metadata = base
    transformed = _apply_raw_replacements(base)
    transformed = _protect_compound_tokens(transformed)

    parts = _split_restored_parts(transformed)
    parts = _remove_tokens(parts)
    parts = _merge_multi_language_tokens(parts)

    parts, existing_language_tag, resulting_language_tag = _apply_language_rules(
        parts, default_lang=default_lang, force_lang=force_lang
    )
    parts = _apply_preferred_resolution(parts, preferred_resolution)
    parts = _apply_preferred_audio(parts, preferred_audio_tag)
    parts = _apply_preferred_video(parts, preferred_video_tag)
    parts = _apply_preferred_hdr(parts, preferred_hdr)

    text = _finalize_text(parts, resulting_language_tag)
    metadata_source = _metadata_source_text(original_for_metadata)

    episode_code = extract_episode_code(metadata_source)
    episode_title = extract_episode_title(metadata_source)

    return (
        re.sub(r"\.+", ".", text).strip("."),
        existing_language_tag,
        resulting_language_tag,
        episode_code,
        episode_title,
    )
