from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

# Prefer rich_click if available; fall back to click when the rich integration is not installed.
try:
    import rich_click as click  # type: ignore[import-not-found]
except Exception:
    import click  # type: ignore[import-not-found]
from urllib.parse import urlsplit

from rich import box
from rich.table import Table

from framekit.core.diagnostics import diagnostics_summary
from framekit.core.i18n import tr
from framekit.core.settings import (
    DEFAULT_SETTINGS,
    SettingsStore,
    resolve_nfo_locale,
    validate_settings,
)
from framekit.core.tools import ToolRegistry
from framekit.modules.metadata.config import resolve_metadata_config
from framekit.modules.metadata.factory import build_metadata_provider
from framekit.modules.nfo.template_registry import NfoTemplateRegistry
from framekit.modules.nfo.templates import list_builtin_templates
from framekit.modules.torrent.service import is_valid_announce_url
from framekit.ui.branding import print_module_banner
from framekit.ui.console import console, print_json

DoctorStatus = Literal["ok", "warn", "err"]


@dataclass(slots=True)
class DoctorCheck:
    section: str
    name: str
    status: DoctorStatus
    detail: str


def _status_label(status: DoctorStatus) -> str:
    if status == "ok":
        return tr("doctor.status.ok", default="OK")
    if status == "warn":
        return tr("doctor.status.warn", default="Warning")
    return tr("doctor.status.err", default="Error")


def _status_style(status: DoctorStatus) -> str:
    if status == "ok":
        return "#22c55e"
    if status == "warn":
        return "#f59e0b"
    return "#ef4444"


def _settings_checks(store: SettingsStore, settings: dict) -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []

    try:
        validate_settings(settings)
        checks.append(
            DoctorCheck(
                section=tr("doctor.section.settings", default="Settings"),
                name=tr("doctor.check.schema", default="schema"),
                status="ok",
                detail=tr(
                    "doctor.detail.version",
                    default="version {version}",
                    version=settings.get("schema_version"),
                ),
            )
        )
    except Exception as exc:
        checks.append(
            DoctorCheck(
                section=tr("doctor.section.settings", default="Settings"),
                name=tr("doctor.check.schema", default="schema"),
                status="err",
                detail=str(exc),
            )
        )

    checks.append(
        DoctorCheck(
            section=tr("doctor.section.settings", default="Settings"),
            name=tr("doctor.check.settings_file", default="settings file"),
            status="ok" if store.path.exists() else "warn",
            detail=str(store.path),
        )
    )

    checks.append(
        DoctorCheck(
            section=tr("doctor.section.settings", default="Settings"),
            name=tr("doctor.check.ui_locale", default="ui locale"),
            status="ok",
            detail=str(
                settings.get("general", {}).get("locale", DEFAULT_SETTINGS["general"]["locale"])
            ),
        )
    )

    return checks


def _metadata_checks(settings: dict) -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []
    config = resolve_metadata_config(settings)

    checks.append(
        DoctorCheck(
            section=tr("doctor.section.metadata", default="Metadata"),
            name=tr("doctor.check.provider", default="provider"),
            status="ok" if config.provider == "tmdb" else "err",
            detail=config.provider or "-",
        )
    )
    checks.append(
        DoctorCheck(
            section=tr("doctor.section.metadata", default="Metadata"),
            name=tr("doctor.check.language", default="language"),
            status="ok",
            detail=config.language or "-",
        )
    )
    checks.append(
        DoctorCheck(
            section=tr("doctor.section.metadata", default="Metadata"),
            name=tr("doctor.check.credentials", default="credentials"),
            status="ok" if config.has_credentials else "warn",
            detail=(
                tr(
                    "doctor.detail.credentials_source",
                    default="{auth_mode} from {source}",
                    auth_mode=config.auth_mode,
                    source=config.credential_source,
                )
                if config.has_credentials
                else tr("common.missing", default="missing")
            ),
        )
    )

    try:
        build_metadata_provider(settings, config=config)
    except Exception as exc:
        checks.append(
            DoctorCheck(
                section=tr("doctor.section.metadata", default="Metadata"),
                name=tr("doctor.check.provider_init", default="provider init"),
                status="err",
                detail=str(exc),
            )
        )
    else:
        checks.append(
            DoctorCheck(
                section=tr("doctor.section.metadata", default="Metadata"),
                name=tr("doctor.check.provider_init", default="provider init"),
                status="ok",
                detail=tr("doctor.detail.ready", default="ready"),
            )
        )

    return checks


