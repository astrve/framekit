from __future__ import annotations

import json
from typing import Any

from rich import box
from rich.table import Table

from framekit.core.cache import CacheManager
from framekit.core.exceptions import SettingsError
from framekit.core.i18n import tr
from framekit.core.paths import get_intelligent_cache_dir
from framekit.core.settings import SettingsStore, redact_settings
from framekit.ui.branding import print_module_banner

# Prefer rich_click if available; fall back to click when the rich integration is not installed.
from framekit.ui.click_helper import click
from framekit.ui.console import console, print_error, print_success, print_warning
from framekit.ui.unified_selector import confirm_choice


def _parse_settings_value(raw_value: str) -> Any:
    stripped = raw_value.strip()
    lowered = stripped.lower()
    if lowered in {"true", "yes", "y", "1", "on"}:
        return True
    if lowered in {"false", "no", "n", "0", "off"}:
        return False
    if lowered in {"null", "none"}:
        return ""

    try:
        return json.loads(stripped)
    except Exception:
        return stripped


def _format_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(redact_settings(value), indent=2, ensure_ascii=False)
    return str(redact_settings(value))


def _status(value: Any) -> str:
    if isinstance(value, bool):
        return (
            tr("common.enabled", default="Enabled")
            if value
            else tr("common.disabled", default="Disabled")
        )
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) or "-"
    return str(value or "-")


def _add_rows(table: Table, rows: list[tuple[str, str]]) -> None:
    for key, value in rows:
        table.add_row(key, value)


def _settings_tables(settings: dict[str, Any]) -> list[Table]:
    redacted = redact_settings(settings)
    general = redacted.get("general", {})
    metadata = redacted.get("metadata", {})
    modules = redacted.get("modules", {})
    nfo = modules.get("nfo", {})
    prez = modules.get("prez", {})
    torrent = modules.get("torrent", {})
    pipeline = modules.get("pipeline", {})

    overview = Table(
        title=tr("settings.overview", default="Framekit overview"),
        box=box.HEAVY,
        expand=True,
    )
    overview.add_column(tr("common.field", default="Field"), width=28, no_wrap=True)
    overview.add_column(tr("common.value", default="Value"), ratio=1)
    _add_rows(
        overview,
        [
            ("UI locale", _status(general.get("locale"))),
            ("Default folder", _status(general.get("default_folder"))),
            ("Metadata default", _status(metadata.get("enabled_by_default"))),
            ("NFO metadata", _status(nfo.get("with_metadata"))),
            ("Prez metadata", _status(prez.get("with_metadata"))),
            ("Pipeline metadata", _status(pipeline.get("with_metadata"))),
            ("NFO template", _status(nfo.get("active_template"))),
            (
                "Prez templates",
                f"HTML={_status(prez.get('html_template'))} | "
                f"BBCode={_status(prez.get('bbcode_template'))}",
            ),
            (
                "Torrent announce",
                _status(torrent.get("selected_announce") or torrent.get("announce")),
            ),
            ("Pipeline modules", _status(pipeline.get("enabled_modules"))),
        ],
    )

    metadata_table = Table(
        title=tr("settings.metadata", default="Metadata"),
        box=box.HEAVY,
        expand=True,
    )
    metadata_table.add_column(tr("common.field", default="Field"), width=28, no_wrap=True)
    metadata_table.add_column(tr("common.value", default="Value"), ratio=1)
    _add_rows(
        metadata_table,
        [
            ("Provider", _status(metadata.get("provider"))),
            ("Language", _status(metadata.get("language"))),
            ("Interactive confirmation", _status(metadata.get("interactive_confirmation"))),
            ("Cache TTL (h)", _status(metadata.get("cache_ttl_hours"))),
            ("TMDb read token", _status(metadata.get("tmdb_read_access_token"))),
        ],
    )

    folders = Table(
        title=tr("settings.paths", default="Module folders"),
        box=box.HEAVY,
        expand=True,
    )
    folders.add_column(tr("common.field", default="Field"), width=28, no_wrap=True)
    folders.add_column(tr("common.value", default="Value"), ratio=1)
    for module_name in ("renamer", "cleanmkv", "nfo", "prez", "torrent", "pipeline", "encoder"):
        module_settings = modules.get(module_name, {})
        folders.add_row(
            f"{module_name}.default_folder", _status(module_settings.get("default_folder"))
        )

    return [overview, metadata_table, folders]


