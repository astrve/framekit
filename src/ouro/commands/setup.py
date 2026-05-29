from __future__ import annotations

import os
import re
import sys
from copy import deepcopy
from pathlib import Path

from rich import box
from rich.panel import Panel
from rich.table import Table

from ouro.core.i18n import set_locale, tr
from ouro.core.paths import (
    ENV_CONFIG_PATH,
    SETTINGS_FILENAME,
    clear_configured_global_settings_path,
    coerce_settings_file_path,
    get_config_dir,
    set_configured_global_settings_path,
)
from ouro.core.settings import DEFAULT_SETTINGS, SettingsStore, normalize_ui_locale
from ouro.modules.metadata.config import (
    looks_like_tmdb_read_access_token,
    normalize_secret_input,
)
from ouro.modules.nfo.logo_registry import NfoLogoRegistry
from ouro.modules.nfo.logo_tools import import_logo_file
from ouro.modules.nfo.selector import choose_yes_no
from ouro.modules.nfo.template_selector import build_template_options, choose_template
from ouro.modules.prez.service import (
    available_bbcode_templates,
    available_html_templates,
    describe_bbcode_template,
    describe_html_template,
)
from ouro.modules.setup.selector import ChoiceOption, choose_option
from ouro.modules.torrent.service import is_valid_announce_url
from ouro.ui.branding import print_module_banner

# Prefer rich_click if available; fall back to click when the rich integration is not installed.
from ouro.ui.click_helper import click
from ouro.ui.console import (
    console,
    print_error,
    print_exception_error,
    print_info,
    print_success,
    print_warning,
)


def _ui_language_options() -> list[ChoiceOption]:
    return [
        ChoiceOption(
            "fr",
            tr("language.name.fr", default="Français"),
            tr("setup.language.fr_hint", default="Interface in French"),
        ),
        ChoiceOption(
            "en",
            tr("language.name.en", default="English"),
            tr("setup.language.en_hint", default="Interface in English"),
        ),
        ChoiceOption(
            "es",
            tr("language.name.es", default="Español"),
            tr("setup.language.es_hint", default="Interface in Spanish"),
        ),
    ]


def _metadata_language_options() -> list[ChoiceOption]:
    return [
        ChoiceOption(
            "en-US",
            "English (US)",
            tr("setup.metadata_language.en_us", default="Recommended default"),
        ),
        ChoiceOption(
            "en-GB", "English (GB)", tr("setup.metadata_language.en_gb", default="British English")
        ),
        ChoiceOption(
            "fr-FR",
            "Français (France)",
            tr("setup.metadata_language.fr_fr", default="French metadata"),
        ),
        ChoiceOption(
            "fr-CA",
            "Français (Canada)",
            tr("setup.metadata_language.fr_ca", default="Canadian French metadata"),
        ),
        ChoiceOption(
            "es-ES",
            "Español (España)",
            tr("setup.metadata_language.es_es", default="Spanish metadata"),
        ),
        ChoiceOption(
            "es-419",
            "Español (Latinoamérica)",
            tr("setup.metadata_language.es_419", default="Latin American Spanish"),
        ),
        ChoiceOption(
            "it-IT", "Italiano", tr("setup.metadata_language.it_it", default="Italian metadata")
        ),
        ChoiceOption(
            "de-DE", "Deutsch", tr("setup.metadata_language.de_de", default="German metadata")
        ),
        ChoiceOption(
            "custom",
            tr("common.custom", default="Custom"),
            tr("setup.metadata_language.custom", default="Enter another locale manually"),
        ),
    ]


class SetupCancelled(Exception):
    """Setup cancelled."""


# Global variable to track if timeline has been displayed
_timeline_displayed = False


def _show_step_timeline(current_step: str, all_steps: list[str]) -> None:
    """Display a visual timeline of setup steps that updates in place."""
    from rich.text import Text

    global _timeline_displayed

    timeline = Text()
    for i, step in enumerate(all_steps):
        if i > 0:
            timeline.append(" → ", style="dim white")

        if step == current_step:
            # Current step: bold and bright
            timeline.append(step, style="bold cyan")
        elif all_steps.index(step) < all_steps.index(current_step):
            # Completed steps: green with checkmark
            timeline.append(f"✓ {step}", style="green")
        else:
            # Upcoming steps: dim
            timeline.append(step, style="dim white")

    if _timeline_displayed:
        # Move cursor up 3 lines (empty + timeline + empty) and erase to end of screen
        console.file.write("\033[3A\033[J")
        console.file.flush()

    console.print()
    console.print(timeline)
    console.print()

    if not _timeline_displayed:
        _timeline_displayed = True


def _show_step(
    title: str, text: str, current_step: str | None = None, all_steps: list[str] | None = None
) -> None:
    """Display a step panel with optional timeline."""
    if current_step and all_steps:
        _show_step_timeline(current_step, all_steps)

    console.print(
        Panel(
            text,
            title=title,
            border_style="white",
            box=box.HEAVY,
            expand=True,
        )
    )


def _deep_merge_defaults(current: dict, defaults: dict) -> dict:
    result = deepcopy(defaults)

    for key, value in current.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge_defaults(value, result[key])
        else:
            result[key] = value

    return result


