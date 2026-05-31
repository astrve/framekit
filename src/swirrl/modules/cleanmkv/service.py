from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from swirrl.core.i18n import tr
from swirrl.core.languages import language_short_label
from swirrl.core.models.cleanmkv import CleanPreset, MkvFileScan, RemuxPlan, TrackInfo
from swirrl.core.naming import release_name_from_mkv_paths
from swirrl.core.reporting import OperationReport
from swirrl.core.tools import ToolRegistry
from swirrl.modules.cleanmkv.planner import build_remux_plan
from swirrl.modules.cleanmkv.remuxer import apply_remux_plan
from swirrl.modules.cleanmkv.scanner import scan_folder
from swirrl.modules.cleanmkv.tracks import track_reference_label


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
    """Service for clean mkv."""

    def _plan_labels(
        self, scan: MkvFileScan, plan: RemuxPlan
    ) -> tuple[list[str], list[str], str | None, str | None]:
        audio_labels = _labels_from_ids(scan.audio_tracks, plan.keep_audio_track_ids)
        subtitle_labels = _labels_from_ids(scan.subtitle_tracks, plan.keep_subtitle_track_ids)
        default_audio_label = _label_from_id(scan.audio_tracks, plan.default_audio_track_id)
        default_subtitle_label = _label_from_id(
            scan.subtitle_tracks, plan.default_subtitle_track_id
        )
        return audio_labels, subtitle_labels, default_audio_label, default_subtitle_label

    def _apply_plan_if_requested(
        self,
        *,
        apply_changes: bool,
        plan: RemuxPlan,
        registry: ToolRegistry,
        copy_unchanged_files: bool,
        progress_callback: Callable[..., None] | None,
        report: OperationReport,
    ) -> bool:
        if not apply_changes:
            return True
        try:
            apply_remux_plan(
                plan,
                registry,
                copy_unchanged_files=copy_unchanged_files,
            )
            if progress_callback is not None:
                progress_callback(plan.source.stat().st_size, files=1)
            return True
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
            return False

    def _resolve_plan_status(
        self,
        *,
        plan: RemuxPlan,
        apply_changes: bool,
        copy_unchanged_files: bool,
    ) -> tuple[str, str, bool]:
        if plan.copy_only:
            if apply_changes and not copy_unchanged_files:
                return (
                    "skipped",
                    tr(
                        "cleanmkv.message.skipped_copy_disabled",
                        default="No track changes needed; unchanged-file copy is disabled.",
                    ),
                    False,
                )
            status = "copied" if apply_changes else "copy-only"
            return (
                status,
                tr("cleanmkv.message.no_track_changes", default="No track changes needed."),
                True,
            )
        status = "remuxed" if apply_changes else "planned"
        message = (
            tr("cleanmkv.message.cleanup_planned", default="Track cleanup planned.")
            if not apply_changes
            else tr("cleanmkv.message.cleanup_applied", default="Track cleanup applied.")
        )
        return status, message, True

    def _record_plan_detail(
        self,
        *,
        report: OperationReport,
        plan: RemuxPlan,
        status: str,
        message: str,
        output_created: bool,
        audio_labels: list[str],
        subtitle_labels: list[str],
        default_audio_label: str | None,
        default_subtitle_label: str | None,
    ) -> None:
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
        """Handle run."""
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

            if plan.skipped:
                report.skipped += 1
                report.add_warning("no_matching_tracks", plan.skip_reason, file=str(scan.path))
                plans.append(plan)
                continue

            plans.append(plan)

            audio_labels, subtitle_labels, default_audio_label, default_subtitle_label = (
                self._plan_labels(scan, plan)
            )

            applied = self._apply_plan_if_requested(
                apply_changes=apply_changes,
                plan=plan,
                registry=registry,
                copy_unchanged_files=copy_unchanged_files,
                progress_callback=progress_callback,
                report=report,
            )
            if not applied:
                continue

            status, message, output_created = self._resolve_plan_status(
                plan=plan,
                apply_changes=apply_changes,
                copy_unchanged_files=copy_unchanged_files,
            )
            self._record_plan_detail(
                report=report,
                plan=plan,
                status=status,
                message=message,
                output_created=output_created,
                audio_labels=audio_labels,
                subtitle_labels=subtitle_labels,
                default_audio_label=default_audio_label,
                default_subtitle_label=default_subtitle_label,
            )

        return report, plans