def run_settings_show(*, json_output: bool = False) -> int:
    """Print the full settings document.

    Args:
        json_output: When ``True``, emit the redacted settings as JSON on
            stdout (suitable for ``jq``) instead of rendering rich tables.
    """
    from framekit.core.json_output import emit_json, json_envelope
    from framekit.core.settings import redact_settings

    store = SettingsStore()
    settings = store.load()

    if json_output:
        emit_json(
            json_envelope(
                command="settings.show",
                data={
                    "path": str(store.path),
                    "settings": redact_settings(settings),
                },
            )
        )
        return 0

    print_module_banner("Settings")
    for table in _settings_tables(settings):
        console.print(table)
        console.print()
    return 0


def run_settings_get(path: str, *, json_output: bool = False) -> int:
    """Read one nested settings key.

    Args:
        path: Dotted path, e.g. ``"general.locale"``.
        json_output: When ``True``, emit an envelope ``{path, value}`` on
            stdout instead of the rich-formatted value.
    """
    from framekit.core.json_output import emit_json, json_envelope
    from framekit.core.settings import redact_settings

    store = SettingsStore()
    try:
        value = store.get(path)
    except SettingsError as exc:
        if json_output:
            emit_json(
                json_envelope(
                    command="settings.get",
                    status="error",
                    error=str(exc),
                    exit_code=1,
                    data={"path": path},
                )
            )
        else:
            print_error(
                tr(
                    "settings.error.get_failed",
                    default="Could not read setting: {message}",
                    message=exc,
                )
            )
        return 1

    if json_output:
        # Redact secret leaves before emitting. ``redact_settings`` walks
        # dicts/lists; for a scalar we wrap and unwrap.
        redacted = redact_settings({path.rsplit(".", 1)[-1]: value})
        emit_json(
            json_envelope(
                command="settings.get",
                data={"path": path, "value": redacted[path.rsplit(".", 1)[-1]]},
            )
        )
    else:
        console.print(_format_value(value))
    return 0


def run_settings_set(path: str, value: str) -> int:
    """Run settings set."""
    store = SettingsStore()
    parsed = _parse_settings_value(value)
    try:
        store.set(path, parsed)
    except SettingsError as exc:
        print_error(
            tr(
                "settings.error.set_failed",
                default="Could not update setting: {message}",
                message=exc,
            )
        )
        return 1

    print_success(tr("settings.success.updated", default="Setting updated: {path}", path=path))
    return 0


def run_settings_reset(path: str) -> int:
    """Run settings reset."""
    store = SettingsStore()
    try:
        store.reset(path)
    except SettingsError as exc:
        print_error(
            tr(
                "settings.error.reset_failed",
                default="Could not reset setting: {message}",
                message=exc,
            )
        )
        return 1

    print_success(tr("settings.success.reset", default="Setting reset: {path}", path=path))
    return 0


def run_cache_stats() -> int:
    """Display cache statistics."""
    store = SettingsStore()
    settings = store.load()
    cache_config = settings.get("cache", {})

    cache_dir = get_intelligent_cache_dir()
    cache_manager = CacheManager(cache_dir, config=cache_config)

    print_module_banner("Cache Statistics")

    all_stats = cache_manager.get_stats()

    for cache_type, stats in all_stats.items():
        table = Table(
            title=f"{cache_type.upper()} Cache",
            box=box.HEAVY,
            expand=True,
        )
        table.add_column(tr("common.field", default="Field"), width=28, no_wrap=True)
        table.add_column(tr("common.value", default="Value"), ratio=1)

        size_mb = stats.total_size_bytes / (1024 * 1024)
        _add_rows(
            table,
            [
                ("Hits", str(stats.hits)),
                ("Misses", str(stats.misses)),
                ("Hit Rate", f"{stats.hit_rate:.1f}%"),
                ("Total Entries", str(stats.total_entries)),
                ("Expired Entries", str(stats.expired_entries)),
                ("Cache Size", f"{size_mb:.2f} MB"),
            ],
        )
        console.print(table)
        console.print()

    return 0


def run_cache_clear(cache_type: str | None) -> int:
    """Clear cache entries."""
    store = SettingsStore()
    settings = store.load()
    cache_config = settings.get("cache", {})

    cache_dir = get_intelligent_cache_dir()
    cache_manager = CacheManager(cache_dir, config=cache_config)

    if cache_type:
        cache_manager.clear(cache_type)
        print_success(
            tr(
                "cache.success.cleared_type",
                default="Cleared {type} cache",
                type=cache_type,
            )
        )
    else:
        cache_manager.clear()
        print_success(tr("cache.success.cleared_all", default="Cleared all caches"))

    return 0


