from __future__ import annotations

import re

VIDEO_EXTENSIONS = {".mkv"}

REMOVE_TOKENS = {"PMTP", "CP", "CR", "AMZN"}

LANGUAGE_TAGS = {"MULTI.VFF", "MULTI.VF2", "VFF", "VFI", "VFQ", "VF2", "VOSTFR"}

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
]


def split_team(stem: str) -> tuple[str, str | None]:
    match = re.search(r"-(?P<team>[A-Za-z0-9]{2,10})$", stem)
    if not match:
        return stem, None

    before = stem[: match.start()]
    if "." not in before:
        return stem, None

    return before, match.group("team").upper()


def extract_existing_language_tag(parts: list[str]) -> str | None:
    for part in parts:
        if part in LANGUAGE_TAGS:
            return part
    return None


def replace_language_tag(parts: list[str], lang_tag: str) -> list[str]:
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
    if any(part in LANGUAGE_TAGS for part in parts):
        return parts

    for index, part in enumerate(parts):
        if re.fullmatch(r"S\d{2}E\d{2}", part) or re.fullmatch(r"S\d{2}", part):
            return parts[: index + 1] + [default_lang] + parts[index + 1 :]

    return [default_lang] + parts


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
    normalized = base.replace("_", ".")
    normalized = re.sub(r"\.+", ".", normalized).strip(".")

    parts = [part for part in normalized.split(".") if part]
    if not parts:
        return None

    episode_code = extract_episode_code(normalized)
    if not episode_code:
        return None

    try:
        code_index = next(
            index for index, part in enumerate(parts) if part.upper() == episode_code.upper()
        )
    except StopIteration:
        return None

    stop_tokens = {
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

    title_parts: list[str] = []

    for part in parts[code_index + 1 :]:
        upper = part.upper()

        if upper in stop_tokens:
            break

        if upper.startswith(("DDP", "EAC3", "AC3", "AAC", "DTS", "TRUEHD", "FLAC")):
            break

        if re.fullmatch(r"(X264|X265|H264|H265)", upper):
            break

        if re.fullmatch(r"\d+", upper):
            break

        title_parts.append(part)

    if not title_parts:
        return None

    return " ".join(title_parts).strip() or None


def normalize_name_part(
    base: str,
    preferred_video_tag: str = "",
    preferred_audio_tag: str = "",
    preferred_resolution: str = "",
    preferred_hdr: str = "",
    default_lang: str = DEFAULT_LANG,
    force_lang: bool = False,
) -> tuple[str, str | None, str | None, str | None, str | None]:
    original_for_metadata = base

    base = base.replace("_", ".")

    for pattern, repl in RAW_REPLACEMENTS:
        base = re.sub(pattern, repl, base)

    base = re.sub(r"[.\-]+", ".", base)
    base = re.sub(r"\.+", ".", base).strip(".")

    for canonical, sentinel in COMPOUND_TOKENS.items():
        base = base.replace(canonical, sentinel)

    parts = [COMPOUND_RESTORE.get(part, part) for part in base.split(".") if part]
    parts = [part for part in parts if part.upper() not in REMOVE_TOKENS]

    merged: list[str] = []
    index = 0
    while index < len(parts):
        token = parts[index]
        if token.upper() == "MULTI":
            next_token = parts[index + 1].upper() if index + 1 < len(parts) else ""
            if next_token in {"VFF", "VFQ", "VF2"}:
                merged.append(f"MULTI.{next_token}")
                index += 2
            else:
                merged.append("MULTI.VFF")
                index += 1
        else:
            merged.append(token)
            index += 1

    existing_language_tag = extract_existing_language_tag(merged)

    if force_lang:
        merged = replace_language_tag(merged, default_lang)
    else:
        merged = ensure_language_tag(merged, default_lang)

    resulting_language_tag = extract_existing_language_tag(merged)

    if preferred_resolution:
        resolution_tokens = {"2160P", "1440P", "1080P", "720P", "480P"}
        replaced = False
        new_parts: list[str] = []
        for part in merged:
            if not replaced and part.upper() in resolution_tokens:
                new_parts.append(preferred_resolution)
                replaced = True
            else:
                new_parts.append(part)
        merged = new_parts

    if preferred_audio_tag:
        audio_prefixes = ("EAC3", "AC3", "AAC", "DTS", "TRUEHD", "FLAC")
        replaced = False
        new_parts = []
        for part in merged:
            if not replaced and part.upper().startswith(audio_prefixes):
                new_parts.append(preferred_audio_tag)
                replaced = True
            else:
                new_parts.append(part)
        merged = new_parts

    if preferred_video_tag:
        video_tokens = {"X264", "X265", "H264", "H265", "x264", "x265"}
        replaced = False
        new_parts = []
        for part in merged:
            if not replaced and part in video_tokens:
                new_parts.append(preferred_video_tag)
                replaced = True
            else:
                new_parts.append(part)
        merged = new_parts

    if preferred_hdr:
        hdr_tokens = {"HDR", "HDR10", "HDR10PLUS", "DV", "HLG"}
        if not any(part.upper() in hdr_tokens for part in merged):
            merged.append(preferred_hdr)

    text = ".".join(merged).upper()
    text = text.replace("WEBRIP", "WEBRip")
    text = text.replace("X264", "x264")
    text = text.replace("X265", "x265")
    text = _apply_localized_title_alias(text, resulting_language_tag)

    metadata_source = original_for_metadata.replace("_", ".")
    metadata_source = re.sub(r"\.+", ".", metadata_source).strip(".")

    episode_code = extract_episode_code(metadata_source)
    episode_title = extract_episode_title(metadata_source)

    return (
        re.sub(r"\.+", ".", text).strip("."),
        existing_language_tag,
        resulting_language_tag,
        episode_code,
        episode_title,
    )
