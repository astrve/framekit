from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

# Prefer rich_click if available; fall back to click when the rich integration is not installed.
try:
    import rich_click as click  # type: ignore[import-not-found]
except Exception:
    import click  # type: ignore[import-not-found]
try:
    from pathvalidate import sanitize_filename  # type: ignore[import]
except ImportError:
    # Provide a minimal sanitize_filename fallback when pathvalidate is unavailable.
    import re as _re

    def sanitize_filename(filename: str, replacement_text: str = "_") -> str:
        """
        Sanitize a filename by replacing characters illegal on most filesystems.
        This fallback keeps alphanumeric characters, dots, dashes and underscores,
        and replaces any other sequence with the given replacement_text.
        """
        return _re.sub(r"[^A-Za-z0-9._-]+", replacement_text, filename)


from rich import box
from rich.panel import Panel
from rich.table import Table

from framekit.commands.cleanmkv import run_cleanmkv_command
from framekit.commands.nfo import run_nfo_command
from framekit.commands.renamer import run_renamer_command
from framekit.commands.torrent import run_torrent_command
from framekit.core.i18n import tr
from framekit.core.models.nfo import ReleaseNfoData
from framekit.core.naming import release_name_from_mkv_paths, torrent_name_from_payload
from framekit.core.paths import PathResolver
from framekit.core.release_inspection import inspect_release_completeness
from framekit.core.settings import (
    SettingsStore,
    metadata_language_for_nfo_locale,
    resolve_nfo_locale,
)
from framekit.modules.metadata.workflow import run_metadata_workflow
from framekit.modules.nfo.builder import build_release_nfo
from framekit.modules.nfo.scanner import scan_nfo_folder
from framekit.modules.nfo.service import NfoService
from framekit.modules.prez.service import PREZ_PRESETS, PrezBuildOptions, PrezService
from framekit.ui.branding import print_module_banner
from framekit.ui.console import (
    console,
    print_error,
    print_exception_error,
    print_info,
    print_success,
)
from framekit.ui.selector import SelectorDivider, SelectorEntry, SelectorOption, select_many

PIPELINE_MODULES = ("renamer", "cleanmkv", "nfo", "torrent", "prez")
PipelineStep = tuple[str, str, Callable[[], int]]


@dataclass(slots=True)
class PipelineContext:
    release: ReleaseNfoData | None = None
    metadata_context: dict | None = None
    nfo_path: Path | None = None
    torrent_path: Path | None = None
    prez_outputs: tuple[Path, ...] = field(default_factory=tuple)


def _module_label(name: str) -> str:
    return {
        "renamer": tr("pipeline.step.renamer", default="Renamer"),
        "cleanmkv": tr("pipeline.step.cleanmkv", default="CleanMKV"),
        "nfo": tr("pipeline.step.nfo", default="NFO + Metadata"),
        "torrent": tr("pipeline.step.torrent", default="Torrent"),
        "prez": tr("pipeline.step.prez", default="Prez"),
    }.get(name, name)


def _resolve_enabled_modules(settings: dict, requested: tuple[str, ...] | None = None) -> set[str]:
    allowed = set(PIPELINE_MODULES)
    if requested is not None:
        return {item for item in requested if item in allowed}
    configured = (
        settings.get("modules", {}).get("pipeline", {}).get("enabled_modules", PIPELINE_MODULES)
    )
    if isinstance(configured, list):
        selected = {
            str(item).strip().lower() for item in configured if str(item).strip().lower() in allowed
        }
        return selected or set(PIPELINE_MODULES)
    return set(PIPELINE_MODULES)


def _maybe_select_modules(
    settings: dict, selected: set[str], select_modules: bool | None
) -> set[str]:
    should_select = sys.stdin.isatty() if select_modules is None else select_modules
    if not should_select:
        return selected
    entries: list[SelectorEntry] = [SelectorDivider("Modules")]
    entries.extend(
        SelectorOption(
            value=name,
            label=_module_label(name),
            hint=tr("pipeline.selector.module_hint", default="Enable this module for this run"),
            selected=False,
        )
        for name in PIPELINE_MODULES
    )
    try:
        values = select_many(
            title=tr("pipeline.selector.title", default="Choose pipeline modules"),
            entries=entries,
            page_size=8,
            minimal_count=1,
        )
    except KeyboardInterrupt:
        raise
    return {str(value) for value in values if str(value) in PIPELINE_MODULES} or selected