def run_cache_cleanup() -> int:
    """Remove expired cache entries."""
    store = SettingsStore()
    settings = store.load()
    cache_config = settings.get("cache", {})

    cache_dir = get_intelligent_cache_dir()
    cache_manager = CacheManager(cache_dir, config=cache_config)

    results = cache_manager.cleanup_expired()

    total_removed = sum(results.values())
    if total_removed == 0:
        print_warning(tr("cache.info.no_expired", default="No expired entries found"))
    else:
        for cache_type, count in results.items():
            if count > 0:
                console.print(
                    f"[green]✓[/green] Removed {count} expired entries from {cache_type} cache"
                )
        print_success(
            tr(
                "cache.success.cleanup",
                default="Removed {count} expired entries",
                count=total_removed,
            )
        )

    return 0


def run_security_status() -> int:
    """Display security vault status."""
    from framekit.core.settings import Settings

    print_module_banner("Security Status")

    try:
        settings_obj = Settings()
        status = settings_obj.get_vault_status()

        table = Table(
            title="Vault Status",
            box=box.HEAVY,
            expand=True,
        )
        table.add_column(tr("common.field", default="Field"), width=28, no_wrap=True)
        table.add_column(tr("common.value", default="Value"), ratio=1)

        _add_rows(
            table,
            [
                ("Security Enabled", _status(settings_obj.is_security_enabled())),
                ("Vault Path", str(status.get("vault_path", "-"))),
                ("Vault Exists", _status(status.get("vault_exists", False))),
                ("Key Storage", str(status.get("key_storage", "-"))),
                ("Key Exists", _status(status.get("key_exists", False))),
                ("Encrypted Entries", str(status.get("entry_count", 0))),
                ("Stored Keys", ", ".join(status.get("keys", [])) or "-"),
            ],
        )
        console.print(table)
        console.print()

        return 0
    except Exception as exc:
        print_error(f"Failed to get security status: {exc}")
        return 1


def run_security_migrate() -> int:
    """Migrate plain text sensitive data to encrypted vault."""
    from framekit.core.settings import Settings

    print_module_banner("Security Migration")

    try:
        settings_obj = Settings()

        if not settings_obj.is_security_enabled():
            print_warning("Security is disabled. Enable it first in framekit.yaml")
            return 1

        console.print("[yellow]Migrating sensitive data to encrypted vault...[/yellow]")
        migrated = settings_obj.migrate_to_vault()

        if migrated["success"]:
            for key in migrated["success"]:
                console.print(f"[green]✓[/green] Migrated: {key}")
            print_success(f"Successfully migrated {len(migrated['success'])} items")

        if migrated["failed"]:
            for key in migrated["failed"]:
                console.print(f"[red]✗[/red] Failed: {key}")
            print_warning(f"Failed to migrate {len(migrated['failed'])} items")

        if not migrated["success"] and not migrated["failed"]:
            print_warning("No sensitive data found to migrate")

        return 0
    except Exception as exc:
        print_error(f"Migration failed: {exc}")
        return 1


def run_security_set_token(token: str | None) -> int:
    """Set TMDB API token securely."""
    from framekit.core.settings import Settings

    print_module_banner("Set TMDB Token")

    try:
        if token is None:
            # Prompt for token
            token = click.prompt("Enter TMDB Read Access Token", hide_input=True, type=str)

        if not token or not token.strip():
            print_error("Token cannot be empty")
            return 1

        settings_obj = Settings()
        try:
            settings_obj.set_tmdb_token(token.strip())
        except Exception as exc:
            if _is_vault_mismatch(exc):
                _hint_reset_vault()
                return 1
            raise

        if settings_obj.is_security_enabled():
            print_success("TMDB token stored securely in encrypted vault")
        else:
            print_success("TMDB token stored in settings (security disabled)")

        return 0
    except Exception as exc:
        print_error(f"Failed to set TMDB token: {exc}")
        return 1


