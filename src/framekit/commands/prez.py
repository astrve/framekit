from __future__ import annotations

import sys
from pathlib import Path

# Prefer rich_click if available; fall back to click when the rich integration is not installed.
try:
    import rich_click as click  # type: ignore[import-not-found]
except Exception:
    import click  # type: ignore[import-not-found]

from framekit.core.diagnostics import log_exception
from framekit.core.i18n import tr
from framekit.core.paths import PathResolver
from framekit.core.settings import (
    SettingsStore,
    metadata_language_for_nfo_locale,
    resolve_nfo_locale,
)
from framekit.modules.metadata.workflow import run_metadata_workflow
from framekit.modules.nfo.builder import build_release_nfo
from framekit.modules.nfo.scanner import scan_nfo_folder
from framekit.modules.prez.service import (
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
from framekit.ui.branding import print_module_banner
from framekit.ui.console import (
    print_error,
    print_exception_error,
    print_info,
    print_success,
    print_warning,
)
from framekit.ui.selector import SelectorDivider, SelectorOption, select_one


def _join_path_parts(parts: tuple[str, ...]) -> str:
    return " ".join(part for part in parts if part).strip()


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
    preset_name = (
        (preset or str(prez_settings.get("preset", "default") or "default")).strip().lower()
    )
    if preset_name not in PREZ_PRESETS:
        preset_name = "default"
    preset_values = PREZ_PRESETS[preset_name]

    if preset is not None:
        resolved_html = html_template or preset_values["html_template"]
        resolved_bbcode = bbcode_template or preset_values["bbcode_template"]
    else:
        resolved_html = (
            html_template
            or str(prez_settings.get("html_template", "") or "")
            or preset_values["html_template"]
        )
        resolved_bbcode = (
            bbcode_template
            or str(prez_settings.get("bbcode_template", "") or "")
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


def _select_template(
    kind: str, choices: tuple[str, ...], current: str, *, grouped: bool = True
) -> str:
    entries = []
    current_category: str | None = None
    kind_key = "html" if kind.lower() == "html" else "bbcode"
    for choice in choices:
        category = template_category(choice, kind=kind_key)
        if grouped and category != current_category:
            entries.append(SelectorDivider(category))
            current_category = category
        hint = (
            describe_html_template(choice)
            if kind_key == "html"
            else describe_bbcode_template(choice)
        )
        entries.append(
            SelectorOption(
                value=choice,
                label=choice,
                hint=hint,
                selected=False,
            )
        )
    try:
        selected = select_one(
            title=tr("prez.selector.title", default="Prez {kind} Template Selector", kind=kind),
            entries=entries,
            page_size=8,
        )
    except KeyboardInterrupt:
        return current
    return str(selected) if selected in choices else current


def _maybe_select_templates(
    *,
    formats: tuple[str, ...],
    html_template: str,
    bbcode_template: str,
    explicit_html: bool,
    explicit_bbcode: bool,
    explicit_preset: bool,
    select_templates: bool | None,
) -> tuple[str, str]:
    if select_templates is None:
        should_select = (
            sys.stdin.isatty()
            and not explicit_preset
            and not explicit_html
            and not explicit_bbcode
            and any(fmt in {"html", "bbcode"} for fmt in formats)
        )
    else:
        should_select = select_templates

    if not should_select:
        return html_template, bbcode_template

    if "bbcode" in formats and not explicit_bbcode:
        bbcode_template = _select_template(
            "BBCode", available_bbcode_templates(), bbcode_template, grouped=False
        )
    if "html" in formats and not explicit_html:
        html_template = _select_template(
            "HTML", available_html_templates(), html_template, grouped=True
        )
    return html_template, bbcode_template


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

    preset_values = PREZ_PRESETS[preset_name]
    if mediainfo_mode:
        configured_mediainfo_mode = mediainfo_mode.strip().lower()
    elif with_mediainfo:
        configured_mediainfo_mode = "spoiler"
    elif preset is not None:
        configured_mediainfo_mode = preset_values.get("mediainfo_mode", "none").strip().lower()
    else:
        configured_mediainfo_mode = (
            str(
                prez_settings.get("mediainfo_mode", "")
                or ("spoiler" if prez_settings.get("include_mediainfo") else "")
                or preset_values.get("mediainfo_mode", "none")
            )
            .strip()
            .lower()
        )
    if configured_mediainfo_mode not in MEDIAINFO_MODES:
        configured_mediainfo_mode = "none"

    formats = _formats_from_option(configured_format)
    resolved_html_template, resolved_bbcode_template = _maybe_select_templates(
        formats=formats,
        html_template=resolved_html_template,
        bbcode_template=resolved_bbcode_template,
        explicit_html=html_template is not None,
        explicit_bbcode=bbcode_template is not None,
        explicit_preset=preset is not None,
        select_templates=select_templates,
    )

    metadata_default = bool(
        settings.get("modules", {})
        .get("prez", {})
        .get("with_metadata", settings.get("metadata", {}).get("enabled_by_default", True))
    )
    use_metadata = metadata_default if with_metadata is None else with_metadata

    metadata_context = None
    if use_metadata:
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
            if result.status == "resolved":
                metadata_context = result.context
            else:
                print_warning(
                    result.message
                    or tr(
                        "prez.warning.metadata_unavailable",
                        default="Metadata unavailable. Continuing without metadata.",
                    )
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

    try:
        _report, result = PrezService().build(
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
            ),
            write=not (dry_run or preview),
        )
    except Exception as exc:
        print_exception_error(exc)
        return 1

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
    for output in result.outputs:
        print_info(tr("common.output", default="Output") + f": {output}")

    if dry_run or preview:
        print_success(tr("prez.success.dry_run", default="Presentation dry-run completed."))
    else:
        print_success(tr("prez.success.written", default="Presentation generated."))

    prez_settings["last_folder"] = str(folder)
    store.save(settings)
    return 0


@click.command("prez", help=tr("cli.prez.help", default="Generate HTML/BBCode presentation files."))
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
    "--locale",
    type=click.Choice(["auto", "en", "fr", "es"]),
    help=tr("cli.prez.option.locale", default="Presentation language."),
)
@click.option(
    "--dry-run",
    is_flag=True,
    help=tr("cli.prez.option.dry_run", default="Preview output paths without writing."),
)
@click.option(
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
        list(available_html_templates()) + ["default", "premium", "tracker", "poster-focus"]
    ),
    help=tr("cli.prez.option.html_template", default="HTML template style."),
)
@click.option(
    "--bbcode-template",
    type=click.Choice(list(available_bbcode_templates()) + ["default", "premium"]),
    help=tr("cli.prez.option.bbcode_template", default="BBCode organization."),
)
@click.option(
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
    return run_prez_command(
        path=_join_path_parts(path_parts) or None,
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