def _join_path_parts(parts: tuple[str, ...]) -> str:
    return " ".join(part for part in parts if part).strip()


def _release_artifacts_folder(root: Path) -> Path:
    return root / "Release"


def _safe_release_folder_name(root: Path) -> str:
    mkv_files = sorted(root.glob("*.mkv"), key=lambda path: path.name.lower())
    if mkv_files:
        return release_name_from_mkv_paths(mkv_files)
    return sanitize_filename(root.name, replacement_text="_").strip(" .") or "release"


def _release_payload_folder(root: Path) -> Path:
    return _release_artifacts_folder(root) / _safe_release_folder_name(root)


def _pipeline_output_folder(work_folder: Path, root: Path | None = None) -> Path:
    if work_folder.parent.name == "Release":
        return work_folder.parent
    if root is not None:
        release_folder = _release_artifacts_folder(root)
        if release_folder.exists() or work_folder != root:
            return release_folder
    return work_folder


def _next_work_folder(root: Path, settings: dict) -> Path:
    release_payload = _release_payload_folder(root)
    if release_payload.exists() and release_payload.is_dir():
        return release_payload
    clean_settings = settings.get("modules", {}).get("cleanmkv", {})
    configured = str(
        clean_settings.get("output_dir_name", "Release/{release}") or "Release/{release}"
    )
    clean_dir = root / configured.format(release=_safe_release_folder_name(root))
    if clean_dir.exists() and clean_dir.is_dir():
        return clean_dir
    release_dir = _release_artifacts_folder(root)
    if release_dir.exists() and release_dir.is_dir():
        candidates = [
            item
            for item in release_dir.iterdir()
            if item.is_dir() and any(child.suffix.lower() == ".mkv" for child in item.iterdir())
        ]
        if len(candidates) == 1:
            return candidates[0]
    legacy_clean_dir = root / "clean"
    return legacy_clean_dir if legacy_clean_dir.exists() and legacy_clean_dir.is_dir() else root


def _run_step(label: str, callback: Callable[[], int]) -> int:
    print_info(tr("pipeline.step.start", default="Starting: {step}", step=label))
    try:
        result = callback()
    except KeyboardInterrupt:
        print_error(tr("runtime.interrupted", default="Interrupted."))
        return 130
    except Exception as exc:
        print_exception_error(
            exc,
            message=tr("pipeline.step.failed", default="Step failed: {step}", step=label),
        )
        return 1

    if result != 0:
        print_error(tr("pipeline.step.failed", default="Step failed: {step}", step=label))
    return result


def _renamer_step(root: Path, remove_terms: tuple[str, ...] = ()) -> int:
    return run_renamer_command(
        path=str(root),
        lang=None,
        apply_changes=True,
        dry_run=False,
        force_lang=False,
        remove_terms=remove_terms,
    )


def _cleanmkv_step(root: Path) -> int:
    return run_cleanmkv_command(
        path=str(root),
        apply_changes=False,
        dry_run=False,
        preset_name=None,
        preset_file=None,
        external_preset=None,
        wizard=False,
        save_preset=None,
        list_presets=False,
    )


def _resolve_pipeline_locale(settings: dict, nfo_locale: str | None) -> str:
    configured = nfo_locale or str(settings.get("modules", {}).get("nfo", {}).get("locale", "auto"))
    return resolve_nfo_locale(
        configured,
        ui_locale=str(settings.get("general", {}).get("locale", "en")),
    )


def _ensure_release_context(work_folder: Path, context: PipelineContext) -> ReleaseNfoData:
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
) -> dict:
    if not metadata_enabled:
        context.metadata_context = {}
        return {}
    if context.metadata_context is not None:
        return context.metadata_context
    result = run_metadata_workflow(
        release,
        settings,
        auto_accept=False,
        show_ui=True,
        language_override=metadata_language_for_nfo_locale(locale),
    )
    context.metadata_context = result.context if result.status == "resolved" else {}
    return context.metadata_context


def _formats_from_prez_setting(value: str | None) -> tuple[str, ...]:
    selected = (value or "both").strip().lower()
    if selected == "both":
        return ("html", "bbcode")
    if selected == "mediainfo":
        return ()
    return (selected,)


