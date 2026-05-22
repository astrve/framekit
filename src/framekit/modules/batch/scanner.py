"""Directory scanning for batch processing."""

from __future__ import annotations

from pathlib import Path

# Extensions accepted as a "release video"
VIDEO_EXTENSIONS: tuple[str, ...] = (".mkv", ".mp4", ".m4v")


def _has_video(folder: Path, recursive: bool = False) -> bool:
    """Return True if folder (optionally recursive) contains any video file."""
    if not folder.exists() or not folder.is_dir():
        return False
    pattern_iter = folder.rglob if recursive else folder.glob
    return any(next(iter(pattern_iter(f"*{ext}")), None) is not None for ext in VIDEO_EXTENSIONS)


def is_valid_release(folder: Path) -> bool:
    """A folder is a valid release if it directly contains at least one video file.

    Subdirectory videos do NOT make it a release (avoids accidentally treating a
    parent folder as the release).
    """
    return _has_video(folder, recursive=False)


def scan_parent_folder(
    parent_path: Path, *, recursive: bool = False, max_depth: int = 2
) -> list[Path]:
    """Scan a parent folder for release subdirectories.

    Modes:
      - recursive=False (default): treat each immediate subdirectory as a candidate.
      - recursive=True: walk up to `max_depth` levels deep looking for video-containing folders.
    """
    if not parent_path.exists() or not parent_path.is_dir():
        return []

    releases = (
        _scan_recursive_releases(parent_path, max_depth=max_depth)
        if recursive
        else _scan_direct_releases(parent_path)
    )
    return _dedupe_and_sort_releases(releases)


def _scan_direct_releases(parent_path: Path) -> list[Path]:
    return [child for child in parent_path.iterdir() if child.is_dir() and is_valid_release(child)]


def _scan_recursive_releases(parent_path: Path, *, max_depth: int) -> list[Path]:
    releases: list[Path] = []

    def _walk(folder: Path, depth: int) -> None:
        if depth > max_depth:
            return
        if is_valid_release(folder):
            releases.append(folder)
            return
        for child in _iter_child_dirs(folder):
            _walk(child, depth + 1)

    for child in _iter_child_dirs(parent_path):
        _walk(child, 1)
    return releases


def _iter_child_dirs(folder: Path) -> list[Path]:
    try:
        return [child for child in folder.iterdir() if child.is_dir()]
    except (PermissionError, OSError):
        return []


def _dedupe_and_sort_releases(releases: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    unique: list[Path] = []
    for release_path in releases:
        resolved = release_path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(release_path)
    return sorted(unique, key=lambda path: path.name.lower())


def count_video_files(folder: Path) -> int:
    """Count video files directly inside `folder` (non-recursive)."""
    if not folder.exists() or not folder.is_dir():
        return 0
    return sum(1 for ext in VIDEO_EXTENSIONS for _ in folder.glob(f"*{ext}"))


# Backward-compat shim: legacy callers use count_mkv_files
def count_mkv_files(folder: Path) -> int:
    """Count .mkv files directly inside `folder` (kept for legacy callers)."""
    if not folder.exists() or not folder.is_dir():
        return 0
    return len(list(folder.glob("*.mkv")))


def detect_release_type(folder: Path) -> str:
    """Heuristic release-type detection.

    Returns "series" if multiple video files (likely episodes), "movie" if exactly one,
    "unknown" otherwise.
    """
    if not is_valid_release(folder):
        return "unknown"
    n = count_video_files(folder)
    if n == 0:
        return "unknown"
    if n == 1:
        return "movie"
    return "series"


def get_release_info(folder: Path) -> dict:
    """Summary dict about a candidate release folder."""
    return {
        "path": folder,
        "name": folder.name,
        "is_valid": is_valid_release(folder),
        "video_count": count_video_files(folder),
        "mkv_count": count_mkv_files(folder),
        "type": detect_release_type(folder),
    }
