"""Pipeline step implementations.

This module contains the individual step functions for each pipeline module:
renamer, cleanmkv, metadata, nfo, torrent, prez, encode, screenshot, seedbox,
rename-parent, and upload.
"""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from swirrl.commands.cleanmkv import run_cleanmkv_command
from swirrl.commands.nfo import run_nfo_command
from swirrl.commands.renamer import run_renamer_command
from swirrl.commands.torrent import run_torrent_command
from swirrl.core.i18n import tr
from swirrl.core.models.nfo import ReleaseNfoData
from swirrl.core.naming import torrent_name_from_payload
from swirrl.core.paths import get_config_dir
from swirrl.core.settings import (
    Settings,
    SettingsStore,
    metadata_language_for_nfo_locale,
    resolve_nfo_locale,
)
from swirrl.modules.metadata.workflow import run_metadata_workflow
from swirrl.modules.nfo.builder import build_release_nfo
from swirrl.modules.nfo.scanner import scan_nfo_folder
from swirrl.modules.nfo.service import NfoService
from swirrl.modules.prez.banner_selector import (
    build_banner_urls,
    normalize_banner_language,
    select_banner_design,
)
from swirrl.modules.prez.service import PREZ_PRESETS, PrezBuildOptions, PrezService
from swirrl.ui.console import (
    print_error,
    print_info,
    print_success,
    print_warning,
)

# PipelineContext imported only for type checkers to break the import cycle.
if TYPE_CHECKING:
    from swirrl.commands.pipeline import PipelineContext
    from swirrl.modules.upload.models import TorrentMetadata


def _renamer_step(
    root: Path, remove_terms: tuple[str, ...] = (), *, auto_mode: bool = False
) -> int:
    """Execute renamer step: standardize filenames.

    Args:
        root: Root directory containing files to rename
        remove_terms: Terms to remove from filenames

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    # Inside the pipeline, the term picker (if any) has already run upstream
    # in `run_pipeline_command`. We force `select_terms=False` here so that
    # `run_renamer_command` never re-opens the picker mid-pipeline, regardless
    # of TTY state.
    return run_renamer_command(
        path=str(root),
        lang=None,
        apply_changes=True,
        dry_run=False,
        force_lang=False,
        remove_terms=remove_terms,
        select_terms=False,
        interactive_conflict_resolution=not auto_mode,
    )


def _cleanmkv_step(
    root: Path,
    *,
    auto_mode: bool = False,
    preset_name: str | None = None,
    external_preset: str | None = None,
    output_dir_name: str | None = None,
) -> int:
    """Execute cleanmkv step: remove unwanted tracks from MKV files.

    Args:
        root: Root directory containing MKV files
        auto_mode: Whether to run in auto mode (no interaction)
        preset_name: Name of cleanmkv preset to use
        external_preset: Path to external preset file
        output_dir_name: Output directory name override

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    # In auto_mode, apply changes immediately without interaction.
    # In interactive mode (auto_mode=False), allow track selection and confirmation.
    # The user already chose cleanmkv as a step, but they should still be able to
    # select tracks and confirm the plan before applying.
    return run_cleanmkv_command(
        path=str(root),
        apply_changes=auto_mode,  # Only auto-apply in auto mode
        dry_run=False,
        preset_name=preset_name,
        preset_file=None,
        external_preset=external_preset,
        wizard=False,
        save_preset=None,
        list_presets=False,
        auto_mode=auto_mode,
        output_dir_name_override=output_dir_name,
    )


def _resolve_pipeline_locale(settings: dict, nfo_locale: str | None) -> str:
    """Resolve the effective NFO locale for the pipeline.

    Args:
        settings: Application settings dictionary
        nfo_locale: NFO locale override

    Returns:
        Resolved locale string
    """
    configured = nfo_locale or str(settings.get("modules", {}).get("nfo", {}).get("locale", "auto"))
    return resolve_nfo_locale(
        configured,
        ui_locale=str(settings.get("general", {}).get("locale", "en")),
    )


def _ensure_release_context(work_folder: Path, context: PipelineContext) -> ReleaseNfoData:
    """Ensure release context is populated by scanning folder if needed.

    Args:
        work_folder: Working directory to scan
        context: Pipeline context to update

    Returns:
        Release NFO data

    Raises:
        ValueError: If no MKV files found
    """
    if context.release is not None:
        return context.release
    episodes = scan_nfo_folder(work_folder)
    if not episodes:
        raise ValueError(
            tr(
                "nfo.error.no_mkv",
                default="No MKV files found in folder: {folder}",
                folder=work_folder,
            )
        )
    context.release = build_release_nfo(work_folder, episodes)
    return context.release


def _ensure_metadata_context(
    release: ReleaseNfoData,
    settings: dict,
    context: PipelineContext,
    locale: str,
    *,
    metadata_enabled: bool = True,
    auto_mode: bool = False,
) -> dict:
    """Ensure metadata context is populated by running metadata workflow if needed.

    Args:
        release: Release NFO data
        settings: Application settings dictionary
        context: Pipeline context to update
        locale: NFO locale
        metadata_enabled: Whether metadata fetching is enabled
        auto_mode: Whether running in auto mode

    Returns:
        Metadata context dictionary
    """
    if not metadata_enabled:
        context.metadata_context = {}
        return {}
    if context.metadata_context is not None:
        return context.metadata_context
    result = run_metadata_workflow(
        release,
        settings,
        auto_accept=auto_mode,
        show_ui=not auto_mode,
        language_override=metadata_language_for_nfo_locale(locale),
    )
    context.metadata_context = result.context if result.status == "resolved" else {}
    return context.metadata_context


def _metadata_step(
    work_folder: Path,
    nfo_locale: str | None,
    context: PipelineContext | None = None,
    settings: dict | None = None,
    *,
    metadata_enabled: bool = True,
    auto_mode: bool = False,
) -> int:
    """Execute metadata step: resolve and cache metadata context."""
    if not metadata_enabled:
        if context is not None:
            context.metadata_context = {}
        print_info(
            tr(
                "pipeline.metadata.disabled",
                default="Metadata disabled for this run.",
            )
        )
        return 0

    if context is None or settings is None:
        return 0

    release = _ensure_release_context(work_folder, context)
    resolved_locale = _resolve_pipeline_locale(settings, nfo_locale)
    metadata_context = _ensure_metadata_context(
        release,
        settings,
        context,
        resolved_locale,
        metadata_enabled=True,
        auto_mode=auto_mode,
    )
    if metadata_context:
        print_success(
            tr(
                "pipeline.metadata.resolved",
                default="Metadata context resolved.",
            )
        )
    else:
        print_warning(
            tr(
                "pipeline.metadata.empty",
                default="No metadata resolved for this release.",
            )
        )
    return 0


def _formats_from_prez_setting(value: str | None) -> tuple[str, ...]:
    """Convert prez format setting to tuple of format strings.

    Args:
        value: Format setting value ("both", "html", "bbcode", "mediainfo")

    Returns:
        Tuple of format strings
    """
    selected = (value or "both").strip().lower()
    if selected == "both":
        return ("html", "bbcode")
    if selected == "mediainfo":
        return ()
    return (selected,)


def _run_nfo_command_fallback(
    *,
    work_folder: Path,
    nfo_locale: str | None,
    metadata_enabled: bool,
    nfo_mode: str | None,
    auto_mode: bool,
) -> int:
    return run_nfo_command(
        path=str(work_folder),
        template=None,
        nfo_locale=nfo_locale,
        write_requested=True,
        with_metadata=metadata_enabled,
        metadata_auto_accept=auto_mode,
        list_templates=False,
        import_template=None,
        import_name=None,
        import_scope=None,
        import_location=None,
        import_logo=None,
        logo_name=None,
        set_logo=None,
        list_logos=False,
        clear_logo=False,
        mode=nfo_mode,
    )


