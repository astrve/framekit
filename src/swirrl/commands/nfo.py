from __future__ import annotations

import os
import sys
from pathlib import Path

from rich import box
from rich.panel import Panel
from rich.table import Table

from swirrl.core.cli_helpers import join_path_parts
from swirrl.core.i18n import tr
from swirrl.core.path_validation import PathValidationError, validate_directory_path
from swirrl.core.paths import PathResolver
from swirrl.core.settings import (
    SettingsStore,
    metadata_language_for_nfo_locale,
    resolve_nfo_locale,
)
from swirrl.core.subprocess_safe import (
    MissingToolError,
    SafeSubprocessError,
    popen_safe,
)
from swirrl.modules.metadata.workflow import run_metadata_workflow
from swirrl.modules.nfo.builder import build_release_nfo
from swirrl.modules.nfo.formatting import format_bytes_human, format_duration_ms_human
from swirrl.modules.nfo.logo_registry import NfoLogoRegistry
from swirrl.modules.nfo.logo_tools import import_logo_file
from swirrl.modules.nfo.scanner import scan_nfo_folder
from swirrl.modules.nfo.selector import choose_yes_no
from swirrl.modules.nfo.service import NfoService
from swirrl.modules.nfo.template_registry import NfoTemplateRegistry, scope_matches
from swirrl.modules.nfo.template_selector import (
    build_template_options,
    choose_import_location,
    choose_template,
    choose_template_scope,
)
from swirrl.modules.nfo.templates import import_template_file
from swirrl.ui.branding import print_module_banner

