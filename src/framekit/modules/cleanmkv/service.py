from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from framekit.core.i18n import tr
from framekit.core.languages import language_short_label
from framekit.core.models.cleanmkv import CleanPreset, MkvFileScan, RemuxPlan, TrackInfo
from framekit.core.naming import release_name_from_mkv_paths
from framekit.core.reporting import OperationReport
from framekit.core.tools import ToolRegistry
from framekit.modules.cleanmkv.planner import build_remux_plan
from framekit.modules.cleanmkv.remuxer import apply_remux_plan
from framekit.modules.cleanmkv.scanner import scan_folder
from framekit.modules.cleanmkv.tracks import track_reference_label


def _format_track_label(track: TrackInfo) -> str:
    return track_reference_label(track) or language_short_label(
        track.language, track.language_variant
    )


def _labels_from_ids(tracks: list[TrackInfo], track_ids: list[int]) -> list[str]:
    selected = [track for track in tracks if track.track_id in track_ids]
    return [_format_track_label(track) for track in selected]


def _label_from_id(tracks: list[TrackInfo], track_id: int | None) -> str | None:
    if track_id is None:
        return None

    for track in tracks:
        if track.track_id == track_id:
            return _format_track_label(track)

    return None


class CleanMkvService:
    def run(
        self,
        folder: Path,
        *,
        preset: CleanPreset,
        output_dir_name: str,
        apply_changes: bool,
        registry: ToolRegistry,
        copy_unchanged_files: bool = True,
        scans: list[MkvFileScan] | None = None,
        progress_callback: Callable[..., None] | None = None,
    ) -> tuple[OperationReport, list[RemuxPlan]]:
        scans = scans if scans is not None else scan_folder(folder, registry)

        report = OperationReport(tool="cleanmkv")
        plans: list[RemuxPlan] = []

        report.scanned = len(scans)
        release_name = release_name_from_mkv_paths([scan.path for scan in scans])

        for scan in scans:
            report.processed += 1

            plan = build_remux_plan(
                scan,
                preset=preset,
                output_dir_name=output_dir_name,
                release_name=release_name,
            )
            plans.append(plan)

            audio_labels = _labels_from_ids(scan.audio_tracks, plan.keep_audio_track_ids)
            subtitle_labels = _labels_from_ids(scan.subtitle_tracks, plan.keep_subtitle_track_ids)
            default_audio_label = _label_from_id(scan.audio_tracks, plan.default_audio_track_id)
            default_subtitle_label = _label_from_id(
                scan.subtitle_tracks, plan.default_subtitle_track_id
            )

            if apply_changes:
                try:
                    apply_remux_plan(
                        plan,
                        registry,
                        copy_unchanged_files=copy_unchanged_files,
                    )
                    if progress_callback is not None:
                        progress_callback(plan.source.stat().st_size, files=1)
                except Exception as exc:
                    report.add_error(
                        "cleanmkv_apply_failed",
                        str(exc),
                        source=str(plan.source),
                        target=str(plan.target),
                    )
                    report.add_detail(
                        file=plan.source.name,
                        action="cleanmkv",
                        status="error",
                        message=str(exc),
                        before={"source": str(plan.source)},
                        after={"target": str(plan.target)},
                    )
                    continue

            output_created = True
            if plan.copy_only:
                if apply_changes and not copy_unchanged_files:
                    status = "skipped"
                    message = tr(
                        "cleanmkv.message.skipped_copy_disabled",
                        default="No track changes needed; unchanged-file copy is disabled.",
                    )
                    output_created = False
                else:
                    status = "copied" if apply_changes else "copy-only"
                    message = tr(
                        "cleanmkv.message.no_track_changes", default="No track changes needed."
                    )
            else:
                status = "remuxed" if apply_changes else "planned"
                message = (
                    tr("cleanmkv.message.cleanup_planned", default="Track cleanup planned.")
                    if not apply_changes
                    else tr("cleanmkv.message.cleanup_applied", default="Track cleanup applied.")
                )

            if status == "skipped":
                report.skipped += 1
            else:
                report.modified += 1

            if output_created:
                report.outputs.append(str(plan.target))
            report.add_detail(
                file=plan.source.name,
                action="cleanmkv",
                status=status,
                message=message,
                before={
                    "source": str(plan.source),
                    "audio_track_ids": plan.keep_audio_track_ids,
                    "subtitle_track_ids": plan.keep_subtitle_track_ids,
                    "audio_labels": audio_labels,
                    "subtitle_labels": subtitle_labels,
                },
                after={
                    "target": str(plan.target),
                    "default_audio_track_id": plan.default_audio_track_id,
                    "default_subtitle_track_id": plan.default_subtitle_track_id,
                    "default_audio_label": default_audio_label,
                    "default_subtitle_label": default_subtitle_label,
                },
            )

        return report, plans
