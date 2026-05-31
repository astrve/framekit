"""Pipeline orchestration and execution logic.

This module handles the core pipeline execution flow, including:
- Step sequencing and execution
- Progress tracking and timing
- Error handling and recovery
- Result reporting
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from swirrl.commands.pipeline_preview import print_pipeline_report
from swirrl.commands.pipeline_steps import (
    _cleanmkv_step,
    _encoder_step,
    _metadata_step,
    _nfo_step,
    _prez_step,
    _rename_parent_step,
    _renamer_step,
    _screenshot_step,
    _seedbox_step,
    _torrent_step,
    _upload_step,
)
from swirrl.core.i18n import tr
from swirrl.ui.console import print_error, print_info, print_success, print_warning

# Type-only import: ``pipeline`` imports ``pipeline_orchestrator`` at runtime,
# so a real import here would create a cycle. Guard with ``TYPE_CHECKING`` so
# pyright resolves ``PipelineStep`` without affecting runtime semantics.
if TYPE_CHECKING:
    from swirrl.commands.pipeline import PipelineStep


def _module_label(name: str) -> str:
    """Return a human-readable label for a pipeline module.

    Args:
        name: Module name

    Returns:
        Human-readable label
    """
    return {
        "renamer": tr("pipeline.step.renamer", default="Renamer"),
        "cleanmkv": tr("pipeline.step.cleanmkv", default="CleanMKV"),
        "metadata": tr("pipeline.step.metadata", default="Metadata (NFO + Prez)"),
        "encode": tr("pipeline.step.encoder", default="Encoder"),
        "encoder": tr("pipeline.step.encoder", default="Encoder"),
        "nfo": tr("pipeline.step.nfo", default="NFO"),
        "torrent": tr("pipeline.step.torrent", default="Torrent"),
        "prez": tr("pipeline.step.prez", default="Prez"),
        "screenshot": tr("pipeline.step.screenshot", default="Screenshot"),
        "seedbox": tr("pipeline.step.seedbox", default="Seedbox"),
        "upload": tr("pipeline.step.upload", default="Upload"),
        "rename-parent": tr("pipeline.step.rename_parent", default="Rename parent"),
    }.get(name, name)


def _is_existing_dir(path: Path) -> bool:
    return path.exists() and path.is_dir()


def _single_release_candidate(release_dir: Path) -> Path | None:
    candidates = [
        item
        for item in release_dir.iterdir()
        if item.is_dir() and any(child.suffix.lower() == ".mkv" for child in item.iterdir())
    ]
    return candidates[0] if len(candidates) == 1 else None


def _configured_clean_dir(root: Path, settings: dict, safe_release_name: str) -> Path:
    clean_settings = settings.get("modules", {}).get("cleanmkv", {})
    configured = str(
        clean_settings.get("output_dir_name", "Release/{release}") or "Release/{release}"
    )
    return root / configured.format(release=safe_release_name)


def _next_work_folder(root: Path, settings: dict) -> Path:
    """Determine the next working folder after transform steps.

    Looks for output from cleanmkv or other transform steps.

    Args:
        root: Root directory
        settings: Application settings

    Returns:
        Path to working folder
    """
    from swirrl.commands.pipeline import (
        release_artifacts_folder,
        release_payload_folder,
        safe_release_folder_name,
    )

    release_payload = release_payload_folder(root)
    if _is_existing_dir(release_payload):
        return release_payload

    clean_dir = _configured_clean_dir(root, settings, safe_release_folder_name(root))
    if _is_existing_dir(clean_dir):
        return clean_dir

    release_dir = release_artifacts_folder(root)
    if _is_existing_dir(release_dir):
        candidate = _single_release_candidate(release_dir)
        if candidate is not None:
            return candidate

    legacy_clean_dir = root / "clean"
    return legacy_clean_dir if _is_existing_dir(legacy_clean_dir) else root


def _pipeline_output_folder(work_folder: Path, root: Path | None = None) -> Path:
    """Determine the output folder for pipeline artifacts.

    Args:
        work_folder: Current working folder
        root: Original root folder (optional)

    Returns:
        Path to output folder
    """
    from swirrl.commands.pipeline import _release_artifacts_folder

    if work_folder.parent.name == "Release":
        return work_folder.parent
    if root is not None:
        return _release_artifacts_folder(root)
    return work_folder


# Stable selection_index → action mapping shared with the web checkpoint UI.
# The web UI renders one button per option in ``pending.json`` using its
# ``index``; the orchestrator interprets the returned ``selection_index`` by
# these fixed semantics regardless of which options were offered.
_STEP_ACTION_APPROVE = 0
_STEP_ACTION_SKIP = 1
_STEP_ACTION_BACK = 2
_STEP_ACTION_ABORT = 3


def _module_summary(name: str) -> str:
    """Return a short human description of what a pipeline step will do."""
    return {
        "renamer": tr(
            "pipeline.summary.renamer",
            default="Rename files using detected media tags and remove terms.",
        ),
        "cleanmkv": tr(
            "pipeline.summary.cleanmkv",
            default="Strip unwanted audio/subtitle tracks from the MKV files.",
        ),
        "metadata": tr(
            "pipeline.summary.metadata",
            default="Fetch metadata (TMDB) and build the NFO + presentation.",
        ),
        "nfo": tr("pipeline.summary.nfo", default="Generate the .nfo description file."),
        "prez": tr(
            "pipeline.summary.prez",
            default="Build the presentation (screenshots, BBCode/HTML).",
        ),
        "torrent": tr("pipeline.summary.torrent", default="Create the .torrent file."),
        "screenshot": tr(
            "pipeline.summary.screenshot", default="Capture screenshots from the release."
        ),
        "encode": tr("pipeline.summary.encode", default="Re-encode the video tracks."),
        "encoder": tr("pipeline.summary.encode", default="Re-encode the video tracks."),
        "seedbox": tr("pipeline.summary.seedbox", default="Push the release to the seedbox."),
        "upload": tr("pipeline.summary.upload", default="Upload to the configured tracker."),
        "rename-parent": tr(
            "pipeline.summary.rename_parent", default="Rename the release parent folder."
        ),
    }.get(name, _module_label(name))


def _write_step_checkpoint(
    chk_dir: Path,
    step: str,
    label: str,
    *,
    index: int,
    total: int,
    can_back: bool,
) -> None:
    """Write a step-boundary checkpoint so the web UI can drive the run.

    Offers Approve / Skip / (Back when not the first step) / Abort. Option
    ``index`` values follow the stable ``_STEP_ACTION_*`` semantics so the
    orchestrator can interpret the response without re-reading the option list.
    """
    import json

    options = [
        {"index": _STEP_ACTION_APPROVE, "label": "Approve", "hint": "Run this step"},
        {"index": _STEP_ACTION_SKIP, "label": "Skip", "hint": "Skip this step"},
    ]
    if can_back:
        options.append(
            {"index": _STEP_ACTION_BACK, "label": "Back", "hint": "Re-run the previous step"}
        )
    options.append(
        {"index": _STEP_ACTION_ABORT, "label": "Abort", "hint": "Stop the pipeline"}
    )

    pending = chk_dir / "pending.json"
    (chk_dir / "response.json").unlink(missing_ok=True)
    pending.write_text(
        json.dumps({
            "type": "step_confirm",
            "step": step,
            "step_index": index,
            "step_total": total,
            "title": f"Step {index}/{total}: {label}",
            "summary": _module_summary(step),
            "options": options,
            "default_index": _STEP_ACTION_APPROVE,
        }),
        encoding="utf-8",
    )


def _wait_step_response(chk_dir: Path, timeout: float = 1800.0) -> str:
    """Poll for a step checkpoint response.

    Returns one of ``'approve'``, ``'skip'``, ``'back'``, ``'abort'``. Reads
    ``selection_index`` from ``response.json`` per the ``_STEP_ACTION_*`` map.
    On timeout (default 30 min) auto-approves so an unattended run keeps going;
    the job can still be cancelled out-of-band (the subprocess is terminated).
    """
    import json
    import time as _time

    pending = chk_dir / "pending.json"
    response = chk_dir / "response.json"
    deadline = _time.monotonic() + timeout
    while _time.monotonic() < deadline:
        if response.exists():
            try:
                data = json.loads(response.read_text(encoding="utf-8"))
                response.unlink(missing_ok=True)
                pending.unlink(missing_ok=True)
                idx = int(data.get("selection_index", _STEP_ACTION_APPROVE))
            except Exception:
                _time.sleep(0.5)
                continue
            if idx == _STEP_ACTION_SKIP:
                return "skip"
            if idx == _STEP_ACTION_BACK:
                return "back"
            if idx == _STEP_ACTION_ABORT:
                return "abort"
            return "approve"
        _time.sleep(0.5)
    pending.unlink(missing_ok=True)
    return "approve"  # timeout → auto-approve (safe default)


def _run_pipeline_with_progress(
    steps: list[tuple[str, str, Callable[[], int]]],
    stop_on_error: bool = True,
    step_callback: Callable[[str, str], None] | None = None,
) -> dict[str, dict]:
    """Run pipeline steps sequentially, collecting timing and error details.

    Args:
        steps: List of (module_name, label, callback) tuples
        stop_on_error: Whether to stop on first error
        step_callback: Optional callback for step notifications

    Returns:
        Dictionary mapping module names to result dictionaries
    """
    import os

    chk_dir_str = os.environ.get("SWIRRL_JOB_CHECKPOINT_DIR", "").strip()
    chk_dir: Path | None = None
    if chk_dir_str:
        p = Path(chk_dir_str)
        if p.is_dir():
            chk_dir = p

    results: dict[str, dict] = {}
    total = len(steps)
    idx = 0

    while idx < len(steps):
        module_name, label, callback = steps[idx]
        if step_callback is not None:
            with contextlib.suppress(Exception):
                step_callback(module_name, label)
        else:
            print_info(
                tr(
                    "pipeline.step.running",
                    default="{label} in progress...",
                    label=label,
                )
            )

        # Step-boundary checkpoint: pause for web UI control when interactive.
        # Approve / Skip / Back (re-run previous) / Abort.
        if chk_dir is not None:
            action = "approve"
            with contextlib.suppress(Exception):
                _write_step_checkpoint(
                    chk_dir,
                    module_name,
                    label,
                    index=idx + 1,
                    total=total,
                    can_back=idx > 0,
                )
                action = _wait_step_response(chk_dir)
            if action == "abort":
                results[module_name] = {
                    "success": False, "code": 130, "elapsed": 0.0,
                    "label": label, "skipped": True,
                    "error": tr("pipeline.aborted", default="Aborted by user."),
                }
                for remaining_module, remaining_label, _ in steps[idx + 1:]:
                    results[remaining_module] = {
                        "success": False, "code": -1, "elapsed": 0,
                        "label": remaining_label, "skipped": True,
                    }
                break
            if action == "back" and idx > 0:
                # Re-run the previous step: drop its recorded result and step back.
                idx -= 1
                results.pop(steps[idx][0], None)
                continue
            if action == "skip":
                results[module_name] = {
                    "success": True, "code": 0, "elapsed": 0.0,
                    "label": label, "skipped": True,
                }
                idx += 1
                continue

        start_time = time.time()
        try:
            code = callback()
            elapsed = time.time() - start_time

            results[module_name] = {
                "success": code == 0,
                "code": code,
                "elapsed": elapsed,
                "label": label,
            }

            if code != 0:
                results[module_name]["error"] = tr(
                    "pipeline.error.step_exit_code",
                    default="{label}: exit code {code}",
                    label=label,
                    code=code,
                )
                if stop_on_error:
                    for remaining_module, remaining_label, _ in steps[idx + 1:]:
                        results[remaining_module] = {
                            "success": False,
                            "code": -1,
                            "elapsed": 0,
                            "label": remaining_label,
                            "skipped": True,
                        }
                    break

        except KeyboardInterrupt:
            elapsed = time.time() - start_time
            results[module_name] = {
                "success": False,
                "code": 130,
                "elapsed": elapsed,
                "label": label,
                "error": tr("runtime.interrupted", default="Interrupted"),
            }
            break
        except Exception as exc:
            elapsed = time.time() - start_time
            error_message = f"{type(exc).__name__}: {exc}"
            logger.exception(f"Pipeline step '{module_name}' crashed")
            print_error(f"{module_name}: {error_message}")
            results[module_name] = {
                "success": False,
                "code": 1,
                "elapsed": elapsed,
                "label": label,
                "error": error_message,
                "exception_type": type(exc).__name__,
            }
            if stop_on_error:
                for remaining_module, remaining_label, _ in steps[idx + 1:]:
                    results[remaining_module] = {
                        "success": False,
                        "code": -1,
                        "elapsed": 0,
                        "label": remaining_label,
                        "skipped": True,
                    }
                break

        idx += 1

    return results


def _dry_run_step(message_key: str, default: str, **kwargs) -> Callable[[], int]:
    return lambda: (print_info(tr(message_key, default=default, **kwargs)), 0)[1]


def _resolve_cleanmkv_options(
    preset_config: dict | None,
) -> tuple[str | None, str | None, str | None]:
    if not preset_config or "cleanmkv" not in preset_config:
        return None, None, None
    cleanmkv_cfg = preset_config["cleanmkv"]
    return (
        cleanmkv_cfg.get("preset"),
        cleanmkv_cfg.get("external_preset"),
        cleanmkv_cfg.get("output_dir_name"),
    )


def _build_phase1_steps(
    *,
    root: Path,
    selected_modules: set[str],
    effective_remove_terms: tuple[str, ...],
    preset_config: dict | None,
    auto_mode: bool,
    dry_run: bool,
) -> list[PipelineStep]:
    steps: list[PipelineStep] = []
    if "renamer" in selected_modules:
        if dry_run:
            steps.append(
                (
                    "renamer",
                    _module_label("renamer"),
                    _dry_run_step(
                        "pipeline.dry_run.renamer",
                        "[dry-run] Would rename files in: {path}",
                        path=root,
                    ),
                )
            )
        elif effective_remove_terms:
            terms_for_step = effective_remove_terms
            steps.append(
                (
                    "renamer",
                    _module_label("renamer"),
                    lambda: _renamer_step(root, terms_for_step, auto_mode=auto_mode),
                )
            )
        else:
            steps.append(
                (
                    "renamer",
                    _module_label("renamer"),
                    lambda: _renamer_step(root, auto_mode=auto_mode),
                )
            )

    if "cleanmkv" in selected_modules:
        if dry_run:
            steps.append(
                (
                    "cleanmkv",
                    _module_label("cleanmkv"),
                    _dry_run_step(
                        "pipeline.dry_run.cleanmkv",
                        "[dry-run] Would remux MKV files in: {path}",
                        path=root,
                    ),
                )
            )
        else:
            cleanmkv_preset_name, cleanmkv_external_preset, cleanmkv_output_dir = (
                _resolve_cleanmkv_options(preset_config)
            )
            _cleanmkv_auto = auto_mode
            steps.append(
                (
                    "cleanmkv",
                    _module_label("cleanmkv"),
                    lambda: _cleanmkv_step(
                        root,
                        auto_mode=_cleanmkv_auto,
                        preset_name=cleanmkv_preset_name,
                        external_preset=cleanmkv_external_preset,
                        output_dir_name=cleanmkv_output_dir,
                    ),
                )
            )
    return steps


def _build_phase2_steps(
    *,
    root: Path,
    work_folder: Path,
    output_folder: Path,
    selected_modules: set[str],
    settings: dict,
    nfo_locale: str | None,
    nfo_mode: str | None,
    select_templates: bool | None,
    metadata_enabled: bool,
    announce: str | None,
    preset: str | None,
    auto_mode: bool,
    dry_run: bool,
    context,
) -> list[PipelineStep]:
    output_steps: list[PipelineStep] = []
    if "metadata" in selected_modules:
        output_steps.append(
            (
                "metadata",
                _module_label("metadata"),
                lambda: _metadata_step(
                    work_folder,
                    nfo_locale,
                    context,
                    settings,
                    metadata_enabled=metadata_enabled,
                    auto_mode=auto_mode,
                ),
            )
        )

    if "encode" in selected_modules:
        if dry_run:
            from swirrl.commands.pipeline_steps import _encoder_step_dry_run

            output_steps.append(
                (
                    "encode",
                    _module_label("encode"),
                    lambda: _encoder_step_dry_run(work_folder, settings),
                )
            )
        else:
            output_steps.append(
                (
                    "encode",
                    _module_label("encode"),
                    lambda: _encoder_step(work_folder, settings),
                )
            )

    if "nfo" in selected_modules:
        nfo_mode_for_step = nfo_mode
        _nfo_auto = auto_mode
        output_steps.append(
            (
                "nfo",
                _module_label("nfo"),
                lambda: _nfo_step(
                    work_folder,
                    nfo_locale,
                    context,
                    settings,
                    metadata_enabled,
                    output_folder,
                    nfo_mode_for_step,
                    _nfo_auto,
                ),
            )
        )

    if "torrent" in selected_modules:
        output_steps.append(
            (
                "torrent",
                _module_label("torrent"),
                lambda: _torrent_step(work_folder, announce, context, output_folder, settings),
            )
        )

    if "prez" in selected_modules:
        _prez_auto = auto_mode
        output_steps.append(
            (
                "prez",
                _module_label("prez"),
                lambda: _prez_step(
                    work_folder,
                    nfo_locale,
                    context,
                    settings,
                    preset,
                    metadata_enabled,
                    output_folder,
                    select_templates,
                    _prez_auto,
                ),
            )
        )

    if "screenshot" in selected_modules:
        if dry_run:
            output_steps.append(
                (
                    "screenshot",
                    _module_label("screenshot"),
                    _dry_run_step(
                        "pipeline.dry_run.screenshot",
                        "[dry-run] Would extract screenshots from release videos",
                    ),
                )
            )
        else:
            output_steps.append(
                (
                    "screenshot",
                    _module_label("screenshot"),
                    lambda: _screenshot_step(work_folder, context, settings),
                )
            )

    if "seedbox" in selected_modules:
        if dry_run:
            output_steps.append(
                (
                    "seedbox",
                    _module_label("seedbox"),
                    _dry_run_step(
                        "pipeline.dry_run.seedbox",
                        "[dry-run] Would push release payload to configured seedbox",
                    ),
                )
            )
        else:
            output_steps.append(
                (
                    "seedbox",
                    _module_label("seedbox"),
                    lambda: _seedbox_step(output_folder, settings, auto_mode=auto_mode),
                )
            )

    if "upload" in selected_modules:
        if dry_run:
            output_steps.append(
                (
                    "upload",
                    _module_label("upload"),
                    _dry_run_step(
                        "pipeline.dry_run.upload",
                        "[dry-run] Would upload to configured trackers",
                    ),
                )
            )
        else:
            _upload_auto = auto_mode
            output_steps.append(
                (
                    "upload",
                    _module_label("upload"),
                    lambda: _upload_step(work_folder, context, settings, _upload_auto),
                )
            )

    return output_steps


def _auto_enable_seedbox(selected_modules: set[str], settings: dict) -> set[str]:
    """Auto-enable seedbox before upload when config is valid and reachable."""
    if "upload" not in selected_modules or "seedbox" in selected_modules:
        return selected_modules
    try:
        from swirrl.commands.seedbox import seedbox_ready_for_pipeline

        ready, _message = seedbox_ready_for_pipeline(settings)
    except Exception:
        ready = False
    if not ready:
        return selected_modules
    updated = set(selected_modules)
    updated.add("seedbox")
    print_info(
        tr(
            "pipeline.seedbox.auto_enabled",
            default="Seedbox module auto-enabled (valid configuration detected).",
        )
    )
    return updated


def _status_and_details(step_result: dict) -> tuple[str, str]:
    if step_result["success"]:
        return tr("common.success", default="OK"), step_result["label"]
    if step_result.get("skipped"):
        return tr("common.skipped", default="Skipped"), step_result["label"]
    return tr("common.failed", default="Failed"), step_result.get("error") or step_result["label"]


def _collect_phase_results(
    report_rows: list[tuple[str, str, str, float]],
    phase_results: dict[str, dict],
) -> int:
    failures = 0
    for module_name, res in phase_results.items():
        status_str, details = _status_and_details(res)
        report_rows.append((module_name, status_str, details, res["elapsed"]))
        if not res["success"] and not res.get("skipped"):
            failures += 1
    return failures


def _first_failure_code(phase_results: dict[str, dict]) -> int:
    for res in phase_results.values():
        if not res["success"] and not res.get("skipped"):
            return int(res["code"])
    return 1


def _artifacts_ready_for_rename_parent(
    selected_modules: set[str],
    phase_results: dict[str, dict],
) -> tuple[bool, str]:
    required_modules = [name for name in ("nfo", "torrent", "prez") if name in selected_modules]
    if not required_modules:
        return False, tr(
            "pipeline.rename_parent.skipped.no_artifacts_selected",
            default="Skipped: no artifacts module selected (nfo/torrent/prez).",
        )
    for module_name in required_modules:
        module_result = phase_results.get(module_name)
        if not module_result or not module_result.get("success", False):
            return False, tr(
                "pipeline.rename_parent.skipped.artifact_failed",
                default="Skipped: required artifact module failed ({module}).",
                module=module_name,
            )
    return True, ""


def execute_pipeline_modules(
    *,
    work_folder: Path,
    output_folder: Path,
    selected_modules: set[str],
    effective_remove_terms: tuple[str, ...],
    settings: dict,
    nfo_locale: str | None,
    nfo_mode: str | None,
    select_templates: bool | None,
    metadata_enabled: bool,
    announce: str | None,
    preset: str | None,
    stop_on_error: bool,
    step_callback: Callable[[str, str], None] | None,
    result_callback: Callable[[dict[str, dict]], None] | None = None,
    preset_config: dict | None = None,
    auto_mode: bool = False,
    dry_run: bool = False,
    source_root: Path | None = None,
) -> int:
    """Execute all selected pipeline modules in sequence.

    This is the main orchestration function that coordinates all pipeline steps.

    Args:
        work_folder: Working directory for pipeline operations
        output_folder: Output directory for processed files
        selected_modules: Set of module names to execute
        effective_remove_terms: Terms to remove during renaming
        settings: Application settings dictionary
        nfo_locale: NFO locale override
        nfo_mode: NFO mode override
        select_templates: Whether to select templates interactively
        metadata_enabled: Whether metadata fetching is enabled
        announce: Torrent announce URL
        preset: Prez preset name
        stop_on_error: Whether to stop pipeline on first error
        step_callback: Optional callback for step progress
        preset_config: Optional preset configuration
        auto_mode: Run the pipeline non-interactively when ``True``.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    from swirrl.commands.pipeline import (
        PipelineContext,
        release_artifacts_folder,
        release_payload_folder,
    )

    root = source_root or work_folder

    # Create Release/ structure upfront so Phase-2 output steps always have a home,
    # even when cleanmkv fails or is skipped.
    if not dry_run:
        release_artifacts_folder(root).mkdir(parents=True, exist_ok=True)

    report_rows: list[tuple[str, str, str, float]] = []
    selected_modules = _auto_enable_seedbox(selected_modules, settings)

    steps = _build_phase1_steps(
        root=root,
        selected_modules=selected_modules,
        effective_remove_terms=effective_remove_terms,
        preset_config=preset_config,
        auto_mode=auto_mode,
        dry_run=dry_run,
    )

    # Track timing for enhanced report
    pipeline_start_time = time.time()

    # Execute Phase 1
    phase1_results = _run_pipeline_with_progress(
        steps, stop_on_error=stop_on_error, step_callback=step_callback
    )
    failures = _collect_phase_results(report_rows, phase1_results)

    # When cleanmkv was selected but failed, copy the original MKVs to the release
    # payload folder so Phase-2 steps (nfo, prez, torrent) have a valid work folder.
    if (
        not dry_run
        and "cleanmkv" in selected_modules
        and not phase1_results.get("cleanmkv", {}).get("success", True)
    ):
        import shutil as _shutil

        _payload = release_payload_folder(root)
        _payload.mkdir(parents=True, exist_ok=True)
        _copied = 0
        for _mkv in root.glob("*.mkv"):
            _dest = _payload / _mkv.name
            if not _dest.exists():
                _shutil.copy2(_mkv, _dest)
                _copied += 1
        if _copied:
            print_warning(
                tr(
                    "pipeline.warn.cleanmkv_fallback",
                    default="CleanMKV failed — copied {n} original MKV(s) to {dest}",
                    n=_copied,
                    dest=_payload,
                )
            )

    if failures and stop_on_error:
        if result_callback is not None:
            result_callback(dict(phase1_results))
        return _first_failure_code(phase1_results)

    # Update work folder after transform steps
    work_folder = _next_work_folder(root, settings)
    output_folder = _pipeline_output_folder(work_folder, root)
    print_info(
        tr("pipeline.info.work_folder", default="Release folder for output steps")
        + f": {work_folder}"
    )
    print_info(tr("pipeline.info.output_folder", default="Output folder") + f": {output_folder}")

    context = PipelineContext(dry_run=dry_run)
    output_steps = _build_phase2_steps(
        root=root,
        work_folder=work_folder,
        output_folder=output_folder,
        selected_modules=selected_modules,
        settings=settings,
        nfo_locale=nfo_locale,
        nfo_mode=nfo_mode,
        select_templates=select_templates,
        metadata_enabled=metadata_enabled and ("metadata" in selected_modules),
        announce=announce,
        preset=preset,
        auto_mode=auto_mode,
        dry_run=dry_run,
        context=context,
    )

    # Execute Phase 2
    phase2_results = _run_pipeline_with_progress(
        output_steps, stop_on_error=stop_on_error, step_callback=step_callback
    )
    failures += _collect_phase_results(report_rows, phase2_results)

    if "rename-parent" in selected_modules:
        rename_label = _module_label("rename-parent")
        should_run_rename_parent, skip_reason = _artifacts_ready_for_rename_parent(
            selected_modules,
            phase2_results,
        )
        if should_run_rename_parent:
            if step_callback is not None:
                with contextlib.suppress(Exception):
                    step_callback("rename-parent", rename_label)
            else:
                print_info(
                    tr(
                        "pipeline.step.running",
                        default="{label} in progress...",
                        label=rename_label,
                    )
                )
            rename_start = time.time()
            rename_code = _rename_parent_step(root, settings, dry_run=dry_run)
            rename_elapsed = time.time() - rename_start
            rename_success = rename_code == 0
            phase2_results["rename-parent"] = {
                "success": rename_success,
                "code": rename_code,
                "elapsed": rename_elapsed,
                "label": rename_label,
                "error": None
                if rename_success
                else tr(
                    "pipeline.error.step_exit_code",
                    default="{label}: exit code {code}",
                    label=rename_label,
                    code=rename_code,
                ),
            }
            status_str, details = _status_and_details(phase2_results["rename-parent"])
            report_rows.append(("rename-parent", status_str, details, rename_elapsed))
            if not rename_success:
                failures += 1
        else:
            phase2_results["rename-parent"] = {
                "success": False,
                "code": -1,
                "elapsed": 0.0,
                "label": rename_label,
                "skipped": True,
                "error": skip_reason,
            }
            report_rows.append(
                (
                    "rename-parent",
                    tr("common.skipped", default="Skipped"),
                    skip_reason,
                    0.0,
                )
            )

    if result_callback is not None:
        result_callback({**phase1_results, **phase2_results})

    # Calculate total pipeline time
    total_pipeline_time = time.time() - pipeline_start_time

    print_pipeline_report(root, report_rows, total_time=total_pipeline_time)

    if failures:
        print_error(
            tr(
                "pipeline.error.completed_with_failures",
                default="Pipeline completed with {count} failed step(s).",
                count=failures,
            )
        )
        return 1

    print_success(tr("pipeline.success.completed", default="Pipeline completed."))
    return 0
