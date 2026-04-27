from __future__ import annotations

import re
from pathlib import Path

try:
    from pathvalidate import sanitize_filename  # type: ignore[import]
except ImportError:
    # Provide a minimal sanitize_filename implementation if pathvalidate is unavailable.
    import re as _re

    def sanitize_filename(filename: str, replacement_text: str = "_") -> str:
        """
        Sanitize a filename by replacing characters illegal on most filesystems.
        This fallback keeps alphanumeric characters, dots, dashes and underscores,
        and replaces any other sequence with the given replacement_text.
        """
        # Replace any run of invalid characters with the replacement text
        return _re.sub(r"[^A-Za-z0-9._-]+", replacement_text, filename)


EPISODE_TOKEN_RE = re.compile(r"(?i)E\d{1,3}(?=([. _-]|$))")


def release_name_from_mkv_paths(paths: list[Path] | tuple[Path, ...]) -> str:
    mkv_paths = sorted(
        (Path(path) for path in paths if Path(path).suffix.lower() == ".mkv"),
        key=lambda p: p.name.lower(),
    )
    if not mkv_paths:
        return "release"
    first = mkv_paths[0]
    name = first.stem
    if len(mkv_paths) > 1:
        name = EPISODE_TOKEN_RE.sub("", name, count=1).strip(" ._-:") or first.stem
    return sanitize_filename(name, replacement_text="_").strip(" .") or "release"


def torrent_name_from_payload(path: Path) -> str:
    payload = Path(path)
    if payload.is_file():
        return sanitize_filename(payload.stem, replacement_text="_").strip(" .") or "release"
    mkv_files = sorted(payload.rglob("*.mkv"), key=lambda p: p.name.lower())
    if mkv_files:
        return release_name_from_mkv_paths(mkv_files)
    return sanitize_filename(payload.name, replacement_text="_").strip(" .") or "release"


def sanitized_release_dir(template: str, release: str) -> str:
    """
    Build a release folder name from a template containing a `{release}` placeholder.

    The release value is sanitized to avoid invalid filesystem characters and leading/trailing
    separators. A missing sanitize_filename function is handled by falling back to a simple
    regular expression replacement.
    """
    try:
        sanitized = sanitize_filename(release, replacement_text="_").strip(" ._-")
    except Exception:
        # Fallback: remove everything except alphanumerics, dot, dash and underscore
        import re as _fallback_re

        sanitized = _fallback_re.sub(r"[^A-Za-z0-9._-]+", "_", release).strip(" ._-")
    return template.format(release=sanitized)
