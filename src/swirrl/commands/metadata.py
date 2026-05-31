from __future__ import annotations

from pathlib import Path

from rich import box
from rich.panel import Panel
from rich.table import Table

from swirrl.core.cli_helpers import join_path_parts
from swirrl.core.i18n import tr
from swirrl.core.paths import PathResolver
from swirrl.core.settings import SettingsStore
from swirrl.modules.metadata.config import (
    looks_like_tmdb_read_access_token,
    mask_secret,
    normalize_secret_input,
    resolve_metadata_config,
)
from swirrl.modules.metadata.workflow import run_metadata_workflow
from swirrl.modules.nfo.builder import build_release_nfo
from swirrl.modules.nfo.scanner import scan_nfo_folder
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


def _build_release_from_folder(folder: Path):
    episodes = scan_nfo_folder(folder)
    if not episodes:
        raise ValueError(
            tr("nfo.error.no_mkv", default="No MKV files found in folder: {folder}", folder=folder)
        )
    return build_release_nfo(folder, episodes)


def _print_doctor(config) -> None:
    table = Table(
        title=tr("metadata.status_title", default="Metadata Status"),
        expand=True,
        box=box.HEAVY,
        border_style="white",
    )
    table.add_column(tr("common.field", default="Field"), width=24, no_wrap=True)
    table.add_column(tr("common.value", default="Value"), ratio=1)

    table.add_row(tr("common.provider", default="Provider"), config.provider or "-")
    table.add_row(tr("common.language", default="Language"), config.language or "-")
    table.add_row(
        tr("metadata.interactive_confirmation", default="Interactive Confirmation"),
        tr("common.enabled", default="Enabled")
        if config.interactive_confirmation
        else tr("common.disabled", default="Disabled"),
    )
    table.add_row(
        tr("common.cache_ttl_hours", default="Cache TTL (hours)"), str(config.cache_ttl_hours)
    )
    table.add_row(
        tr("common.credentials_present", default="Credentials Present"),
        tr("common.yes", default="Yes")
        if config.has_credentials
        else tr("common.no", default="No"),
    )
    table.add_row(
        tr("metadata.credential_source", default="Credential Source"),
        config.credential_source or "-",
    )
    table.add_row(tr("metadata.auth_mode", default="Auth Mode"), config.auth_mode or "-")
    table.add_row(
        tr("common.read_access_token", default="Read Access Token"),
        mask_secret(config.tmdb_read_access_token or ""),
    )

    console.print(table)


def _print_setup_help() -> None:
    lines = tr("metadata.setup_help_body", default="Metadata setup help").splitlines()

    console.print(
        Panel(
            "\n".join(lines),
            title=tr("metadata.setup_help_title", default="Metadata Setup Help"),
            border_style="white",
            box=box.HEAVY,
            expand=True,
        )
    )


def _store_token_interactive(settings: dict, store: SettingsStore) -> int:
    while True:
        prompt = tr(
            "metadata.prompt.token",
            default="TMDb Read Access Token (type 'cancel' to abort, 'clear' to remove): ",
        )
        raw = console.input(f"[white]{prompt}[/white]").strip()

        if raw.lower() == "cancel":
            print_warning(
                tr("metadata.warning.token_update_cancelled", default="Token update cancelled.")
            )
            return 0

        if raw.lower() == "clear":
            settings.setdefault("metadata", {})
            settings["metadata"]["tmdb_read_access_token"] = ""  # nosec B105
            store.save(settings)
            print_success(tr("metadata.success.token_cleared", default="TMDb token cleared."))
            return 0

        if not raw:
            print_error(tr("metadata.error.token_empty", default="Token cannot be empty."))
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

        settings.setdefault("metadata", {})
        settings["metadata"]["tmdb_read_access_token"] = token
        store.save(settings)
        print_success(tr("metadata.success.token_saved", default="TMDb token saved."))
        return 0


