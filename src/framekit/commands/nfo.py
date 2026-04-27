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

    if not folder.exists() or not folder.is_dir():
        print_error(
            tr(
                "cleanmkv.error.folder_not_found",
                default="Folder not found: {folder}",
                folder=folder,
            )
        )
        return 1

    try:
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

    _print_nfo_preflight(
        folder=folder,
        template_name=template_name,
        template_source=template_source,
        selection_mode=selection_mode,
        metadata_enabled=with_metadata,
        template_locale=resolved_nfo_locale,
        metadata_language=metadata_language,
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

    try:
        report, release, rendered = service.build(
            folder,
            template_name=template_name,
            logo_path=logo_path,
            template_locale=resolved_nfo_locale,
            extra_context=extra_context,
        )
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

    if write_requested:
        try:
            _write_report, output_path = service.write_rendered(
                folder,
                release=release,
                rendered=rendered,
                template_name=template_name,
                template_locale=resolved_nfo_locale,
            )
        except Exception as exc:
            print_exception_error(exc)
            return 1

        print_success(tr("nfo.success.written", default="NFO written: {path}", path=output_path))
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
        _print_rendered_nfo(rendered)

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
            _write_report, output_path = service.write_rendered(
                folder,
                release=release,
                rendered=rendered,
                template_name=template_name,
                template_locale=resolved_nfo_locale,
            )
        except Exception as exc:
            print_exception_error(exc)
            return 1

        print_success(tr("nfo.success.written", default="NFO written: {path}", path=output_path))

        open_folder = choose_yes_no(
            tr("nfo.confirm.open_output_folder", default="Do you want to open the output folder?"),
            yes_label=tr("common.yes", default="Yes"),
            no_label=tr("common.no", default="No"),
            default_yes=False,
        )

        if open_folder:
            try:
                _open_folder(output_path)
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
    )