def _resolve_nfo_effective_mode(nfo_settings: dict, nfo_mode: str | None) -> str:
    settings_mode = str(nfo_settings.get("mode", "global") or "global").lower()
    if settings_mode not in ("global", "per_file", "both"):
        settings_mode = "global"
    if nfo_mode is None:
        return settings_mode
    return nfo_mode if nfo_mode in ("global", "per_file", "both") else settings_mode


def _execute_global_nfo_mode(
    *,
    service: NfoService,
    work_folder: Path,
    output_folder: Path | None,
    release: ReleaseNfoData,
    template_name: str,
    logo_path: str,
    resolved_locale: str,
    metadata_context: dict,
    dry_run: bool,
) -> Path | None:
    report, release, rendered = service.build_from_release(
        work_folder,
        release=release,
        template_name=template_name,
        logo_path=logo_path,
        template_locale=resolved_locale,
        extra_context=metadata_context,
    )
    resolved_template = str(report.details[0].after.get("template", template_name))
    if dry_run:
        print_info(
            tr(
                "pipeline.dry_run.nfo_global",
                default="[dry-run] Would write global NFO to: {path}",
                path=output_folder or work_folder,
            )
        )
        return None
    _write_report, written_global = service.write_rendered(
        output_folder or work_folder,
        release=release,
        rendered=rendered,
        template_name=resolved_template,
        template_locale=resolved_locale,
    )
    print_info(tr("nfo.success.written", default="NFO written: {path}", path=written_global))
    return written_global


def _execute_per_file_nfo_mode(
    *,
    service: NfoService,
    work_folder: Path,
    output_folder: Path | None,
    release: ReleaseNfoData,
    template_name: str,
    logo_path: str,
    resolved_locale: str,
    metadata_context: dict,
    dry_run: bool,
) -> list[Path]:
    per_file_results = service.build_per_file(
        work_folder,
        template_name=template_name,
        logo_path=logo_path,
        template_locale=resolved_locale,
        extra_context=metadata_context,
    )
    target_dir = output_folder or work_folder
    if dry_run:
        print_info(
            tr(
                "pipeline.dry_run.nfo_per_file",
                default="[dry-run] Would write {count} per-file NFOs",
                count=len(per_file_results),
            )
        )
        return []
    written_per_file = _write_pipeline_per_file_nfos(per_file_results, target_dir)
    for path in written_per_file:
        print_info(tr("nfo.success.written", default="NFO written: {path}", path=path))
    return written_per_file


def _assign_nfo_output_context(
    context: PipelineContext, written_global: Path | None, written_per_file: list[Path]
) -> None:
    context.nfo_outputs = tuple(
        path for path in ([written_global] if written_global else []) + written_per_file
    )
    context.nfo_path = written_global or (written_per_file[0] if written_per_file else None)


def _write_pipeline_sidecar_nfo(
    *,
    release: ReleaseNfoData,
    rendered: str,
    output_folder: Path | None,
    dry_run: bool,
) -> Path | None:
    if not release.episodes:
        return None
    source_file = release.episodes[0].file_path
    target_dir = output_folder or source_file.parent
    target = target_dir / source_file.with_suffix(".nfo").name
    if dry_run:
        print_info(
            tr(
                "pipeline.dry_run.nfo_sidecar",
                default="[dry-run] Would write sidecar NFO: {path}",
                path=target,
            )
        )
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered, encoding="utf-8")
    print_info(tr("nfo.success.written", default="NFO written: {path}", path=target))
    return target


def _write_pipeline_per_file_nfos(
    results: Sequence[tuple[object, ReleaseNfoData, str, Path]], output_folder: Path
) -> list[Path]:
    output_folder.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for _report, _release, rendered, source_path in results:
        target = output_folder / source_path.with_suffix(".nfo").name
        target.write_text(rendered, encoding="utf-8")
        written.append(target)
    return written


def _nfo_step(
    work_folder: Path,
    nfo_locale: str | None,
    context: PipelineContext | None = None,
    settings: dict | None = None,
    metadata_enabled: bool = True,
    output_folder: Path | None = None,
    nfo_mode: str | None = None,
    auto_mode: bool = False,
) -> int:
    """Execute NFO step: generate NFO files with metadata.

    Args:
        work_folder: Working directory containing MKV files
        nfo_locale: NFO locale override
        context: Pipeline context (optional)
        settings: Application settings (optional)
        metadata_enabled: Whether metadata fetching is enabled
        output_folder: Output directory for NFO files
        nfo_mode: NFO mode ("global", "per_file", "both")
        auto_mode: Whether running in auto mode

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    if context is None or settings is None:
        return _run_nfo_command_fallback(
            work_folder=work_folder,
            nfo_locale=nfo_locale,
            metadata_enabled=metadata_enabled,
            nfo_mode=nfo_mode,
            auto_mode=auto_mode,
        )

    release = _ensure_release_context(work_folder, context)
    resolved_locale = _resolve_pipeline_locale(settings, nfo_locale)
    metadata_context = _ensure_metadata_context(
        release,
        settings,
        context,
        resolved_locale,
        metadata_enabled=metadata_enabled,
        auto_mode=auto_mode,
    )
    nfo_settings = settings.setdefault("modules", {}).setdefault("nfo", {})
    template_name = str(nfo_settings.get("active_template", "default") or "default")
    logo_path = str(nfo_settings.get("logo_path", "") or "")
    effective_mode = _resolve_nfo_effective_mode(nfo_settings, nfo_mode)
    service = NfoService()
    dry_run = context.dry_run
    media_kind = (release.media_kind or "").lower()

    # Upload-safe policy:
    # - movie/single_episode: sidecar NFO next to MKV + global NFO in release folder.
    # - season/special packs: per-file NFOs + global NFO in release folder.
    if media_kind in {"movie", "single_episode"}:
        report, built_release, rendered = service.build_from_release(
            work_folder,
            release=release,
            template_name=template_name,
            logo_path=logo_path,
            template_locale=resolved_locale,
            extra_context=metadata_context,
        )
        resolved_template = str(report.details[0].after.get("template", template_name))
        written_global = (
            None
            if dry_run
            else service.write_rendered(
                output_folder or work_folder,
                release=built_release,
                rendered=rendered,
                template_name=resolved_template,
                template_locale=resolved_locale,
            )[1]
        )
        if dry_run:
            print_info(
                tr(
                    "pipeline.dry_run.nfo_global",
                    default="[dry-run] Would write global NFO to: {path}",
                    path=output_folder or work_folder,
                )
            )
        elif written_global is not None:
            print_info(
                tr("nfo.success.written", default="NFO written: {path}", path=written_global)
            )

        written_sidecar = _write_pipeline_sidecar_nfo(
            release=built_release,
            rendered=rendered,
            output_folder=output_folder,
            dry_run=dry_run,
        )
        context.nfo_outputs = tuple(
            path for path in (written_global, written_sidecar) if isinstance(path, Path)
        )
        context.nfo_path = written_global or written_sidecar
        return 0

    if media_kind in {"season_pack", "special_pack"}:
        written_global = _execute_global_nfo_mode(
            service=service,
            work_folder=work_folder,
            output_folder=output_folder,
            release=release,
            template_name=template_name,
            logo_path=logo_path,
            resolved_locale=resolved_locale,
            metadata_context=metadata_context,
            dry_run=dry_run,
        )
        written_per_file = _execute_per_file_nfo_mode(
            service=service,
            work_folder=work_folder,
            output_folder=output_folder,
            release=release,
            template_name=template_name,
            logo_path=logo_path,
            resolved_locale=resolved_locale,
            metadata_context=metadata_context,
            dry_run=dry_run,
        )
        _assign_nfo_output_context(context, written_global, written_per_file)
        return 0

    written_global = (
        _execute_global_nfo_mode(
            service=service,
            work_folder=work_folder,
            output_folder=output_folder,
            release=release,
            template_name=template_name,
            logo_path=logo_path,
            resolved_locale=resolved_locale,
            metadata_context=metadata_context,
            dry_run=dry_run,
        )
        if effective_mode in ("global", "both")
        else None
    )
    written_per_file = (
        _execute_per_file_nfo_mode(
            service=service,
            work_folder=work_folder,
            output_folder=output_folder,
            release=release,
            template_name=template_name,
            logo_path=logo_path,
            resolved_locale=resolved_locale,
            metadata_context=metadata_context,
            dry_run=dry_run,
        )
        if effective_mode in ("per_file", "both")
        else []
    )
    _assign_nfo_output_context(context, written_global, written_per_file)
    return 0


def _torrent_step(
    work_folder: Path,
    announce: str | None,
    context: PipelineContext | None = None,
    output_folder: Path | None = None,
    settings: dict | None = None,
) -> int:
    """Execute torrent step: create torrent file.

    Args:
        work_folder: Working directory containing files to torrent
        announce: Torrent announce URL
        context: Pipeline context (optional)
        output_folder: Output directory for torrent file

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    torrent_output = (
        output_folder or work_folder.parent
    ) / f"{torrent_name_from_payload(work_folder)}.torrent"
    torrent_settings = (settings or {}).get("modules", {}).get("torrent", {})
    configured_mode = str(
        torrent_settings.get("pipeline_content_mode", "folder") or "folder"
    ).lower()
    content_mode = configured_mode if configured_mode in {"auto", "media", "folder"} else "folder"
    effective_dry_run = context.dry_run if context else False
    if effective_dry_run:
        print_info(
            tr(
                "pipeline.dry_run.torrent",
                default="[dry-run] Would create torrent: {path}",
                path=torrent_output,
            )
        )
        return 0
    code = run_torrent_command(
        path=str(work_folder),
        output=str(torrent_output),
        announce=announce,
        private=None,
        piece_length=None,
        dry_run=False,
        content_mode=content_mode,
    )
    if context is not None and code == 0:
        context.torrent_path = torrent_output
    return code