def _store_token_value(settings: dict, store: SettingsStore, raw_value: str) -> int:
    token = normalize_secret_input(raw_value)

    if not looks_like_tmdb_read_access_token(token):
        print_error(
            tr(
                "metadata.error.invalid_token",
                default="That does not look like a valid TMDb read access token.",
            )
        )
        return 1

    from swirrl.core.settings import Settings

    settings_obj = Settings()
    if settings_obj.is_security_enabled():
        settings_obj.set_tmdb_token(token)
        print_success(
            tr(
                "metadata.success.token_saved_encrypted",
                default="TMDb token saved securely (encrypted).",
            )
        )
    else:
        settings.setdefault("metadata", {})
        settings["metadata"]["tmdb_read_access_token"] = token
        store.save(settings)
        print_success(tr("metadata.success.token_saved", default="TMDb token saved."))
    return 0


def _resolved_value(resolved, attr: str):
    return getattr(resolved, attr, None)


def _resolved_title_and_year(resolved) -> tuple[str | None, str | None]:
    title = (
        _resolved_value(resolved, "title")
        or _resolved_value(resolved, "episode_title")
        or _resolved_value(resolved, "series_title")
    )
    year = _resolved_value(resolved, "year") or _resolved_value(resolved, "series_year")
    return title, year


def _metadata_rows(resolved) -> list[tuple[str, str]]:
    title, year = _resolved_title_and_year(resolved)
    season_number = _resolved_value(resolved, "season_number")
    episode_number = _resolved_value(resolved, "episode_number")
    return [
        (
            tr("common.provider", default="Provider"),
            _resolved_value(resolved, "provider_name") or "-",
        ),
        (
            tr("metadata.provider_id", default="Provider ID"),
            _resolved_value(resolved, "provider_id") or "-",
        ),
        (tr("common.title", default="Title"), title or "-"),
        (tr("common.year", default="Year"), str(year) if year is not None else "-"),
        (
            tr("metadata.season", default="Season"),
            str(season_number) if season_number is not None else "-",
        ),
        (
            tr("metadata.episode", default="Episode"),
            str(episode_number) if episode_number is not None else "-",
        ),
        (tr("metadata.air_date", default="Air Date"), _resolved_value(resolved, "air_date") or "-"),
        (tr("metadata.imdb_id", default="IMDb ID"), _resolved_value(resolved, "imdb_id") or "-"),
        (
            tr("metadata.imdb_url", default="IMDb URL"),
            _resolved_value(resolved, "external_url") or "-",
        ),
    ]


def _print_resolved_metadata(resolved) -> None:
    table = Table(
        title=tr("metadata.resolved_title", default="Resolved Metadata"),
        expand=True,
        box=box.HEAVY,
        border_style="white",
    )
    table.add_column(tr("common.field", default="Field"), width=20, no_wrap=True)
    table.add_column(tr("common.value", default="Value"), ratio=1)

    for label, value in _metadata_rows(resolved):
        table.add_row(label, value)

    console.print(table)

    overview = _resolved_value(resolved, "overview")
    if overview:
        console.print(
            Panel(
                overview,
                title=tr("metadata.overview", default="Overview"),
                border_style="white",
                box=box.HEAVY,
                expand=True,
            )
        )


def _emit_status_json(config) -> None:
    from swirrl.core.json_output import emit_json, json_envelope

    emit_json(
        json_envelope(
            command="metadata.status",
            data={
                "provider": config.provider,
                "language": config.language,
                "interactive_confirmation": config.interactive_confirmation,
                "cache_ttl_hours": config.cache_ttl_hours,
                "has_credentials": config.has_credentials,
                "credential_source": config.credential_source,
                "auth_mode": config.auth_mode,
                "read_access_token_masked": mask_secret(config.tmdb_read_access_token or ""),
            },
        )
    )