def _nfo_step(
    work_folder: Path,
    nfo_locale: str | None,
    context: PipelineContext | None = None,
    settings: dict | None = None,
    metadata_enabled: bool = True,
    output_folder: Path | None = None,
) -> int:
    if context is None or settings is None:
        return run_nfo_command(
            path=str(work_folder),
            template=None,
            nfo_locale=nfo_locale,
            write_requested=True,
            with_metadata=metadata_enabled,
            metadata_auto_accept=False,
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
        )

    release = _ensure_release_context(work_folder, context)
    resolved_locale = _resolve_pipeline_locale(settings, nfo_locale)
    metadata_context = _ensure_metadata_context(
        release,
        settings,
        context,
        resolved_locale,
        metadata_enabled=metadata_enabled,
    )
    nfo_settings = settings.setdefault("modules", {}).setdefault("nfo", {})
    template_name = str(nfo_settings.get("active_template", "default") or "default")
    logo_path = str(nfo_settings.get("logo_path", "") or "")
    service = NfoService()
    report, release, rendered = service.build_from_release(
        work_folder,
        release=release,
        template_name=template_name,
        logo_path=logo_path,
        template_locale=resolved_locale,
        extra_context=metadata_context,
    )
    resolved_template = str(report.details[0].after.get("template", template_name))
    _write_report, output_path = service.write_rendered(
        output_folder or work_folder,
        release=release,
        rendered=rendered,
        template_name=resolved_template,
        template_locale=resolved_locale,
    )
    context.nfo_path = output_path
    print_info(tr("nfo.success.written", default="NFO written: {path}", path=output_path))
    return 0


def _torrent_step(
    work_folder: Path,
    announce: str | None,
    context: PipelineContext | None = None,
    output_folder: Path | None = None,
) -> int:
    torrent_output = (
        output_folder or work_folder.parent
    ) / f"{torrent_name_from_payload(work_folder)}.torrent"
    code = run_torrent_command(
        path=str(work_folder),
        output=str(torrent_output),
        announce=announce,
        private=None,
        piece_length=None,
        dry_run=False,
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
) -> int:
    if context is None or settings is None:
        from framekit.commands.prez import run_prez_command

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
    )
    prez_settings = settings.setdefault("modules", {}).setdefault("prez", {})
    preset_name = (preset or str(prez_settings.get("preset", "default") or "default")).lower()
    if preset_name not in PREZ_PRESETS:
        preset_name = "default"
    preset_values = PREZ_PRESETS[preset_name]
    html_template = str(
        (preset_values["html_template"] if preset else prez_settings.get("html_template"))
        or preset_values["html_template"]
    )
    bbcode_template = str(
        (preset_values["bbcode_template"] if preset else prez_settings.get("bbcode_template"))
        or preset_values["bbcode_template"]
    )
    output_format = str(
        (preset_values["format"] if preset else prez_settings.get("format"))
        or preset_values["format"]
    )
    if select_templates is None:
        should_select_templates = bool(sys.stdin.isatty() and not preset)
    else:
        should_select_templates = select_templates
    if should_select_templates:
        from framekit.commands.prez import _maybe_select_templates

        html_template, bbcode_template = _maybe_select_templates(
            formats=_formats_from_prez_setting(output_format),
            html_template=html_template,
            bbcode_template=bbcode_template,
            explicit_html=False,
            explicit_bbcode=False,
            explicit_preset=bool(preset),
            select_templates=True,
        )
    mediainfo_mode = str(
        (preset_values["mediainfo_mode"] if preset else prez_settings.get("mediainfo_mode"))
        or preset_values["mediainfo_mode"]
    )
    _report, result = PrezService().build(
        work_folder,
        options=PrezBuildOptions(
            formats=_formats_from_prez_setting(output_format),
            output_dir=output_folder,
            metadata_context=metadata_context,
            locale=resolved_locale,
            mediainfo_mode=mediainfo_mode,
            html_template=html_template,
            bbcode_template=bbcode_template,
            preset=preset_name,
            release=release,
        ),
        write=True,
    )
    context.prez_outputs = result.outputs
    for output in result.outputs:
        print_info(tr("common.output", default="Output") + f": {output}")
    return 0