def _prez_step(
    work_folder: Path,
    nfo_locale: str | None,
    context: PipelineContext | None = None,
    settings: dict | None = None,
    preset: str | None = None,
    metadata_enabled: bool = True,
    output_folder: Path | None = None,
    select_templates: bool | None = None,
    auto_mode: bool = False,
) -> int:
    """Execute prez step: generate presentation files (HTML/BBCode).

    Args:
        work_folder: Working directory containing release
        nfo_locale: NFO locale override
        context: Pipeline context (optional)
        settings: Application settings (optional)
        preset: Prez preset name
        metadata_enabled: Whether metadata fetching is enabled
        output_folder: Output directory for prez files
        select_templates: Whether to select templates interactively
        auto_mode: Whether running in auto mode

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    if context is None or settings is None:
        from swirrl.commands.prez import run_prez_command

        return run_prez_command(
            path=str(work_folder),
            output_dir=None,
            output_format="both",
            with_metadata=metadata_enabled,
            locale=nfo_locale,
            dry_run=False,
            preset=preset,
            select_templates=select_templates,
        )

    release = _ensure_release_context(work_folder, context)
    resolved_locale = _resolve_pipeline_locale(settings, nfo_locale)
    metadata_context = _ensure_metadata_context(
        release,
        settings,
        context,
        resolved_locale,
        metadata_enabled=metadata_enabled,
        auto_mode=auto_mode,
    )
    prez_settings = settings.setdefault("modules", {}).setdefault("prez", {})
    (
        preset_name,
        output_format,
        html_template,
        bbcode_template,
        mediainfo_mode,
    ) = _resolve_prez_pipeline_configuration(prez_settings, preset)

    html_template, bbcode_template = _resolve_prez_templates_for_pipeline(
        output_format=output_format,
        html_template=html_template,
        bbcode_template=bbcode_template,
        preset=preset,
        auto_mode=auto_mode,
        select_templates=select_templates,
    )
    formats_tuple = _formats_from_prez_setting(output_format)
    banner_urls = _resolve_pipeline_banner_urls(
        prez_settings=prez_settings,
        resolved_locale=resolved_locale,
        formats_tuple=formats_tuple,
        preset=preset,
        auto_mode=auto_mode,
        settings=settings,
    )

    effective_dry_run = context.dry_run
    options = _build_pipeline_prez_options(
        formats_tuple=formats_tuple,
        output_folder=output_folder,
        metadata_context=metadata_context,
        resolved_locale=resolved_locale,
        mediainfo_mode=mediainfo_mode,
        html_template=html_template,
        bbcode_template=bbcode_template,
        preset_name=preset_name,
        release=release,
        banner_urls=banner_urls,
    )
    _report, result = PrezService().build(work_folder, options=options, write=not effective_dry_run)
    _finalize_pipeline_prez_step(
        context=context,
        result=result,
        formats_tuple=formats_tuple,
        dry_run=effective_dry_run,
    )
    return 0


_PIPELINE_VIDEO_SUFFIXES = {".mkv", ".mp4", ".m4v", ".avi", ".mov", ".m2ts", ".ts"}


def _clamp_int(value: object, default: int, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return min(max(parsed, minimum), maximum)


def _coerce_positive_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _coerce_float(value: object, default: float, *, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return min(max(parsed, minimum), maximum)


def _resolve_screenshot_pipeline_config(settings: dict) -> tuple[object, str, str]:
    from swirrl.core.models.screenshot import ScreenshotConfig

    screenshot_settings = settings.get("modules", {}).get("screenshot", {})
    if not isinstance(screenshot_settings, dict):
        screenshot_settings = {}
    fmt = str(screenshot_settings.get("format", "png") or "png").strip().lower()
    if fmt == "jpeg":
        fmt = "jpg"
    if fmt not in {"png", "jpg"}:
        fmt = "png"
    output_dir_name = str(screenshot_settings.get("output_dir_name", "screens") or "screens").strip()
    if not output_dir_name:
        output_dir_name = "screens"
    target = str(screenshot_settings.get("target", "prez") or "prez").strip().lower()
    if target not in {"prez", "nfo", "both", "none"}:
        target = "prez"
    config = ScreenshotConfig(
        count=_clamp_int(screenshot_settings.get("count"), 6, minimum=1, maximum=50),
        width=_coerce_positive_int(screenshot_settings.get("width")),
        height=_coerce_positive_int(screenshot_settings.get("height")),
        quality=_clamp_int(screenshot_settings.get("quality"), 2, minimum=1, maximum=31),
        format=fmt,
        skip_start_seconds=_clamp_int(
            screenshot_settings.get("skip_start_seconds"), 60, minimum=0, maximum=3600
        ),
        skip_end_seconds=_clamp_int(
            screenshot_settings.get("skip_end_seconds"), 120, minimum=0, maximum=3600
        ),
        skip_start_percent=_coerce_float(
            screenshot_settings.get("skip_start_percent"), 5.0, minimum=0.0, maximum=100.0
        ),
        skip_end_percent=_coerce_float(
            screenshot_settings.get("skip_end_percent"), 5.0, minimum=0.0, maximum=100.0
        ),
        avoid_black_frames=bool(screenshot_settings.get("avoid_black_frames", True)),
        black_threshold=_coerce_float(
            screenshot_settings.get("black_threshold"), 0.05, minimum=0.0, maximum=1.0
        ),
        min_interval_seconds=_clamp_int(
            screenshot_settings.get("min_interval_seconds"), 30, minimum=1, maximum=3600
        ),
    )
    return config, output_dir_name, target


def _pipeline_video_inputs(work_folder: Path, context: PipelineContext | None) -> list[Path]:
    if context is not None and context.release is not None and context.release.episodes:
        candidates = [
            Path(episode.file_path)
            for episode in context.release.episodes
            if Path(episode.file_path).exists()
        ]
        unique = sorted({path.resolve(): path for path in candidates}.values(), key=lambda p: p.name.lower())
        if unique:
            return unique
    if not work_folder.exists():
        return []
    return sorted(
        path
        for path in work_folder.iterdir()
        if path.is_file() and path.suffix.lower() in _PIPELINE_VIDEO_SUFFIXES
    )


def _render_screenshot_nfo_block(screenshots: Sequence[Path]) -> str:
    lines = ["", "<!-- Swirrl Screenshots -->", "<screenshots>"]
    for path in screenshots:
        lines.append(f"  <shot>{path.name}</shot>")
    lines.extend(["</screenshots>", ""])
    return "\n".join(lines)


def _render_screenshot_bbcode_block(screenshots: Sequence[Path]) -> str:
    lines = ["", "[b]Screenshots[/b]"]
    for path in screenshots:
        lines.append(f"[img]{path.as_posix()}[/img]")
    lines.append("")
    return "\n".join(lines)


def _render_screenshot_html_block(screenshots: Sequence[Path]) -> str:
    lines = [
        "",
        "<section class=\"swirrl-screenshots\">",
        "  <h2>Screenshots</h2>",
        "  <div class=\"swirrl-screenshots-grid\">",
    ]
    for path in screenshots:
        src = path.as_posix()
        lines.append(f"    <img src=\"{src}\" alt=\"{path.name}\" loading=\"lazy\"/>")
    lines.extend(["  </div>", "</section>", ""])
    return "\n".join(lines)


def _append_screenshot_block(path: Path, block: str, marker: str) -> None:
    try:
        existing = path.read_text(encoding="utf-8")
    except Exception as exc:
        print_warning(f"Failed to read {path.name} for screenshot injection: {exc}")
        return
    if marker in existing:
        return
    try:
        path.write_text(existing.rstrip() + "\n" + block, encoding="utf-8")
    except Exception as exc:
        print_warning(f"Failed to inject screenshots into {path.name}: {exc}")


def _inject_pipeline_screenshots_into_outputs(
    *,
    context: PipelineContext | None,
    screenshots: Sequence[Path],
    target: str,
) -> None:
    if context is None or not screenshots or target == "none":
        return

    if target in {"nfo", "both"}:
        for nfo_path in context.nfo_outputs:
            if nfo_path.exists() and nfo_path.suffix.lower() == ".nfo":
                _append_screenshot_block(
                    nfo_path,
                    _render_screenshot_nfo_block(screenshots),
                    "<!-- Swirrl Screenshots -->",
                )

    if target in {"prez", "both"}:
        for output in context.prez_outputs:
            if not output.exists():
                continue
            suffix = output.suffix.lower()
            if suffix == ".html":
                _append_screenshot_block(
                    output,
                    _render_screenshot_html_block(screenshots),
                    "<section class=\"swirrl-screenshots\">",
                )
            elif output.name.lower().endswith(".bbcode.txt"):
                _append_screenshot_block(
                    output,
                    _render_screenshot_bbcode_block(screenshots),
                    "[b]Screenshots[/b]",
                )


def _screenshot_step(
    work_folder: Path,
    context: PipelineContext | None = None,
    settings: dict | None = None,
) -> int:
    """Execute screenshot step: extract stills from release video files."""
    from swirrl.modules.screenshot.service import ScreenshotService

    if context is not None and context.dry_run:
        print_info(
            tr(
                "pipeline.dry_run.screenshot",
                default="[dry-run] Would extract screenshots from release videos",
            )
        )
        return 0

    if settings is None:
        settings = SettingsStore().load()
    config, output_dir_name, target = _resolve_screenshot_pipeline_config(settings)
    videos = _pipeline_video_inputs(work_folder, context)
    if not videos:
        print_info(
            tr(
                "pipeline.screenshot.no_videos",
                default="No video files found for screenshot extraction.",
            )
        )
        return 0

    output_dir = work_folder / output_dir_name
    service = ScreenshotService()
    report = service.extract_screenshots(
        video_paths=videos,
        output_dir=output_dir,
        config=config,
        release_name=work_folder.name,
    )
    screenshots = tuple(
        screenshot
        for result in report.results
        for screenshot in result.screenshots
        if screenshot.exists()
    )
    if context is not None:
        context.screenshot_outputs = screenshots
    if report.total_failures and not screenshots:
        print_error(
            tr(
                "pipeline.screenshot.failed",
                default="Screenshot extraction failed for all inputs.",
            )
        )
        return 1
    if screenshots:
        print_success(
            tr(
                "pipeline.screenshot.done",
                default="Extracted {count} screenshot(s).",
                count=len(screenshots),
            )
        )
        _inject_pipeline_screenshots_into_outputs(
            context=context,
            screenshots=screenshots,
            target=target,
        )
    return 0


def _seedbox_step(
    work_folder: Path,
    settings: dict | None = None,
    *,
    auto_mode: bool = False,
) -> int:
    """Execute seedbox step before upload."""
    from swirrl.commands.seedbox import (
        run_seedbox_push,
        seedbox_ready_for_pipeline,
    )

    current_settings = settings if settings is not None else SettingsStore().load()
    ready, message = seedbox_ready_for_pipeline(current_settings)
    if not ready:
        print_warning(message)
        return 1
    return run_seedbox_push(
        path=str(work_folder),
        seedbox_name=None,
        remote_path=None,
        category=None,
        dry_run=False,
        verbose=auto_mode,
        allow_cwd=False,
        non_interactive=True,
    )


def _rename_parent_step(root: Path, settings: dict | None = None, *, dry_run: bool = False) -> int:
    """Execute rename-parent step as final pipeline action."""
    from swirrl.commands.tools import _derive_name_from_payload, _derive_name_from_renamer, _rename_folder

    if not root.exists() or not root.is_dir():
        return 1
    current_settings = settings if settings is not None else SettingsStore().load()
    default_lang = str(
        (current_settings.get("modules") or {}).get("renamer", {}).get("default_language_tag")
        or "MULTI"
    )
    new_name = _derive_name_from_payload(root) or _derive_name_from_renamer(root, default_lang)
    if not new_name:
        print_warning(
            tr(
                "tools.rename_parent.no_files",
                default="Could not derive a folder name — no recognizable release files found in {folder}",
                folder=root,
            )
        )
        return 1
    _rename_folder(root, new_name, apply=not dry_run)
    return 0


def _resolve_prez_pipeline_configuration(
    prez_settings: dict, preset: str | None
) -> tuple[str, str, str, str, str]:
    preset_name = (preset or str(prez_settings.get("preset", "default") or "default")).lower()
    if preset_name not in PREZ_PRESETS:
        preset_name = "default"
    preset_values = PREZ_PRESETS[preset_name]
    html_template = _resolve_prez_setting_value(
        preset_values=preset_values,
        prez_settings=prez_settings,
        setting_key="html_template",
        preset_forced=bool(preset),
    )
    bbcode_template = _resolve_prez_setting_value(
        preset_values=preset_values,
        prez_settings=prez_settings,
        setting_key="bbcode_template",
        preset_forced=bool(preset),
    )
    output_format = _resolve_prez_setting_value(
        preset_values=preset_values,
        prez_settings=prez_settings,
        setting_key="format",
        preset_forced=bool(preset),
    )
    mediainfo_mode = _resolve_prez_setting_value(
        preset_values=preset_values,
        prez_settings=prez_settings,
        setting_key="mediainfo_mode",
        preset_forced=bool(preset),
    )
    return (
        preset_name,
        output_format,
        html_template,
        bbcode_template,
        mediainfo_mode,
    )


def _resolve_prez_setting_value(
    *,
    preset_values: dict[str, str],
    prez_settings: dict,
    setting_key: str,
    preset_forced: bool,
) -> str:
    configured = preset_values[setting_key] if preset_forced else prez_settings.get(setting_key)
    return str(configured or preset_values[setting_key])


def _resolve_prez_templates_for_pipeline(
    *,
    output_format: str,
    html_template: str,
    bbcode_template: str,
    preset: str | None,
    auto_mode: bool,
    select_templates: bool | None,
) -> tuple[str, str]:
    if select_templates is None:
        should_select_templates = bool(sys.stdin.isatty() and not preset and not auto_mode)
    else:
        should_select_templates = select_templates and not auto_mode
    if not should_select_templates:
        return html_template, bbcode_template
    from swirrl.commands.prez import (
        _maybe_select_templates,  # pyright: ignore[reportPrivateUsage]  # Internal helper shared between command modules
    )

    return _maybe_select_templates(
        formats=_formats_from_prez_setting(output_format),
        html_template=html_template,
        bbcode_template=bbcode_template,
        explicit_html=False,
        explicit_bbcode=False,
        explicit_preset=bool(preset),
        select_templates=True,
    )


def _resolve_pipeline_banner_urls(
    *,
    prez_settings: dict,
    resolved_locale: str,
    formats_tuple: tuple[str, ...],
    preset: str | None,
    auto_mode: bool,
    settings: dict,
) -> dict[str, str]:
    banner_language = normalize_banner_language(resolved_locale)
    banner_design = _resolve_pipeline_banner_design(
        prez_settings=prez_settings,
        formats_tuple=formats_tuple,
        preset=preset,
        auto_mode=auto_mode,
        banner_language=banner_language,
        settings=settings,
    )
    return build_banner_urls(banner_design, banner_language)


def _resolve_pipeline_banner_design(
    *,
    prez_settings: dict,
    formats_tuple: tuple[str, ...],
    preset: str | None,
    auto_mode: bool,
    banner_language: str,
    settings: dict,
) -> str:
    banner_design: str | None = prez_settings.get("banner_design")
    can_select = not auto_mode and sys.stdin.isatty() and "bbcode" in formats_tuple and not preset
    if can_select:
        chosen = select_banner_design(
            language=banner_language, current_design=banner_design, default_textual=True
        )
        banner_design = _persist_pipeline_banner_design(
            chosen=chosen,
            current_design=banner_design,
            prez_settings=prez_settings,
            settings=settings,
        )
    return banner_design or "textual"


def _persist_pipeline_banner_design(
    *,
    chosen: str | None,
    current_design: str | None,
    prez_settings: dict,
    settings: dict,
) -> str | None:
    if chosen is None:
        return current_design
    if chosen != current_design:
        prez_settings["banner_design"] = chosen
        with contextlib.suppress(Exception):
            SettingsStore().save(settings)
    return chosen


def _build_pipeline_prez_options(
    *,
    formats_tuple: tuple[str, ...],
    output_folder: Path | None,
    metadata_context: dict,
    resolved_locale: str,
    mediainfo_mode: str,
    html_template: str,
    bbcode_template: str,
    preset_name: str,
    release: ReleaseNfoData,
    banner_urls: dict[str, str],
) -> PrezBuildOptions:
    return PrezBuildOptions(
        formats=formats_tuple,
        output_dir=output_folder,
        metadata_context=metadata_context,
        locale=resolved_locale,
        mediainfo_mode=mediainfo_mode,
        html_template=html_template,
        bbcode_template=bbcode_template,
        preset=preset_name,
        release=release,
        banner_audio=banner_urls["audio"],
        banner_information=banner_urls["information"],
        banner_metadata=banner_urls["metadata"],
        banner_release=banner_urls["release"],
        banner_subtitles=banner_urls["subtitles"],
        banner_synopsis=banner_urls["synopsis"],
        banner_technical=banner_urls["technical"],
    )


def _finalize_pipeline_prez_step(
    *,
    context: PipelineContext,
    result,
    formats_tuple: tuple[str, ...],
    dry_run: bool,
) -> None:
    if dry_run:
        print_info(
            tr(
                "pipeline.dry_run.prez",
                default="[dry-run] Would generate prez files ({formats})",
                formats=", ".join(formats_tuple),
            )
        )
        return
    context.prez_outputs = result.outputs
    for output in result.outputs:
        print_info(tr("common.output", default="Output") + f": {output}")


def _encoder_step(work_folder: Path, settings: dict) -> int:
    """Execute encoder step: encode MKV files using configured preset.

    Encoded files replace originals in-place (cleanmkv already made copies).

    Args:
        work_folder: Working directory containing MKV files
        settings: Application settings dictionary

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    from swirrl.modules.encoder import EncoderService, PresetLoader

    preset_name, ffmpeg_path, ffprobe_path = _pipeline_encoder_settings(settings)
    if not preset_name:
        _warn_encoder_preset_missing(PresetLoader())
        return 0

    mkv_files = sorted(work_folder.glob("*.mkv"))
    if not mkv_files:
        print_info(
            tr(
                "pipeline.encoder.no_mkv",
                default="No MKV files to encode in: {folder}",
                folder=work_folder,
            )
        )
        return 0

    loader = PresetLoader()
    preset = _resolve_pipeline_encoder_preset(preset_name, loader)
    if preset is None:
        return 0

    service = _create_pipeline_encoder_service(
        preset,
        ffmpeg_path=ffmpeg_path,
        ffprobe_path=ffprobe_path,
        encoder_service_cls=EncoderService,
    )
    if service is None:
        return 1
    failures = _run_pipeline_encoder_jobs(service, mkv_files)
    return 0 if failures == 0 else 1


