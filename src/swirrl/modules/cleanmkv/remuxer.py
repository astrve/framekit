from __future__ import annotations

import shutil
import subprocess  # nosec B404

from swirrl.core.i18n import tr
from swirrl.core.models.cleanmkv import RemuxPlan
from swirrl.core.path_validation import PathValidationError, validate_file_path
from swirrl.core.subprocess_safe import SafeSubprocessError, run_safe
from swirrl.core.tools import ToolRegistry


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Run ``mkvmerge`` remux with the project's safe wrapper.

    Uses :func:`run_safe` so the binary is resolved via ``shutil.which``,
    ``shell=False`` is enforced, output is decoded as UTF-8, and a 600-second
    timeout caps any single remux.
    """
    try:
        return run_safe(
            cmd,
            timeout=600,
            check=False,
            capture_output=True,
            log_label="mkvmerge remux",
        )
    except SafeSubprocessError as exc:
        # Timeout / missing-binary failures surface as a ``RuntimeError`` for
        # parity with the previous direct-subprocess implementation.
        raise RuntimeError(
            f"mkvmerge process failed: {exc}. Command: {' '.join(cmd[:3])}..."
        ) from exc


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
    """Apply remux plan with security validation.

    Args:
        plan: Remux plan containing source and target paths
        registry: Tool registry for finding mkvmerge
        copy_unchanged_files: Whether to copy files that don't need remuxing

    Raises:
        PathValidationError: If source or target paths are invalid
        RuntimeError: If mkvmerge fails
    """
    # Validate source file path
    try:
        validated_source = validate_file_path(
            plan.source,
            allowed_extensions={".mkv"},
            must_exist=True,
        )
    except PathValidationError as e:
        raise RuntimeError(f"Invalid source file: {e}") from e

    # Validate target file path (must_exist=False since we're creating it)
    try:
        validated_target = validate_file_path(
            plan.target,
            allowed_extensions={".mkv"},
            must_exist=False,
        )
    except PathValidationError as e:
        raise RuntimeError(f"Invalid target file: {e}") from e

    # Create target directory
    validated_target.parent.mkdir(parents=True, exist_ok=True)

    if plan.copy_only:
        if copy_unchanged_files:
            shutil.copy2(validated_source, validated_target)
        return

    # Use require_tool for better error messages with installation instructions
    mkvmerge_path = registry.require_tool("mkvmerge")

    # Build command with validated paths
    cmd = [
        mkvmerge_path,
        "-o",
        str(validated_target),
        "--audio-tracks",
        ",".join(str(x) for x in plan.keep_audio_track_ids) if plan.keep_audio_track_ids else "",
        "--subtitle-tracks",
        ",".join(str(x) for x in plan.keep_subtitle_track_ids)
        if plan.keep_subtitle_track_ids
        else "",
    ]

    _append_default_track_flags(cmd, plan)

    # Add source file at the end
    # Using -- would be ideal but mkvmerge doesn't support it consistently
    cmd.append(str(validated_source))

    result = _run(cmd)
    if result.returncode != 0:
        raise RuntimeError(
            tr(
                "cleanmkv.error.remux_failed",
                default="mkvmerge remux failed on {file}: {message}",
                file=validated_source.name,
                message=result.stderr.strip(),
            )
        )
