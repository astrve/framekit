from __future__ import annotations

import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import urlsplit

from rich import box
from rich.table import Table

from framekit.commands.benchmark import benchmark_command
from framekit.core.diagnostics import diagnostics_summary
from framekit.core.i18n import tr
from framekit.core.paths import (
    get_cache_dir,
    get_config_dir,
    get_master_key_path,
    get_vault_path,
)
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

# Prefer rich_click if available; fall back to click when the rich integration is not installed.
from framekit.ui.click_helper import click
from framekit.ui.console import console, print_json

MINIMUM_PYTHON_VERSION = (3, 12)
MIN_FREE_CACHE_MB = 200  # Below this, prez/cache eviction starts hurting UX.
TMDB_PROBE_TIMEOUT_SECONDS = 4.0

DoctorStatus = Literal["ok", "warn", "err"]


@dataclass(slots=True)
class DoctorCheck:
    """Doctor check."""

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


def _runtime_checks() -> list[DoctorCheck]:
    """Python runtime + free disk space at default cache/config dirs."""
    checks: list[DoctorCheck] = []
    section = tr("doctor.section.runtime", default="Runtime")

    py_version = sys.version_info[:3]
    py_status: DoctorStatus = "ok" if py_version >= MINIMUM_PYTHON_VERSION else "err"
    checks.append(
        DoctorCheck(
            section=section,
            name=tr("doctor.check.python_version", default="Python"),
            status=py_status,
            detail=(
                f"{py_version[0]}.{py_version[1]}.{py_version[2]} "
                f"(minimum {MINIMUM_PYTHON_VERSION[0]}.{MINIMUM_PYTHON_VERSION[1]})"
            ),
        )
    )

    for label, path in (
        (tr("doctor.check.cache_dir", default="cache dir"), get_cache_dir()),
        (tr("doctor.check.config_dir", default="config dir"), get_config_dir()),
    ):
        try:
            target = path if path.exists() else path.parent
            usage = shutil.disk_usage(target)
            free_mb = usage.free // (1024 * 1024)
        except OSError as exc:
            checks.append(
                DoctorCheck(
                    section=section,
                    name=label,
                    status="warn",
                    detail=str(exc),
                )
            )
            continue
        status: DoctorStatus = "ok" if free_mb >= MIN_FREE_CACHE_MB else "warn"
        checks.append(
            DoctorCheck(
                section=section,
                name=label,
                status=status,
                detail=tr(
                    "doctor.detail.disk_free",
                    default="{free_mb} MB free at {path}",
                    free_mb=free_mb,
                    path=str(path),
                ),
            )
        )

    return checks


def _network_checks(settings: dict) -> list[DoctorCheck]:
    """Best-effort connectivity probes for the metadata and update endpoints.

    Each probe is wrapped in a tight timeout; the doctor command must remain
    responsive even on a flaky network.
    """
    checks: list[DoctorCheck] = []
    section = tr("doctor.section.network", default="Network")

    try:
        import httpx
    except ImportError:
        checks.append(
            DoctorCheck(
                section=section,
                name="httpx",
                status="err",
                detail="httpx not installed (should be a runtime dependency).",
            )
        )
        return checks

    endpoints = (
        ("TMDb", "https://api.themoviedb.org/3/configuration"),
        ("PyPI", "https://pypi.org/pypi/framekit-cli/json"),
    )

    for label, url in endpoints:
        try:
            with httpx.Client(timeout=TMDB_PROBE_TIMEOUT_SECONDS) as client:
                response = client.get(url)
                status: DoctorStatus = "ok" if response.status_code < 500 else "warn"
                detail = f"HTTP {response.status_code}"
        except Exception as exc:
            status = "warn"
            detail = f"unreachable ({exc.__class__.__name__})"
        checks.append(
            DoctorCheck(
                section=section,
                name=label,
                status=status,
                detail=detail,
            )
        )

    return checks


def _tmdb_token_probe(settings: dict) -> list[DoctorCheck]:
    """Make one authenticated call to TMDb when a token is configured.

    Verifies that the token is well-formed and accepted by TMDb. Skipped
    when no credentials are configured (already flagged by metadata checks).
    """
    config = resolve_metadata_config(settings)
    if not config.has_credentials:
        return []

    section = tr("doctor.section.metadata", default="Metadata")
    try:
        provider = build_metadata_provider(settings, config=config)
    except Exception as exc:
        return [
            DoctorCheck(
                section=section,
                name=tr("doctor.check.tmdb_auth", default="TMDb auth"),
                status="err",
                detail=str(exc),
            )
        ]

    try:
        # ``provider`` is typed as the abstract ``MetadataProvider`` base.
        # ``http_client`` and ``_headers`` are TMDb-specific surface; narrow
        # to the concrete provider so static checkers stop flagging the
        # attributes and a non-TMDb provider gets a clean diagnostic instead
        # of a misleading attribute error.
        from framekit.modules.metadata.tmdb_provider import TMDbProvider

        if not isinstance(provider, TMDbProvider):
            return [
                DoctorCheck(
                    section=section,
                    name=tr("doctor.check.tmdb_auth", default="TMDb auth"),
                    status="warn",
                    detail=tr(
                        "doctor.detail.not_tmdb",
                        default="Active provider is not TMDb; skipping auth probe.",
                    ),
                )
            ]
        provider.http_client.get_json("/configuration", headers=provider._headers())  # pyright: ignore[reportPrivateUsage]  # doctor inspects provider auth headers to surface config errors
    except Exception as exc:
        return [
            DoctorCheck(
                section=section,
                name=tr("doctor.check.tmdb_auth", default="TMDb auth"),
                status="err",
                detail=str(exc),
            )
        ]
    return [
        DoctorCheck(
            section=section,
            name=tr("doctor.check.tmdb_auth", default="TMDb auth"),
            status="ok",
            detail=tr("doctor.detail.token_valid", default="token accepted"),
        )
    ]