def _pipeline_encoder_settings(settings: dict) -> tuple[str, str, str]:
    encoder_settings = settings.get("modules", {}).get("encoder", {})
    preset_name = str(encoder_settings.get("preset", "") or "").strip()
    ffmpeg_path = str(encoder_settings.get("ffmpeg_path", "ffmpeg") or "ffmpeg")
    ffprobe_path = str(encoder_settings.get("ffprobe_path", "ffprobe") or "ffprobe")
    return preset_name, ffmpeg_path, ffprobe_path


def _available_encoder_preset_hint(loader) -> str:
    available = loader.list_presets()
    return (
        ", ".join(f"{directory}/{name}" for directory, names in available.items() for name in names)
        or "none found"
    )


def _warn_encoder_preset_missing(loader) -> None:
    print_warning(
        tr(
            "pipeline.encoder.no_preset",
            default="Encoder preset not configured. Set modules.encoder.preset in settings. Available: {hint}",
            hint=_available_encoder_preset_hint(loader),
        )
    )


def _resolve_pipeline_encoder_preset(preset_name: str, loader):
    from swirrl.modules.encoder import PresetLoader

    config_loader = PresetLoader(presets_dir=get_config_dir() / "Presets" / "Encoder")
    for current_loader in (loader, config_loader):
        try:
            return current_loader.load_preset_by_name(preset_name)
        except FileNotFoundError:
            continue
        except Exception as exc:
            print_error(
                tr(
                    "pipeline.encoder.preset_error",
                    default="Failed to load encoder preset: {error}",
                    error=str(exc),
                )
            )
            return None

    print_warning(
        tr(
            "pipeline.encoder.preset_not_found",
            default="Encoder preset '{name}' not found. Available: {hint}",
            name=preset_name,
            hint=_available_encoder_preset_hint(loader),
        )
    )
    return None


