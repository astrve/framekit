from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ouro.core.cli_helpers import join_path_parts
from ouro.core.diagnostics import log_exception
from ouro.core.i18n import tr
from ouro.core.paths import PathResolver
from ouro.core.settings import (
    SettingsStore,
    metadata_language_for_nfo_locale,
    resolve_nfo_locale,
)
from ouro.modules.metadata.workflow import run_metadata_workflow
from ouro.modules.nfo.builder import build_release_nfo
from ouro.modules.nfo.scanner import scan_nfo_folder
from ouro.modules.prez.banner_selector import (
    build_banner_urls,
    normalize_banner_language,
    select_banner_design,
)
from ouro.modules.prez.service import (
    MEDIAINFO_MODES,
    PREZ_PRESETS,
    PrezBuildOptions,
    PrezService,
    available_bbcode_templates,
    available_html_templates,
    available_prez_presets,
    describe_bbcode_template,
    describe_html_template,
    template_category,
)
from ouro.modules.prez.template_selector import select_template_collapsible
from ouro.ui.branding import print_module_banner

# Prefer rich_click if available; fall back to click when the rich integration is not installed.
from ouro.ui.click_helper import click
from ouro.ui.console import (
    print_error,
    print_exception_error,
    print_info,
    print_success,
    print_warning,
)


def _first_text(*values: object) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def _formats_from_option(value: str | None) -> tuple[str, ...]:
    selected = (value or "both").strip().lower()
    if selected == "both":
        return ("html", "bbcode")
    if selected == "mediainfo":
        return ()
    return (selected,)


def _print_templates() -> None:
    print_info(tr("prez.templates.html", default="HTML templates") + ":")
    for name in available_html_templates():
        print_info(
            f"  - {name} [{template_category(name, kind='html')}] {describe_html_template(name)}"
        )
    print_info(tr("prez.templates.bbcode", default="BBCode templates") + ":")
    for name in available_bbcode_templates():
        print_info(
            f"  - {name} [{template_category(name, kind='bbcode')}] "
            f"{describe_bbcode_template(name)}"
        )
    print_info(
        tr("prez.templates.presets", default="Prez presets")
        + ": "
        + ", ".join(available_prez_presets())
    )


def _resolve_template_settings(
    settings: dict, preset: str | None, html_template: str | None, bbcode_template: str | None
) -> tuple[str, str, str]:
    prez_settings = settings.setdefault("modules", {}).setdefault("prez", {})
    preset_source = _first_text(preset, prez_settings.get("preset"), "default") or "default"
    preset_name = preset_source.lower()
    if preset_name not in PREZ_PRESETS:
        preset_name = "default"
    preset_values = PREZ_PRESETS[preset_name]

    if preset is not None:
        resolved_html = (
            _first_text(html_template, preset_values["html_template"])
            or preset_values["html_template"]
        )
        resolved_bbcode = (
            _first_text(bbcode_template, preset_values["bbcode_template"])
            or preset_values["bbcode_template"]
        )
        return preset_name, resolved_html, resolved_bbcode

    resolved_html = (
        _first_text(
            html_template,
            prez_settings.get("html_template"),
            preset_values["html_template"],
        )
        or preset_values["html_template"]
    )
    resolved_bbcode = (
        _first_text(
            bbcode_template,
            prez_settings.get("bbcode_template"),
            preset_values["bbcode_template"],
        )
        or preset_values["bbcode_template"]
    )
    return preset_name, resolved_html, resolved_bbcode


def _resolve_format_setting(
    settings: dict, preset_name: str, output_format: str | None, *, explicit_preset: bool
) -> str:
    if output_format:
        return output_format
    if explicit_preset:
        return PREZ_PRESETS[preset_name].get("format", "both")
    prez_settings = settings.setdefault("modules", {}).setdefault("prez", {})
    configured = str(prez_settings.get("format", "") or "").strip().lower()
    if configured in {"html", "bbcode", "both", "mediainfo"}:
        return configured
    return PREZ_PRESETS[preset_name].get("format", "both")


