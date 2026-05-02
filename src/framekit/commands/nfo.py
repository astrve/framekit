from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Prefer rich_click if available; fall back to click when the rich integration is not installed.
try:
    import rich_click as click  # type: ignore[import-not-found]
except Exception:
    import click  # type: ignore[import-not-found]
from rich import box
from rich.panel import Panel
from rich.table import Table

from framekit.core.i18n import tr
from framekit.core.paths import PathResolver
from framekit.core.settings import (
    SettingsStore,
    metadata_language_for_nfo_locale,
    resolve_nfo_locale,
)
from framekit.modules.metadata.workflow import run_metadata_workflow
from framekit.modules.nfo.builder import build_release_nfo
from framekit.modules.nfo.formatting import format_bytes_human, format_duration_ms_human
from framekit.modules.nfo.logo_registry import NfoLogoRegistry
from framekit.modules.nfo.logo_tools import import_logo_file
from framekit.modules.nfo.scanner import scan_nfo_folder
from framekit.modules.nfo.selector import choose_yes_no
from framekit.modules.nfo.service import NfoService
from framekit.modules.nfo.template_registry import NfoTemplateRegistry, scope_matches
from framekit.modules.nfo.template_selector import (
    build_template_options,
    choose_import_location,
    choose_template,
    choose_template_scope,
)
from framekit.modules.nfo.templates import import_template_file
from framekit.ui.branding import print_module_banner
from framekit.ui.console import (
    console,
    print_error,
    print_exception_error,
    print_info,
    print_success,
    print_warning,
)
from framekit.ui.selector import SelectorOption, select_one

# Valid NFO output modes:
# - "global"   → single NFO for the whole release (default, legacy behavior).
# - "per_file" → one NFO per .mkv, written next to each source file.
# - "both"     → produce both at once.
NFO_MODES = ("global", "per_file", "both")


def _normalize_nfo_mode(value: str | None, default: str = "global") -> str:
    if not value:
        return default
    candidate = str(value).strip().lower()
    return candidate if candidate in NFO_MODES else default


def _choose_nfo_mode(*, preferred: str = "global") -> str | None:
    """
    Open an interactive picker letting the user choose between
    `global` / `per_file` / `both`. Returns the chosen value, or `None`
    if the user cancelled.
    """
    options = [
        SelectorOption(
            value="global",
            label=tr("nfo.mode.global", default="Global (one NFO for the release)"),
            hint=tr(
                "nfo.mode.global_hint",
                default="Single NFO file at the release root — current default behaviour.",
            ),
            selected=(preferred == "global"),
        ),
        SelectorOption(
            value="per_file",
            label=tr("nfo.mode.per_file", default="Per file (one NFO per .mkv)"),
            hint=tr(
                "nfo.mode.per_file_hint",
                default="Each MKV gets its own .nfo next to it. Useful for season packs.",
            ),
            selected=(preferred == "per_file"),
        ),
        SelectorOption(
            value="both",
            label=tr("nfo.mode.both", default="Both (global + per file)"),
            hint=tr(
                "nfo.mode.both_hint",
                default="Generate the global NFO and one NFO per file in the same run.",
            ),
            selected=(preferred == "both"),
        ),
    ]
    try:
        result = select_one(
            title=tr("nfo.mode.picker_title", default="Choose NFO output mode"),
            entries=options,
            page_size=4,
        )
    except KeyboardInterrupt:
        return None
    except RuntimeError:
        # Headless: callers should pre-resolve the mode via settings or CLI.
        return None
    if result is None:
        return None
    return str(result)


def _join_path_parts(parts: tuple[str, ...]) -> str:
    return " ".join(part for part in parts if part).strip()


def _format_metadata_exception(exc: Exception) -> str:
    message = str(exc)
    lowered = message.lower()
    if "remote end closed connection without response" in lowered:
        return tr(
            "metadata.error.remote_closed",
            default="TMDb network error: the remote server closed the connection without sending a response.",
        )
    if "http network error" in lowered or "tmdb request failed" in lowered:
        return tr(
            "metadata.error.network",
            default="TMDb network error: {message}",
            message=message,
        )
    return message