def _ensure_setup_shape(settings: dict) -> dict:
    settings.setdefault("general", {})
    settings["general"].setdefault("locale", DEFAULT_SETTINGS["general"]["locale"])

    settings.setdefault("metadata", {})
    settings["metadata"].setdefault("provider", "tmdb")
    settings["metadata"].setdefault("interactive_confirmation", True)
    settings["metadata"].setdefault("cache_ttl_hours", 168)
    settings["metadata"].setdefault("language", "en-US")
    settings["metadata"].setdefault("tmdb_read_access_token", "")
    settings["metadata"].setdefault("enabled_by_default", True)
    settings["metadata"].setdefault("prompt_missing_token_in_pipeline", True)

    settings.setdefault("setup", {})
    settings["setup"].setdefault("completed", False)
    settings["setup"].setdefault("prompt_on_start", True)

    settings.setdefault("modules", {})
    settings["modules"].setdefault("renamer", {})
    settings["modules"]["renamer"].setdefault("default_folder", "")

    settings["modules"].setdefault("cleanmkv", {})
    settings["modules"]["cleanmkv"].setdefault("default_folder", "")

    settings["modules"].setdefault("nfo", {})
    settings["modules"]["nfo"].setdefault("default_folder", "")
    settings["modules"]["nfo"].setdefault("active_template", "default")
    settings["modules"]["nfo"].setdefault("logo_path", "")
    settings["modules"]["nfo"].setdefault("active_logo", "")
    settings["modules"]["nfo"].setdefault("with_metadata", True)

    settings["modules"].setdefault("prez", {})
    settings["modules"]["prez"].setdefault("preset", "default")
    settings["modules"]["prez"].setdefault("html_template", "aurora")
    settings["modules"]["prez"].setdefault("bbcode_template", "classic")
    settings["modules"]["prez"].setdefault("with_metadata", True)

    settings["modules"].setdefault("torrent", {})
    settings["modules"]["torrent"].setdefault("announce", "")
    settings["modules"]["torrent"].setdefault("announce_urls", [])
    settings["modules"]["torrent"].setdefault("selected_announce", "")
    settings["modules"]["torrent"].setdefault("prompt_save_announce", True)

    return settings


def _load_settings_with_defaults(store: SettingsStore) -> dict:
    current = store.load()
    merged = _deep_merge_defaults(current, DEFAULT_SETTINGS)
    return _ensure_setup_shape(merged)


def _strip_wrapping_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and (
        (value.startswith('"') and value.endswith('"'))
        or (value.startswith("'") and value.endswith("'"))
    ):
        return value[1:-1].strip()
    return value


def _workspace_paths(project_root: Path, folder_name: str) -> tuple[Path, Path]:
    appdata_path = get_config_dir() / "Workspace" / folder_name
    project_path = project_root / "Workspace" / folder_name
    return appdata_path, project_path


def _show_resolved_path(label: str, path_value: str) -> None:
    console.print(
        Panel(
            path_value or "-",
            title=tr("setup.resolved_path_title", default="{label} resolved path", label=label),
            border_style="white",
            box=box.HEAVY,
            expand=True,
        )
    )


def _prompt_custom_path(label: str, current: str = "") -> str | None:
    _show_step(
        tr("setup.custom_path_title", default="{label} custom path", label=label),
        tr(
            "setup.custom_path_body",
            default=(
                "Enter a full folder path.\n\n"
                "Quotes are optional.\n"
                "Examples:\n"
                r"- E:\Releases\NFO"
                "\n"
                r'- "E:\My Folder\NFO"'
                "\n\n"
                "Type 'back' to return to the previous step.\n"
                "Type 'quit' to leave setup."
            ),
        ),
    )

    while True:
        suffix = f" [{current}]" if current else ""
        raw = console.input(
            f"[white]{tr('setup.prompt.custom_path', default='{label} custom path{suffix}: ', label=label, suffix=suffix)}[/white]"
        ).strip()

        if raw.lower() == "quit":
            raise SetupCancelled
        if raw.lower() == "back":
            return None

        cleaned = _strip_wrapping_quotes(raw)
        if not cleaned:
            print_error(
                tr(
                    "setup.error.path_empty",
                    default="Path cannot be empty. Type 'back' to return or 'quit' to leave setup.",
                )
            )
            continue

        return cleaned


def _preferred_workspace_choice(current_value: str, appdata_path: Path, project_path: Path) -> str:
    if current_value:
        current_normalized = str(Path(current_value))
        if current_normalized == str(appdata_path):
            return "appdata"
        if current_normalized == str(project_path):
            return "project"
        return "custom"
    return "project"


def _choose_workspace_path(
    label: str, current_value: str, appdata_path: Path, project_path: Path
) -> str | None:
    _show_step(
        tr("setup.default_folder_title", default="{label} default folder", label=label),
        tr(
            "setup.default_folder_body",
            default=(
                "Choose where Ouro should start when no path is passed to the command.\n\n"
                "AppData Workspace: managed by Ouro in your user profile.\n"
                "Ouro Project Workspace: inside your current Ouro project.\n"
                "Custom Path: anywhere you want."
            ),
        ),
    )

    while True:
        preferred = _preferred_workspace_choice(current_value, appdata_path, project_path)

        options = [
            ChoiceOption(
                "appdata",
                tr("setup.workspace.appdata", default="AppData Workspace"),
                str(appdata_path),
            ),
            ChoiceOption(
                "project",
                tr("setup.workspace.project", default="Ouro Project Workspace"),
                str(project_path),
            ),
            ChoiceOption(
                "custom",
                tr("setup.workspace.custom", default="Custom Path"),
                current_value
                or tr("setup.workspace.custom_hint", default="Choose any folder you want"),
            ),
        ]

        selected = choose_option(
            title=tr("setup.default_folder_title", default="{label} default folder", label=label),
            options=options,
            preferred_value=preferred,
        )
        if selected is None:
            raise SetupCancelled

        if selected == "appdata":
            resolved = str(appdata_path)
        elif selected == "project":
            resolved = str(project_path)
        else:
            resolved = _prompt_custom_path(label, current=current_value)
            if resolved is None:
                continue

        _show_resolved_path(label, resolved)
        return resolved