def _resolve_release_target(resolver: PathResolver, path: str | None):
    folder = resolver.resolve_start_folder("nfo", path or None)
    if not folder.exists():
        raise FileNotFoundError(
            tr(
                "cleanmkv.error.folder_not_found",
                default="Folder not found: {folder}",
                folder=folder,
            )
        )

    if folder.is_file():
        if folder.suffix.lower() != ".mkv":
            raise ValueError(
                tr(
                    "cleanmkv.error.invalid_file_type",
                    default="File is not an MKV: {file}",
                    file=folder,
                )
            )
        episodes = scan_nfo_folder(folder.parent)
        episodes = [ep for ep in episodes if ep.file_path == folder]
        if not episodes:
            raise ValueError(
                tr(
                    "nfo.error.no_mkv",
                    default="No MKV files found in folder: {folder}",
                    folder=folder,
                )
            )
        return folder, build_release_nfo(folder.parent, episodes)

    if not folder.is_dir():
        raise FileNotFoundError(
            tr(
                "cleanmkv.error.folder_not_found",
                default="Folder not found: {folder}",
                folder=folder,
            )
        )
    return folder, _build_release_from_folder(folder)


def _emit_workflow_error_json(error: str, *, skipped: bool = False) -> None:
    from swirrl.core.json_output import emit_json, json_envelope

    emit_json(
        json_envelope(
            command="metadata.resolve",
            status="skipped" if skipped else "error",
            error=error,
            exit_code=1,
        )
    )


def _handle_missing_credentials(json_output: bool) -> int:
    if json_output:
        _emit_workflow_error_json("missing_credentials")
        return 1
    print_warning(
        tr(
            "metadata.warning.missing_credentials",
            default="Metadata credentials are missing.",
        )
    )
    print_info(tr("metadata.info.run_setup", default="Run: swirrl setup"))
    print_info(tr("metadata.info.check_status", default="Or check status with: swirrl md -s"))
    return 1


def _handle_unsupported_specials(result, json_output: bool) -> int:
    if json_output:
        _emit_workflow_error_json("unsupported_specials", skipped=True)
        return 1
    print_warning(
        result.message
        or tr(
            "metadata.warning.unsupported_specials",
            default="Special season detected. Metadata is not supported for this case yet.",
        )
    )
    return 1


def _handle_simple_workflow_error(
    status: str,
    *,
    json_output: bool,
    json_error: str,
    message_key: str,
    default_message: str,
    skipped: bool = False,
) -> int:
    if json_output:
        _emit_workflow_error_json(json_error, skipped=skipped)
        return 1
    if status == "cancelled":
        print_warning(tr(message_key, default=default_message))
    else:
        print_warning(tr(message_key, default=default_message))
    return 1


def _handle_workflow_failure(result, json_output: bool) -> int | None:
    status = result.status
    if status == "missing_credentials":
        return _handle_missing_credentials(json_output)
    if status == "unsupported_specials":
        return _handle_unsupported_specials(result, json_output)
    simple_failures: dict[str, tuple[str, str, bool]] = {
        "no_candidates": (
            "no_candidates",
            tr("metadata.warning.no_candidates", default="No metadata candidates found."),
            False,
        ),
        "cancelled": (
            "cancelled",
            tr("metadata.warning.selection_cancelled", default="Metadata selection cancelled."),
            True,
        ),
    }
    if status in simple_failures:
        json_error, message, skipped = simple_failures[status]
        if json_output:
            _emit_workflow_error_json(json_error, skipped=skipped)
        else:
            print_warning(message)
        return 1
    if result.status != "resolved":
        message = result.message or tr(
            "metadata.error.workflow_failed", default="Metadata workflow failed."
        )
        if json_output:
            _emit_workflow_error_json(message)
        else:
            print_error(message)
        return 1
    return None