def _create_pipeline_encoder_service(
    preset,
    *,
    ffmpeg_path: str,
    ffprobe_path: str,
    encoder_service_cls,
):
    try:
        return encoder_service_cls(preset, ffmpeg_path=ffmpeg_path, ffprobe_path=ffprobe_path)
    except RuntimeError as exc:
        print_error(str(exc))
        return None


def _run_pipeline_encoder_jobs(service, mkv_files: list[Path]) -> int:
    failures = 0
    for input_file in mkv_files:
        output_file = input_file.with_suffix(".enc.mkv")
        print_info(
            tr("pipeline.encoder.encoding", default="Encoding: {file}", file=input_file.name)
        )
        result = service.encode(input_file, output_file, show_progress=True)
        if result.success:
            input_file.unlink()
            output_file.rename(input_file)
            ratio = result.compression_ratio or 0.0
            print_success(
                tr(
                    "pipeline.encoder.done",
                    default="Encoded: {file} ({ratio:.1f}% smaller)",
                    file=input_file.name,
                    ratio=ratio,
                )
            )
            continue
        failures += 1
        for error in result.errors:
            print_error(f"  {error}")
        if output_file.exists():
            output_file.unlink()
    return failures


def _encoder_step_dry_run(work_folder: Path, settings: dict) -> int:
    """Preview encoder step without encoding."""
    encoder_settings = settings.get("modules", {}).get("encoder", {})
    preset_name = str(encoder_settings.get("preset", "") or "").strip()
    mkv_files = sorted(work_folder.glob("*.mkv"))
    if not preset_name:
        print_info(
            tr(
                "pipeline.dry_run.encoder_no_preset",
                default="[dry-run] Encoder: no preset configured, would skip",
            )
        )
    elif not mkv_files:
        print_info(
            tr(
                "pipeline.dry_run.encoder_no_files",
                default="[dry-run] Encoder: no MKV files to encode",
            )
        )
    else:
        print_info(
            tr(
                "pipeline.dry_run.encoder",
                default="[dry-run] Would encode {count} file(s) with preset '{preset}'",
                count=len(mkv_files),
                preset=preset_name,
            )
        )
    return 0


