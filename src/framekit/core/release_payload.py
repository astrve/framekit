from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

VIDEO_EXTENSIONS = {
    ".mkv",
    ".mp4",
    ".m4v",
    ".avi",
    ".mov",
    ".m2ts",
    ".ts",
    ".wmv",
}
NFO_EXTENSIONS = {".nfo"}

_SERIES_PATTERNS = (
    re.compile(r"(?i)(?:^|[ ._\-])s\d{1,2}e\d{1,3}(?:$|[ ._\-])"),
    re.compile(r"(?i)(?:^|[ ._\-])s\d{1,2}(?:$|[ ._\-])"),
    re.compile(r"(?i)(?:^|[ ._\-])\d{1,2}x\d{1,3}(?:$|[ ._\-])"),
)
_YEAR_RE = re.compile(r"^(?:19\d{2}|20\d{2})$")
_RESOLUTION_TOKENS = {
    "2160P": "2160p",
    "4K": "2160p",
    "UHD": "2160p",
    "1080P": "1080p",
    "1080I": "1080i",
    "720P": "720p",
    "576P": "576p",
    "480P": "480p",
}
_SOURCE_TOKENS = {
    "WEB": "WEB",
    "WEBDL": "WEB",
    "WEB-DL": "WEB",
    "WEBRIP": "WEBRip",
    "BLURAY": "BluRay",
    "BLU-RAY": "BluRay",
    "BDRIP": "BluRay",
    "BRRIP": "BluRay",
    "REMUX": "REMUX",
    "HDTV": "HDTV",
    "DVD": "DVD",
    "DVDRIP": "DVD",
}
_STOP_TOKENS = {
    *set(_RESOLUTION_TOKENS),
    *set(_SOURCE_TOKENS),
    "MULTI",
    "MULTI.VFF",
    "VFF",
    "VF2",
    "VFI",
    "VFQ",
    "VOSTFR",
    "TRUEFRENCH",
    "FRENCH",
    "ENGLISH",
    "FR",
    "EN",
    "ES",
    "DUAL",
    "AAC",
    "AC3",
    "EAC3",
    "DDP",
    "DTS",
    "TRUEHD",
    "FLAC",
    "ATMOS",
    "X264",
    "X265",
    "H264",
    "H265",
    "HEVC",
    "AVC",
    "HDR",
    "HDR10",
    "HDR10PLUS",
    "DV",
    "HLG",
}


@dataclass(frozen=True)
class ReleasePayload:
    """Resolved release payload directory and its immediate release files."""

    path: Path
    video_files: tuple[Path, ...]
    nfo_files: tuple[Path, ...]
    category: str
    score: int

    @property
    def primary_video(self) -> Path | None:
        return self.video_files[0] if self.video_files else None


def find_release_payload(path: Path, *, max_depth: int = 5) -> ReleasePayload | None:
    """Find the deepest useful release payload directory under ``path``.

    A payload directory is a folder that directly contains at least one video
    file. NFO files strongly boost the score because upload-ready releases are
    usually staged as ``mkv + nfo`` in the same final folder.
    """
    root = path.expanduser()
    if root.is_file():
        if root.suffix.lower() not in VIDEO_EXTENSIONS:
            return None
        return ReleasePayload(
            path=root.parent,
            video_files=(root,),
            nfo_files=tuple(_files_with_suffix(root.parent, NFO_EXTENSIONS)),
            category=infer_media_category(root.parent, (root,)),
            score=100,
        )
    if not root.is_dir():
        return None

    candidates = _candidate_payloads(root, max_depth=max_depth)

    if not candidates:
        return None
    return _best_payload(candidates)


def find_release_payloads(path: Path, *, max_depth: int = 5) -> list[ReleasePayload]:
    """Find one upload-ready payload per top-level release folder under ``path``."""
    root = path.expanduser()
    if root.is_file():
        payload = find_release_payload(root, max_depth=max_depth)
        return [payload] if payload else []
    if not root.is_dir():
        return []

    candidates = _candidate_payloads(root, max_depth=max_depth)
    if not candidates:
        return []

    groups: dict[str, list[ReleasePayload]] = {}
    for candidate in candidates:
        try:
            relative = candidate.path.relative_to(root)
        except ValueError:
            continue
        group_key = relative.parts[0] if relative.parts else "."
        groups.setdefault(group_key, []).append(candidate)

    child_groups = {key: value for key, value in groups.items() if key != "."}
    if len(child_groups) >= 2 or ("." not in groups and child_groups):
        payloads = [_best_payload(group) for group in child_groups.values()]
    else:
        payloads = [_best_payload(candidates)]

    return sorted(payloads, key=lambda item: str(item.path).lower())


def infer_media_category(path: Path, video_files: tuple[Path, ...] | list[Path]) -> str:
    """Infer seedbox category from release folder and video names."""
    haystack = " ".join([path.name, *(file.stem for file in video_files)])
    if any(pattern.search(haystack) for pattern in _SERIES_PATTERNS):
        return "series"
    return "movies"


def derive_library_folder_name(payload: ReleasePayload) -> str | None:
    """Build a readable library folder name from a release payload."""
    source = payload.primary_video.stem if payload.primary_video else payload.path.name
    parsed = _parse_release_label(source)
    if not parsed.title:
        return None

    title = _title_case(parsed.title)
    if parsed.season and payload.category == "series":
        title = f"{title} {parsed.season}"

    if parsed.year:
        title = f"{title} ({parsed.year})"

    if parsed.quality:
        return f"{title} - {parsed.quality}"
    return title


@dataclass(frozen=True)
class _ParsedReleaseLabel:
    title: str
    year: str
    season: str
    quality: str