def _choose_interface_language(current: str) -> str:
    _show_step(
        tr("setup.interface_language_title", default="Interface language"),
        tr(
            "setup.interface_language_body",
            default=(
                "This controls the language used by Ouro CLI messages.\n\n"
                "Metadata language is configured separately later."
            ),
        ),
    )

    selected = choose_option(
        title=tr("setup.choose_interface_language", default="Choose interface language"),
        options=_ui_language_options(),
        preferred_value=normalize_ui_locale(current),
    )
    if selected is None:
        raise SetupCancelled

    set_locale(selected)
    print_success(
        tr(
            "language.success.set",
            default="Interface language set to {language} ({locale}).",
            language=tr(f"language.name.{selected}", default=selected),
            locale=selected,
        )
    )
    return selected


def _is_valid_locale(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})?", value))


def _prompt_custom_language(current: str) -> str | None:
    _show_step(
        tr("setup.custom_metadata_language_title", default="Custom metadata language"),
        tr(
            "setup.custom_metadata_language_body",
            default=(
                "Enter a locale code for metadata.\n\n"
                "Examples:\n"
                "- en-US\n"
                "- fr-FR\n"
                "- es-419\n"
                "- de-DE\n\n"
                "Type 'back' to return to the previous step.\n"
                "Type 'quit' to leave setup."
            ),
        ),
    )

    while True:
        suffix = f" [{current}]" if current else ""
        raw = console.input(
            f"[white]{tr('setup.prompt.custom_metadata_language', default='Custom metadata language{suffix}: ', suffix=suffix)}[/white]"
        ).strip()

        if raw.lower() == "quit":
            raise SetupCancelled
        if raw.lower() == "back":
            return None

        if not raw:
            print_error(
                tr(
                    "setup.error.language_empty",
                    default="Language cannot be empty. Type 'back' to return or 'quit' to leave setup.",
                )
            )
            continue

        if not _is_valid_locale(raw):
            print_error(
                tr(
                    "setup.error.invalid_locale",
                    default="That does not look like a valid locale code.",
                )
            )
            continue

        return raw


def _choose_metadata_language(current: str) -> str:
    _show_step(
        tr("setup.metadata_language_title", default="Metadata language"),
        tr(
            "setup.metadata_language_body",
            default=(
                "This controls the language used when Ouro requests metadata online.\n\n"
                "Recommended: English (US) for the most consistent results."
            ),
        ),
    )

    while True:
        selected = choose_option(
            title=tr("setup.choose_metadata_language", default="Choose metadata language"),
            options=_metadata_language_options(),
            preferred_value=current or "en-US",
        )
        if selected is None:
            raise SetupCancelled

        if selected != "custom":
            print_success(
                tr(
                    "setup.success.metadata_language_set",
                    default="Metadata language set to: {locale}",
                    locale=selected,
                )
            )
            return selected

        custom = _prompt_custom_language(current)
        if custom is None:
            continue

        print_success(
            tr(
                "setup.success.metadata_language_set",
                default="Metadata language set to: {locale}",
                locale=custom,
            )
        )
        return custom


def _prompt_tmdb_token(current_token: str) -> str | None:
    _show_step(
        tr("setup.tmdb_token_title", default="TMDb read access token"),
        tr(
            "setup.tmdb_token_body",
            default=(
                "Ouro uses this token to search movie and episode metadata.\n\n"
                "Paste your TMDb Read Access Token here.\n"
                "Do not paste the TMDb API key.\n\n"
                "Type 'skip' to continue without changing this value.\n"
                "Type 'back' to return to the previous step.\n"
                "Type 'clear' to remove an existing token.\n"
                "Type 'quit' to leave setup."
            ),
        ),
    )

    while True:
        raw = console.input(
            f"[white]{tr('setup.prompt.tmdb_token', default='TMDb Read Access Token: ')}[/white]"
        ).strip()

        if raw.lower() == "quit":
            raise SetupCancelled
        if raw.lower() == "back":
            return None
        if raw.lower() == "skip":
            if current_token:
                print_info(tr("setup.info.keep_tmdb_token", default="Keeping current TMDb token."))
                return current_token
            print_warning(
                tr("setup.warning.no_tmdb_token", default="Continuing without a TMDb token.")
            )
            return ""
        if raw.lower() == "clear":
            print_warning(tr("metadata.success.token_cleared", default="TMDb token cleared."))
            return ""

        if not raw:
            print_error(
                tr(
                    "setup.error.token_empty",
                    default="Token cannot be empty. Type 'skip', 'back', 'clear' or 'quit'.",
                )
            )
            continue

        token = normalize_secret_input(raw)

        if not looks_like_tmdb_read_access_token(token):
            print_error(
                tr(
                    "metadata.error.invalid_token",
                    default="That does not look like a valid TMDb read access token.",
                )
            )
            continue

        print_success(
            tr("setup.success.tmdb_token_valid", default="TMDb read access token looks valid.")
        )
        return token


