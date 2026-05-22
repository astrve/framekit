from __future__ import annotations

from rich import box
from rich.table import Table

from framekit.core.i18n import get_supported_locales, set_locale, tr
from framekit.core.settings import SettingsStore, normalize_ui_locale
from framekit.ui.branding import print_module_banner

# Prefer rich_click if available; fall back to click when the rich integration is not installed.
from framekit.ui.click_helper import click
from framekit.ui.console import console, print_error, print_success

# Allowed values for per-module locale (nfo/prez): "auto" follows general.locale.
_MODULE_LOCALE_CHOICES = ("auto", *sorted(get_supported_locales()))


def _locale_label(locale_code: str) -> str:
    return tr(f"language.name.{locale_code}", default=locale_code)


def _display_module_locale(value: str) -> str:
    """Format a per-module locale value for display."""
    if value == "auto":
        return tr("language.auto", default="auto (follows UI locale)")
    return f"{_locale_label(value)} ({value})"


def run_language_show() -> int:
    """Run language show."""
    store = SettingsStore()
    settings = store.load()
    current = normalize_ui_locale(settings.get("general", {}).get("locale", ""))
    nfo_locale = settings.get("modules", {}).get("nfo", {}).get("locale", "auto")
    prez_locale = settings.get("modules", {}).get("prez", {}).get("locale", "auto")
    metadata_lang = settings.get("metadata", {}).get("language", "en-US")

    print_module_banner("Language")
    table = Table(
        title=tr("language.current_title", default="Language Settings"),
        expand=True,
        box=box.HEAVY,
        border_style="white",
    )
    table.add_column(tr("common.field", default="Field"), width=22, no_wrap=True)
    table.add_column(tr("common.value", default="Value"), ratio=1)
    table.add_row(
        tr("language.current", default="UI language"), f"{_locale_label(current)} ({current})"
    )
    table.add_row(
        tr("language.nfo_locale", default="NFO locale"), _display_module_locale(nfo_locale)
    )
    table.add_row(
        tr("language.prez_locale", default="Prez locale"), _display_module_locale(prez_locale)
    )
    table.add_row(tr("language.metadata_lang", default="Metadata language"), metadata_lang)
    table.add_row(
        tr("language.available", default="Available languages"),
        ", ".join(f"{_locale_label(code)} ({code})" for code in get_supported_locales()),
    )
    console.print(table)
    return 0


def run_language_set(locale_code: str) -> int:
    """Run language set."""
    supported = set(get_supported_locales())
    requested = (locale_code or "").strip().replace("_", "-").lower().split("-", 1)[0]
    if requested not in supported:
        print_error(
            tr(
                "language.error.unsupported",
                default="Unsupported interface language: {locale}. Supported values: {supported}",
                locale=locale_code,
                supported=", ".join(get_supported_locales()),
            )
        )
        return 1

    normalized = normalize_ui_locale(requested)

    store = SettingsStore()
    settings = store.load()
    settings.setdefault("general", {})["locale"] = normalized
    store.save(settings)
    set_locale(normalized)

    print_success(
        tr(
            "language.success.set",
            default="Interface language set to {language} ({locale}).",
            language=_locale_label(normalized),
            locale=normalized,
        )
    )
    return 0


def run_language_module_set(module: str, config_key: str, value: str) -> int:
    """Set a per-module locale value (nfo or prez)."""
    if value not in _MODULE_LOCALE_CHOICES:
        print_error(
            tr(
                "language.error.unsupported_module",
                default="Unsupported locale for {module}: {value}. Allowed: {choices}",
                module=module,
                value=value,
                choices=", ".join(_MODULE_LOCALE_CHOICES),
            )
        )
        return 1

    store = SettingsStore()
    store.set(config_key, value)
    print_success(
        tr(
            "language.success.module_set",
            default="{module} locale set to {value}.",
            module=module,
            value=_display_module_locale(value),
        )
    )
    return 0


def run_language_metadata_set(value: str) -> int:
    """Set the metadata (TMDb) language."""
    store = SettingsStore()
    store.set("metadata.language", value)
    print_success(
        tr(
            "language.success.metadata_set",
            default="Metadata language set to {value}.",
            value=value,
        )
    )
    return 0


@click.group(
    "language",
    invoke_without_command=True,
    help=tr("cli.language.help", default="Show or change the Framekit interface language."),
)
@click.pass_context
def language_command(ctx: click.Context) -> int | None:
    """Handle language command."""
    if ctx.invoked_subcommand is None:
        return run_language_show()
    return None


@language_command.command(
    "set", help=tr("cli.language.set.help", default="Set the Framekit interface language.")
)
@click.argument("locale", type=click.Choice(list(get_supported_locales())))
def language_set_command(locale: str) -> int:
    """Handle language set command."""
    return run_language_set(locale)


@language_command.command(
    "show", help=tr("cli.language.show.help", default="Show all language settings.")
)
def language_show_command() -> int:
    """Explicit show subcommand."""
    return run_language_show()


@language_command.command(
    "nfo",
    help=tr(
        "cli.language.nfo.help",
        default="Set the NFO generation locale (auto | en | fr | es).",
    ),
)
@click.argument("locale", type=click.Choice(list(_MODULE_LOCALE_CHOICES)))
def language_nfo_command(locale: str) -> int:
    """Set NFO module locale."""
    return run_language_module_set("NFO", "modules.nfo.locale", locale)


@language_command.command(
    "prez",
    help=tr(
        "cli.language.prez.help",
        default="Set the Prez generation locale (auto | en | fr | es).",
    ),
)
@click.argument("locale", type=click.Choice(list(_MODULE_LOCALE_CHOICES)))
def language_prez_command(locale: str) -> int:
    """Set Prez module locale."""
    return run_language_module_set("Prez", "modules.prez.locale", locale)


@language_command.command(
    "metadata",
    help=tr(
        "cli.language.metadata.help",
        default="Set the metadata/TMDb language (BCP-47, e.g. en-US, fr-FR).",
    ),
)
@click.argument("language")
def language_metadata_command(language: str) -> int:
    """Set metadata language (BCP-47 tag for TMDb queries)."""
    return run_language_metadata_set(language)