# Prefer rich_click if available; fall back to click when the rich integration is not installed.
from swirrl.ui.click_helper import click
from swirrl.ui.console import (
    console,
    print_error,
    print_exception_error,
    print_info,
    print_success,
    print_warning,
)
from swirrl.ui.unified_selector import SelectorOption
from swirrl.ui.unified_selector import select_one as _select_one

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
    """Open an interactive picker for the NFO mode.

    Lets the user choose between ``global`` / ``per_file`` / ``both``.
    Returns the chosen value, or ``None`` if the user cancelled.
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
    """Open folder containing the NFO file.

    Args:
        path: Path to the NFO file

    Raises:
        PathValidationError: If the folder path is invalid or unsafe
    """
    try:
        # Validate the parent directory before opening
        folder_path = validate_directory_path(path.parent, must_exist=True)
        folder = str(folder_path)
    except PathValidationError as e:
        print_error(f"Cannot open folder: {e}")
        return
    except Exception as e:
        print_error(f"Failed to validate folder path: {e}")
        return

    if sys.platform == "win32":
        try:
            os.startfile(folder)  # nosec B606
        except OSError as e:
            print_error(f"Failed to open folder: {e}")
        return

    if sys.platform == "darwin":
        try:
            # ``popen_safe`` resolves ``open`` via ``shutil.which`` so a
            # writable PATH entry on macOS cannot substitute a hostile
            # binary.
            popen_safe(["open", folder], log_label="macOS open folder")
        except MissingToolError:
            print_error("macOS 'open' utility not found on PATH. Verify your shell configuration.")
        except (OSError, SafeSubprocessError) as e:
            print_error(f"Failed to open folder: {e}")
        return

    try:
        # ``popen_safe`` resolves ``xdg-open`` via ``shutil.which`` to
        # mitigate PATH-hijack on shared Linux hosts.
        popen_safe(["xdg-open", folder], log_label="xdg-open folder")
    except MissingToolError:
        print_error(
            "'xdg-open' not found on PATH. Install xdg-utils to enable the 'open folder' shortcut."
        )
    except (OSError, SafeSubprocessError) as e:
        print_error(f"Failed to open folder: {e}")


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


def _dash(value: str | None) -> str:
    return value if value else "-"


def _nfo_summary_rows(release) -> list[tuple[str, str]]:
    return [
        (tr("common.media_kind", default="Media Kind"), _dash(release.media_kind)),
        (tr("common.release_title", default="Release Title"), _dash(release.release_title)),
        (tr("common.display_title", default="Display Title"), _dash(release.title_display)),
        (tr("common.series", default="Series"), _dash(release.series_title)),
        (tr("common.year", default="Year"), _dash(release.year)),
        (tr("common.source", default="Source"), _dash(release.source)),
        (tr("common.resolution", default="Resolution"), _dash(release.resolution)),
        (tr("common.video", default="Video"), _dash(release.video_tag)),
        (tr("common.audio", default="Audio"), _dash(release.audio_tag)),
        (tr("common.language", default="Language"), _dash(release.language_tag)),
        (
            tr("common.audio_summary", default="Audio Summary"),
            _dash(release.audio_languages_display),
        ),
        ("HDR", _dash(release.hdr_display)),
        (tr("common.team", default="Team"), _dash(release.team)),
        (tr("common.episodes", default="Episodes"), str(len(release.episodes))),
        (tr("common.file_size", default="File Size"), format_bytes_human(release.total_size_bytes)),
        (
            tr("common.total_duration", default="Total Duration"),
            format_duration_ms_human(release.total_duration_ms),
        ),
    ]


def _print_nfo_summary(release) -> None:
    table = Table(
        title=tr("nfo.preview_summary", default="NFO Preview Summary"),
        expand=True,
        box=box.HEAVY,
        border_style="white",
    )
    table.add_column(tr("common.field", default="Field"), width=18, no_wrap=True)
    table.add_column(tr("common.value", default="Value"), ratio=1)

    for field, value in _nfo_summary_rows(release):
        table.add_row(field, value)

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


def _handle_nfo_command_flags(
    *,
    list_templates: bool,
    list_logos: bool,
    import_logo: str | None,
    logo_name: str | None,
    set_logo: str | None,
    clear_logo: bool,
    import_template: str | None,
    import_name: str | None,
    import_scope: str | None,
    import_location: str | None,
    settings: dict,
    store: SettingsStore,
) -> int | None:
    """Handle NFO command flags (list, import, set operations).

    Returns exit code if a flag was handled, None if no flag was processed.
    """
    if list_templates:
        _print_templates()
        return 0
    if list_logos:
        _print_logos()
        return 0
    if import_logo:
        return _handle_import_logo_flag(import_logo, logo_name, settings, store)
    if set_logo:
        return _handle_set_logo_flag(set_logo, settings, store)
    if clear_logo:
        return _handle_clear_logo_flag(settings, store)
    if import_template:
        return _handle_import_template_flag(
            import_template=import_template,
            import_name=import_name,
            import_scope=import_scope,
            import_location=import_location,
        )

    return None


def _handle_import_logo_flag(
    import_logo: str,
    logo_name: str | None,
    settings: dict,
    store: SettingsStore,
) -> int:
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


def _handle_set_logo_flag(set_logo: str, settings: dict, store: SettingsStore) -> int:
    record = NfoLogoRegistry().find(set_logo)
    if record is None:
        print_error(tr("nfo.unknown_logo", default="Unknown logo: {name}", name=set_logo))
        return 1
    settings["modules"]["nfo"]["active_logo"] = record.logo_name
    settings["modules"]["nfo"]["logo_path"] = record.file_path
    store.save(settings)
    print_success(
        tr("nfo.active_logo_set", default="Active logo set to: {name}", name=record.display_name)
    )
    return 0


def _handle_clear_logo_flag(settings: dict, store: SettingsStore) -> int:
    settings["modules"]["nfo"]["active_logo"] = ""
    settings["modules"]["nfo"]["logo_path"] = ""
    store.save(settings)
    print_success(tr("nfo.active_logo_cleared", default="Active logo cleared."))
    return 0


def _handle_import_template_flag(
    *,
    import_template: str,
    import_name: str | None,
    import_scope: str | None,
    import_location: str | None,
) -> int:
    scope = import_scope or choose_template_scope(preferred_scope="universal")
    if scope is None:
        print_warning(tr("nfo.template_import_cancelled", default="Template import cancelled."))
        return 1
    storage_location = import_location or choose_import_location(preferred="appdata")
    if storage_location is None:
        print_warning(tr("nfo.template_import_cancelled", default="Template import cancelled."))
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


def _write_nfo_outputs(
    *,
    service: NfoService,
    folder: Path,
    scan_root: Path,
    is_single_file: bool,
    resolved_mode: str,
    release,
    rendered: str,
    per_file_results: list,
    template_name: str,
    resolved_nfo_locale: str,
) -> tuple[Path | None, list[Path]]:
    written_global: Path | None = None
    written_per_file: list[Path] = []
    media_kind = (getattr(release, "media_kind", "") or "").lower()
    release_folder = (
        scan_root.parent
        if scan_root.parent.name == "Release"
        else scan_root
        if scan_root.name == "Release"
        else scan_root / "Release"
    )
    release_folder.mkdir(parents=True, exist_ok=True)

    # Upload-safe defaults:
    # - movie/single_episode => sidecar + global in Release
    # - season/special pack => per-file + global in Release
    if media_kind in {"movie", "single_episode"}:
        _write_report, output_path = service.write_rendered(
            release_folder,
            release=release,
            rendered=rendered,
            template_name=template_name,
            template_locale=resolved_nfo_locale,
        )
        written_global = output_path
        if release.episodes:
            sidecar_target = release.episodes[0].file_path.with_suffix(".nfo")
            sidecar_target.write_text(rendered, encoding="utf-8")
            if sidecar_target != output_path:
                written_per_file = [sidecar_target]
        return written_global, written_per_file

    if media_kind in {"season_pack", "special_pack"}:
        _write_report, output_path = service.write_rendered(
            release_folder,
            release=release,
            rendered=rendered,
            template_name=template_name,
            template_locale=resolved_nfo_locale,
        )
        written_global = output_path
        _per_report, outputs = service.write_per_file(
            folder,
            results=per_file_results,
            template_name=template_name,
            template_locale=resolved_nfo_locale,
        )
        written_per_file = outputs
        return written_global, written_per_file

    if resolved_mode in ("global", "both") or is_single_file:
        target_folder = scan_root if is_single_file else folder
        _write_report, output_path = service.write_rendered(
            target_folder,
            release=release,
            rendered=rendered,
            template_name=template_name,
            template_locale=resolved_nfo_locale,
        )
        written_global = output_path

    if resolved_mode in ("per_file", "both") and not is_single_file:
        _per_report, outputs = service.write_per_file(
            folder,
            results=per_file_results,
            template_name=template_name,
            template_locale=resolved_nfo_locale,
        )
        written_per_file = outputs

    return written_global, written_per_file


def _confirm_yes_no_or_cancel(prompt_key: str, default_text: str, default_yes: bool) -> bool | None:
    return choose_yes_no(
        tr(prompt_key, default=default_text),
        yes_label=tr("common.yes", default="Yes"),
        no_label=tr("common.no", default="No"),
        default_yes=default_yes,
    )


def _print_written_nfo_paths(written_global: Path | None, written_per_file: list[Path]) -> None:
    if written_global is not None:
        print_success(
            tr("nfo.success.written", default="NFO written: {path}", path=str(written_global))
        )
    for nfo_path in written_per_file:
        print_success(tr("nfo.success.written", default="NFO written: {path}", path=str(nfo_path)))


def _maybe_open_nfo_output_folder(first_output: Path | None) -> None:
    if first_output is None:
        return
    open_folder = _confirm_yes_no_or_cancel(
        "nfo.confirm.open_output_folder",
        "Do you want to open the output folder?",
        False,
    )
    if not open_folder:
        return
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


def _resolve_nfo_folder_and_file(
    *,
    resolver: PathResolver,
    settings: dict,
    cli_path: str | None,
    write_requested: bool,
    with_metadata: bool,
) -> tuple[Path, bool, Path | None, Path]:
    """Resolve NFO folder, determine if single file mode, and validate.

    Returns:
        Tuple of (folder, is_single_file, selected_file, scan_root)
    """
    folder = _resolve_folder(
        resolver,
        settings,
        cli_path=cli_path,
        require_explicit=bool(write_requested or with_metadata),
    )

    if not folder.exists():
        raise FileNotFoundError(
            tr(
                "cleanmkv.error.folder_not_found",
                default="Folder not found: {folder}",
                folder=folder,
            )
        )

    is_single_file = False
    selected_file: Path | None = None
    scan_root = folder

    if folder.is_file():
        if folder.suffix.lower() != ".mkv":
            raise ValueError(
                tr(
                    "cleanmkv.error.invalid_file_type",
                    default="File is not an MKV: {file}",
                    file=folder,
                )
            )
        is_single_file = True
        selected_file = folder
        scan_root = folder.parent
    elif not folder.is_dir():
        raise FileNotFoundError(
            tr(
                "cleanmkv.error.folder_not_found",
                default="Folder not found: {folder}",
                folder=folder,
            )
        )

    return folder, is_single_file, selected_file, scan_root


def _build_nfo_release_probe(
    *,
    folder: Path,
    is_single_file: bool,
    selected_file: Path | None,
    scan_root: Path,
):
    """Build release probe for NFO generation."""
    if is_single_file:
        episodes = scan_nfo_folder(scan_root)
        episodes = [ep for ep in episodes if ep.file_path == selected_file]
        if not episodes:
            raise ValueError(
                tr(
                    "nfo.error.no_mkv",
                    default="No MKV files found in folder: {folder}",
                    folder=folder,
                )
            )
        return build_release_nfo(scan_root, episodes)
    else:
        return _build_release_from_folder(folder)


def _resolve_nfo_configuration(
    *,
    template: str | None,
    settings: dict,
    release_probe,
    nfo_locale: str | None,
    mode: str | None,
    is_single_file: bool,
    write_requested: bool,
) -> tuple[str, str, str, str, str, str]:
    """Resolve NFO configuration (template, locale, mode, etc.).

    Returns:
        Tuple of (template_name, template_source, selection_mode,
                 resolved_nfo_locale, metadata_language, resolved_mode)
    """
    chosen_template = _resolve_template_choice(template, settings, release_probe.media_kind)
    if chosen_template is None:
        raise ValueError(
            tr("nfo.warning.template_selection_cancelled", default="Template selection cancelled.")
        )

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

    # Resolve NFO mode
    settings_mode = _normalize_nfo_mode(nfo_settings.get("mode"), default="global")
    if mode is not None:
        resolved_mode = _normalize_nfo_mode(mode, default=settings_mode)
    elif is_single_file:
        resolved_mode = "global"
    elif sys.stdin.isatty() and not write_requested:
        picked = _choose_nfo_mode(preferred=settings_mode)
        if picked is None:
            raise ValueError(tr("nfo.action_cancelled", default="NFO action cancelled."))
        resolved_mode = picked
    else:
        resolved_mode = settings_mode

    return (
        template_name,
        template_source,
        selection_mode,
        resolved_nfo_locale,
        metadata_language,
        resolved_mode,
    )


def _build_nfo_outputs(
    *,
    service: NfoService,
    folder: Path,
    scan_root: Path,
    is_single_file: bool,
    release_probe,
    resolved_mode: str,
    template_name: str,
    logo_path: str,
    resolved_nfo_locale: str,
    extra_context: dict,
):
    """Build NFO outputs (global and/or per-file).

    Returns:
        Tuple of (report, release, rendered, per_file_results)
    """
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
            # per_file only
            release = release_probe
            rendered = ""
            from swirrl.core.reporting import OperationReport as _OperationReport

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

    return report, release, rendered, per_file_results


def _handle_nfo_interactive_workflow(
    *,
    service: NfoService,
    folder: Path,
    scan_root: Path,
    is_single_file: bool,
    resolved_mode: str,
    release,
    rendered: str,
    per_file_results: list,
    template_name: str,
    resolved_nfo_locale: str,
) -> int:
    """Handle interactive NFO workflow (preview, confirmation, writing).

    Returns exit code.
    """
    show_full_preview = _confirm_yes_no_or_cancel(
        "nfo.confirm.open_preview",
        "Do you want to open the final rendered NFO preview?",
        False,
    )
    if show_full_preview is None:
        print_warning(tr("nfo.action_cancelled", default="NFO action cancelled."))
        return 1
    if show_full_preview:
        preview_text = rendered or (per_file_results[0][2] if per_file_results else "")
        if preview_text:
            _print_rendered_nfo(preview_text)

    generate_nfo = _confirm_yes_no_or_cancel(
        "nfo.confirm.generate_file",
        "Do you want to generate the NFO file?",
        True,
    )

    if generate_nfo is None:
        print_warning(tr("nfo.action_cancelled", default="NFO action cancelled."))
        return 1

    if generate_nfo:
        written_global, written_per_file = _write_nfo_outputs(
            service=service,
            folder=folder,
            scan_root=scan_root,
            is_single_file=is_single_file,
            resolved_mode=resolved_mode,
            release=release,
            rendered=rendered,
            per_file_results=per_file_results,
            template_name=template_name,
            resolved_nfo_locale=resolved_nfo_locale,
        )
        first_output: Path | None = written_global or (
            written_per_file[0] if written_per_file else None
        )
        _print_written_nfo_paths(written_global, written_per_file)
        _maybe_open_nfo_output_folder(first_output)
    else:
        print_success(
            tr(
                "nfo.success.preview_no_write",
                default="NFO preview completed without writing a file.",
            )
        )

    return 0


def _handle_nfo_write_requested(
    *,
    service: NfoService,
    folder: Path,
    scan_root: Path,
    is_single_file: bool,
    resolved_mode: str,
    release,
    rendered: str,
    per_file_results: list,
    template_name: str,
    resolved_nfo_locale: str,
) -> int:
    """Handle non-interactive write-requested mode.

    Returns exit code.
    """
    try:
        nfo_written_global, nfo_written_per_file = _write_nfo_outputs(
            service=service,
            folder=folder,
            scan_root=scan_root,
            is_single_file=is_single_file,
            resolved_mode=resolved_mode,
            release=release,
            rendered=rendered,
            per_file_results=per_file_results,
            template_name=template_name,
            resolved_nfo_locale=resolved_nfo_locale,
        )
    except Exception as exc:
        print_exception_error(exc)
        return 1

    if nfo_written_global is not None:
        print_success(
            tr("nfo.success.written", default="NFO written: {path}", path=str(nfo_written_global))
        )
    for nfo_path in nfo_written_per_file:
        print_success(tr("nfo.success.written", default="NFO written: {path}", path=str(nfo_path)))
    if not nfo_written_global and not nfo_written_per_file:
        print_warning(
            tr(
                "nfo.warning.nothing_written",
                default="No NFO files were written.",
            )
        )
    return 0


def _display_nfo_summary(
    *,
    release,
    metadata_notice: str | None,
    folder: Path,
    template_name: str,
    resolved_nfo_locale: str,
    with_metadata: bool,
    metadata_language: str,
    report,
    is_single_file: bool,
    resolved_mode: str,
    per_file_results: list,
) -> None:
    """Display NFO generation summary information."""
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
    """Execute the NFO command with template selection and metadata integration.

    This is the main entry point for the NFO command. It handles template/logo
    management, NFO generation with optional metadata, and supports both global
    and per-file output modes.
    """
    store = SettingsStore()
    settings = store.load()
    resolver = PathResolver(settings)

    # Determine metadata settings
    metadata_default = bool(
        settings.get("modules", {})
        .get("nfo", {})
        .get("with_metadata", settings.get("metadata", {}).get("enabled_by_default", True))
    )
    with_metadata = metadata_default if with_metadata is None else with_metadata

    # Handle command flags (list, import, set operations)
    flag_result = _handle_nfo_command_flags(
        list_templates=list_templates,
        list_logos=list_logos,
        import_logo=import_logo,
        logo_name=logo_name,
        set_logo=set_logo,
        clear_logo=clear_logo,
        import_template=import_template,
        import_name=import_name,
        import_scope=import_scope,
        import_location=import_location,
        settings=settings,
        store=store,
    )
    if flag_result is not None:
        return flag_result

    print_module_banner("NFO")

    # Resolve folder and determine single-file vs directory mode
    try:
        folder, is_single_file, selected_file, scan_root = _resolve_nfo_folder_and_file(
            resolver=resolver,
            settings=settings,
            cli_path=path,
            write_requested=write_requested,
            with_metadata=with_metadata,
        )
    except Exception as exc:
        print_exception_error(exc)
        return 1

    # Build release probe
    try:
        release_probe = _build_nfo_release_probe(
            folder=folder,
            is_single_file=is_single_file,
            selected_file=selected_file,
            scan_root=scan_root,
        )
    except Exception as exc:
        print_exception_error(exc)
        return 1

    # Resolve NFO configuration (template, locale, mode)
    try:
        (
            template_name,
            template_source,
            selection_mode,
            resolved_nfo_locale,
            metadata_language,
            resolved_mode,
        ) = _resolve_nfo_configuration(
            template=template,
            settings=settings,
            release_probe=release_probe,
            nfo_locale=nfo_locale,
            mode=mode,
            is_single_file=is_single_file,
            write_requested=write_requested,
        )
    except Exception as exc:
        print_exception_error(exc)
        return 1

    nfo_settings = settings.setdefault("modules", {}).setdefault("nfo", {})
    logo_path = nfo_settings.get("logo_path", "")

    # Fallback to bundled default logo if none configured
    if not logo_path:
        from swirrl.core.paths import get_bundled_nfo_logos_dir

        _default_logo = get_bundled_nfo_logos_dir() / "swirrl.txt"
        if _default_logo.is_file():
            logo_path = str(_default_logo)
    service = NfoService()

    # Display preflight information
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

    # Resolve metadata context if enabled
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

    # Build NFO outputs
    try:
        report, release, rendered, per_file_results = _build_nfo_outputs(
            service=service,
            folder=folder,
            scan_root=scan_root,
            is_single_file=is_single_file,
            release_probe=release_probe,
            resolved_mode=resolved_mode,
            template_name=template_name,
            logo_path=logo_path,
            resolved_nfo_locale=resolved_nfo_locale,
            extra_context=extra_context,
        )
    except Exception as exc:
        print_exception_error(exc)
        return 1

    # Display summary
    _display_nfo_summary(
        release=release,
        metadata_notice=metadata_notice,
        folder=folder,
        template_name=template_name,
        resolved_nfo_locale=resolved_nfo_locale,
        with_metadata=with_metadata,
        metadata_language=metadata_language,
        report=report,
        is_single_file=is_single_file,
        resolved_mode=resolved_mode,
        per_file_results=per_file_results,
    )

    # Handle write-requested mode (non-interactive) or interactive workflow
    if write_requested:
        return _handle_nfo_write_requested(
            service=service,
            folder=folder,
            scan_root=scan_root,
            is_single_file=is_single_file,
            resolved_mode=resolved_mode,
            release=release,
            rendered=rendered,
            per_file_results=per_file_results,
            template_name=template_name,
            resolved_nfo_locale=resolved_nfo_locale,
        )

    return _handle_nfo_interactive_workflow(
        service=service,
        folder=folder,
        scan_root=scan_root,
        is_single_file=is_single_file,
        resolved_mode=resolved_mode,
        release=release,
        rendered=rendered,
        per_file_results=per_file_results,
        template_name=template_name,
        resolved_nfo_locale=resolved_nfo_locale,
    )


@click.command(
    "nfo",
    help=tr(
        "cli.nfo.help",
        default=(
            "Build localized, tracker-ready NFO files with optional metadata integration.\n\n"
            "The NFO command generates professional NFO files using customizable templates, with "
            "support for metadata enrichment, multiple output modes, and custom logos.\n\n"
            "Quick examples:\n"
            "  swirrl nfo <folder>                         # Interactive template selection\n"
            "  swirrl nf <folder> -m                       # Include TMDb metadata\n"
            "  swirrl nfo <folder> --write                 # Write immediately\n"
            "  swirrl nf <file.mkv> -m -y                  # Single episode with auto-metadata\n"
            "  swirrl nfo --list-templates                 # Show available templates\n\n"
            "Output modes:\n"
            "  • global: Single NFO for entire release (default)\n"
            "  • per_file: One NFO per media file\n"
            "  • both: Generate both global and per-file NFOs\n\n"
            "Features:\n"
            "  • Multiple template styles (default, detailed)\n"
            "  • Multi-language support (EN/FR/ES)\n"
            "  • Metadata integration from TMDb\n"
            "  • Custom logo support\n"
            "  • Template import/export\n"
            "  • Preview before writing\n\n"
            "Best practices:\n"
            "  • Use -m for metadata-enriched NFOs\n"
            "  • Preview output before writing\n"
            "  • Import custom templates for unique styles\n"
            "  • Use --locale to match tracker requirements\n\n"
            "Related commands: metadata, prez, pipeline"
        ),
    ),
)
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
    import_logo: str | None,
    logo_name: str | None,
    set_logo: str | None,
    list_logos: bool,
    clear_logo: bool,
    mode: str | None,
) -> int:
    """Handle nfo command."""
    return run_nfo_command(
        path=join_path_parts(path_parts) or None,
        template=template,
        nfo_locale=nfo_locale,
        write_requested=write_requested,
        with_metadata=with_metadata,
        metadata_auto_accept=metadata_auto_accept,
        list_templates=list_templates,
        import_template=import_template,
        import_name=import_name,
        import_scope=import_scope,
        import_location=None,
        import_logo=import_logo,
        logo_name=logo_name,
        set_logo=set_logo,
        list_logos=list_logos,
        clear_logo=clear_logo,
        mode=mode,
    )


select_one = _select_one  # backwards-compatible patch target for tests