def _open_folder(path: Path) -> None:
    folder = str(path.parent)

    if sys.platform == "win32":
        os.startfile(folder)
        return

    if sys.platform == "darwin":
        subprocess.Popen(["open", folder])
        return

    subprocess.Popen(["xdg-open", folder])


def _print_logos() -> None:
    registry = NfoLogoRegistry()
    logos = registry.load_all()

    table = Table(
        title=tr("nfo.logos.available_title", default="Available NFO Logos"),
        expand=True,
        box=box.HEAVY,
        border_style="white",
    )
    table.add_column(tr("common.name", default="Name"), ratio=1)
    table.add_column(tr("common.internal_name", default="Internal Name"), ratio=1)
    table.add_column(tr("common.path", default="Path"), ratio=2)

    if not logos:
        table.add_row("-", "-", "-")
    else:
        for logo in logos:
            table.add_row(logo.display_name, logo.logo_name, logo.file_path)

    console.print(table)


def _print_templates() -> None:
    registry = NfoTemplateRegistry()
    records = registry.list_all()

    table = Table(
        title=tr("nfo.templates.available_title", default="Available NFO Templates"),
        expand=True,
        box=box.HEAVY,
        border_style="white",
    )
    table.add_column(tr("common.name", default="Name"), ratio=2)
    table.add_column(tr("common.template", default="Template"), ratio=2)
    table.add_column(tr("common.scope", default="Scope"), width=18, no_wrap=True)
    table.add_column(tr("common.source", default="Source"), width=12, no_wrap=True)

    for record in records:
        table.add_row(
            record.display_name,
            record.template_name,
            record.scope,
            record.source,
        )

    console.print(table)


def _print_nfo_summary(release) -> None:
    table = Table(
        title=tr("nfo.preview_summary", default="NFO Preview Summary"),
        expand=True,
        box=box.HEAVY,
        border_style="white",
    )
    table.add_column(tr("common.field", default="Field"), width=18, no_wrap=True)
    table.add_column(tr("common.value", default="Value"), ratio=1)

    table.add_row(tr("common.media_kind", default="Media Kind"), release.media_kind or "-")
    table.add_row(tr("common.release_title", default="Release Title"), release.release_title or "-")
    table.add_row(tr("common.display_title", default="Display Title"), release.title_display or "-")
    table.add_row(tr("common.series", default="Series"), release.series_title or "-")
    table.add_row(tr("common.year", default="Year"), release.year or "-")
    table.add_row(tr("common.source", default="Source"), release.source or "-")
    table.add_row(tr("common.resolution", default="Resolution"), release.resolution or "-")
    table.add_row(tr("common.video", default="Video"), release.video_tag or "-")
    table.add_row(tr("common.audio", default="Audio"), release.audio_tag or "-")
    table.add_row(tr("common.language", default="Language"), release.language_tag or "-")
    table.add_row(
        tr("common.audio_summary", default="Audio Summary"), release.audio_languages_display or "-"
    )
    table.add_row("HDR", release.hdr_display or "-")
    table.add_row(tr("common.team", default="Team"), release.team or "-")
    table.add_row(tr("common.episodes", default="Episodes"), str(len(release.episodes)))
    table.add_row(
        tr("common.file_size", default="File Size"), format_bytes_human(release.total_size_bytes)
    )
    table.add_row(
        tr("common.total_duration", default="Total Duration"),
        format_duration_ms_human(release.total_duration_ms),
    )

    console.print(table)


def _print_rendered_nfo(rendered_text: str) -> None:
    console.print()
    console.print(
        Panel(
            rendered_text,
            title=tr("nfo.final_rendered", default="Final Rendered NFO"),
            border_style="white",
            box=box.HEAVY,
            expand=True,
        )
    )