def _maybe_select_templates(
    *,
    formats: tuple[str, ...],
    html_template: str,
    bbcode_template: str,
    explicit_html: bool,
    explicit_bbcode: bool,
    explicit_preset: bool,
    select_templates: bool | None,
    metadata_context: dict | None = None,
) -> tuple[str, str]:
    should_select = _should_select_templates(
        formats=formats,
        explicit_html=explicit_html,
        explicit_bbcode=explicit_bbcode,
        explicit_preset=explicit_preset,
        select_templates=select_templates,
    )

    if not should_select:
        return html_template, bbcode_template

    # Use new collapsible selector with smart suggestions
    if "bbcode" in formats and not explicit_bbcode:
        bbcode_template = select_template_collapsible(
            kind="bbcode",
            current=bbcode_template,
            metadata=metadata_context,
        )
    if "html" in formats and not explicit_html:
        html_template = select_template_collapsible(
            kind="html",
            current=html_template,
            metadata=metadata_context,
        )
    return html_template, bbcode_template


def _should_select_templates(
    *,
    formats: tuple[str, ...],
    explicit_html: bool,
    explicit_bbcode: bool,
    explicit_preset: bool,
    select_templates: bool | None,
) -> bool:
    if select_templates is not None:
        return select_templates
    if explicit_preset or explicit_html or explicit_bbcode:
        return False
    if not sys.stdin.isatty():
        return False
    return any(fmt in {"html", "bbcode"} for fmt in formats)


def _resolve_prez_locale(settings: dict, locale: str | None) -> tuple[str, str]:
    prez_settings = settings.setdefault("modules", {}).setdefault("prez", {})
    configured_locale = locale or str(prez_settings.get("locale", "auto") or "auto")
    resolved_locale = resolve_nfo_locale(
        configured_locale,
        ui_locale=str(settings.get("general", {}).get("locale", "en")),
    )
    return configured_locale, resolved_locale


def _resolve_mediainfo_mode(
    *,
    prez_settings: dict,
    preset: str | None,
    preset_name: str,
    with_mediainfo: bool,
    mediainfo_mode: str | None,
) -> str:
    preset_values = PREZ_PRESETS[preset_name]
    if mediainfo_mode:
        configured = mediainfo_mode.strip().lower()
    elif with_mediainfo:
        configured = "spoiler"
    elif preset is not None:
        configured = preset_values.get("mediainfo_mode", "none").strip().lower()
    else:
        configured = (
            str(
                prez_settings.get("mediainfo_mode", "")
                or ("spoiler" if prez_settings.get("include_mediainfo") else "")
                or preset_values.get("mediainfo_mode", "none")
            )
            .strip()
            .lower()
        )
    return configured if configured in MEDIAINFO_MODES else "none"


def _resolve_use_metadata(settings: dict, with_metadata: bool | None) -> bool:
    metadata_default = bool(
        settings.get("modules", {})
        .get("prez", {})
        .get("with_metadata", settings.get("metadata", {}).get("enabled_by_default", True))
    )
    return metadata_default if with_metadata is None else with_metadata


def _load_metadata_context(
    folder: Path, settings: dict, metadata_language: str
) -> dict[str, Any] | None:
    episodes = scan_nfo_folder(folder)
    release = build_release_nfo(folder, episodes)
    result = run_metadata_workflow(
        release,
        settings,
        auto_accept=False,
        show_ui=True,
        language_override=metadata_language,
    )
    return result.context if result.status == "resolved" else None