def _template_checks(settings: dict) -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []
    active_template = str(settings.get("modules", {}).get("nfo", {}).get("active_template", ""))

    try:
        builtin = list_builtin_templates()
    except Exception as exc:
        checks.append(
            DoctorCheck(
                section=tr("doctor.section.templates", default="Templates"),
                name=tr("doctor.check.builtin_nfo_templates", default="builtin NFO templates"),
                status="err",
                detail=str(exc),
            )
        )
        builtin = []
    else:
        checks.append(
            DoctorCheck(
                section=tr("doctor.section.templates", default="Templates"),
                name=tr("doctor.check.builtin_nfo_templates", default="builtin NFO templates"),
                status="ok" if builtin else "err",
                detail=tr("doctor.detail.found_count", default="{count} found", count=len(builtin)),
            )
        )

    configured_nfo_locale = str(
        settings.get("modules", {}).get("nfo", {}).get("locale", "auto") or "auto"
    )
    resolved_nfo_locale = resolve_nfo_locale(
        configured_nfo_locale,
        ui_locale=str(
            settings.get("general", {}).get("locale", DEFAULT_SETTINGS["general"]["locale"])
        ),
    )
    checks.append(
        DoctorCheck(
            section=tr("doctor.section.templates", default="Templates"),
            name=tr("doctor.check.nfo_locale", default="NFO locale"),
            status="ok",
            detail=(
                tr(
                    "doctor.detail.nfo_locale_auto",
                    default="auto -> {locale}",
                    locale=resolved_nfo_locale,
                )
                if configured_nfo_locale == "auto"
                else resolved_nfo_locale
            ),
        )
    )

    try:
        record = NfoTemplateRegistry().find(active_template)
    except Exception as exc:
        checks.append(
            DoctorCheck(
                section=tr("doctor.section.templates", default="Templates"),
                name=tr("doctor.check.active_nfo_template", default="active NFO template"),
                status="err",
                detail=str(exc),
            )
        )
    else:
        checks.append(
            DoctorCheck(
                section=tr("doctor.section.templates", default="Templates"),
                name=tr("doctor.check.active_nfo_template", default="active NFO template"),
                status="ok" if record else "warn",
                detail=active_template or "-",
            )
        )

    return checks


def _tool_checks(store: SettingsStore) -> tuple[list[DoctorCheck], list[dict]]:
    registry = ToolRegistry(store)
    statuses = registry.get_all_statuses()
    checks: list[DoctorCheck] = []

    for item in statuses:
        if item.available:
            status: DoctorStatus = "ok"
            detail = item.version or item.resolved_path or "available"
        else:
            status = "warn"
            detail = item.error or tr("tools.not_found", default="not found")

        checks.append(
            DoctorCheck(
                section=tr("doctor.section.tools", default="External Tools"),
                name=item.name,
                status=status,
                detail=detail,
            )
        )

    return checks, [
        {
            "name": item.name,
            "configured_path": item.configured_path,
            "resolved_path": item.resolved_path,
            "available": item.available,
            "version": item.version,
            "error": item.error,
        }
        for item in statuses
    ]


