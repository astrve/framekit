"""Pipeline orchestration and execution logic.

This module handles the core pipeline execution flow, including:
- Step sequencing and execution
- Progress tracking and timing
- Error handling and recovery
- Result reporting
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from framekit.commands.pipeline_preview import print_pipeline_report
from framekit.commands.pipeline_steps import (
    _cleanmkv_step,
    _encoder_step,
    _nfo_step,
    _prez_step,
    _renamer_step,
    _torrent_step,
    _upload_step,
)
from framekit.core.i18n import tr
from framekit.ui.console import print_error, print_info, print_success, print_warning

# Type-only import: ``pipeline`` imports ``pipeline_orchestrator`` at runtime,
# so a real import here would create a cycle. Guard with ``TYPE_CHECKING`` so
# pyright resolves ``PipelineStep`` without affecting runtime semantics.
if TYPE_CHECKING:
    from framekit.commands.pipeline import PipelineStep


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
        "encoder": tr("pipeline.step.encoder", default="Encoder"),
        "nfo": tr("pipeline.step.nfo", default="NFO + Metadata"),
        "torrent": tr("pipeline.step.torrent", default="Torrent"),
        "prez": tr("pipeline.step.prez", default="Prez"),
        "upload": tr("pipeline.step.upload", default="Upload"),
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
    from framekit.commands.pipeline import (
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
    from framekit.commands.pipeline import _release_artifacts_folder

    if work_folder.parent.name == "Release":
        return work_folder.parent
    if root is not None:
        return _release_artifacts_folder(root)
    return work_folder


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
    import contextlib

    results = {}

    for i, (module_name, label, callback) in enumerate(steps, 1):
        if step_callback is not None:
            with contextlib.suppress(Exception):
                step_callback(module_name, label)

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
                    for remaining_module, remaining_label, _ in steps[i:]:
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
                for remaining_module, remaining_label, _ in steps[i:]:
                    results[remaining_module] = {
                        "success": False,
                        "code": -1,
                        "elapsed": 0,
                        "label": remaining_label,
                        "skipped": True,
                    }
                break

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
                ("renamer", _module_label("renamer"), lambda: _renamer_step(root, terms_for_step))
            )
        else:
            steps.append(("renamer", _module_label("renamer"), lambda: _renamer_step(root)))

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
    if "encoder" in selected_modules:
        if dry_run:
            from framekit.commands.pipeline_steps import _encoder_step_dry_run

            output_steps.append(
                (
                    "encoder",
                    _module_label("encoder"),
                    lambda: _encoder_step_dry_run(work_folder, settings),
                )
            )
        else:
            output_steps.append(
                (
                    "encoder",
                    _module_label("encoder"),
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
    from framekit.commands.pipeline import (
        PipelineContext,
        release_artifacts_folder,
        release_payload_folder,
    )

    root = work_folder

    # Create Release/ structure upfront so Phase-2 output steps always have a home,
    # even when cleanmkv fails or is skipped.
    if not dry_run:
        release_artifacts_folder(root).mkdir(parents=True, exist_ok=True)

    report_rows: list[tuple[str, str, str, float]] = []
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
        work_folder=work_folder,
        output_folder=output_folder,
        selected_modules=selected_modules,
        settings=settings,
        nfo_locale=nfo_locale,
        nfo_mode=nfo_mode,
        select_templates=select_templates,
        metadata_enabled=metadata_enabled,
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