def _vault_checks(settings: dict) -> list[DoctorCheck]:
    """Vault file + key file existence and (POSIX) permission hygiene."""
    checks: list[DoctorCheck] = []
    section = tr("doctor.section.security", default="Security")
    security_cfg = settings.get("security", {}) if isinstance(settings, dict) else {}  # pyright: ignore[reportUnnecessaryIsInstance]  # Defensive guard: settings may be a raw mapping or None at call sites

    checks.append(
        DoctorCheck(
            section=section,
            name=tr("doctor.check.security_enabled", default="vault enabled"),
            status="ok" if security_cfg.get("enabled") else "warn",
            detail=tr("common.enabled", default="enabled")
            if security_cfg.get("enabled")
            else tr("common.disabled", default="disabled"),
        )
    )

    for label, path in (
        (tr("doctor.check.vault_file", default="vault file"), get_vault_path()),
        (tr("doctor.check.key_file", default="key file"), get_master_key_path()),
    ):
        if not Path(path).exists():
            checks.append(
                DoctorCheck(
                    section=section,
                    name=label,
                    status="warn",
                    detail=tr("common.not_found", default="not found"),
                )
            )
            continue
        try:
            from framekit.core.security.permissions import verify_secure_permissions

            secure = verify_secure_permissions(Path(path))
        except Exception as exc:
            checks.append(
                DoctorCheck(
                    section=section,
                    name=label,
                    status="warn",
                    detail=f"could not inspect: {exc}",
                )
            )
            continue
        checks.append(
            DoctorCheck(
                section=section,
                name=label,
                status="ok" if secure else "warn",
                detail=tr(
                    "doctor.detail.perm_secure",
                    default="owner-only",
                )
                if secure
                else tr(
                    "doctor.detail.perm_loose",
                    default="loose permissions (run: framekit settings security repair)",
                ),
            )
        )

    return checks


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


def collect_doctor_payload() -> dict[str, object]:
    """Build doctor payload used by CLI JSON output and web API."""
    store = SettingsStore()
    settings = store.load()

    tool_checks, tool_payload = _tool_checks(store)
    checks = [
        *_runtime_checks(),
        *tool_checks,
        *_settings_checks(store, settings),
        *_metadata_checks(settings),
        *_tmdb_token_probe(settings),
        *_template_checks(settings),
        *_torrent_checks(settings),
        *_vault_checks(settings),
        *_network_checks(settings),
        *_diagnostics_checks(),
    ]
    checks.append(_summary_check(checks))

    return {
        "tools": tool_payload,
        "checks": [asdict(check) for check in checks],
    }


def run_doctor_command(*, json_output: bool) -> int:
    """Run doctor command."""
    payload = collect_doctor_payload()
    raw_checks = cast(list[dict[str, Any]], payload["checks"])
    checks = [DoctorCheck(**item) for item in raw_checks]

    if json_output:
        print_json(payload)
        return 0

    print_module_banner("Doctor")
    _render_checks(checks)
    return 0


@click.group(
    "doctor",
    invoke_without_command=True,
    help=tr(
        "cli.doctor.help",
        default=(
            "Run comprehensive environment and configuration diagnostics.\n\n"
            "The doctor command performs health checks on your Framekit installation, verifying "
            "external tools, settings, metadata configuration, templates, and more.\n\n"
            "Quick examples:\n"
            "  fk doctor                               # Run all checks\n"
            "  fk diag -j                              # Output as JSON\n"
            "  fk doc                                  # Quick health check\n"
            "  fk doctor benchmark                     # Run performance benchmarks\n\n"
            "Checks performed:\n"
            "  • External tools (mkvmerge, ffmpeg, ffprobe, mediainfo)\n"
            "  • Settings file and schema validation\n"
            "  • Metadata provider configuration\n"
            "  • TMDb credentials\n"
            "  • NFO templates availability\n"
            "  • Torrent announce URLs\n"
            "  • Debug and logging configuration\n\n"
            "Status indicators:\n"
            "  • OK (green): Everything working correctly\n"
            "  • Warning (yellow): Non-critical issues\n"
            "  • Error (red): Critical problems requiring attention\n\n"
            "Best practices:\n"
            "  • Run doctor after installation\n"
            "  • Check before reporting issues\n"
            "  • Use -j for automated monitoring\n"
            "  • Review warnings for optimization opportunities\n\n"
            "Subcommands:\n"
            "  benchmark                               # Run performance benchmarks\n\n"
            "Related commands: setup, settings"
        ),
    ),
)
@click.option(
    "-j",
    "--json",
    "json_output",
    is_flag=True,
    help=tr("cli.doctor.option.json", default="Output checks as JSON."),
)
@click.pass_context
def doctor_command(ctx: click.Context, json_output: bool) -> int:
    """Doctor command group with default health check behavior."""
    # If no subcommand is invoked, run the health checks
    if ctx.invoked_subcommand is None:
        return run_doctor_command(json_output=json_output)
    return 0


# Register benchmark as a subcommand of doctor
doctor_command.add_command(benchmark_command)