def run_security_reset_vault() -> int:
    """Back up an unreadable vault and create a fresh one.

    Used when the encryption key no longer matches the on-disk vault file
    (key store wiped, vault restored from another machine, etc.). The old
    vault file is moved aside with a timestamped suffix and a new empty
    vault is created with the current key.
    """
    from framekit.core.settings import Settings

    print_module_banner("Reset Vault")

    settings_obj = Settings()
    if not settings_obj.is_security_enabled():
        print_warning(
            "Security is disabled — there is no vault to reset. "
            "Enable it first with: framekit settings security toggle --enable"
        )
        return 1

    confirmed = confirm_choice(
        title="This will back up the existing vault and create a fresh empty one. "
        "Stored tokens / announces will need to be re-entered. Continue?",
        default=False,
    )
    if not confirmed:
        print_warning("Cancelled.")
        return 1

    try:
        vault = settings_obj.get_vault()
    except Exception as exc:
        print_error(f"Could not access vault: {exc}")
        return 1

    if vault is None:
        print_error("Vault is unavailable.")
        return 1

    try:
        backup = vault.reset()
    except Exception as exc:
        print_error(f"Reset failed: {exc}")
        return 1

    if backup is not None:
        print_success(f"Old vault backed up to: {backup}")
    print_success("Fresh empty vault created. Re-store credentials with:")
    console.print("  [cyan]framekit settings security set-token[/cyan]")
    console.print("  [cyan]framekit settings security set-announces[/cyan]")
    return 0


def run_security_set_announces(announces: list[str]) -> int:
    """Set torrent announce URLs securely."""
    from framekit.core.settings import Settings

    print_module_banner("Set Torrent Announces")

    try:
        if not announces:
            # Prompt for announces
            console.print(
                "[yellow]Enter announce URLs (one per line, empty line to finish):[/yellow]"
            )
            announces = []
            while True:
                url = click.prompt("Announce URL", default="", show_default=False)
                if not url.strip():
                    break
                announces.append(url.strip())

        if not announces:
            print_error("At least one announce URL is required")
            return 1

        settings_obj = Settings()
        try:
            settings_obj.set_torrent_announces(announces)
        except Exception as exc:
            # Unwrap chained ``VaultKeyMismatchError`` (callers wrap into
            # SettingsError). When the vault key no longer matches the file,
            # offer the dedicated recovery flow instead of bubbling an opaque
            # "Failed to decrypt vault" message.
            if _is_vault_mismatch(exc):
                _hint_reset_vault()
                return 1
            raise

        if settings_obj.is_security_enabled():
            print_success(f"Stored {len(announces)} announce URL(s) securely in encrypted vault")
        else:
            print_success(
                f"Stored {len(announces)} announce URL(s) in settings (security disabled)"
            )

        return 0
    except Exception as exc:
        print_error(f"Failed to set announce URLs: {exc}")
        return 1


def _is_vault_mismatch(exc: BaseException) -> bool:
    """Return ``True`` if ``exc`` (or its chain) is a ``VaultKeyMismatchError``."""
    from framekit.core.security.vault import VaultKeyMismatchError

    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, VaultKeyMismatchError):
            return True
        current = current.__cause__ or current.__context__
    return False


def _hint_reset_vault() -> None:
    """Print the standard recovery hint for a vault key mismatch."""
    print_error(
        "Vault decryption failed: the current key does not match the existing encrypted vault file."
    )
    console.print()
    console.print("[bold yellow]Suggestions:[/bold yellow]")
    console.print(
        "  • Restore the original key (keyring entry or master.key file) if available, then retry."
    )
    console.print(
        "  • Or back up the unreadable vault and start fresh: "
        "[cyan]framekit settings security reset-vault[/cyan]"
    )
    console.print(
        "  • Or disable security entirely: [cyan]framekit settings security toggle --disable[/cyan]"
    )


def run_security_reset() -> int:
    """Reset security by rotating encryption key."""
    from framekit.core.settings import Settings

    print_module_banner("Reset Security")

    try:
        settings_obj = Settings()

        if not settings_obj.is_security_enabled():
            print_warning("Security is disabled")
            return 1

        # Confirm action
        confirmed = confirm_choice(
            title="This will re-encrypt all data with a new key. Continue?", default=False
        )

        if not confirmed:
            print_warning("Cancelled")
            return 1

        vault = settings_obj.get_vault()
        if vault:
            vault.rotate_key()
            print_success("Security reset complete. All data re-encrypted with new key.")
        else:
            print_error("Vault not available")
            return 1

        return 0
    except Exception as exc:
        print_error(f"Failed to reset security: {exc}")
        return 1