def _build_release_from_folder(folder: Path):
    episodes = scan_nfo_folder(folder)
    if not episodes:
        raise ValueError(
            tr("nfo.error.no_mkv", default="No MKV files found in folder: {folder}", folder=folder)
        )
    return build_release_nfo(folder, episodes)


def _resolve_metadata_context(
    release,
    settings: dict,
    auto_accept: bool,
    metadata_language: str | None = None,
) -> tuple[dict, str | None]:
    result = run_metadata_workflow(
        release,
        settings,
        auto_accept=auto_accept,
        show_ui=True,
        language_override=metadata_language,
    )

    if result.status == "missing_credentials":
        return (
            {},
            tr(
                "nfo.metadata.missing_credentials",
                default="Metadata requested but no credentials are configured. Continuing without metadata.",
            ),
        )

    if result.status == "unsupported_specials":
        return {}, result.message or tr(
            "nfo.metadata.unsupported_specials",
            default="Special season detected. Continuing without metadata.",
        )

    if result.status == "no_candidates":
        return {}, tr(
            "nfo.metadata.no_candidates",
            default="No metadata candidates found. Continuing without metadata.",
        )

    if result.status == "cancelled":
        return {}, tr(
            "nfo.metadata.cancelled",
            default="Metadata selection cancelled. Continuing without metadata.",
        )

    if result.status != "resolved":
        return {}, result.message or tr(
            "nfo.metadata.failed", default="Metadata workflow failed. Continuing without metadata."
        )

    return result.context, None


def _resolve_template_choice(template_arg: str | None, settings: dict, media_kind: str):
    registry = NfoTemplateRegistry()
    records = registry.list_all()
    options = build_template_options(records)

    if template_arg:
        for option in options:
            if option.template_name == template_arg:
                return option
        return None

    preferred = settings["modules"]["nfo"].get("active_template", "default")
    chosen = choose_template(options, preferred_name=preferred)
    if chosen is None:
        return None

    if chosen.source == "builtin":
        settings["modules"]["nfo"]["active_template"] = chosen.template_name
        return chosen

    if not scope_matches(chosen.scope, media_kind):
        print_warning(
            tr(
                "nfo.template_scoped_warning",
                default="Template '{template}' is scoped to '{scope}', but current media kind is '{media_kind}'. Continuing anyway.",
                template=chosen.display_name,
                scope=chosen.scope,
                media_kind=media_kind,
            )
        )

    settings["modules"]["nfo"]["active_template"] = chosen.template_name
    return chosen


def _print_nfo_preflight(
    folder: Path,
    template_name: str,
    template_source: str,
    selection_mode: str,
    metadata_enabled: bool,
    template_locale: str,
    metadata_language: str | None = None,
    output_mode: str | None = None,
) -> None:
    table = Table(
        title=tr("nfo.build_setup", default="NFO Build Setup"),
        expand=True,
        box=box.HEAVY,
        border_style="white",
    )
    table.add_column(tr("common.field", default="Field"), width=18, no_wrap=True)
    table.add_column(tr("common.value", default="Value"), ratio=1)

    table.add_row(tr("common.folder", default="Folder"), str(folder))
    table.add_row(tr("common.template", default="Template"), template_name or "-")
    table.add_row(tr("nfo.template_source", default="Template Source"), template_source or "-")
    table.add_row(tr("nfo.template_locale", default="NFO Locale"), template_locale or "-")
    table.add_row(
        tr("nfo.metadata_language", default="TMDb Metadata Language"),
        metadata_language if metadata_enabled and metadata_language else "-",
    )
    table.add_row(tr("nfo.selection_mode", default="Selection Mode"), selection_mode or "-")
    if output_mode:
        table.add_row(
            tr("nfo.output_mode", default="Output Mode"),
            tr(f"nfo.mode.{output_mode}_short", default=output_mode),
        )
    table.add_row(
        tr("common.metadata", default="Metadata"),
        tr("common.enabled", default="Enabled")
        if metadata_enabled
        else tr("common.disabled", default="Disabled"),
    )

    console.print(table)