def _resolve_image_host_api_key(settings: dict) -> tuple[str, str]:
    """Resolve image host configuration and API key, including vault fallback."""
    upload_cfg = settings.get("upload", {})
    image_host = str(upload_cfg.get("image_host", "") or "")
    image_host_api_key = str(upload_cfg.get("image_host_api_key", "") or "")
    if image_host_api_key:
        return image_host, image_host_api_key
    try:
        vault = Settings().get_vault()
        if vault:
            image_host_api_key = str(vault.retrieve("image_host_api_key", default="") or "")
    except Exception as vault_exc:
        from loguru import logger as _logger

        _logger.warning(
            "Could not resolve image_host_api_key from vault: "
            f"{vault_exc}. Upload will fall back to anonymous host limits "
            "or skip image embedding."
        )
    return image_host, image_host_api_key


def _upload_pipeline_screenshots(
    *,
    work_folder: Path,
    context: PipelineContext | None,
    image_host: str,
    image_host_api_key: str,
    image_host_service_cls,
) -> list[str]:
    """Upload screenshot outputs and return hosted URLs."""
    if not image_host:
        return []
    screenshots = _collect_pipeline_screenshots(work_folder=work_folder, context=context)
    if not screenshots:
        return []
    print_info(f"Uploading {len(screenshots)} screenshot(s) to {image_host}...")
    try:
        image_service = image_host_service_cls(image_host, image_host_api_key)
        uploaded = image_service.upload_batch(screenshots[:10])
        image_urls = [url for _, url in uploaded if url]
        print_success(f"✓ Uploaded {len(image_urls)} screenshot(s)")
        return image_urls
    except Exception as e:
        print_warning(f"Image upload failed: {e}")
        return []


def _collect_pipeline_screenshots(
    *, work_folder: Path, context: PipelineContext | None
) -> list[Path]:
    screenshots = _screenshots_from_context(context)
    screenshots.extend(_screenshots_from_work_folder(work_folder))
    return _dedupe_and_sort_paths(screenshots)


def _screenshots_from_context(context: PipelineContext | None) -> list[Path]:
    if context is None:
        return []
    screenshot_outputs = tuple(getattr(context, "screenshot_outputs", ()) or ())
    if screenshot_outputs:
        return [path for path in screenshot_outputs if isinstance(path, Path) and path.exists()]
    prez_outputs = tuple(getattr(context, "prez_outputs", ()) or ())
    if not prez_outputs:
        return []
    return [
        path
        for path in prez_outputs
        if isinstance(path, Path) and path.suffix.lower() in _SCREENSHOT_SUFFIXES
    ]


_SCREENSHOT_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
_SCREENSHOT_DIRS = {"screens", "screen", "screenshots", "screenshot", "captures"}
_SCREENSHOT_PREFIXES = ("screen", "screenshot", "capture", "thumb")


def _screenshots_from_work_folder(work_folder: Path) -> list[Path]:
    if not work_folder.exists():
        return []
    screenshots: list[Path] = []
    for child in work_folder.iterdir():
        screenshots.extend(_screenshots_from_folder_child(child))
    return screenshots


def _screenshots_from_folder_child(child: Path) -> list[Path]:
    if child.is_dir() and child.name.lower() in _SCREENSHOT_DIRS:
        return [
            path
            for path in sorted(child.iterdir())
            if path.is_file() and path.suffix.lower() in _SCREENSHOT_SUFFIXES
        ]
    if _is_screenshot_candidate(child):
        return [child]
    return []


def _is_screenshot_candidate(path: Path) -> bool:
    if not path.is_file() or path.suffix.lower() not in _SCREENSHOT_SUFFIXES:
        return False
    return path.stem.lower().startswith(_SCREENSHOT_PREFIXES)


def _dedupe_and_sort_paths(paths: list[Path]) -> list[Path]:
    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(path)
    return sorted(deduped, key=lambda item: item.as_posix().lower())


def _resolve_pipeline_upload_description(
    *,
    context: PipelineContext | None,
    image_urls: list[str],
    inject_images_into_bbcode_fn,
) -> str:
    """Resolve upload description from BBCode output and inject screenshot URLs."""
    description = "Release created with Swirrl"
    if context and context.prez_outputs:
        for output in context.prez_outputs:
            lower_name = output.name.lower()
            if lower_name.endswith((".bbcode", ".bbcode.txt")):
                try:
                    description = output.read_text(encoding="utf-8")
                    break
                except Exception:  # nosec B110
                    pass
    if image_urls:
        description = inject_images_into_bbcode_fn(description, image_urls)
    return description


def _build_pipeline_upload_metadata(
    *,
    context: PipelineContext | None,
    release_name: str,
    parsed,
    nfo_data,
    description: str,
) -> TorrentMetadata:
    """Build upload metadata from parser/NFO/context sources."""
    from swirrl.modules.upload.models import TorrentMetadata

    media_kind = _pipeline_upload_media_kind(context)
    category = _pipeline_upload_category(media_kind)
    context_meta = context.metadata_context if context else None
    return TorrentMetadata(
        name=release_name,
        description=description,
        category=category,
        type=parsed.source or "Other",
        resolution=parsed.resolution or "1080p",
        tmdb_id=nfo_data.tmdb_id or (context_meta.get("tmdb_id") if context_meta else None),
        imdb_id=nfo_data.imdb_id or (context_meta.get("imdb_id") if context_meta else None),
        tvdb_id=nfo_data.tvdb_id or (context_meta.get("tvdb_id") if context_meta else None),
        source=parsed.source,
        codec=parsed.codec,
        audio=parsed.audio,
        hdr=parsed.hdr,
        tags=_pipeline_upload_tags(parsed),
        nfo_path=str(context.nfo_path) if context and context.nfo_path else None,
    )