def _torrent_checks(settings: dict) -> list[DoctorCheck]:
    torrent = settings.get("modules", {}).get("torrent", {})
    announce_urls = tuple(str(value) for value in torrent.get("announce_urls", []) if value)
    selected = str(torrent.get("selected_announce") or torrent.get("announce") or "").strip()

    # Determine the status and detail for the selected announce.  If a
    # selected announce is present and valid, mask its query parameters
    # to avoid leaking private passkeys.  When invalid, report an error.
    if selected:
        if is_valid_announce_url(selected):
            status: DoctorStatus = "ok"
            # Remove query parameters from the URL so that passkeys and
            # other sensitive parameters are not displayed.  Fall back
            # to a placeholder if parsing fails.
            try:
                parts = urlsplit(selected)
                sanitized = f"{parts.scheme}://{parts.netloc}{parts.path}"
            except Exception:
                sanitized = "********"
            detail = sanitized
        else:
            status = "err"
            detail = tr("torrent.error.invalid_announce", default="Invalid announce URL")
    else:
        status = "warn"
        detail = tr("common.not_configured", default="not configured")

    return [
        DoctorCheck(
            section=tr("doctor.section.torrent", default="Torrent"),
            name=tr("doctor.check.announce", default="announce URL"),
            status=status,
            detail=detail,
        ),
        DoctorCheck(
            section=tr("doctor.section.torrent", default="Torrent"),
            name=tr("doctor.check.announce_profiles", default="announce profiles"),
            status="ok" if announce_urls else "warn",
            detail=tr(
                "doctor.detail.found_count", default="{count} found", count=len(announce_urls)
            ),
        ),
    ]


def _diagnostics_checks() -> list[DoctorCheck]:
    summary = diagnostics_summary()
    log_file = summary.get("log_file")
    return [
        DoctorCheck(
            section=tr("doctor.section.diagnostics", default="Diagnostics"),
            name=tr("doctor.check.debug_mode", default="debug mode"),
            status="ok" if summary.get("debug") else "warn",
            detail=tr("common.enabled", default="enabled")
            if summary.get("debug")
            else tr("common.disabled", default="disabled"),
        ),
        DoctorCheck(
            section=tr("doctor.section.diagnostics", default="Diagnostics"),
            name=tr("doctor.check.log_file", default="log file"),
            status="ok" if log_file else "warn",
            detail=str(log_file)
            if log_file
            else tr("common.not_configured", default="not configured"),
        ),
    ]


def _summary_check(checks: list[DoctorCheck]) -> DoctorCheck:
    errors = sum(1 for item in checks if item.status == "err")
    warnings = sum(1 for item in checks if item.status == "warn")

    if errors:
        status: DoctorStatus = "err"
    elif warnings:
        status = "warn"
    else:
        status = "ok"

    return DoctorCheck(
        section=tr("doctor.section.summary", default="Summary"),
        name=tr("common.result", default="result"),
        status=status,
        detail=tr(
            "doctor.summary_detail",
            default="{errors} error(s), {warnings} warning(s)",
            errors=errors,
            warnings=warnings,
        ),
    )


def _render_checks(checks: list[DoctorCheck]) -> None:
    table = Table(
        title=tr("doctor.environment_check", default="Environment Check"),
        expand=True,
        border_style="white",
        box=box.HEAVY,
    )
    table.add_column(tr("common.section", default="Section"), width=18, no_wrap=True)
    table.add_column(tr("common.check", default="Check"), width=24, no_wrap=True)
    table.add_column(tr("common.status", default="Status"), width=12, no_wrap=True)
    table.add_column(tr("common.detail", default="Detail"), ratio=1)

    for check in checks:
        table.add_row(
            check.section,
            check.name,
            f"[{_status_style(check.status)}]{_status_label(check.status)}[/{_status_style(check.status)}]",
            check.detail,
        )

    console.print(table)


def run_doctor_command(*, json_output: bool) -> int:
    store = SettingsStore()
    settings = store.load()

    tool_checks, tool_payload = _tool_checks(store)
    checks = [
        *tool_checks,
        *_settings_checks(store, settings),
        *_metadata_checks(settings),
        *_template_checks(settings),
        *_torrent_checks(settings),
        *_diagnostics_checks(),
    ]
    checks.append(_summary_check(checks))

    if json_output:
        print_json(
            {
                "tools": tool_payload,
                "checks": [asdict(check) for check in checks],
            }
        )
        return 0

    print_module_banner("Doctor")
    _render_checks(checks)
    return 0


@click.command(
    "doctor", help=tr("cli.doctor.help", default="Run environment and configuration checks.")
)
@click.option(
    "-j",
    "--json",
    "json_output",
    is_flag=True,
    help=tr("cli.doctor.option.json", default="Output checks as JSON."),
)
def doctor_command(json_output: bool) -> int:
    return run_doctor_command(json_output=json_output)