def run_security_clear_vault() -> int:
    """Clear all data from the encrypted vault."""
    from framekit.core.settings import Settings

    print_module_banner("Clear Vault")

    try:
        settings_obj = Settings()

        if not settings_obj.is_security_enabled():
            print_warning("Security is disabled")
            return 1

        vault = settings_obj.get_vault()
        if not vault:
            print_error("Vault not available")
            return 1

        # Show current vault status
        status = vault.get_status()
        entry_count = status.get("entry_count", 0)

        if entry_count == 0:
            print_warning("Vault is already empty")
            return 0

        console.print(f"[yellow]Vault contains {entry_count} encrypted entries:[/yellow]")
        for key in status.get("keys", []):
            console.print(f"  • {key}")
        console.print()

        # Confirm action
        confirmed = confirm_choice(
            title="This will permanently delete all encrypted data from the vault. Continue?",
            default=False,
        )

        if not confirmed:
            print_warning("Cancelled")
            return 1

        vault.clear()
        print_success("Vault cleared successfully. All encrypted data has been removed.")

        return 0
    except Exception as exc:
        print_error(f"Failed to clear vault: {exc}")
        return 1


def run_security_toggle(enable: bool | None) -> int:
    """Enable or disable encryption."""
    from framekit.core.settings import Settings, SettingsStore

    print_module_banner("Toggle Encryption")

    try:
        settings_obj = Settings()
        store = SettingsStore()

        current_status = settings_obj.is_security_enabled()

        if enable is None:
            # Show current status and prompt
            console.print(
                f"[yellow]Encryption is currently: {'ENABLED' if current_status else 'DISABLED'}[/yellow]"
            )
            enable = confirm_choice(title="Enable encryption?", default=current_status)

        if enable == current_status:
            print_warning(f"Encryption is already {'enabled' if enable else 'disabled'}")
            return 0

        if enable:
            # Enabling encryption
            console.print("[yellow]Enabling encryption...[/yellow]")
            store.set("security.enabled", True)
            print_success(
                "Encryption enabled. Sensitive data will now be stored in the encrypted vault."
            )
            console.print(
                "[cyan]Tip: Use 'fk settings security migrate' to move existing sensitive data to the vault[/cyan]"
            )
        else:
            # Disabling encryption - warn user
            console.print(
                "[red]WARNING: Disabling encryption will store sensitive data in plain text![/red]"
            )
            confirmed = confirm_choice(
                title="Are you sure you want to disable encryption?", default=False
            )

            if not confirmed:
                print_warning("Cancelled")
                return 1

            store.set("security.enabled", False)
            print_success("Encryption disabled. Sensitive data will be stored in plain text.")
            console.print(
                "[yellow]Note: Existing encrypted data in the vault remains encrypted[/yellow]"
            )

        return 0
    except Exception as exc:
        print_error(f"Failed to toggle encryption: {exc}")
        return 1


@click.group(
    "settings",
    invoke_without_command=True,
    help=tr(
        "cli.settings.help",
        default=(
            "Inspect Framekit configuration, cache and security.\n\n"
            "Examples:\n"
            "  fk settings                     Show all settings\n"
            "  fk settings reset general.locale\n"
            "  fk settings cache stats\n"
            "  fk settings security status\n\n"
            "Subcommands:\n"
            "  reset <path>      Reset a setting to its default value\n"
            "  cache             Manage intelligent cache system\n"
            "  security          Manage encrypted vault for sensitive data"
        ),
    ),
)
@click.option(
    "-j",
    "--json",
    "json_output",
    is_flag=True,
    help=tr("cli.settings.json", default="Emit the settings document as JSON on stdout."),
)
@click.pass_context
def settings_command(ctx: click.Context, json_output: bool) -> int | None:
    """Display or update the active Framekit settings.

    With no subcommand, prints the full document. Pass ``--json`` for a
    machine-readable envelope suitable for ``jq``.
    """
    if ctx.invoked_subcommand is None:
        return run_settings_show(json_output=json_output)
    return None


@settings_command.command(
    "reset", help=tr("cli.settings.reset.help", default="Reset one setting to its default value.")
)
@click.argument("path")
def settings_reset_command(path: str) -> int:
    """Handle settings reset command."""
    return run_settings_reset(path)


@settings_command.group(
    "cache",
    help=tr("cli.settings.cache.help", default="Manage intelligent cache system."),
)
def cache_command() -> None:
    """Handle cache command."""