def _load_metadata_context_with_warning(
    folder: Path,
    settings: dict,
    metadata_language: str,
) -> dict[str, Any] | None:
    try:
        episodes = scan_nfo_folder(folder)
        release = build_release_nfo(folder, episodes)
        result = run_metadata_workflow(
            release,
            settings,
            auto_accept=False,
            show_ui=True,
            language_override=metadata_language,
        )
    except Exception as exc:
        log_exception(exc)
        print_warning(
            tr(
                "prez.warning.metadata_unavailable",
                default="Metadata unavailable. Continuing without metadata.",
            )
            + f" {exc}"
        )
        return None

    if result.status == "resolved":
        return result.context
    print_warning(
        result.message
        or tr(
            "prez.warning.metadata_unavailable",
            default="Metadata unavailable. Continuing without metadata.",
        )
    )
    return None


def _maybe_select_banner(
    *,
    formats: tuple[str, ...],
    prez_settings: dict,
    resolved_locale: str,
    preset: str | None,
    bbcode_template: str | None,
    store: SettingsStore,
    settings: dict,
) -> str | None:
    should_select_banner = (
        sys.stdin.isatty() and "bbcode" in formats and preset is None and bbcode_template is None
    )
    if not should_select_banner:
        return None

    banner_language = normalize_banner_language(resolved_locale)
    current_banner = prez_settings.get("banner_design")
    banner_design = select_banner_design(
        language=banner_language,
        current_design=current_banner,
    )
    if banner_design and banner_design != current_banner:
        prez_settings["banner_design"] = banner_design
        store.save(settings)
        print_success(
            tr(
                "prez.banner.selected",
                default="Banner design selected: {design}",
                design=banner_design if banner_design != "textual" else "Textual (No Banner)",
            )
        )
    return banner_design


def _print_prez_summary(
    *,
    folder: Path,
    resolved_locale: str,
    configured_format: str,
    use_metadata: bool,
    resolved_html_template: str,
    resolved_bbcode_template: str,
    configured_mediainfo_mode: str,
    outputs: Sequence[Path],
) -> None:
    print_info(tr("common.folder", default="Folder") + f": {folder}")
    print_info(tr("prez.locale", default="Prez Locale") + f": {resolved_locale}")
    print_info(
        tr("cli.prez.option.format", default="Presentation format") + f": {configured_format}"
    )
    print_info(
        tr("common.metadata", default="Metadata")
        + ": "
        + (
            tr("common.enabled", default="Enabled")
            if use_metadata
            else tr("common.disabled", default="Disabled")
        )
    )
    print_info(tr("prez.template.html", default="HTML template") + f": {resolved_html_template}")
    print_info(
        tr("prez.template.bbcode", default="BBCode template") + f": {resolved_bbcode_template}"
    )
    print_info(
        tr("prez.mediainfo_mode", default="MediaInfo mode") + f": {configured_mediainfo_mode}"
    )
    for output in outputs:
        print_info(tr("common.output", default="Output") + f": {output}")


def _build_prez_outputs(
    *,
    folder: Path,
    output_dir: str | None,
    formats: tuple[str, ...],
    metadata_context: dict[str, Any] | None,
    resolved_locale: str,
    with_mediainfo: bool,
    configured_mediainfo_mode: str,
    resolved_html_template: str,
    resolved_bbcode_template: str,
    preset_name: str,
    banner_urls: dict[str, str],
    dry_run: bool,
    preview: bool,
):
    try:
        return PrezService().build(
            folder,
            options=PrezBuildOptions(
                formats=formats,
                output_dir=Path(output_dir) if output_dir else None,
                metadata_context=metadata_context,
                locale=resolved_locale,
                include_mediainfo=with_mediainfo,
                mediainfo_mode=configured_mediainfo_mode,
                html_template=resolved_html_template,
                bbcode_template=resolved_bbcode_template,
                preset=preset_name,
                banner_audio=banner_urls["audio"],
                banner_information=banner_urls["information"],
                banner_metadata=banner_urls["metadata"],
                banner_release=banner_urls["release"],
                banner_subtitles=banner_urls["subtitles"],
                banner_synopsis=banner_urls["synopsis"],
                banner_technical=banner_urls["technical"],
            ),
            write=not (dry_run or preview),
        )
    except Exception as exc:
        print_exception_error(exc)
        return None


