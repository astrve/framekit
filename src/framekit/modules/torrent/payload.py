from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from framekit.core.i18n import tr
from framekit.core.naming import release_name_from_mkv_paths, torrent_name_from_payload


@dataclass(frozen=True, slots=True)
class TorrentPayloadCandidate:
    label: str
    path: Path
    files: tuple[Path, ...]
    name: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class TorrentPayload:
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
    return tuple(
        sorted(
            (
                item
                for item in path.iterdir()
                if item.is_file() and item.suffix.lower() in VIDEO_SUFFIXES
            ),
            key=lambda p: p.name.lower(),
        )
    )


def _mkv_files_recursive(path: Path) -> tuple[Path, ...]:
    return tuple(sorted(path.rglob("*.mkv"), key=lambda p: str(p).lower()))


def _sidecar_files(path: Path, selected: tuple[Path, ...]) -> tuple[Path, ...]:
    selected_set = {item.resolve() for item in selected if item.exists()}
    siblings = path.parent.iterdir() if path.is_file() else path.rglob("*")
    ignored: list[Path] = []
    for item in siblings:
        if not item.is_file() or item.suffix.lower() == ".torrent":
            continue
        try:
            resolved = item.resolve()
        except OSError:
            resolved = item
        if resolved not in selected_set:
            ignored.append(item)
    return tuple(sorted(ignored, key=lambda p: str(p).lower()))


def discover_torrent_payload_candidates(path: Path) -> tuple[TorrentPayloadCandidate, ...]:
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
    # Root-level media files become their own group(s)
    root_mkv = _mkv_files_at(target)
    if root_mkv:
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

    # Inspect immediate subdirectories
    for child in sorted(
        (item for item in target.iterdir() if item.is_dir()), key=lambda p: p.name.lower()
    ):
        # Special handling for a Release/ folder: treat each subfolder of Release as its own group
        if child.name.lower() == "release":
            # If there are MKV files directly under Release/, treat them as a group
            release_root_mkv = _mkv_files_at(child)
            if release_root_mkv:
                name = release_name_from_mkv_paths(release_root_mkv)
                candidates.append(
                    TorrentPayloadCandidate(
                        label=f"{child.name}/",
                        path=child,
                        files=release_root_mkv,
                        name=name,
                        description=tr(
                            "torrent.payload.subfolder",
                            default="{count} media file(s) in subfolder",
                            count=len(release_root_mkv),
                        ),
                    )
                )
            # Each subfolder inside Release is considered a separate group
            for sub in sorted(
                (item for item in child.iterdir() if item.is_dir()), key=lambda p: p.name.lower()
            ):
                sub_files = _mkv_files_recursive(sub)
                if not sub_files:
                    continue
                name = release_name_from_mkv_paths(sub_files)
                candidates.append(
                    TorrentPayloadCandidate(
                        label=f"{sub.name}/",
                        path=sub,
                        files=sub_files,
                        name=name,
                        description=tr(
                            "torrent.payload.subfolder",
                            default="{count} media file(s) in subfolder",
                            count=len(sub_files),
                        ),
                    )
                )
            # Do not treat the Release folder itself generically below
            continue

        # Generic subfolder handling: collect all MKVs recursively in the subfolder
        sub_files = _mkv_files_recursive(child)
        if not sub_files:
            continue
        name = release_name_from_mkv_paths(sub_files)
        candidates.append(
            TorrentPayloadCandidate(
                label=f"{child.name}/",
                path=child,
                files=sub_files,
                name=name,
                description=tr(
                    "torrent.payload.subfolder",
                    default="{count} media file(s) in subfolder",
                    count=len(sub_files),
                ),
            )
        )
    return tuple(candidates)


def resolve_torrent_payload(path: Path, *, content_mode: str = "auto") -> TorrentPayload:
    mode = (content_mode or "auto").strip().lower()
    target = Path(path)

    if mode == "folder":
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

    candidates = discover_torrent_payload_candidates(target)
    if not candidates:
        raise ValueError(
            tr("torrent.error.no_media", default="No media payload found for torrent creation.")
        )

    if mode == "media":
        if len(candidates) != 1:
            groups = ", ".join(candidate.label for candidate in candidates)
            raise ValueError(
                tr(
                    "torrent.error.ambiguous_payload",
                    default="Multiple media groups detected: {groups}. Use --select-content or target the desired folder/file.",
                    groups=groups,
                )
            )
        selected = candidates[0]
    elif mode == "auto":
        if target.is_file() or len(candidates) == 1:
            selected = candidates[0]
        else:
            subfolders = [candidate for candidate in candidates if candidate.path != target]
            root_candidates = [candidate for candidate in candidates if candidate.path == target]
            if not root_candidates and len(subfolders) == 1:
                selected = subfolders[0]
            else:
                groups = ", ".join(candidate.label for candidate in candidates)
                raise ValueError(
                    tr(
                        "torrent.error.ambiguous_payload",
                        default="Multiple media groups detected: {groups}. Use --select-content or target the desired folder/file.",
                        groups=groups,
                    )
                )
    else:
        raise ValueError(
            tr(
                "torrent.error.invalid_content_mode",
                default="Invalid torrent content mode: {mode}",
                mode=content_mode,
            )
        )

    return TorrentPayload(
        path=selected.path,
        files=selected.files,
        name=selected.name,
        ignored_files=_sidecar_files(selected.path, selected.files),
        mode=mode,
    )