def _emit_resolved_json(result) -> None:
    from swirrl.core.json_output import emit_json, json_envelope

    resolved = result.resolved
    emit_json(
        json_envelope(
            command="metadata.resolve",
            data={
                "provider_name": getattr(resolved, "provider_name", None),
                "provider_id": getattr(resolved, "provider_id", None),
                "imdb_id": getattr(resolved, "imdb_id", None),
                "external_url": getattr(resolved, "external_url", None),
                "title": (
                    getattr(resolved, "title", None)
                    or getattr(resolved, "episode_title", None)
                    or getattr(resolved, "series_title", None)
                ),
                "year": getattr(resolved, "year", None) or getattr(resolved, "series_year", None),
                "season_number": getattr(resolved, "season_number", None),
                "episode_number": getattr(resolved, "episode_number", None),
                "air_date": getattr(resolved, "air_date", None),
                "overview": getattr(resolved, "overview", None),
            },
        )
    )


def _handle_metadata_token_actions(
    *,
    settings: dict,
    store: SettingsStore,
    clear_requested: bool,
    prompt_token: bool,
    set_token: str | None,
    json_output: bool,
) -> int | None:
    from swirrl.core.json_output import emit_json, json_envelope

    if clear_requested:
        settings.setdefault("metadata", {})
        settings["metadata"]["tmdb_read_access_token"] = ""  # nosec B105
        store.save(settings)
        if json_output:
            emit_json(json_envelope(command="metadata.clear", data={"cleared": True}))
        else:
            print_success(tr("metadata.success.token_cleared", default="TMDb token cleared."))
        return 0
    if prompt_token:
        return _store_token_interactive(settings, store)
    if set_token:
        return _store_token_value(settings, store, set_token)
    return None


def _handle_metadata_info_actions(
    *, config, status_requested: bool, help_requested: bool, json_output: bool
) -> int | None:
    if status_requested:
        if json_output:
            _emit_status_json(config)
        else:
            _print_doctor(config)
        return 0
    if help_requested:
        _print_setup_help()
        return 0
    return None


def _resolve_release_for_metadata(resolver: PathResolver, path: str | None):
    try:
        _folder, release = _resolve_release_target(resolver, path)
        return release, None
    except (FileNotFoundError, ValueError) as exc:
        print_error(str(exc))
        return None, 1
    except Exception as exc:
        print_exception_error(exc)
        return None, 1


def run_metadata_command(
    *,
    path: str | None,
    auto_accept: bool,
    status_requested: bool,
    help_requested: bool,
    prompt_token: bool,
    set_token: str | None,
    clear_requested: bool,
    json_output: bool = False,
) -> int:
    """Drive the ``swirrl metadata`` command end-to-end.

    When ``json_output`` is ``True`` the command emits a structured envelope
    on stdout for every meaningful exit path (status, error, no candidates,
    resolved metadata) — see :func:`swirrl.core.json_output.json_envelope`.
    """
    store = SettingsStore()
    settings = store.load()
    resolver = PathResolver(settings)

    action_exit = _handle_metadata_token_actions(
        settings=settings,
        store=store,
        clear_requested=clear_requested,
        prompt_token=prompt_token,
        set_token=set_token,
        json_output=json_output,
    )
    if action_exit is not None:
        return action_exit

    config = resolve_metadata_config(settings)
    info_exit = _handle_metadata_info_actions(
        config=config,
        status_requested=status_requested,
        help_requested=help_requested,
        json_output=json_output,
    )
    if info_exit is not None:
        return info_exit

    release, resolve_exit = _resolve_release_for_metadata(resolver, path)
    if resolve_exit is not None:
        return resolve_exit
    if release is None:
        return 1

    print_module_banner("Metadata")

    try:
        result = run_metadata_workflow(
            release,
            settings,
            auto_accept=auto_accept,
            show_ui=True,
        )
    except Exception as exc:
        print_exception_error(exc, message=_format_metadata_exception(exc))
        return 1

    workflow_failure = _handle_workflow_failure(result, json_output)
    if workflow_failure is not None:
        return workflow_failure

    if json_output:
        _emit_resolved_json(result)
    else:
        _print_resolved_metadata(result.resolved)
        print_success(tr("metadata.success.resolved", default="Metadata resolved successfully."))
    return 0


