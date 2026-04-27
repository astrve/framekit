from __future__ import annotations

import shutil
import subprocess

from framekit.core.i18n import tr
from framekit.core.models.cleanmkv import RemuxPlan
from framekit.core.tools import ToolRegistry


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _append_default_track_flags(cmd: list[str], plan: RemuxPlan) -> None:
    """Normalize default flags for every kept audio/subtitle track.

    mkvmerge preserves flags from the source unless told otherwise. Setting only
    the desired default track to ``yes`` can leave another kept track marked as
    default if it was already flagged in the source.
    """

    for track_id in plan.keep_audio_track_ids:
        flag = "yes" if track_id == plan.default_audio_track_id else "no"
        cmd.extend(["--default-track-flag", f"{track_id}:{flag}"])

    for track_id in plan.keep_subtitle_track_ids:
        flag = "yes" if track_id == plan.default_subtitle_track_id else "no"
        cmd.extend(["--default-track-flag", f"{track_id}:{flag}"])


def apply_remux_plan(
    plan: RemuxPlan,
    registry: ToolRegistry,
    *,
    copy_unchanged_files: bool = True,
) -> None:
    plan.target.parent.mkdir(parents=True, exist_ok=True)

    if plan.copy_only:
        if copy_unchanged_files:
            shutil.copy2(plan.source, plan.target)
        return

    mkvmerge_path = registry.resolve_tool_path("mkvmerge")
    if not mkvmerge_path:
        raise RuntimeError(
            tr(
                "tools.mkvmerge_not_found",
                default="mkvmerge not found. Configure it or add it to PATH.",
            )
        )

    cmd = [
        mkvmerge_path,
        "-o",
        str(plan.target),
        "--audio-tracks",
        ",".join(str(x) for x in plan.keep_audio_track_ids) if plan.keep_audio_track_ids else "",
        "--subtitle-tracks",
        ",".join(str(x) for x in plan.keep_subtitle_track_ids)
        if plan.keep_subtitle_track_ids
        else "",
    ]

    _append_default_track_flags(cmd, plan)

    cmd.append(str(plan.source))

    result = _run(cmd)
    if result.returncode != 0:
        raise RuntimeError(
            tr(
                "cleanmkv.error.remux_failed",
                default="mkvmerge remux failed on {file}: {message}",
                file=plan.source.name,
                message=result.stderr.strip(),
            )
        )