def _print_prez_completion(dry_run: bool, preview: bool) -> None:
    if dry_run or preview:
        print_success(tr("prez.success.dry_run", default="Presentation dry-run completed."))
        return
    print_success(tr("prez.success.written", default="Presentation generated."))


def _resolve_metadata_context(
    *,
    folder: Path,
    settings: dict,
    metadata_language: str,
    use_metadata: bool,
    warn_on_failure: bool,
) -> dict[str, Any] | None:
    if not use_metadata:
        return None
    try:
        metadata_context = _load_metadata_context(folder, settings, metadata_language)
    except Exception:  # nosec B110
        metadata_context = None
    if metadata_context is not None:
        return metadata_context
    if warn_on_failure:
        return _load_metadata_context_with_warning(folder, settings, metadata_language)
    return None


def _resolve_templates_and_metadata(
    *,
    folder: Path,
    settings: dict,
    metadata_language: str,
    use_metadata: bool,
    formats: tuple[str, ...],
    html_template: str,
    bbcode_template: str,
    explicit_html: bool,
    explicit_bbcode: bool,
    explicit_preset: bool,
    select_templates: bool | None,
) -> tuple[dict[str, Any] | None, str, str]:
    metadata_context = _resolve_metadata_context(
        folder=folder,
        settings=settings,
        metadata_language=metadata_language,
        use_metadata=use_metadata,
        warn_on_failure=False,
    )
    resolved_html_template, resolved_bbcode_template = _maybe_select_templates(
        formats=formats,
        html_template=html_template,
        bbcode_template=bbcode_template,
        explicit_html=explicit_html,
        explicit_bbcode=explicit_bbcode,
        explicit_preset=explicit_preset,
        select_templates=select_templates,
        metadata_context=metadata_context,
    )
    return metadata_context, resolved_html_template, resolved_bbcode_template


def _resolve_banner_design_or_default(
    *,
    formats: tuple[str, ...],
    prez_settings: dict,
    resolved_locale: str,
    preset: str | None,
    bbcode_template: str | None,
    store: SettingsStore,
    settings: dict,
) -> str:
    banner_design = _maybe_select_banner(
        formats=formats,
        prez_settings=prez_settings,
        resolved_locale=resolved_locale,
        preset=preset,
        bbcode_template=bbcode_template,
        store=store,
        settings=settings,
    )
    if banner_design is None:
        return str(prez_settings.get("banner_design", "textual") or "textual")
    return banner_design