def _pipeline_explain_text() -> str:
    return (
        "1. renamer → normalize names\\n"
        "2. cleanmkv → remux selected tracks\\n"
        "3. nfo → build localized NFO and optional TMDb metadata\\n"
        "4. torrent → prepare tracker torrent\\n"
        "5. prez → generate HTML / BBCode presentation\\n\\n"
        "Defaults used by pipeline:\\n"
        "• enabled modules come from settings unless overridden\\n"
        "• metadata is enabled by default and can be disabled with --no-metadata\\n"
        "• --preview shows the planned run without writing outputs\\n"
        "• --explain describes the workflow only and exits"
    )


def _print_pipeline_preview(
    folder: Path,
    release: ReleaseNfoData,
    enabled_modules: tuple[str, ...],
    *,
    root: Path,
    work_folder: Path,
    output_folder: Path,
    nfo_locale: str,
    announce: str | None,
    preset: str | None,
    metadata_enabled: bool,
    html_template: str | None = None,
    bbcode_template: str | None = None,
) -> None:
    table = Table(
        title=tr("pipeline.preview", default="Pipeline preview"), box=box.HEAVY, expand=True
    )
    table.add_column(tr("common.field", default="Field"), width=24, no_wrap=True)
    table.add_column(tr("common.value", default="Value"), ratio=1)
    completeness = inspect_release_completeness(release)
    table.add_row(tr("common.folder", default="Folder"), str(folder))
    table.add_row(tr("pipeline.preview.input_folder", default="Input folder"), str(root))
    table.add_row(tr("pipeline.preview.payload_folder", default="Payload folder"), str(work_folder))
    table.add_row(tr("pipeline.preview.output_folder", default="Output folder"), str(output_folder))
    table.add_row(tr("common.release_title", default="Release Title"), release.release_title or "-")
    table.add_row(tr("common.media_kind", default="Media Kind"), release.media_kind or "-")
    table.add_row(
        tr("pipeline.preview.modules", default="Modules"), ", ".join(enabled_modules) or "-"
    )
    table.add_row(
        tr("common.metadata", default="Metadata"),
        tr("common.enabled", default="Enabled")
        if metadata_enabled
        else tr("common.disabled", default="Disabled"),
    )
    table.add_row(tr("pipeline.preview.nfo_locale", default="NFO/Prez locale"), nfo_locale or "-")
    table.add_row(tr("pipeline.preview.announce", default="Announce"), announce or "-")
    table.add_row(tr("pipeline.preview.preset", default="Prez preset"), preset or "-")
    table.add_row(tr("prez.template.html", default="HTML template"), html_template or "-")
    table.add_row(tr("prez.template.bbcode", default="BBCode template"), bbcode_template or "-")
    table.add_row(
        tr("inspect.episode_completeness", default="Episode completeness"), completeness.label
    )
    table.add_row(
        tr("pipeline.preview.expected_outputs", default="Expected outputs"),
        " → ".join(name for name in PIPELINE_MODULES if name in enabled_modules),
    )
    console.print(table)


def _print_pipeline_report(folder: Path, results: list[tuple[str, str, str]]) -> None:
    table = Table(
        title=tr("pipeline.report", default="Pipeline report"), box=box.HEAVY, expand=True
    )
    table.add_column(tr("common.module", default="Module"), width=16, no_wrap=True)
    table.add_column(tr("common.status", default="Status"), width=12, no_wrap=True)
    table.add_column(tr("common.details", default="Details"), ratio=1)
    for module_name, status, details in results:
        table.add_row(module_name, status, details)
    console.print(table)
    console.print(
        Panel(
            str(folder),
            title=tr("common.folder", default="Folder"),
            border_style="white",
            expand=True,
        )
    )