@click.command(
    "metadata",
    help=tr(
        "cli.metadata.help",
        default=(
            "Search and resolve TMDb metadata for movies and TV shows.\n\n"
            "The metadata command searches The Movie Database (TMDb) for matching content, "
            "presents candidates, and resolves the correct metadata for your release.\n\n"
            "Quick examples:\n"
            "  swirrl metadata <folder>                    # Interactive metadata search\n"
            "  swirrl meta <folder> -y                     # Auto-accept top match\n"
            "  swirrl md <file.mkv>                        # Resolve single episode\n"
            "  swirrl metadata --status                    # Check configuration\n"
            "  swirrl meta --token                         # Set TMDb API token\n\n"
            "Setup:\n"
            "  1. Get a TMDb Read Access Token from https://www.themoviedb.org/settings/api\n"
            "  2. Run: swirrl metadata --token\n"
            "  3. Paste your token when prompted\n"
            "  4. Test with: swirrl meta <folder>\n\n"
            "Features:\n"
            "  • Automatic movie/TV show detection\n"
            "  • Multi-language support\n"
            "  • Interactive candidate selection\n"
            "  • Intelligent caching\n"
            "  • IMDb ID resolution\n\n"
            "Best practices:\n"
            "  • Use descriptive folder/file names for better matching\n"
            "  • Check status with --status before first use\n"
            "  • Use -y for batch processing with confidence\n"
            "  • Clear token with --clear if needed\n\n"
            "Related commands: nfo, prez, pipeline"
        ),
    ),
)
@click.argument("path_parts", nargs=-1)
@click.option(
    "-y",
    "--auto-accept",
    is_flag=True,
    help=tr(
        "cli.metadata.option.auto_accept",
        default="Automatically accept the top metadata candidate.",
    ),
)
@click.option(
    "-s",
    "--status",
    "status_requested",
    is_flag=True,
    help=tr(
        "cli.metadata.option.status", default="Show metadata credential and configuration status."
    ),
)
@click.option(
    "-i",
    "--help-setup",
    "help_requested",
    is_flag=True,
    help=tr("cli.metadata.option.help_setup", default="Show metadata setup help."),
)
@click.option(
    "-t",
    "--token",
    "prompt_token",
    is_flag=True,
    help=tr(
        "cli.metadata.option.token", default="Prompt to store a TMDb read access token locally."
    ),
)
@click.option(
    "-T",
    "--set-token",
    "set_token",
    metavar="TOKEN",
    help=tr("cli.metadata.option.set_token", default="Store a TMDb read access token locally."),
)
@click.option(
    "-c",
    "--clear",
    "clear_requested",
    is_flag=True,
    help=tr("cli.metadata.option.clear", default="Clear the locally stored TMDb token."),
)
@click.option(
    "-j",
    "--json",
    "json_output",
    is_flag=True,
    help=tr(
        "cli.metadata.option.json",
        default="Emit resolved metadata or status as JSON on stdout.",
    ),
)
def metadata_command(
    path_parts: tuple[str, ...],
    auto_accept: bool,
    status_requested: bool,
    help_requested: bool,
    prompt_token: bool,
    set_token: str | None,
    clear_requested: bool,
    json_output: bool,
) -> int:
    """Resolve TMDb metadata for a folder or single MKV file."""
    path_value = join_path_parts(path_parts) or None
    return run_metadata_command(
        path=path_value,
        auto_accept=auto_accept,
        status_requested=status_requested,
        help_requested=help_requested,
        prompt_token=prompt_token,
        set_token=set_token,
        clear_requested=clear_requested,
        json_output=json_output,
    )
