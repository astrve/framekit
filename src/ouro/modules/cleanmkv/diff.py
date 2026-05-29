"""Mediainfo diff — show before/after track comparison for CleanMKV."""

from __future__ import annotations

from pathlib import Path

from rich.table import Table

from ouro.core.i18n import tr
from ouro.core.models.cleanmkv import MkvFileScan, TrackInfo
from ouro.core.tools import ToolRegistry
from ouro.modules.cleanmkv.scanner import scan_mkv_file
from ouro.ui.console import console


def _track_summary(track: TrackInfo) -> str:
    parts = [track.codec]
    if track.language:
        parts.append(track.language)
    if track.channels:
        parts.append(track.channels)
    if track.title:
        parts.append(f'"{track.title}"')
    flags = []
    if track.is_default:
        flags.append("D")
    if track.is_forced:
        flags.append("F")
    if flags:
        parts.append(f"[{''.join(flags)}]")
    return " | ".join(parts)


def build_diff_table(
    source_scan: MkvFileScan,
    target_path: Path,
    registry: ToolRegistry,
) -> Table | None:
    """Build a Rich table comparing tracks before and after remux.

    Returns None if target_path does not exist (dry-run or failed remux).
    """
    if not target_path.exists():
        return None

    target_scan = scan_mkv_file(target_path, registry)

    table = Table(
        title=tr(
            "cleanmkv.diff.title",
            default="Track Diff: {name}",
            name=source_scan.path.name,
        ),
        show_lines=True,
    )
    table.add_column("Type", width=8)
    table.add_column("Before", style="red")
    table.add_column("After", style="green")
    table.add_column("Status", width=10)

    before_audio = _track_map(source_scan.audio_tracks)
    after_audio = _track_map(target_scan.audio_tracks)
    before_subs = _track_map(source_scan.subtitle_tracks)
    after_subs = _track_map(target_scan.subtitle_tracks)

    _append_diff_rows(table, "Audio", before_audio, after_audio)
    _append_diff_rows(table, "Sub", before_subs, after_subs)

    return table


def _track_map(tracks: list[TrackInfo]) -> dict[int, TrackInfo]:
    return {track.track_id: track for track in tracks}


def _append_diff_rows(
    table: Table,
    label: str,
    before_tracks: dict[int, TrackInfo],
    after_tracks: dict[int, TrackInfo],
) -> None:
    for track_id, track in before_tracks.items():
        if track_id in after_tracks:
            table.add_row(
                label,
                _track_summary(track),
                _track_summary(after_tracks[track_id]),
                "[green]kept[/]",
            )
        else:
            table.add_row(label, _track_summary(track), "", "[red]removed[/]")

    for track_id, track in after_tracks.items():
        if track_id not in before_tracks:
            table.add_row(label, "", _track_summary(track), "[yellow]new[/]")


def print_diff_for_plans(
    scans: list[MkvFileScan],
    plans: list,
    registry: ToolRegistry,
) -> None:
    """Print diff tables for all files that were remuxed."""
    scan_map = {scan.path: scan for scan in scans}

    for plan in plans:
        if plan.copy_only:
            continue
        source_scan = scan_map.get(plan.source)
        if source_scan is None:
            continue
        table = build_diff_table(source_scan, plan.target, registry)
        if table is not None:
            console.print(table)
            console.print()