def _resolve_folder(
    resolver: PathResolver,
    settings: dict,
    *,
    cli_path: str | None,
    require_explicit: bool,
) -> Path:
    if require_explicit and not cli_path:
        raise ValueError(
            tr(
                "nfo.error.folder_required_for_write_metadata",
                default="Please provide a target folder explicitly when using --write or --with-metadata.",
            )
        )

    return resolver.resolve_start_folder("nfo", cli_path or None)


def run_nfo_command(
    *,
    path: str | None,
    template: str | None,
    nfo_locale: str | None,
    write_requested: bool,
    with_metadata: bool | None,
    metadata_auto_accept: bool,
    list_templates: bool,
    import_template: str | None,
    import_name: str | None,
    import_scope: str | None,
    import_location: str | None,
    import_logo: str | None,
    logo_name: str | None,
    set_logo: str | None,
    list_logos: bool,
    clear_logo: bool,
    mode: str | None = None,
) -> int:
    store = SettingsStore()
    settings = store.load()
    resolver = PathResolver(settings)
    metadata_default = bool(
        settings.get("modules", {})
        .get("nfo", {})
        .get("with_metadata", settings.get("metadata", {}).get("enabled_by_default", True))
    )
    with_metadata = metadata_default if with_metadata is None else with_metadata

    if list_templates:
        _print_templates()
        return 0

    if list_logos:
        _print_logos()
        return 0

    if import_logo:
        try:
            record = import_logo_file(import_logo, logo_name)
        except Exception as exc:
            print_exception_error(exc)
            return 1

        settings["modules"]["nfo"]["active_logo"] = record.logo_name
        settings["modules"]["nfo"]["logo_path"] = record.file_path
        store.save(settings)

        print_success(
            tr("nfo.logo_imported", default="Logo imported: {name}", name=record.display_name)
        )
        print_info(
            tr("nfo.active_logo_set", default="Active logo set to: {name}", name=record.logo_name)
        )
        return 0

    if set_logo:
        record = NfoLogoRegistry().find(set_logo)
        if record is None:
            print_error(tr("nfo.unknown_logo", default="Unknown logo: {name}", name=set_logo))
            return 1

        settings["modules"]["nfo"]["active_logo"] = record.logo_name
        settings["modules"]["nfo"]["logo_path"] = record.file_path
        store.save(settings)

        print_success(
            tr(
                "nfo.active_logo_set",
                default="Active logo set to: {name}",
                name=record.display_name,
            )
        )
        return 0

    if clear_logo:
        settings["modules"]["nfo"]["active_logo"] = ""
        settings["modules"]["nfo"]["logo_path"] = ""
        store.save(settings)

        print_success(tr("nfo.active_logo_cleared", default="Active logo cleared."))
        return 0

    if import_template:
        scope = import_scope
        if not scope:
            scope = choose_template_scope(preferred_scope="universal")
            if scope is None:
                print_warning(
                    tr("nfo.template_import_cancelled", default="Template import cancelled.")
                )
                return 1

        storage_location = import_location
        if not storage_location:
            storage_location = choose_import_location(preferred="appdata")
            if storage_location is None:
                print_warning(
                    tr("nfo.template_import_cancelled", default="Template import cancelled.")
                )
                return 1

        try:
            record = import_template_file(
                import_template,
                import_name,
                scope=scope,
                storage_location=storage_location,
                base_dir=Path.cwd(),
            )
        except Exception as exc:
            print_exception_error(exc)
            return 1

        print_success(
            tr(
                "nfo.template_imported",
                default="Template imported: {name} [{scope}] -> {path}",
                name=record.display_name,
                scope=record.scope,
                path=record.file_path,
            )
        )
        return 0

    print_module_banner("NFO")

    try:
        folder = _resolve_folder(
            resolver,
            settings,
            cli_path=path,
            require_explicit=bool(write_requested or with_metadata),
        )
    except Exception as exc:
        print_exception_error(exc)
        return 1

    # Support both directories and single MKV files for NFO generation.  When a file
    # is provided ensure it is an MKV; otherwise report an error.  This avoids
    # requiring callers to create a separate folder for each episode.
    if not folder.exists():
        print_error(
            tr(
                "cleanmkv.error.folder_not_found",
                default="Folder not found: {folder}",
                folder=folder,
            )
        )
        return 1

    is_single_file = False
    selected_file: Path | None = None
    scan_root = folder
    # Determine whether the target is a single MKV file or a folder.
    if folder.is_file():
        # Validate that the provided file is an MKV.  NFO generation
        # operates only on MKV containers.
        if folder.suffix.lower() != ".mkv":
            print_error(
                tr(
                    "cleanmkv.error.invalid_file_type",
                    default="File is not an MKV: {file}",
                    file=folder,
                )
            )
            return 1
        is_single_file = True
        selected_file = folder
        scan_root = folder.parent
    elif not folder.is_dir():
        # Neither a file nor a directory
        print_error(
            tr(
                "cleanmkv.error.folder_not_found",
                default="Folder not found: {folder}",
                folder=folder,
            )
        )
        return 1

    # Build a probe release for template selection.  When operating on a
    # single file we scan the parent folder and filter to the chosen file.
    try:
        if is_single_file:
            episodes = scan_nfo_folder(scan_root)
            episodes = [ep for ep in episodes if ep.file_path == selected_file]
            if not episodes:
                print_error(
                    tr(
                        "nfo.error.no_mkv",
                        default="No MKV files found in folder: {folder}",
                        folder=folder,
                    )
                )
                return 1
            release_probe = build_release_nfo(scan_root, episodes)
        else:
            release_probe = _build_release_from_folder(folder)
    except Exception as exc:
        print_exception_error(exc)
        return 1

    chosen_template = _resolve_template_choice(template, settings, release_probe.media_kind)
    if chosen_template is None:
        print_warning(
            tr("nfo.warning.template_selection_cancelled", default="Template selection cancelled.")
        )
        return 1

    template_name = chosen_template.template_name
    template_source = chosen_template.source
    selection_mode = (
        tr("nfo.selection_mode.explicit", default="explicit")
        if template
        else tr("nfo.selection_mode.interactive", default="interactive")
    )
    nfo_settings = settings.setdefault("modules", {}).setdefault("nfo", {})
    configured_nfo_locale = nfo_locale or str(nfo_settings.get("locale", "auto") or "auto")
    resolved_nfo_locale = resolve_nfo_locale(
        configured_nfo_locale,
        ui_locale=str(settings.get("general", {}).get("locale", "en")),
    )
    metadata_language = metadata_language_for_nfo_locale(resolved_nfo_locale)
    logo_path = nfo_settings.get("logo_path", "")
    service = NfoService()

    # Resolve the NFO output mode. CLI flag wins, then settings, then an
    # interactive picker (when running in a TTY without an explicit mode and
    # not in a single-file run). Single-file mode always behaves as "global"
    # because there is exactly one file to write.
    settings_mode = _normalize_nfo_mode(nfo_settings.get("mode"), default="global")
    if mode is not None:
        resolved_mode = _normalize_nfo_mode(mode, default=settings_mode)
    elif is_single_file:
        resolved_mode = "global"
    elif sys.stdin.isatty() and not write_requested:
        picked = _choose_nfo_mode(preferred=settings_mode)
        if picked is None:
            print_warning(tr("nfo.action_cancelled", default="NFO action cancelled."))
            return 1
        resolved_mode = picked
    else:
        resolved_mode = settings_mode

    _print_nfo_preflight(
        folder=folder,
        template_name=template_name,
        template_source=template_source,
        selection_mode=selection_mode,
        metadata_enabled=with_metadata,
        template_locale=resolved_nfo_locale,
        metadata_language=metadata_language,
        output_mode=resolved_mode,
    )

    extra_context: dict = {}
    metadata_notice: str | None = None
    if with_metadata:
        try:
            extra_context, metadata_notice = _resolve_metadata_context(
                release_probe,
                settings,
                auto_accept=metadata_auto_accept,
                metadata_language=metadata_language,
            )
        except Exception as exc:
            metadata_notice = tr(
                "nfo.metadata.skipped",
                default="Metadata skipped: {message}",
                message=_format_metadata_exception(exc),
            )

    # Build the NFO. When operating on a single file we always behave as
    # `global` (one output, single-file scope). For folders we honour the
    # resolved mode: `global` builds one release-wide NFO, `per_file` builds
    # one NFO per .mkv, `both` does both.
    try:
        if is_single_file:
            report, release, rendered = service.build_from_release(
                scan_root,
                release=release_probe,
                template_name=template_name,
                logo_path=logo_path,
                template_locale=resolved_nfo_locale,
                extra_context=extra_context,
            )
            per_file_results: list = []
        else:
            if resolved_mode in ("global", "both"):
                report, release, rendered = service.build(
                    folder,
                    template_name=template_name,
                    logo_path=logo_path,
                    template_locale=resolved_nfo_locale,
                    extra_context=extra_context,
                )
            else:
                # `per_file` only — still build a global release for the
                # preview/summary table so the user sees what is being processed.
                release = release_probe
                rendered = ""
                report = type(release_probe).__class__  # placeholder, replaced below
                from framekit.core.reporting import OperationReport as _OperationReport

                report = _OperationReport(tool="nfo")
                report.scanned = len(release.episodes)
                report.processed = len(release.episodes)
                report.modified = 0
                report.add_detail(
                    file=None,
                    action="nfo",
                    status="planned",
                    message=tr(
                        "nfo.message.per_file_planned",
                        default="Per-file NFOs will be generated ({count}).",
                        count=len(release.episodes),
                    ),
                    before={"folder": str(folder)},
                    after={"template": template_name, "locale": resolved_nfo_locale},
                )

            if resolved_mode in ("per_file", "both"):
                per_file_results = service.build_per_file(
                    folder,
                    template_name=template_name,
                    logo_path=logo_path,
                    template_locale=resolved_nfo_locale,
                    extra_context=extra_context,
                )
            else:
                per_file_results = []
    except Exception as exc:
        print_exception_error(exc)
        return 1

    _print_nfo_summary(release)
    if metadata_notice:
        print_warning(metadata_notice)

    print_info(tr("common.folder", default="Folder") + f": {folder}")
    print_info(tr("common.template", default="Template") + f": {template_name}")
    print_info(tr("nfo.template_locale", default="NFO Locale") + f": {resolved_nfo_locale}")
    if with_metadata:
        print_info(
            tr("nfo.metadata_language", default="TMDb Metadata Language") + f": {metadata_language}"
        )
    print_info(tr("nfo.info.scanned", default="Scanned: {count}", count=report.scanned))
    print_info(tr("nfo.info.processed", default="Processed: {count}", count=report.processed))
    if not is_single_file and resolved_mode != "global":
        print_info(
            tr(
                "nfo.info.per_file_planned",
                default="Per-file NFOs planned: {count}",
                count=len(per_file_results),
            )
        )

    def _write_global() -> Path | None:
        target_folder = scan_root if is_single_file else folder
        _write_report, output_path = service.write_rendered(
            target_folder,
            release=release,
            rendered=rendered,
            template_name=template_name,
            template_locale=resolved_nfo_locale,
        )
        return output_path

    def _write_per_file() -> list[Path]:
        if not per_file_results:
            return []
        _per_report, outputs = service.write_per_file(
            folder,
            results=per_file_results,
            template_name=template_name,
            template_locale=resolved_nfo_locale,
        )
        return outputs

    if write_requested:
        try:
            written_global: Path | None = None
            written_per_file: list[Path] = []
            if resolved_mode in ("global", "both") or is_single_file:
                written_global = _write_global()
            if resolved_mode in ("per_file", "both") and not is_single_file:
                written_per_file = _write_per_file()
        except Exception as exc:
            print_exception_error(exc)
            return 1

        if written_global is not None:
            print_success(
                tr("nfo.success.written", default="NFO written: {path}", path=str(written_global))
            )
        for nfo_path in written_per_file:
            print_success(
                tr("nfo.success.written", default="NFO written: {path}", path=str(nfo_path))
            )
        if not written_global and not written_per_file:
            print_warning(
                tr(
                    "nfo.warning.nothing_written",
                    default="No NFO files were written.",
                )
            )
        settings["modules"]["nfo"]["last_folder"] = str(folder)
        store.save(settings)
        return 0

    show_full_preview = choose_yes_no(
        tr(
            "nfo.confirm.open_preview",
            default="Do you want to open the final rendered NFO preview?",
        ),
        yes_label=tr("common.yes", default="Yes"),
        no_label=tr("common.no", default="No"),
        default_yes=False,
    )

    if show_full_preview is None:
        print_warning(tr("nfo.action_cancelled", default="NFO action cancelled."))
        return 1

    if show_full_preview:
        # In `per_file`-only mode there is no global rendered text, so show
        # the first per-file preview instead. This gives the user a concrete
        # sample of what every file will look like.
        if rendered:
            _print_rendered_nfo(rendered)
        elif per_file_results:
            _print_rendered_nfo(per_file_results[0][2])

    generate_nfo = choose_yes_no(
        tr("nfo.confirm.generate_file", default="Do you want to generate the NFO file?"),
        yes_label=tr("common.yes", default="Yes"),
        no_label=tr("common.no", default="No"),
        default_yes=True,
    )

    if generate_nfo is None:
        print_warning(tr("nfo.action_cancelled", default="NFO action cancelled."))
        return 1

    if generate_nfo:
        try:
            written_global: Path | None = None
            written_per_file: list[Path] = []
            if resolved_mode in ("global", "both") or is_single_file:
                written_global = _write_global()
            if resolved_mode in ("per_file", "both") and not is_single_file:
                written_per_file = _write_per_file()
        except Exception as exc:
            print_exception_error(exc)
            return 1

        first_output: Path | None = written_global or (
            written_per_file[0] if written_per_file else None
        )
        if written_global is not None:
            print_success(
                tr("nfo.success.written", default="NFO written: {path}", path=str(written_global))
            )
        for nfo_path in written_per_file:
            print_success(
                tr("nfo.success.written", default="NFO written: {path}", path=str(nfo_path))
            )

        if first_output is not None:
            open_folder = choose_yes_no(
                tr(
                    "nfo.confirm.open_output_folder",
                    default="Do you want to open the output folder?",
                ),
                yes_label=tr("common.yes", default="Yes"),
                no_label=tr("common.no", default="No"),
                default_yes=False,
            )

            if open_folder:
                try:
                    _open_folder(first_output)
                except Exception as exc:
                    print_warning(
                        tr(
                            "nfo.warning.open_output_failed",
                            default="Could not open output folder: {message}",
                            message=exc,
                        )
                    )
    else:
        print_success(
            tr(
                "nfo.success.preview_no_write",
                default="NFO preview completed without writing a file.",
            )
        )

    settings["modules"]["nfo"]["last_folder"] = str(folder)
    store.save(settings)

    return 0