def _choose_builtin_template(current_template: str) -> str:
    _show_step(
        tr("setup.preferred_template_title", default="Preferred NFO template"),
        tr(
            "setup.preferred_template_body",
            default=(
                "Choose from built-in and custom templates.\n\n"
                "Built-in templates: default (lighter) and detailed (richer).\n"
                "Custom templates: imported by users for specific needs."
            ),
        ),
    )

    # Load all templates (builtin + custom)
    from ouro.modules.nfo.template_registry import NfoTemplateRegistry

    registry = NfoTemplateRegistry()
    records = registry.list_all()

    options = build_template_options(records)
    chosen = choose_template(options, preferred_name=current_template or "default")
    if chosen is None:
        raise SetupCancelled
    print_success(
        tr(
            "setup.success.preferred_template_set",
            default="Preferred template set to: {name}",
            name=chosen.display_name,
        )
    )
    return chosen.template_name


def _prompt_logo_import() -> tuple[str, str] | None:
    _show_step(
        tr("setup.import_logo_title", default="Import NFO logo"),
        tr(
            "setup.import_logo_body",
            default=(
                "You can import a text-based logo for templates that support it.\n\n"
                "Accepted files: .txt, .nfo, .asc\n"
                "Type 'back' to return to the previous step.\n"
                "Type 'quit' to leave setup."
            ),
        ),
    )

    while True:
        raw_path = console.input(
            f"[white]{tr('setup.prompt.logo_path', default='Logo file path: ')}[/white]"
        ).strip()

        if raw_path.lower() == "quit":
            raise SetupCancelled
        if raw_path.lower() == "back":
            return None

        cleaned_path = _strip_wrapping_quotes(raw_path)
        if not cleaned_path:
            print_error(tr("setup.error.logo_path_empty", default="Logo path cannot be empty."))
            continue

        logo_name = (
            console.input(
                f"[white]{tr('setup.prompt.logo_display_name', default='Logo display name [optional]: ')}[/white]"
            ).strip()
            or None
        )

        try:
            record = import_logo_file(cleaned_path, logo_name=logo_name)
        except Exception as exc:
            print_exception_error(exc)
            continue

        print_success(
            tr("nfo.logo_imported", default="Logo imported: {name}", name=record.display_name)
        )
        return record.logo_name, record.file_path


def _choose_logo(current_logo_name: str) -> tuple[str, str]:
    registry = NfoLogoRegistry()

    _show_step(
        tr("setup.nfo_logo_title", default="NFO logo"),
        tr(
            "setup.nfo_logo_body",
            default=(
                "The logo is optional.\n\n"
                "It is printed at the top of templates that support logo rendering."
            ),
        ),
    )

    ask_import = choose_yes_no(
        tr("setup.confirm.import_logo_now", default="Do you want to import a logo now?"),
        default_yes=False,
    )
    if ask_import is None:
        raise SetupCancelled
    if ask_import:
        imported = _prompt_logo_import()
        if imported is not None:
            return imported

    logos = registry.load_all()
    if not logos:
        print_info(
            tr("setup.info.no_logos", default="No logos available. Continuing without logo.")
        )
        return "", ""

    options = [
        ChoiceOption(
            "__none__",
            tr("setup.logo.no_logo", default="No logo"),
            tr("setup.logo.no_logo_hint", default="Disable logo rendering"),
        )
    ]
    options.extend(
        ChoiceOption(
            value=logo.logo_name,
            label=logo.display_name,
            description=logo.logo_name,
        )
        for logo in logos
    )

    selected = choose_option(
        title=tr("setup.choose_active_logo", default="Choose active NFO logo"),
        options=options,
        preferred_value=current_logo_name or "__none__",
    )
    if selected is None:
        raise SetupCancelled

    if selected == "__none__":
        print_info(tr("setup.info.no_active_logo", default="No active logo selected."))
        return "", ""

    record = registry.find(selected)
    if record is None:
        print_warning(
            tr(
                "setup.warning.logo_not_resolved",
                default="Could not resolve selected logo. Continuing without logo.",
            )
        )
        return "", ""

    print_success(
        tr("nfo.active_logo_set", default="Active logo set to: {name}", name=record.display_name)
    )
    return record.logo_name, record.file_path


def _choose_prez_option(title: str, values: tuple[str, ...], current: str, *, html: bool) -> str:
    options = [
        ChoiceOption(
            value,
            value,
            describe_html_template(value) if html else describe_bbcode_template(value),
        )
        for value in values
    ]
    selected = choose_option(title=title, options=options, preferred_value=current)
    if selected is None:
        raise SetupCancelled
    return selected


def _configure_prez_defaults(settings: dict) -> None:
    prez = settings["modules"].setdefault("prez", {})
    prez["bbcode_template"] = _choose_prez_option(
        tr("setup.prez.choose_bbcode", default="Choose default BBCode Prez template"),
        available_bbcode_templates(),
        str(prez.get("bbcode_template") or "classic"),
        html=False,
    )
    prez["html_template"] = _choose_prez_option(
        tr("setup.prez.choose_html", default="Choose default HTML Prez template"),
        available_html_templates(),
        str(prez.get("html_template") or "aurora"),
        html=True,
    )


def _prompt_torrent_announce(current: str) -> str | None:
    while True:
        suffix = f" [{current}]" if current else ""
        raw = console.input(
            f"[white]{tr('setup.prompt.announce', default='Default announce URL{suffix}: ', suffix=suffix)}[/white]"
        ).strip()
        if raw.lower() == "quit":
            raise SetupCancelled
        if raw.lower() == "back":
            return None
        if not raw and current:
            return current
        if not is_valid_announce_url(raw):
            print_error(
                tr(
                    "torrent.error.invalid_announce",
                    default="Tracker announce must be a valid http(s) or udp URL.",
                )
            )
            continue
        return raw