def run_pipeline_command(
    *,
    path: str | None,
    nfo_locale: str | None,
    announce: str | None,
    skip_renamer: bool,
    skip_cleanmkv: bool,
    skip_nfo: bool,
    skip_torrent: bool,
    skip_prez: bool,
    preset: str | None = None,
    preview: bool = False,
    explain: bool = False,
    with_metadata: bool | None = None,
    remove_terms: tuple[str, ...] = (),
    select_modules: bool | None = None,
    select_templates: bool | None = None,
    enabled_modules: tuple[str, ...] | None = None,
) -> int:
    store = SettingsStore()
    settings = store.load()
    resolver = PathResolver(settings)

    print_module_banner("Pipeline")
    if explain:
        console.print(
            Panel(
                _pipeline_explain_text(),
                title=tr("pipeline.explain", default="Pipeline explain"),
                border_style="white",
                expand=True,
            )
        )
        return 0

    root = resolver.resolve_start_folder("pipeline", path or None)
    if not root.exists() or not root.is_dir():
        print_error(
            tr("cleanmkv.error.folder_not_found", default="Folder not found: {folder}", folder=root)
        )
        return 1

    stop_on_error = bool(settings.get("modules", {}).get("pipeline", {}).get("stop_on_error", True))
    metadata_default = bool(
        settings.get("modules", {})
        .get("pipeline", {})
        .get(
            "with_metadata",
            settings.get("metadata", {}).get("enabled_by_default", True),
        )
    )
    metadata_enabled = metadata_default if with_metadata is None else with_metadata

    selected_modules = _resolve_enabled_modules(settings, enabled_modules)
    selected_modules = _maybe_select_modules(settings, selected_modules, select_modules)
    if skip_renamer:
        selected_modules.discard("renamer")
    if skip_cleanmkv:
        selected_modules.discard("cleanmkv")
    if skip_nfo:
        selected_modules.discard("nfo")
    if skip_torrent:
        selected_modules.discard("torrent")
    if skip_prez:
        selected_modules.discard("prez")

    work_folder = _next_work_folder(root, settings)
    output_folder = _pipeline_output_folder(work_folder, root)

    if preview:
        context = PipelineContext()
        try:
            release = _ensure_release_context(work_folder, context)
        except Exception:
            release = _ensure_release_context(root, context)
            work_folder = root
            output_folder = _pipeline_output_folder(work_folder, root)
        prez_settings = settings.get("modules", {}).get("prez", {})
        _print_pipeline_preview(
            root,
            release,
            tuple(name for name in PIPELINE_MODULES if name in selected_modules),
            root=root,
            work_folder=work_folder,
            output_folder=output_folder,
            nfo_locale=_resolve_pipeline_locale(settings, nfo_locale),
            announce=announce
            or settings.get("modules", {}).get("torrent", {}).get("selected_announce")
            or settings.get("modules", {}).get("torrent", {}).get("announce"),
            preset=preset or str(prez_settings.get("preset", "default") or "default"),
            metadata_enabled=metadata_enabled,
            html_template=str(prez_settings.get("html_template", "-") or "-"),
            bbcode_template=str(prez_settings.get("bbcode_template", "-") or "-"),
        )
        return 0

    report_rows: list[tuple[str, str, str]] = []
    failures = 0

    steps: list[PipelineStep] = []
    if "renamer" in selected_modules:
        if remove_terms:
            steps.append(
                ("renamer", _module_label("renamer"), lambda: _renamer_step(root, remove_terms))
            )
        else:
            steps.append(("renamer", _module_label("renamer"), lambda: _renamer_step(root)))
    if "cleanmkv" in selected_modules:
        steps.append(("cleanmkv", _module_label("cleanmkv"), lambda: _cleanmkv_step(root)))

    for module_name, label, callback in steps:
        code = _run_step(label, callback)
        if code != 0:
            failures += 1
            report_rows.append((module_name, tr("common.failed", default="Failed"), label))
            if stop_on_error:
                return code
        else:
            report_rows.append((module_name, tr("common.success", default="OK"), label))

    work_folder = _next_work_folder(root, settings)
    output_folder = _pipeline_output_folder(work_folder, root)
    print_info(
        tr("pipeline.info.work_folder", default="Release folder for output steps")
        + f": {work_folder}"
    )
    print_info(tr("pipeline.info.output_folder", default="Output folder") + f": {output_folder}")

    context = PipelineContext()

    output_steps: list[PipelineStep] = []
    if "nfo" in selected_modules:
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
                ),
            )
        )
    if "torrent" in selected_modules:
        output_steps.append(
            (
                "torrent",
                _module_label("torrent"),
                lambda: _torrent_step(work_folder, announce, context, output_folder),
            )
        )
    if "prez" in selected_modules:
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
                ),
            )
        )

    for module_name, label, callback in output_steps:
        code = _run_step(label, callback)
        if code != 0:
            failures += 1
            report_rows.append((module_name, tr("common.failed", default="Failed"), label))
            if stop_on_error:
                return code
        else:
            report_rows.append((module_name, tr("common.success", default="OK"), label))

    settings.setdefault("modules", {}).setdefault("pipeline", {})["last_folder"] = str(root)
    store.save(settings)

    _print_pipeline_report(root, report_rows)

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