def _pipeline_upload_media_kind(context: PipelineContext | None) -> str:
    if context and context.metadata_context:
        hinted = context.metadata_context.get("media_kind")
        if isinstance(hinted, str) and hinted.strip():
            return hinted
    if context and context.release:
        return _release_media_kind_to_upload_kind((context.release.media_kind or "").lower())
    return "movie"


def _release_media_kind_to_upload_kind(kind: str) -> str:
    if kind in ("single_episode", "season_pack", "special_pack"):
        return "tv"
    if kind == "anime":
        return "anime"
    return "movie"


def _pipeline_upload_category(media_kind: str) -> str:
    if media_kind == "anime":
        return "Anime"
    if media_kind == "movie":
        return "Movie"
    return "TV"


def _pipeline_upload_tags(parsed) -> list[str]:
    return [tag for tag in [parsed.codec, parsed.audio, parsed.hdr] if tag]


def _has_custom_api_tracker(settings: dict, tracker_names: list[str]) -> bool:
    trackers = settings.get("upload", {}).get("trackers", [])
    by_name = {
        str(tracker.get("name", "")): tracker for tracker in trackers if isinstance(tracker, dict)
    }
    for tracker_name in tracker_names:
        tracker = by_name.get(tracker_name, {})
        tracker_type = str(tracker.get("type", "") or "").lower()
        if tracker_type == "custom_json_api_v1":
            return True
    return False


def _first_custom_api_defaults(settings: dict, tracker_names: list[str]) -> dict:
    trackers = settings.get("upload", {}).get("trackers", [])
    by_name = {
        str(tracker.get("name", "")): tracker for tracker in trackers if isinstance(tracker, dict)
    }
    for tracker_name in tracker_names:
        tracker = by_name.get(tracker_name, {})
        tracker_type = str(tracker.get("type", "") or "").lower()
        if tracker_type != "custom_json_api_v1":
            continue
        defaults = tracker.get("defaults", {})
        if isinstance(defaults, dict):
            return defaults
        return {}
    return {}


def _genres_from_metadata_context(context: PipelineContext | None) -> set[str]:
    if context is None or not context.metadata_context:
        return set()
    values: list[object] = []
    values.append(context.metadata_context.get("metadata_movie"))
    values.append(context.metadata_context.get("metadata_episode"))
    values.append(context.metadata_context.get("metadata_season"))
    episode_map = context.metadata_context.get("metadata_episode_map", {})
    if isinstance(episode_map, dict):
        values.extend(episode_map.values())

    genres: set[str] = set()
    for item in values:
        if item is None:
            continue
        raw_genres = getattr(item, "genres", None)
        if not isinstance(raw_genres, list):
            continue
        for genre in raw_genres:
            if isinstance(genre, str) and genre.strip():
                genres.add(genre.strip().lower())
    return genres


def _looks_like_animation(context: PipelineContext | None, parsed, nfo_data) -> bool:
    animation_markers = {"animation", "anime", "cartoon"}
    if _genres_from_metadata_context(context) & animation_markers:
        return True

    nfo_genres = getattr(nfo_data, "genre", [])
    if isinstance(nfo_genres, list):
        normalized = {str(genre).strip().lower() for genre in nfo_genres if str(genre).strip()}
        if normalized & animation_markers:
            return True

    title = str(getattr(parsed, "title", "") or "").lower()
    return any(marker in title for marker in ("anime", "animation"))


def _custom_api_subcategory_id(media_kind: str, is_animation: bool) -> int:
    if media_kind in {"tv", "single_episode", "season_pack", "special_pack"}:
        return 2 if is_animation else 7
    return 1 if is_animation else 6


def _custom_api_quality_option(parsed) -> int | None:
    source = str(getattr(parsed, "source", "") or "").lower()
    resolution = str(getattr(parsed, "resolution", "") or "").lower()
    if source == "remux":
        return 12
    if source == "bluray":
        return 10 if resolution == "2160p" else 11
    if source == "web-dl":
        if resolution == "2160p":
            return 26
        if resolution == "1080p":
            return 25
        return 24
    if source in {"webrip", "hdtv"} and resolution == "1080p":
        return 16
    return None


def _custom_api_language_option(context: PipelineContext | None) -> int | None:
    if context is None or context.release is None:
        return None
    blob = " ".join(
        [
            str(context.release.language_tag or ""),
            str(context.release.audio_languages_display or ""),
        ]
    ).lower()
    if "vf2" in blob:
        return 422
    if "vfq" in blob or "queb" in blob:
        return 6
    if "vostfr" in blob:
        return 8
    if "vff" in blob or "franc" in blob:
        return 2
    if "multi" in blob:
        return 4
    if "anglais" in blob or "english" in blob:
        return 1
    return None


def _custom_api_season_episode_options(
    context: PipelineContext | None, parsed
) -> tuple[int | None, int | None]:
    media_kind = _pipeline_upload_media_kind(context)
    season_number = getattr(parsed, "season", None)
    episode_number = getattr(parsed, "episode", None)

    if media_kind == "season_pack":
        if isinstance(season_number, int) and 1 <= season_number <= 30:
            return 120 + season_number, 96
        return 120, 96
    if media_kind in {"single_episode", "tv"}:
        season_option = 120
        if isinstance(season_number, int) and 1 <= season_number <= 30:
            season_option = 120 + season_number
        episode_option = 117
        if isinstance(episode_number, int) and 1 <= episode_number <= 20:
            episode_option = 96 + episode_number
        return season_option, episode_option
    return None, None


def _apply_custom_api_metadata_mapping(
    *,
    settings: dict,
    tracker_names: list[str],
    context: PipelineContext | None,
    parsed,
    nfo_data,
    metadata: TorrentMetadata,
) -> TorrentMetadata:
    if not _has_custom_api_tracker(settings, tracker_names):
        return metadata

    defaults = _first_custom_api_defaults(settings, tracker_names)
    media_kind = _pipeline_upload_media_kind(context)
    is_animation = _looks_like_animation(context, parsed, nfo_data)

    options: dict[str, object] = {}
    raw_default_options = defaults.get("custom_api_options", {})
    if isinstance(raw_default_options, dict):
        options.update(raw_default_options)

    language_id = _custom_api_language_option(context)
    if language_id is not None and "1" not in options:
        options["1"] = [language_id]

    quality_id = _custom_api_quality_option(parsed)
    if quality_id is not None and "2" not in options:
        options["2"] = quality_id

    season_option, episode_option = _custom_api_season_episode_options(context, parsed)
    if season_option is not None and "7" not in options:
        options["7"] = season_option
    if episode_option is not None and "6" not in options:
        options["6"] = episode_option

    default_category_id = defaults.get("custom_api_category_id")
    category_id = default_category_id if isinstance(default_category_id, int) else 1

    default_subcategory_id = defaults.get("custom_api_subcategory_id")
    inferred_subcategory_id = _custom_api_subcategory_id(media_kind, is_animation)
    subcategory_id = (
        default_subcategory_id
        if isinstance(default_subcategory_id, int)
        else inferred_subcategory_id
    )

    description_format = str(defaults.get("custom_api_description_format", "standard")).lower()
    if description_format not in {"standard", "html"}:
        description_format = "standard"

    return metadata.model_copy(
        update={
            "custom_api_category_id": category_id,
            "custom_api_subcategory_id": subcategory_id,
            "custom_api_options": options,
            "custom_api_description_format": description_format,
            "category": "Films & Videos",
            "type": "custom_json_api_v1",
            "resolution": "custom_json_api_v1",
        }
    )