def run_prez_command(
    *,
    path: str | None,
    output_dir: str | None,
    output_format: str | None,
    with_metadata: bool | None,
    locale: str | None,
    dry_run: bool,
    preview: bool = False,
    with_mediainfo: bool = False,
    mediainfo_mode: str | None = None,
    html_template: str | None = None,
    bbcode_template: str | None = None,
    preset: str | None = None,
    list_templates: bool = False,
    select_templates: bool | None = None,
) -> int:
    """Run prez command."""
    store = SettingsStore()
    settings = store.load()
    resolver = PathResolver(settings)

    print_module_banner("Prez")

    if list_templates:
        _print_templates()
        return 0

    folder = resolver.resolve_start_folder("prez", path or None)
    if not folder.exists() or not folder.is_dir():
        print_error(
            tr(
                "cleanmkv.error.folder_not_found",
                default="Folder not found: {folder}",
                folder=folder,
            )
        )
        return 1

    prez_settings = settings.setdefault("modules", {}).setdefault("prez", {})
    configured_locale = locale or str(prez_settings.get("locale", "auto") or "auto")
    resolved_locale = resolve_nfo_locale(
        configured_locale,
        ui_locale=str(settings.get("general", {}).get("locale", "en")),
    )
    metadata_language = metadata_language_for_nfo_locale(resolved_locale)
    preset_name, resolved_html_template, resolved_bbcode_template = _resolve_template_settings(
        settings,
        preset,
        html_template,
        bbcode_template,
    )
    configured_format = _resolve_format_setting(
        settings, preset_name, output_format, explicit_preset=preset is not None
    )

    configured_mediainfo_mode = _resolve_mediainfo_mode(
        prez_settings=prez_settings,
        preset=preset,
        preset_name=preset_name,
        with_mediainfo=with_mediainfo,
        mediainfo_mode=mediainfo_mode,
    )

    formats = _formats_from_option(configured_format)

    use_metadata = _resolve_use_metadata(settings, with_metadata)

    metadata_context, resolved_html_template, resolved_bbcode_template = (
        _resolve_templates_and_metadata(
            folder=folder,
            settings=settings,
            metadata_language=metadata_language,
            use_metadata=use_metadata,
            formats=formats,
            html_template=resolved_html_template,
            bbcode_template=resolved_bbcode_template,
            explicit_html=html_template is not None,
            explicit_bbcode=bbcode_template is not None,
            explicit_preset=preset is not None,
            select_templates=select_templates,
        )
    )

    banner_design = _resolve_banner_design_or_default(
        formats=formats,
        prez_settings=prez_settings,
        resolved_locale=resolved_locale,
        preset=preset,
        bbcode_template=bbcode_template,
        store=store,
        settings=settings,
    )

    if use_metadata and metadata_context is None:
        metadata_context = _resolve_metadata_context(
            folder=folder,
            settings=settings,
            metadata_language=metadata_language,
            use_metadata=use_metadata,
            warn_on_failure=True,
        )

    banner_urls = build_banner_urls(banner_design, normalize_banner_language(resolved_locale))

    build_result = _build_prez_outputs(
        folder=folder,
        output_dir=output_dir,
        formats=formats,
        metadata_context=metadata_context,
        resolved_locale=resolved_locale,
        with_mediainfo=with_mediainfo,
        configured_mediainfo_mode=configured_mediainfo_mode,
        resolved_html_template=resolved_html_template,
        resolved_bbcode_template=resolved_bbcode_template,
        preset_name=preset_name,
        banner_urls=banner_urls,
        dry_run=dry_run,
        preview=preview,
    )
    if build_result is None:
        return 1
    _report, result = build_result

    _print_prez_summary(
        folder=folder,
        resolved_locale=resolved_locale,
        configured_format=configured_format,
        use_metadata=use_metadata,
        resolved_html_template=resolved_html_template,
        resolved_bbcode_template=resolved_bbcode_template,
        configured_mediainfo_mode=configured_mediainfo_mode,
        outputs=result.outputs,
    )

    _print_prez_completion(dry_run, preview)

    return 0