def _configure_torrent_defaults(settings: dict, store: SettingsStore) -> None:
    torrent = settings["modules"].setdefault("torrent", {})
    current = str(torrent.get("selected_announce") or torrent.get("announce") or "")
    announce = _prompt_torrent_announce(current)
    if announce is None:
        return

    # Use secure storage if security is enabled
    from ouro.core.settings import Settings

    settings_obj = Settings()
    if settings_obj.is_security_enabled():
        # Get existing announces and add the new one
        existing_announces = settings_obj.get_torrent_announces()
        if announce not in existing_announces:
            existing_announces.append(announce)
        settings_obj.set_torrent_announces(existing_announces)
        settings_obj.set_selected_announce(announce)
        # Reload settings to get the encrypted placeholders
        settings.clear()
        settings.update(store.load())
    else:
        urls = [str(value) for value in torrent.get("announce_urls", []) if value]
        if announce not in urls:
            urls.append(announce)
        torrent["announce_urls"] = urls
        torrent["announce"] = announce
        torrent["selected_announce"] = announce


def _summary_value(value: str | None, fallback: str = "-") -> str:
    return value if value else fallback


def _setup_summary_rows(settings: dict) -> list[tuple[str, str]]:
    general = settings["general"]
    metadata = settings["metadata"]
    modules = settings["modules"]
    nfo_module = modules["nfo"]
    prez_module = modules["prez"]
    torrent_module = modules["torrent"]
    token = settings["metadata"].get("tmdb_read_access_token", "")
    metadata_confirmation = (
        tr("common.enabled", default="Enabled")
        if metadata.get("interactive_confirmation", True)
        else tr("common.disabled", default="Disabled")
    )
    tmdb_status = (
        tr("common.configured", default="Configured")
        if token
        else tr("common.missing", default="missing")
    )
    return [
        (
            tr("setup.summary.interface_language", default="Interface Language"),
            _summary_value(general.get("locale", "")),
        ),
        (
            tr("setup.summary.renamer_folder", default="Renamer Default Folder"),
            _summary_value(modules["renamer"].get("default_folder", "")),
        ),
        (
            tr("setup.summary.cleanmkv_folder", default="CleanMKV Default Folder"),
            _summary_value(modules["cleanmkv"].get("default_folder", "")),
        ),
        (
            tr("setup.summary.nfo_folder", default="NFO Default Folder"),
            _summary_value(nfo_module.get("default_folder", "")),
        ),
        (
            tr("setup.summary.metadata_language", default="Metadata Language"),
            _summary_value(metadata.get("language", "")),
        ),
        (
            tr("setup.summary.metadata_confirmation", default="Metadata Confirmation"),
            metadata_confirmation,
        ),
        (tr("setup.summary.tmdb_token", default="TMDb Token"), tmdb_status),
        (
            tr("setup.summary.preferred_nfo_template", default="Preferred NFO Template"),
            _summary_value(nfo_module.get("active_template", "")),
        ),
        (
            tr("setup.summary.active_nfo_logo", default="Active NFO Logo"),
            _summary_value(
                nfo_module.get("active_logo", ""),
                fallback=tr("common.none", default="None"),
            ),
        ),
        (
            tr("setup.summary.prez", default="Prez Defaults"),
            f"{prez_module.get('bbcode_template', '-')} / {prez_module.get('html_template', '-')}",
        ),
        (
            tr("setup.summary.torrent", default="Torrent Announce"),
            _summary_value(torrent_module.get("selected_announce", "")),
        ),
    ]


def _print_setup_summary(settings: dict) -> None:
    table = Table(
        title=tr("setup.summary_title", default="Ouro Setup Summary"),
        expand=True,
        box=box.HEAVY,
        border_style="white",
    )
    table.add_column(tr("common.field", default="Field"), width=24, no_wrap=True)
    table.add_column(tr("common.value", default="Value"), ratio=1)
    for field, value in _setup_summary_rows(settings):
        table.add_row(field, value)

    console.print(table)


def _ensure_default_folders_exist(settings: dict) -> None:
    keys = [
        ("renamer", "Renamer"),
        ("cleanmkv", "CleanMKV"),
        ("nfo", "NFO"),
    ]

    for module_key, label in keys:
        raw_path = settings["modules"][module_key].get("default_folder", "")
        if not raw_path:
            continue

        try:
            Path(raw_path).mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            print_warning(
                tr(
                    "setup.warning.create_folder_failed",
                    default="Could not create {label} default folder: {message}",
                    label=label,
                    message=exc,
                )
            )


SETUP_STEPS = [
    "Storage",
    "Language",
    "Security",
    "Folders",
    "Metadata",
    "NFO Template",
    "Prez",
    "Torrent",
    "Logo",
    "Summary",
]


def _show_setup_welcome() -> None:
    console.print(
        Panel(
            tr(
                "setup.welcome_body",
                default=(
                    "Welcome to Ouro guided setup.\n\n"
                    "This setup will guide you through default folders, metadata, and NFO preferences.\n"
                    "Nothing is saved until the final confirmation screen."
                ),
            ),
            title=tr("setup.welcome_title", default="Ouro Setup"),
            border_style="white",
            box=box.HEAVY,
            expand=True,
        )
    )


def _ask_optional_step(prompt: str, *, default_yes: bool) -> bool:
    selection = choose_yes_no(tr(prompt), default_yes=default_yes)
    if selection is None:
        raise SetupCancelled
    return bool(selection)