@click.command(
    "pipeline",
    help=tr("cli.pipeline.help", default="Run renamer → cleanmkv → NFO/metadata → torrent → prez."),
)
@click.argument("path_parts", nargs=-1)
@click.option(
    "--locale",
    "nfo_locale",
    type=click.Choice(["auto", "en", "fr", "es"]),
    help=tr("cli.pipeline.option.locale", default="NFO/prez output language."),
)
@click.option(
    "--announce",
    help=tr("cli.pipeline.option.announce", default="Tracker announce URL for torrent creation."),
)
@click.option(
    "--skip-renamer",
    is_flag=True,
    help=tr("cli.pipeline.option.skip_renamer", default="Skip renamer step."),
)
@click.option(
    "--skip-cleanmkv",
    is_flag=True,
    help=tr("cli.pipeline.option.skip_cleanmkv", default="Skip CleanMKV step."),
)
@click.option(
    "--skip-nfo",
    is_flag=True,
    help=tr("cli.pipeline.option.skip_nfo", default="Skip NFO/metadata step."),
)
@click.option(
    "--skip-torrent",
    is_flag=True,
    help=tr("cli.pipeline.option.skip_torrent", default="Skip torrent step."),
)
@click.option(
    "--skip-prez",
    is_flag=True,
    help=tr("cli.pipeline.option.skip_prez", default="Skip prez step."),
)
@click.option(
    "--select-modules/--no-select-modules",
    default=None,
    help=tr(
        "cli.pipeline.option.select_modules",
        default="Open or bypass the interactive pipeline module selector.",
    ),
)
@click.option(
    "--modules",
    "enabled_modules_option",
    help=tr(
        "cli.pipeline.option.modules",
        default="Comma-separated modules for this run: renamer,cleanmkv,nfo,torrent,prez.",
    ),
)
@click.option(
    "--select-templates/--no-select-templates",
    default=None,
    help=tr(
        "cli.pipeline.option.select_templates",
        default="Open or bypass the interactive Prez template selector during pipeline.",
    ),
)
@click.option(
    "--preset",
    type=click.Choice(list(PREZ_PRESETS)),
    help=tr("cli.pipeline.option.preset", default="Prez preset for pipeline output."),
)
@click.option(
    "--preview",
    is_flag=True,
    help=tr("cli.pipeline.option.preview", default="Preview the planned pipeline run and exit."),
)
@click.option(
    "--explain",
    is_flag=True,
    help=tr("cli.pipeline.option.explain", default="Explain the pipeline workflow and exit."),
)
@click.option(
    "--remove-term",
    "remove_terms",
    multiple=True,
    help=tr(
        "cli.pipeline.option.remove_term",
        default="Remove a term during the Renamer step. Can be used multiple times.",
    ),
)
@click.option(
    "-m/-nm",
    "--with-metadata/--no-metadata",
    "with_metadata",
    default=None,
    help=tr(
        "cli.pipeline.option.with_metadata",
        default="Enable metadata for NFO/Prez in pipeline. Use --no-metadata or -nm to disable metadata for this run.",
    ),
)
def pipeline_command(
    path_parts: tuple[str, ...],
    nfo_locale: str | None,
    announce: str | None,
    skip_renamer: bool,
    skip_cleanmkv: bool,
    skip_nfo: bool,
    skip_torrent: bool,
    skip_prez: bool,
    select_modules: bool | None = None,
    select_templates: bool | None = None,
    enabled_modules_option: str | None = None,
    preset: str | None = None,
    preview: bool = False,
    explain: bool = False,
    with_metadata: bool | None = None,
    remove_terms: tuple[str, ...] = (),
) -> int:
    return run_pipeline_command(
        path=_join_path_parts(path_parts) or None,
        nfo_locale=nfo_locale,
        announce=announce,
        skip_renamer=skip_renamer,
        skip_cleanmkv=skip_cleanmkv,
        skip_nfo=skip_nfo,
        skip_torrent=skip_torrent,
        skip_prez=skip_prez,
        preset=preset,
        preview=preview,
        explain=explain,
        with_metadata=with_metadata,
        remove_terms=remove_terms,
        select_modules=select_modules,
        select_templates=select_templates,
        enabled_modules=tuple(
            item.strip().lower()
            for item in (enabled_modules_option or "").split(",")
            if item.strip()
        )
        if enabled_modules_option
        else None,
    )