@click.command(
    "prez",
    help=tr(
        "cli.prez.help",
        default=(
            "Generate beautiful HTML and BBCode presentation files for tracker uploads.\n\n"
            "Prez creates visually appealing presentations with technical details, screenshots, "
            "and optional metadata integration for professional tracker releases.\n\n"
            "Quick examples:\n"
            "  ouro prez <folder>                        # Interactive template selection\n"
            "  ouro prez <folder> -m                     # Include TMDb metadata\n"
            "  ouro prez <folder> --format html          # HTML only\n"
            "  ouro prez <folder> --preset premium       # Use preset\n"
            "  ouro prez --list-templates                # Show available templates\n\n"
            "Template categories:\n"
            "  • HTML: 20+ templates (cinematic, minimal, poster-focus, timeline, etc.)\n"
            "  • BBCode: 8 templates (classic, detailed, spoiler, tracker, etc.)\n"
            "  • Presets: Predefined combinations (default, premium, tracker, minimal)\n\n"
            "Features:\n"
            "  • Multiple output formats (HTML, BBCode, both)\n"
            "  • Rich template library\n"
            "  • Metadata integration\n"
            "  • MediaInfo inclusion\n"
            "  • Multi-language support\n\n"
            "Best practices:\n"
            "  • Use --select-templates for interactive browsing\n"
            "  • Include metadata with -m for richer presentations\n"
            "  • Try different templates to find your style\n"
            "  • Use presets for consistent output\n\n"
            "Related commands: nfo, metadata, pipeline"
        ),
    ),
)
@click.argument("path_parts", nargs=-1)
@click.option(
    "-o", "--output-dir", help=tr("cli.prez.option.output_dir", default="Output directory.")
)
@click.option(
    "-f",
    "--format",
    "output_format",
    type=click.Choice(["html", "bbcode", "both", "mediainfo"]),
    default=None,
    help=tr("cli.prez.option.format", default="Presentation format."),
)
@click.option(
    "-m/-nm",
    "--with-metadata/--no-metadata",
    "with_metadata",
    default=None,
    help=tr(
        "cli.prez.option.with_metadata",
        default="Enrich presentation with metadata. Use --no-metadata or -nm to disable metadata for this run.",
    ),
)
@click.option(
    "-l",
    "--locale",
    type=click.Choice(["auto", "en", "fr", "es"]),
    help=tr("cli.prez.option.locale", default="Presentation language."),
)
@click.option(
    "-d",
    "--dry-run",
    is_flag=True,
    help=tr("cli.prez.option.dry_run", default="Preview output paths without writing."),
)
@click.option(
    "-p",
    "--preview",
    is_flag=True,
    help=tr(
        "cli.prez.option.preview", default="Preview generated presentation choices without writing."
    ),
)
@click.option(
    "--with-mediainfo",
    is_flag=True,
    help=tr(
        "cli.prez.option.with_mediainfo",
        default="Include a raw MediaInfo spoiler in generated presentations.",
    ),
)
@click.option(
    "--mediainfo-mode",
    type=click.Choice(["none", "spoiler", "only"]),
    help=tr(
        "cli.prez.option.mediainfo_mode",
        default="MediaInfo handling: none, spoiler, or only.",
    ),
)
@click.option(
    "--html-template",
    type=click.Choice(
        [*available_html_templates(), "default", "premium", "tracker", "poster-focus"]
    ),
    show_choices=False,
    help=tr(
        "cli.prez.option.html_template",
        default="HTML template style (e.g. 'default', 'premium'). Use --list-templates for all.",
    ),
)
@click.option(
    "--bbcode-template",
    type=click.Choice([*available_bbcode_templates(), "default", "premium"]),
    help=tr("cli.prez.option.bbcode_template", default="BBCode organization."),
)
@click.option(
    "-P",
    "--preset",
    type=click.Choice(list(available_prez_presets())),
    help=tr("cli.prez.option.preset", default="Prez preset."),
)
@click.option(
    "--list-templates",
    is_flag=True,
    help=tr("cli.prez.option.list_templates", default="List available prez templates and presets."),
)
@click.option(
    "--select-templates/--no-select-templates",
    default=None,
    help=tr(
        "cli.prez.option.select_templates",
        default="Open or bypass the interactive Prez template selector.",
    ),
)
def prez_command(
    path_parts: tuple[str, ...],
    output_dir: str | None,
    output_format: str | None,
    with_metadata: bool | None,
    locale: str | None,
    dry_run: bool,
    preview: bool = False,
    with_mediainfo: bool = False,
    mediainfo_mode: str | None = None,
    html_template: str | None = None,
    bbcode_template: str | None = None,
    preset: str | None = None,
    list_templates: bool = False,
    select_templates: bool | None = None,
) -> int:
    """Handle prez command."""
    return run_prez_command(
        path=join_path_parts(path_parts) or None,
        output_dir=output_dir,
        output_format=output_format,
        with_metadata=with_metadata,
        locale=locale,
        dry_run=dry_run,
        preview=preview,
        with_mediainfo=with_mediainfo,
        mediainfo_mode=mediainfo_mode,
        html_template=html_template,
        bbcode_template=bbcode_template,
        preset=preset,
        list_templates=list_templates,
        select_templates=select_templates,
    )