def _default_global_settings_path() -> Path:
    return (get_config_dir() / SETTINGS_FILENAME).resolve()


def _choose_settings_storage_path(current_path: Path) -> Path:
    _show_step(
        tr("setup.storage_title", default="Ouro settings storage"),
        tr(
            "setup.storage_body",
            default=(
                "Choose where Ouro should save its global configuration.\n\n"
                "Recommended: the OS user config directory.\n"
                "Custom folder: useful for a dedicated disk or portable setup.\n\n"
                "Project configs still stay opt-in with 'ouro init'."
            ),
        ),
        current_step="Storage",
        all_steps=SETUP_STEPS,
    )

    default_path = _default_global_settings_path()
    while True:
        selected = choose_option(
            title=tr("setup.storage_choose_title", default="Choose settings storage"),
            options=[
                ChoiceOption(
                    "default",
                    tr("setup.storage.default", default="Recommended OS location"),
                    str(default_path),
                ),
                ChoiceOption(
                    "custom",
                    tr("setup.storage.custom", default="Custom folder"),
                    str(current_path.parent),
                ),
            ],
            preferred_value="default" if current_path.resolve() == default_path else "custom",
        )
        if selected is None:
            raise SetupCancelled
        if selected == "default":
            return default_path

        custom = _prompt_custom_path(
            tr("setup.storage.custom_label", default="Ouro config folder"),
            current=str(current_path.parent),
        )
        if custom is None:
            continue
        return coerce_settings_file_path(custom).resolve()


def _run_storage_step() -> SettingsStore:
    store = SettingsStore()
    _show_step_timeline("Storage", SETUP_STEPS)

    if not _ask_optional_step("setup.confirm.configure_storage", default_yes=False):
        return store

    if os.environ.get(ENV_CONFIG_PATH, "").strip():
        print_warning(
            tr(
                "setup.storage.env_override",
                default=(
                    "OURO_CONFIG is set. It overrides setup storage choices. "
                    "Unset it to use a custom global config folder."
                ),
            )
        )
        return store

    selected_path = _choose_settings_storage_path(store.path)
    default_path = _default_global_settings_path()
    if selected_path == default_path:
        clear_configured_global_settings_path()
    else:
        selected_path = set_configured_global_settings_path(selected_path)

    print_success(
        tr(
            "setup.storage.saved",
            default="Ouro settings path configured: {path}",
            path=str(selected_path),
        )
    )
    return SettingsStore(selected_path)


def _run_language_step(settings: dict) -> None:
    _show_step_timeline("Language", SETUP_STEPS)
    if not _ask_optional_step("setup.confirm.choose_interface_language", default_yes=False):
        return
    settings["general"]["locale"] = _choose_interface_language(
        settings["general"].get("locale", DEFAULT_SETTINGS["general"]["locale"])
    )


def _run_security_step(settings: dict) -> None:
    _show_step_timeline("Security", SETUP_STEPS)
    if not _ask_optional_step("setup.confirm.configure_security", default_yes=False):
        return

    _show_step(
        tr("setup.security_title", default="Security Configuration"),
        tr(
            "setup.security_body",
            default=(
                "Ouro can encrypt sensitive data (TMDb tokens, torrent announce URLs)\n"
                "using a secure vault stored in your system keyring.\n\n"
                "Recommended: enabled for better security.\n"
                "Note: You can change this later with 'ouro settings security toggle'."
            ),
        ),
        current_step="Security",
        all_steps=SETUP_STEPS,
    )
    current_security = settings.get("security", {}).get("enabled", True)
    enable_security = choose_yes_no(
        tr(
            "setup.confirm.enable_security",
            default="Do you want to enable encryption for sensitive data?",
        ),
        yes_label=tr("common.yes", default="Yes (Recommended)"),
        no_label=tr("common.no", default="No (Plain text)"),
        default_yes=current_security,
    )
    if enable_security is None:
        raise SetupCancelled
    security = settings.setdefault("security", {})
    security["enabled"] = bool(enable_security)
    if enable_security:
        _show_step(
            tr("setup.security_storage_title", default="Secret storage backend"),
            tr(
                "setup.security_storage_body",
                default=(
                    "Choose where encryption keys are stored.\n"
                    "Keyring uses your OS secure storage. File mode uses a local vault file."
                ),
            ),
            current_step="Security",
            all_steps=SETUP_STEPS,
        )
        current_storage = str(security.get("key_storage", "keyring") or "keyring").lower()
        storage_choice = choose_option(
            title=tr("setup.security_storage_choice", default="Choose secret storage backend"),
            options=[
                ChoiceOption(
                    "keyring",
                    tr("setup.security_storage.keyring", default="System keyring"),
                    tr(
                        "setup.security_storage.keyring_hint",
                        default="Recommended. Uses secure OS credential store.",
                    ),
                ),
                ChoiceOption(
                    "file",
                    tr("setup.security_storage.file", default="Local encrypted file"),
                    tr(
                        "setup.security_storage.file_hint",
                        default="Portable, but requires managing the vault file path.",
                    ),
                ),
            ],
            preferred_value=current_storage if current_storage in {"keyring", "file"} else "keyring",
        )
        if storage_choice is None:
            raise SetupCancelled
        security["key_storage"] = storage_choice
        if storage_choice == "file":
            default_vault = str(security.get("vault_path", "") or "").strip()
            if not default_vault:
                default_vault = str(get_config_dir() / "security.vault")
            vault_path = click.prompt("Vault file path", default=default_vault).strip()
            security["vault_path"] = vault_path
        else:
            security["vault_path"] = ""
        auto_migrate = choose_yes_no(
            tr(
                "setup.security_auto_migrate",
                default="Migrate existing plaintext secrets to encrypted storage automatically?",
            ),
            default_yes=bool(security.get("auto_migrate", True)),
        )
        if auto_migrate is None:
            raise SetupCancelled
        security["auto_migrate"] = bool(auto_migrate)
        backup_before_changes = choose_yes_no(
            tr(
                "setup.security_backup_before_changes",
                default="Create backup before changing encrypted secrets?",
            ),
            default_yes=bool(security.get("backup_before_changes", True)),
        )
        if backup_before_changes is None:
            raise SetupCancelled
        security["backup_before_changes"] = bool(backup_before_changes)
        print_success(
            tr(
                "setup.success.security_enabled",
                default="Security enabled. Sensitive data will be encrypted.",
            )
        )
    else:
        print_warning(
            tr(
                "setup.warning.security_disabled",
                default="Security disabled. Sensitive data will be stored in plain text.",
            )
        )


