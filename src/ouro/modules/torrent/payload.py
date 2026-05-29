from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from ouro.core.i18n import tr
from ouro.core.naming import release_name_from_mkv_paths, torrent_name_from_payload


@dataclass(frozen=True, slots=True)
class TorrentPayloadCandidate:
    """Torrent payload candidate."""

    label: str
    path: Path
    files: tuple[Path, ...]
    name: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class TorrentPayload:
    """Torrent payload."""

    path: Path
    files: tuple[Path, ...]
    name: str
    ignored_files: tuple[Path, ...] = ()
    mode: str = "auto"


VIDEO_SUFFIXES = {".mkv"}
EPISODE_TOKEN_RE = re.compile(r"(?i)E\d{1,3}(?=([. _-]|$))")


def _media_group_name(paths: tuple[Path, ...]) -> str:
    if not paths:
        return "release"
    if len(paths) > 1:
        first = sorted(paths, key=lambda p: p.name.lower())[0]
        name = EPISODE_TOKEN_RE.sub("", first.stem, count=1).strip(" ._-:") or first.stem
        return release_name_from_mkv_paths([first.with_name(f"{name}{first.suffix}")])
    return release_name_from_mkv_paths(paths)


def _group_root_media(paths: tuple[Path, ...]) -> tuple[tuple[str, tuple[Path, ...]], ...]:
    groups: dict[str, list[Path]] = {}
    for path in paths:
        stem = EPISODE_TOKEN_RE.sub("", path.stem, count=1).strip(" ._-:") or path.stem
        groups.setdefault(stem.lower(), []).append(path)
    result: list[tuple[str, tuple[Path, ...]]] = []
    for items in groups.values():
        grouped = tuple(sorted(items, key=lambda p: p.name.lower()))
        result.append((_media_group_name(grouped), grouped))
    return tuple(sorted(result, key=lambda item: item[0].lower()))


def _mkv_files_at(path: Path) -> tuple[Path, ...]:
    results: list[Path] = []
    for item in path.iterdir():
        if not item.is_file() or item.suffix.lower() not in VIDEO_SUFFIXES:
            continue
        if item.is_symlink():
            logger.warning("Skipping symlink in torrent payload: {}", item)
            continue
        results.append(item)
    return tuple(sorted(results, key=lambda p: p.name.lower()))


def _mkv_files_recursive(path: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(
            (item for item in path.rglob("*.mkv") if not item.is_symlink()),
            key=lambda p: str(p).lower(),
        )
    )


def _sidecar_files(path: Path, selected: tuple[Path, ...]) -> tuple[Path, ...]:
    selected_set = {item.resolve() for item in selected if item.exists()}
    siblings = path.parent.iterdir() if path.is_file() else path.rglob("*")
    ignored: list[Path] = []
    for item in siblings:
        if not item.is_file() or item.suffix.lower() == ".torrent":
            continue
        if item.is_symlink():
            logger.warning("Skipping symlink in sidecar scan: {}", item)
            continue
        try:
            resolved = item.resolve()
        except OSError:
            resolved = item
        if resolved not in selected_set:
            ignored.append(item)
    return tuple(sorted(ignored, key=lambda p: str(p).lower()))


def _candidate_description(count: int) -> str:
    return tr(
        "torrent.payload.subfolder",
        default="{count} media file(s) in subfolder",
        count=count,
    )


def _append_root_media_candidates(
    *, candidates: list[TorrentPayloadCandidate], target: Path
) -> None:
    root_mkv = _mkv_files_at(target)
    if not root_mkv:
        return
    for name, files in _group_root_media(root_mkv):
        candidates.append(
            TorrentPayloadCandidate(
                label=name,
                path=target,
                files=files,
                name=name,
                description=tr(
                    "torrent.payload.root_media",
                    default="{count} media file(s) at selected folder root",
                    count=len(files),
                ),
            )
        )


def _append_release_folder_candidates(
    *, candidates: list[TorrentPayloadCandidate], release_dir: Path
) -> None:
    release_root_mkv = _mkv_files_at(release_dir)
    if release_root_mkv:
        candidates.append(
            TorrentPayloadCandidate(
                label=f"{release_dir.name}/",
                path=release_dir,
                files=release_root_mkv,
                name=release_name_from_mkv_paths(release_root_mkv),
                description=_candidate_description(len(release_root_mkv)),
            )
        )
    for sub in sorted(
        (item for item in release_dir.iterdir() if item.is_dir()), key=lambda p: p.name.lower()
    ):
        _append_subfolder_candidate(candidates=candidates, folder=sub)


def _append_subfolder_candidate(*, candidates: list[TorrentPayloadCandidate], folder: Path) -> None:
    sub_files = _mkv_files_recursive(folder)
    if not sub_files:
        return
    candidates.append(
        TorrentPayloadCandidate(
            label=f"{folder.name}/",
            path=folder,
            files=sub_files,
            name=release_name_from_mkv_paths(sub_files),
            description=_candidate_description(len(sub_files)),
        )
    )


def _append_subfolder_candidates(
    *, candidates: list[TorrentPayloadCandidate], target: Path
) -> None:
    for child in sorted(
        (item for item in target.iterdir() if item.is_dir()), key=lambda p: p.name.lower()
    ):
        if child.name.lower() == "release":
            _append_release_folder_candidates(candidates=candidates, release_dir=child)
            continue
        _append_subfolder_candidate(candidates=candidates, folder=child)


