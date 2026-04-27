from __future__ import annotations

# Prefer rich_click if available; fall back to click when the rich integration is not installed.
try:
    import rich_click as click  # type: ignore[import-not-found]
except Exception:
    import click  # type: ignore[import-not-found]
from rich import box
from rich.table import Table

from framekit.core.i18n import get_supported_locales, set_locale, tr
from framekit.core.settings import SettingsStore, normalize_ui_locale
from framekit.ui.branding import print_module_banner
from framekit.ui.console import console, print_error, print_success


def _locale_label(locale_code: str) -> str:
    return tr(f"language.name.{locale_code}", default=locale_code)


def run_language_show() -> int:
    store = SettingsStore()
    settings = store.load()
    current = normalize_ui_locale(settings.get("general", {}).get("locale", ""))

    print_module_banner("Language")
    table = Table(
        title=tr("language.current_title", default="Interface Language"),
        expand=True,
        box=box.HEAVY,
        border_style="white",
    )
    table.add_column(tr("common.field", default="Field"), width=22, no_wrap=True)
    table.add_column(tr("common.value", default="Value"), ratio=1)
    table.add_row(
        tr("language.current", default="Current language"), f"{_locale_label(current)} ({current})"
    )
    table.add_row(
        tr("language.available", default="Available languages"),
        ", ".join(f"{_locale_label(code)} ({code})" for code in get_supported_locales()),
    )
    console.print(table)
    return 0


def run_language_set(locale_code: str) -> int:
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


@click.group(
    "language",
    invoke_without_command=True,
    help=tr("cli.language.help", default="Show or change the Framekit interface language."),
)
@click.pass_context
def language_command(ctx: click.Context) -> int | None:
    if ctx.invoked_subcommand is None:
        return run_language_show()
    return None


@language_command.command(
    "set", help=tr("cli.language.set.help", default="Set the Framekit interface language.")
)
@click.argument("locale", type=click.Choice(list(get_supported_locales())))
def language_set_command(locale: str) -> int:
    return run_language_set(locale)