def _configure_folder_paths(settings: dict, project_root: Path) -> None:
    renamer_appdata, renamer_project = _workspace_paths(project_root, "Renamer")
    cleanmkv_appdata, cleanmkv_project = _workspace_paths(project_root, "CleanMKV")
    nfo_appdata, nfo_project = _workspace_paths(project_root, "NFO")

    renamer_path = _choose_workspace_path(
        "Renamer",
        settings["modules"]["renamer"].get("default_folder", ""),
        renamer_appdata,
        renamer_project,
    )
    if renamer_path is not None:
        settings["modules"]["renamer"]["default_folder"] = renamer_path

    cleanmkv_path = _choose_workspace_path(
        "CleanMKV",
        settings["modules"]["cleanmkv"].get("default_folder", ""),
        cleanmkv_appdata,
        cleanmkv_project,
    )
    if cleanmkv_path is not None:
        settings["modules"]["cleanmkv"]["default_folder"] = cleanmkv_path

    nfo_path = _choose_workspace_path(
        "NFO",
        settings["modules"]["nfo"].get("default_folder", ""),
        nfo_appdata,
        nfo_project,
    )
    if nfo_path is not None:
        settings["modules"]["nfo"]["default_folder"] = nfo_path


def _run_folders_step(settings: dict, project_root: Path) -> None:
    _show_step_timeline("Folders", SETUP_STEPS)
    if not _ask_optional_step("setup.confirm.configure_folders", default_yes=True):
        return
    _configure_folder_paths(settings, project_root)


def _handle_tmdb_token_update(settings: dict, store: SettingsStore) -> None:
    while True:
        token_choice = choose_yes_no(
            tr(
                "setup.confirm.add_update_tmdb_token",
                default="Do you want to add or update a TMDb read access token?",
            ),
            yes_label=tr("common.yes", default="Yes"),
            no_label=tr("common.no", default="No"),
            default_yes=not bool(settings["metadata"].get("tmdb_read_access_token", "")),
        )
        if token_choice is None:
            raise SetupCancelled
        if not token_choice:
            return

        token_value = _prompt_tmdb_token(settings["metadata"].get("tmdb_read_access_token", ""))
        if token_value is None:
            continue

        from ouro.core.settings import Settings

        settings_obj = Settings()
        if settings_obj.is_security_enabled():
            settings_obj.set_tmdb_token(token_value)
            settings.clear()
            settings.update(store.load())
        else:
            settings["metadata"]["tmdb_read_access_token"] = token_value
        return


def _run_metadata_step(settings: dict, store: SettingsStore) -> None:
    _show_step_timeline("Metadata", SETUP_STEPS)
    if not _ask_optional_step("setup.confirm.configure_metadata", default_yes=True):
        return

    settings["metadata"]["language"] = _choose_metadata_language(
        settings["metadata"].get("language", "en-US") or "en-US"
    )
    _show_step(
        tr("setup.metadata_confirmation_title", default="Metadata confirmation"),
        tr(
            "setup.metadata_confirmation_body",
            default=(
                "When enabled, Ouro lets you review and confirm the metadata match\n"
                "before it is used in the NFO.\n\n"
                "Recommended: enabled."
            ),
        ),
        current_step="Metadata",
        all_steps=SETUP_STEPS,
    )
    interactive_choice = choose_yes_no(
        tr(
            "setup.confirm.metadata_confirmation_enabled",
            default="Do you want metadata confirmation enabled?",
        ),
        yes_label=tr("common.yes", default="Yes"),
        no_label=tr("common.no", default="No"),
        default_yes=settings["metadata"].get("interactive_confirmation", True),
    )
    if interactive_choice is None:
        raise SetupCancelled
    settings["metadata"]["interactive_confirmation"] = bool(interactive_choice)
    _handle_tmdb_token_update(settings, store)


def _run_nfo_template_step(settings: dict) -> None:
    _show_step_timeline("NFO Template", SETUP_STEPS)
    if not _ask_optional_step("setup.confirm.choose_nfo_template", default_yes=True):
        return
    current_template = settings["modules"]["nfo"].get("active_template", "default") or "default"
    settings["modules"]["nfo"]["active_template"] = _choose_builtin_template(current_template)


def _run_prez_step(settings: dict) -> None:
    _show_step_timeline("Prez", SETUP_STEPS)
    if not _ask_optional_step("setup.confirm.configure_prez", default_yes=True):
        return
    _configure_prez_defaults(settings)