def discover_torrent_payload_candidates(path: Path) -> tuple[TorrentPayloadCandidate, ...]:
    """Handle discover torrent payload candidates."""
    target = Path(path)
    if target.is_file():
        if target.suffix.lower() not in VIDEO_SUFFIXES:
            return ()
        return (
            TorrentPayloadCandidate(
                label=target.name,
                path=target,
                files=(target,),
                name=torrent_name_from_payload(target),
                description=tr("torrent.payload.single_file", default="Single media file"),
            ),
        )

    candidates: list[TorrentPayloadCandidate] = []
    _append_root_media_candidates(candidates=candidates, target=target)
    _append_subfolder_candidates(candidates=candidates, target=target)
    return tuple(candidates)


def _resolve_folder_mode_payload(target: Path, mode: str) -> TorrentPayload:
    files = tuple(
        sorted(
            (
                item
                for item in ([target] if target.is_file() else target.rglob("*"))
                if item.is_file() and item.suffix.lower() != ".torrent"
            ),
            key=lambda p: str(p).lower(),
        )
    )
    if not files:
        raise ValueError(
            tr("torrent.error.no_files", default="No files found for torrent creation.")
        )
    return TorrentPayload(
        path=target, files=files, name=torrent_name_from_payload(target), mode=mode
    )


def _candidate_labels(candidates: tuple[TorrentPayloadCandidate, ...]) -> str:
    return ", ".join(candidate.label for candidate in candidates)


def _raise_ambiguous_payload(candidates: tuple[TorrentPayloadCandidate, ...]) -> None:
    raise ValueError(
        tr(
            "torrent.error.ambiguous_payload",
            default="Multiple media groups detected: {groups}. Use --select-content or target the desired folder/file.",
            groups=_candidate_labels(candidates),
        )
    )


def _multi_group_warning(
    *, candidates: tuple[TorrentPayloadCandidate, ...], selected: TorrentPayloadCandidate
) -> str:
    return tr(
        "torrent.warning.multi_group",
        default="Multiple media groups detected: {groups}. Using first group: {selected}.",
        groups=_candidate_labels(candidates),
        selected=selected.label,
    )


def _resolve_media_mode_candidate(
    *, candidates: tuple[TorrentPayloadCandidate, ...], allow_ambiguous: bool
) -> tuple[TorrentPayloadCandidate, str | None]:
    if len(candidates) == 1:
        return candidates[0], None
    if not allow_ambiguous:
        _raise_ambiguous_payload(candidates)
    selected = candidates[0]
    return selected, _multi_group_warning(candidates=candidates, selected=selected)


def _resolve_auto_mode_candidate(
    *,
    target: Path,
    candidates: tuple[TorrentPayloadCandidate, ...],
    allow_ambiguous: bool,
) -> tuple[TorrentPayloadCandidate, str | None]:
    if target.is_file() or len(candidates) == 1:
        return candidates[0], None
    subfolders = [candidate for candidate in candidates if candidate.path != target]
    root_candidates = [candidate for candidate in candidates if candidate.path == target]
    if not root_candidates and len(subfolders) == 1:
        return subfolders[0], None
    if not allow_ambiguous:
        _raise_ambiguous_payload(candidates)
    selected = candidates[0]
    return selected, _multi_group_warning(candidates=candidates, selected=selected)


def _resolve_candidate_for_mode(
    *,
    mode: str,
    target: Path,
    candidates: tuple[TorrentPayloadCandidate, ...],
    allow_ambiguous: bool,
) -> tuple[TorrentPayloadCandidate, str | None]:
    if mode == "media":
        return _resolve_media_mode_candidate(candidates=candidates, allow_ambiguous=allow_ambiguous)
    if mode == "auto":
        return _resolve_auto_mode_candidate(
            target=target, candidates=candidates, allow_ambiguous=allow_ambiguous
        )
    raise ValueError(
        tr(
            "torrent.error.invalid_content_mode",
            default="Invalid torrent content mode: {mode}",
            mode=mode,
        )
    )


def resolve_torrent_payload(
    path: Path, *, content_mode: str = "auto", allow_ambiguous: bool = False
) -> tuple[TorrentPayload, str | None]:
    """Resolve torrent payload from a path.

    Returns:
        A tuple of (TorrentPayload, warning_message). The warning_message is None
        if no ambiguity was detected, or a string describing the multi-group situation.
    """
    mode = (content_mode or "auto").strip().lower()
    target = Path(path)

    if mode == "folder":
        return _resolve_folder_mode_payload(target, mode), None

    candidates = discover_torrent_payload_candidates(target)
    if not candidates:
        raise ValueError(
            tr("torrent.error.no_media", default="No media payload found for torrent creation.")
        )
    selected, warning = _resolve_candidate_for_mode(
        mode=mode,
        target=target,
        candidates=candidates,
        allow_ambiguous=allow_ambiguous,
    )

    return (
        TorrentPayload(
            path=selected.path,
            files=selected.files,
            name=selected.name,
            ignored_files=_sidecar_files(selected.path, selected.files),
            mode=mode,
        ),
        warning,
    )