@click.command("nfo", help=tr("cli.nfo.help", default="Build tracker-ready NFO files."))
@click.argument("path_parts", nargs=-1)
@click.option("-t", "--template", help=tr("cli.nfo.option.template", default="Template name."))
@click.option(
    "--locale",
    "nfo_locale",
    type=click.Choice(["auto", "en", "fr", "es"]),
    help=tr(
        "cli.nfo.option.locale", default="NFO output language. Defaults to modules.nfo.locale."
    ),
)
@click.option(
    "-w",
    "--write",
    "write_requested",
    is_flag=True,
    help=tr("cli.nfo.option.write", default="Write the NFO file immediately."),
)
@click.option(
    "-m/-nm",
    "--with-metadata/--no-metadata",
    "with_metadata",
    default=None,
    help=tr(
        "cli.nfo.option.with_metadata",
        default="Enrich the NFO with metadata. Use --no-metadata or -nm to disable metadata for this run.",
    ),
)
@click.option(
    "-y",
    "--metadata-auto-accept",
    is_flag=True,
    help=tr(
        "cli.nfo.option.metadata_auto_accept",
        default="Automatically accept the top metadata candidate.",
    ),
)
@click.option(
    "-L",
    "-lt",
    "--list-templates",
    is_flag=True,
    help=tr("cli.nfo.option.list_templates", default="List available NFO templates."),
)
@click.option(
    "-it",
    "--import-template",
    metavar="PATH",
    help=tr("cli.nfo.option.import_template", default="Path to a .jinja2 or .j2 template file."),
)
@click.option(
    "-in",
    "--import-name",
    help=tr("cli.nfo.option.import_name", default="Display name for an imported template."),
)
@click.option(
    "-is",
    "--import-scope",
    type=click.Choice(["movie", "single_episode", "season_pack", "universal"]),
    help=tr("cli.nfo.option.import_scope", default="Scope for an imported template."),
)
@click.option(
    "-il",
    "--import-location",
    type=click.Choice(["appdata", "project"]),
    help=tr("cli.nfo.option.import_location", default="Where to store an imported template."),
)
@click.option(
    "-ig",
    "--import-logo",
    metavar="PATH",
    help=tr("cli.nfo.option.import_logo", default="Path to a text logo file (.txt, .nfo, .asc)."),
)
@click.option(
    "-ln",
    "--logo-name",
    help=tr("cli.nfo.option.logo_name", default="Display name for an imported logo."),
)
@click.option(
    "-sl",
    "--set-logo",
    help=tr("cli.nfo.option.set_logo", default="Set the active logo by internal logo name."),
)
@click.option(
    "-lg",
    "--list-logos",
    is_flag=True,
    help=tr("cli.nfo.option.list_logos", default="List available imported logos."),
)
@click.option(
    "-cl",
    "--clear-logo",
    is_flag=True,
    help=tr("cli.nfo.option.clear_logo", default="Disable the active logo."),
)
@click.option(
    "--mode",
    "mode",
    type=click.Choice(["global", "per_file", "both"]),
    default=None,
    help=tr(
        "cli.nfo.option.mode",
        default="NFO output mode: 'global' (single release NFO), 'per_file' (one NFO per file), or 'both'.",
    ),
)
def nfo_command(
    path_parts: tuple[str, ...],
    template: str | None,
    nfo_locale: str | None,
    write_requested: bool,
    with_metadata: bool | None,
    metadata_auto_accept: bool,
    list_templates: bool,
    import_template: str | None,
    import_name: str | None,
    import_scope: str | None,
    import_location: str | None,
    import_logo: str | None,
    logo_name: str | None,
    set_logo: str | None,
    list_logos: bool,
    clear_logo: bool,
    mode: str | None,
) -> int:
    return run_nfo_command(
        path=_join_path_parts(path_parts) or None,
        template=template,
        nfo_locale=nfo_locale,
        write_requested=write_requested,
        with_metadata=with_metadata,
        metadata_auto_accept=metadata_auto_accept,
        list_templates=list_templates,
        import_template=import_template,
        import_name=import_name,
        import_scope=import_scope,
        import_location=import_location,
        import_logo=import_logo,
        logo_name=logo_name,
        set_logo=set_logo,
        list_logos=list_logos,
        clear_logo=clear_logo,
        mode=mode,
    )