@cache_command.command(
    "stats",
    help=tr("cli.settings.cache.stats.help", default="Display cache statistics."),
)
def cache_stats_command() -> int:
    """Handle cache stats command."""
    return run_cache_stats()


@cache_command.command(
    "clear",
    help=tr("cli.settings.cache.clear.help", default="Clear cache entries."),
)
@click.option(
    "--type",
    "cache_type",
    type=click.Choice(["tmdb", "mediainfo", "release"], case_sensitive=False),
    help=tr("cli.settings.cache.clear.type", default="Cache type to clear (all if not specified)"),
)
def cache_clear_command(cache_type: str | None) -> int:
    """Handle cache clear command."""
    return run_cache_clear(cache_type)


@cache_command.command(
    "cleanup",
    help=tr("cli.settings.cache.cleanup.help", default="Remove expired cache entries."),
)
def cache_cleanup_command() -> int:
    """Handle cache cleanup command."""
    return run_cache_cleanup()


@settings_command.group(
    "security",
    help=tr("cli.settings.security.help", default="Manage encrypted vault for sensitive data."),
)
def security_command() -> None:
    """Handle security command."""


@security_command.command(
    "status",
    help=tr("cli.settings.security.status.help", default="Display security vault status."),
)
def security_status_command() -> int:
    """Handle security status command."""
    return run_security_status()


@security_command.command(
    "migrate",
    help=tr(
        "cli.settings.security.migrate.help", default="Migrate plain text data to encrypted vault."
    ),
)
def security_migrate_command() -> int:
    """Handle security migrate command."""
    return run_security_migrate()


@security_command.command(
    "set-token",
    help=tr("cli.settings.security.set_token.help", default="Set TMDB API token securely."),
)
@click.option(
    "--token",
    help=tr("cli.settings.security.set_token.token", default="TMDB Read Access Token"),
)
def security_set_token_command(token: str | None) -> int:
    """Handle security set token command."""
    return run_security_set_token(token)


@security_command.command(
    "set-announces",
    help=tr(
        "cli.settings.security.set_announces.help", default="Set torrent announce URLs securely."
    ),
)
@click.argument("announces", nargs=-1)
def security_set_announces_command(announces: tuple[str, ...]) -> int:
    """Handle security set announces command."""
    return run_security_set_announces(list(announces))


@security_command.command(
    "reset",
    help=tr("cli.settings.security.reset.help", default="Reset security (rotate encryption key)."),
)
def security_reset_command() -> int:
    """Handle security reset command."""
    return run_security_reset()


@security_command.command(
    "reset-vault",
    help=tr(
        "cli.settings.security.reset_vault.help",
        default=(
            "Back up an unreadable vault and start a fresh one. Use when the "
            "current key no longer matches the existing vault file (key store "
            "wiped, vault restored from another machine, etc.)."
        ),
    ),
)
def security_reset_vault_command() -> int:
    """Move broken vault aside and recreate an empty one."""
    return run_security_reset_vault()


@security_command.command(
    "clear-vault",
    help=tr(
        "cli.settings.security.clear_vault.help", default="Clear all data from encrypted vault."
    ),
)
def security_clear_vault_command() -> int:
    """Handle security clear vault command."""
    return run_security_clear_vault()


@security_command.command(
    "toggle",
    help=tr("cli.settings.security.toggle.help", default="Enable or disable encryption."),
)
@click.option(
    "--enable/--disable",
    "enable",
    default=None,
    help=tr("cli.settings.security.toggle.enable", default="Enable or disable encryption"),
)
def security_toggle_command(enable: bool | None) -> int:
    """Handle security toggle command."""
    return run_security_toggle(enable)


# ---------------------------------------------------------------------------
# Doctor & Benchmark — registered as settings subcommands
# ---------------------------------------------------------------------------


@settings_command.command(
    "doctor",
    help=tr(
        "cli.settings.doctor.help",
        default="Run environment and configuration diagnostics.",
    ),
)
@click.option(
    "-j",
    "--json",
    "json_output",
    is_flag=True,
    help=tr("cli.settings.doctor.json", default="Output checks as JSON."),
)
def settings_doctor_command(json_output: bool) -> int:
    """Run doctor diagnostics as a settings subcommand."""
    from framekit.commands.doctor import run_doctor_command

    return run_doctor_command(json_output=json_output)


from framekit.commands.benchmark import benchmark_command  # noqa: E402

settings_command.add_command(benchmark_command)