def _parse_release_label(value: str) -> _ParsedReleaseLabel:
    stem = value.rsplit("-", 1)[0]
    normalized = _normalize_release_tokens(stem)
    tokens = [token for token in normalized.split(".") if token]

    year = next((token for token in tokens if _YEAR_RE.match(token)), "")
    season = _extract_season(tokens)
    resolution = _extract_resolution(tokens)
    source = _extract_source(tokens)
    title_tokens = _extract_title_tokens(tokens, year=year)

    quality = " ".join(part for part in (resolution, source) if part)
    return _ParsedReleaseLabel(
        title=" ".join(title_tokens).strip(),
        year=year,
        season=season,
        quality=quality,
    )


def _iter_candidate_dirs(root: Path, *, max_depth: int) -> list[Path]:
    folders = [root]
    try:
        children = list(root.rglob("*"))
    except OSError:
        return folders
    for child in children:
        if not child.is_dir():
            continue
        try:
            depth = len(child.relative_to(root).parts)
        except ValueError:
            continue
        if depth <= max_depth:
            folders.append(child)
    return folders


def _candidate_payloads(root: Path, *, max_depth: int) -> list[ReleasePayload]:
    candidates: list[ReleasePayload] = []
    for folder in _iter_candidate_dirs(root, max_depth=max_depth):
        video_files = tuple(_files_with_suffix(folder, VIDEO_EXTENSIONS))
        if not video_files:
            continue
        nfo_files = tuple(_files_with_suffix(folder, NFO_EXTENSIONS))
        candidates.append(
            ReleasePayload(
                path=folder,
                video_files=video_files,
                nfo_files=nfo_files,
                category=infer_media_category(folder, video_files),
                score=_score_candidate(root, folder, video_files, nfo_files),
            )
        )
    return candidates


def _best_payload(candidates: list[ReleasePayload]) -> ReleasePayload:
    return max(candidates, key=lambda item: (item.score, _payload_size(item), len(item.path.parts)))


def _files_with_suffix(folder: Path, suffixes: set[str]) -> list[Path]:
    try:
        files = list(folder.iterdir())
    except OSError:
        return []
    return sorted(
        file
        for file in files
        if file.is_file() and file.suffix.lower() in suffixes and "sample" not in file.stem.lower()
    )


def _score_candidate(
    root: Path,
    folder: Path,
    video_files: tuple[Path, ...],
    nfo_files: tuple[Path, ...],
) -> int:
    score = 100
    if nfo_files:
        score += 500
    if folder.name.lower() not in {"sample", "samples"}:
        score += 50
    if folder.parent.name.lower() == "release":
        score += 40
    if _looks_like_release_name(folder.name):
        score += 30
    if folder == root and any(child.is_dir() for child in _safe_iterdir(folder)):
        score -= 80
    score += min(len(video_files), 5) * 10
    return score


def _payload_size(payload: ReleasePayload) -> int:
    return sum(file.stat().st_size for file in payload.video_files if file.exists())


def _safe_iterdir(folder: Path) -> list[Path]:
    try:
        return list(folder.iterdir())
    except OSError:
        return []


def _looks_like_release_name(value: str) -> bool:
    upper = value.upper()
    return bool(re.search(r"(?:19\d{2}|20\d{2})", upper)) or any(
        token in upper for token in ("1080P", "2160P", "720P", "WEB", "BLURAY", "REMUX")
    )


def _normalize_release_tokens(value: str) -> str:
    replacements = (
        (r"(?i)\bWEB[ ._\-]?DL\b", "WEB"),
        (r"(?i)\bWEB[ ._\-]?RIP\b", "WEBRip"),
        (r"(?i)\bH[ ._\-]?264\b", "H264"),
        (r"(?i)\bH[ ._\-]?265\b", "H265"),
        (r"(?i)\bX[ ._\-]?264\b", "X264"),
        (r"(?i)\bX[ ._\-]?265\b", "X265"),
        (r"(?i)\bS(\d{1,2})E(\d{1,3})\b", _format_episode_match),
        (r"(?i)\bS(\d{1,2})\b", _format_season_match),
    )
    result = value.replace("_", ".")
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result)
    result = re.sub(r"[ \-]+", ".", result)
    return re.sub(r"\.+", ".", result).strip(".")


def _format_episode_match(match: re.Match[str]) -> str:
    return f"S{int(match.group(1)):02d}E{int(match.group(2)):02d}"


def _format_season_match(match: re.Match[str]) -> str:
    return f"S{int(match.group(1)):02d}"


def _extract_season(tokens: list[str]) -> str:
    for token in tokens:
        match = re.match(r"(?i)^S(\d{2})(?:E\d{2,3})?$", token)
        if match:
            return f"S{int(match.group(1)):02d}"
    return ""


def _extract_resolution(tokens: list[str]) -> str:
    for token in tokens:
        mapped = _RESOLUTION_TOKENS.get(token.upper())
        if mapped:
            return mapped
    return ""


def _extract_source(tokens: list[str]) -> str:
    for token in tokens:
        mapped = _SOURCE_TOKENS.get(token.upper())
        if mapped:
            return mapped
    return ""


def _extract_title_tokens(tokens: list[str], *, year: str) -> list[str]:
    title_tokens: list[str] = []
    for token in tokens:
        upper = token.upper()
        if token == year or _is_episode_token(upper) or upper in _STOP_TOKENS:
            break
        title_tokens.append(token)
    return title_tokens


def _is_episode_token(token: str) -> bool:
    return bool(re.match(r"^S\d{2}(?:E\d{2,3})?$", token))


def _title_case(value: str) -> str:
    words = re.sub(r"\s+", " ", value.replace(".", " ")).strip().split(" ")
    return " ".join(word.capitalize() if not word.isupper() else word.title() for word in words)