def _run_torrent_step(settings: dict, store: SettingsStore) -> None:
    _show_step_timeline("Torrent", SETUP_STEPS)
    if not _ask_optional_step("setup.confirm.configure_torrent", default_yes=True):
        return
    _configure_torrent_defaults(settings, store)


def _run_logo_step(settings: dict) -> None:
    _show_step_timeline("Logo", SETUP_STEPS)
    if not _ask_optional_step("setup.confirm.configure_nfo_logo", default_yes=False):
        return
    logo_name, logo_path = _choose_logo(settings["modules"]["nfo"].get("active_logo", ""))
    settings["modules"]["nfo"]["active_logo"] = logo_name
    settings["modules"]["nfo"]["logo_path"] = logo_path


def _save_setup(settings: dict, store: SettingsStore, mark_completed: bool) -> int:
    _show_step_timeline("Summary", SETUP_STEPS)
    _print_setup_summary(settings)

    save_choice = choose_yes_no(
        tr("setup.confirm.save", default="Do you want to save this setup?"),
        yes_label=tr("common.yes", default="Yes"),
        no_label=tr("common.no", default="No"),
        default_yes=True,
    )
    if save_choice is None:
        raise SetupCancelled
    if not save_choice:
        print_warning(
            tr("setup.warning.cancelled_not_saved", default="Setup cancelled. Nothing was saved.")
        )
        return 0

    if mark_completed:
        settings["setup"]["completed"] = True
    settings["setup"]["prompt_on_start"] = False
    _ensure_default_folders_exist(settings)
    store.save(settings)
    print_success(tr("setup.success.saved", default="Ouro setup saved."))
    return 0


def run_guided_setup(*, mark_completed: bool = True) -> int:
    """Run guided setup."""
    print_module_banner("Setup")
    _show_setup_welcome()

    try:
        store = _run_storage_step()
        settings = _load_settings_with_defaults(store)
        project_root = Path.cwd()
        _run_language_step(settings)
        _run_security_step(settings)
        _run_folders_step(settings, project_root)
        _run_metadata_step(settings, store)
        _run_nfo_template_step(settings)
        _run_prez_step(settings)
        _run_torrent_step(settings, store)
        _run_logo_step(settings)
        return _save_setup(settings, store, mark_completed)

    except SetupCancelled:
        print_warning(
            tr("setup.warning.cancelled_not_saved", default="Setup cancelled. Nothing was saved.")
        )
        return 0


def maybe_offer_first_time_setup() -> None:
    """Handle maybe offer first time setup."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return

    store = SettingsStore()
    settings = _load_settings_with_defaults(store)

    setup_state = settings.get("setup", {})
    if setup_state.get("completed", False):
        return
    if not setup_state.get("prompt_on_start", True):
        return

    if len(sys.argv) > 1 and sys.argv[1] in {
        "setup",
        "init",
        "examples",
        "ex",
        "doctor",
        "doc",
        "diag",
        "about",
        "license",
        "language",
        "lang",
        "-h",
        "--help",
        "--version",
    }:
        return

    should_run = choose_yes_no(
        tr("setup.confirm.run_now", default="Do you want to run guided setup now?"),
        yes_label=tr("common.yes", default="Yes"),
        no_label=tr("common.no", default="No"),
        default_yes=True,
    )

    if should_run is None:
        settings["setup"]["prompt_on_start"] = False
        store.save(settings)
        return

    if should_run:
        run_guided_setup(mark_completed=True)
    else:
        settings["setup"]["prompt_on_start"] = False
        store.save(settings)


@click.command(
    "setup",
    help=tr(
        "cli.setup.help",
        default=(
            "Run the Ouro setup wizard.\n\n"
            "The setup command now uses the wizard flow only, with Normal and Advanced modes.\n\n"
            "Quick examples:\n"
            "  ouro setup                                # Wizard in Normal mode\n"
            "  ouro setup --mode advanced                # Wizard in Advanced mode\n"
            "  ouro init                                 # Same as setup\n\n"
            "Related commands: settings, doctor, metadata"
        ),
    ),
)
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["normal", "advanced"], case_sensitive=False),
    default="normal",
    show_default=True,
    help=tr(
        "cli.setup.mode.help",
        default="Wizard mode: normal (essential) or advanced (full options)",
    ),
)
@click.option(
    "--wizard",
    "-w",
    is_flag=True,
    hidden=True,
    help=tr(
        "cli.setup.wizard.help",
        default="Deprecated. Setup already uses the wizard flow.",
    ),
)
@click.option(
    "--profile",
    "-p",
    type=click.Choice(["normal", "advanced", "beginner", "custom"], case_sensitive=False),
    default=None,
    hidden=True,
    help=tr(
        "cli.setup.profile.help",
        default="Deprecated profile alias for compatibility.",
    ),
)
def setup_command(mode: str, wizard: bool, profile: str | None) -> int:
    """Handle setup command."""
    _ = wizard  # kept for backward compatibility
    from ouro.modules.setup import SetupWizard, WizardCancelled

    requested = (profile or mode or "normal").strip().lower()
    if requested in {"beginner", "custom"}:
        requested = "normal"
    if requested not in {"normal", "advanced"}:
        requested = "normal"

    try:
        setup_wizard = SetupWizard(profile=requested)
        setup_wizard.run()
        return 0
    except WizardCancelled:
        console.print(
            tr("wizard.cancelled", default="Setup wizard cancelled."),
            style="yellow",
        )
        return 1
    except Exception as e:
        console.print(
            tr("wizard.error", default=f"Setup wizard error: {e}"),
            style="red",
        )
        return 1