def _pipeline_best_effort_dupe_check(tracker_name: str, metadata: TorrentMetadata) -> None:
    """Run non-blocking duplicate check on first tracker."""
    try:
        from swirrl.modules.upload.dupe_checker import DupeChecker
        from swirrl.modules.upload.service import UploadService as _US

        first_config = _US()._load_tracker_config(tracker_name)  # pyright: ignore[reportPrivateUsage]
        from swirrl.modules.upload.adapters.gazelle import GazelleAdapter
        from swirrl.modules.upload.adapters.unit3d import UNIT3DAdapter

        adapter_cls = GazelleAdapter if first_config.type == "gazelle" else UNIT3DAdapter
        with adapter_cls(first_config) as adapter:
            dupe_result = DupeChecker(adapter).check(metadata)
        if dupe_result.has_dupes:
            print_warning(
                f"Possible duplicates found on {tracker_name} "
                f"(confidence: {dupe_result.confidence}):"
            )
            for dupe in dupe_result.dupes[:3]:
                print_warning(f"  - [{dupe.get('id')}] {dupe.get('name', '?')}")
            print_warning("Proceeding with upload anyway (auto-upload mode).")
    except Exception as dupe_exc:
        print_warning(f"Dupe check skipped: {dupe_exc}")


def _upload_results_exit_code(results: Mapping[str, object]) -> int:
    """Render summary and compute upload step exit code."""
    if not results:
        print_error(tr("pipeline.upload.failed", default="Upload failed on all trackers"))
        return 1
    success_count = sum(1 for result in results.values() if getattr(result, "success", False))
    failed_count = len(results) - success_count
    if success_count > 0:
        print_success(
            tr(
                "pipeline.upload.summary",
                default="Upload complete: {success} successful, {failed} failed",
                success=success_count,
                failed=failed_count,
            )
        )
        return 0
    print_error(tr("pipeline.upload.failed", default="Upload failed on all trackers"))
    return 1


def _validate_upload_step_preconditions(
    settings: dict,
    context: PipelineContext | None,
) -> tuple[int | None, Path | None]:
    """Validate upload preconditions and return (early_exit_code, torrent_path)."""
    if not settings.get("upload", {}).get("enabled", False):
        print_info(tr("pipeline.upload.disabled", default="Upload module is disabled in settings"))
        return 0, None
    if not settings.get("upload", {}).get("auto_upload", False):
        print_info(
            tr("pipeline.upload.auto_disabled", default="Auto-upload is disabled in settings")
        )
        return 0, None
    if context is None or context.torrent_path is None:
        print_warning(
            tr("pipeline.upload.no_torrent", default="No torrent file found. Skipping upload step.")
        )
        return 0, None
    torrent_path = context.torrent_path
    if not torrent_path.exists():
        print_error(
            tr(
                "pipeline.upload.torrent_not_found",
                default="Torrent file not found: {path}",
                path=str(torrent_path),
            )
        )
        return 1, None
    return None, torrent_path


def _parse_pipeline_upload_release(
    *,
    torrent_path: Path,
    context: PipelineContext | None,
    nfo_data_cls,
    nfo_parser_cls,
    release_parser_cls,
) -> tuple[str, object, object]:
    """Parse release name and optional NFO metadata for upload step."""
    release_name = torrent_path.stem
    print_info(f"Parsing release: {release_name}")
    parsed = release_parser_cls.parse(release_name)
    if parsed.resolution:
        print_info(f"  Resolution: {parsed.resolution}")
    if parsed.source:
        print_info(f"  Source: {parsed.source}")
    if parsed.codec:
        print_info(f"  Codec: {parsed.codec}")

    nfo_data = nfo_data_cls()
    if context and context.nfo_path and context.nfo_path.exists():
        nfo_data = nfo_parser_cls.parse(context.nfo_path)
        print_info(f"Parsed NFO: {context.nfo_path.name}")
        if nfo_data.imdb_id:
            print_info(f"  IMDB: {nfo_data.imdb_id}")
        if nfo_data.tmdb_id:
            print_info(f"  TMDB: {nfo_data.tmdb_id}")

    return release_name, parsed, nfo_data


def _resolve_upload_tracker_names(settings: dict) -> list[str]:
    """Resolve configured tracker names or return empty list."""
    trackers = settings.get("upload", {}).get("trackers", [])
    if not trackers:
        print_warning(
            tr(
                "pipeline.upload.no_trackers",
                default="No trackers configured. Skipping upload step.",
            )
        )
        return []
    return [tracker["name"] for tracker in trackers]


def _upload_step(
    work_folder: Path,
    context: PipelineContext | None = None,
    settings: dict | None = None,
    auto_mode: bool = False,
) -> int:
    """Execute upload step: upload torrent to configured trackers.

    Uses all Phase 1-2 features:
    - ReleaseParser for metadata extraction
    - NFOParser for IDs and metadata
    - MetadataMapper for fuzzy matching
    - DupeChecker for duplicate detection
    - ImageHostService for screenshot hosting
    - BBCode templates for descriptions
    - Parallel multi-tracker uploads

    Args:
        work_folder: Working directory containing the release
        context: Pipeline context with torrent path
        settings: Settings dictionary
        auto_mode: Whether running in auto mode

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    from swirrl.modules.upload.image_host import ImageHostService, inject_images_into_bbcode
    from swirrl.modules.upload.metadata_extractor import NFOData, NFOParser, ReleaseParser
    from swirrl.modules.upload.service import UploadService

    if settings is None:
        settings = SettingsStore().load()
    early_code, torrent_path = _validate_upload_step_preconditions(settings, context)
    if early_code is not None:
        return early_code
    if torrent_path is None:
        return 1
    release_name, parsed, nfo_data = _parse_pipeline_upload_release(
        torrent_path=torrent_path,
        context=context,
        nfo_data_cls=NFOData,
        nfo_parser_cls=NFOParser,
        release_parser_cls=ReleaseParser,
    )

    image_host, image_host_api_key = _resolve_image_host_api_key(settings)
    image_urls = _upload_pipeline_screenshots(
        work_folder=work_folder,
        context=context,
        image_host=image_host,
        image_host_api_key=image_host_api_key,
        image_host_service_cls=ImageHostService,
    )
    description = _resolve_pipeline_upload_description(
        context=context,
        image_urls=image_urls,
        inject_images_into_bbcode_fn=inject_images_into_bbcode,
    )
    metadata = _build_pipeline_upload_metadata(
        context=context,
        release_name=release_name,
        parsed=parsed,
        nfo_data=nfo_data,
        description=description,
    )

    tracker_names = _resolve_upload_tracker_names(settings)
    if not tracker_names:
        return 0
    metadata = _apply_custom_api_metadata_mapping(
        settings=settings,
        tracker_names=tracker_names,
        context=context,
        parsed=parsed,
        nfo_data=nfo_data,
        metadata=metadata,
    )
    _pipeline_best_effort_dupe_check(tracker_names[0], metadata)

    print_info(
        tr(
            "pipeline.upload.starting",
            default="Uploading to {count} tracker(s)...",
            count=len(tracker_names),
        )
    )

    service = UploadService()
    max_parallel = settings.get("upload", {}).get("max_parallel_uploads", 3)
    results = service.upload_to_multiple(
        torrent_path, metadata, tracker_names, max_parallel=max_parallel
    )
    return _upload_results_exit_code(results)
