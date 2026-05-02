from __future__ import annotations

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
from framekit.core.settings import SettingsStore
from framekit.modules.metadata.config import (
    looks_like_tmdb_api_key,
    looks_like_tmdb_read_access_token,
    mask_secret,
    normalize_secret_input,
    resolve_metadata_config,
)
from framekit.modules.metadata.workflow import run_metadata_workflow
from framekit.modules.nfo.builder import build_release_nfo
from framekit.modules.nfo.scanner import scan_nfo_folder
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
    table.add_row(tr("common.api_key", default="API Key"), mask_secret(config.tmdb_api_key or ""))

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
            settings["metadata"]["tmdb_read_access_token"] = ""
            settings["metadata"]["tmdb_api_key"] = ""
            store.save(settings)
            print_success(tr("metadata.success.token_cleared", default="TMDb token cleared."))
            return 0

        if not raw:
            print_error(tr("metadata.error.token_empty", default="Token cannot be empty."))
            continue

        token = normalize_secret_input(raw)

        if looks_like_tmdb_api_key(token):
            print_error(
                tr(
                    "metadata.error.api_key_instead_token",
                    default="That looks like a TMDb API key, not a TMDb read access token.",
                )
            )
            continue

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
        settings["metadata"]["tmdb_api_key"] = ""
        store.save(settings)
        print_success(tr("metadata.success.token_saved", default="TMDb token saved."))
        return 0


def _store_token_value(settings: dict, store: SettingsStore, raw_value: str) -> int:
    token = normalize_secret_input(raw_value)

    if looks_like_tmdb_api_key(token):
        print_error(
            tr(
                "metadata.error.api_key_instead_token",
                default="That looks like a TMDb API key, not a TMDb read access token.",
            )
        )
        return 1

    if not looks_like_tmdb_read_access_token(token):
        print_error(
            tr(
                "metadata.error.invalid_token",
                default="That does not look like a valid TMDb read access token.",
            )
        )
        return 1

    settings.setdefault("metadata", {})
    settings["metadata"]["tmdb_read_access_token"] = token
    settings["metadata"]["tmdb_api_key"] = ""
    store.save(settings)
    print_success(tr("metadata.success.token_saved", default="TMDb token saved."))
    return 0


def _print_resolved_metadata(resolved) -> None:
    table = Table(
        title=tr("metadata.resolved_title", default="Resolved Metadata"),
        expand=True,
        box=box.HEAVY,
        border_style="white",
    )
    table.add_column(tr("common.field", default="Field"), width=20, no_wrap=True)
    table.add_column(tr("common.value", default="Value"), ratio=1)

    provider_name = getattr(resolved, "provider_name", None)
    provider_id = getattr(resolved, "provider_id", None)
    imdb_id = getattr(resolved, "imdb_id", None)
    external_url = getattr(resolved, "external_url", None)

    title = (
        getattr(resolved, "title", None)
        or getattr(resolved, "episode_title", None)
        or getattr(resolved, "series_title", None)
    )
    year = getattr(resolved, "year", None) or getattr(resolved, "series_year", None)
    season_number = getattr(resolved, "season_number", None)
    episode_number = getattr(resolved, "episode_number", None)
    air_date = getattr(resolved, "air_date", None)
    overview = getattr(resolved, "overview", None)

    table.add_row(tr("common.provider", default="Provider"), provider_name or "-")
    table.add_row(tr("metadata.provider_id", default="Provider ID"), provider_id or "-")
    table.add_row(tr("common.title", default="Title"), title or "-")
    table.add_row(tr("common.year", default="Year"), str(year) if year is not None else "-")
    table.add_row(
        tr("metadata.season", default="Season"),
        str(season_number) if season_number is not None else "-",
    )
    table.add_row(
        tr("metadata.episode", default="Episode"),
        str(episode_number) if episode_number is not None else "-",
    )
    table.add_row(tr("metadata.air_date", default="Air Date"), air_date or "-")
    table.add_row(tr("metadata.imdb_id", default="IMDb ID"), imdb_id or "-")
    table.add_row(tr("metadata.imdb_url", default="IMDb URL"), external_url or "-")

    console.print(table)

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


def run_metadata_command(
    *,
    path: str | None,
    auto_accept: bool,
    status_requested: bool,
    help_requested: bool,
    prompt_token: bool,
    set_token: str | None,
    clear_requested: bool,
) -> int:
    store = SettingsStore()
    settings = store.load()
    resolver = PathResolver(settings)

    if clear_requested:
        settings.setdefault("metadata", {})
        settings["metadata"]["tmdb_read_access_token"] = ""
        settings["metadata"]["tmdb_api_key"] = ""
        store.save(settings)
        print_success(tr("metadata.success.token_cleared", default="TMDb token cleared."))
        return 0

    if prompt_token:
        return _store_token_interactive(settings, store)

    if set_token:
        return _store_token_value(settings, store, set_token)

    config = resolve_metadata_config(settings)

    if status_requested:
        _print_doctor(config)
        return 0

    if help_requested:
        _print_setup_help()
        return 0

    folder = resolver.resolve_start_folder("nfo", path or None)
    # Support both directories and single MKV files.  When a file is provided
    # ensure it is an MKV; otherwise report an error.  This avoids requiring
    # callers to create a separate folder for each episode when resolving
    # metadata.
    if not folder.exists():
        print_error(
            tr(
                "cleanmkv.error.folder_not_found",
                default="Folder not found: {folder}",
                folder=folder,
            )
        )
        return 1

    is_single_file = False
    selected_file: Path | None = None
    scan_root = folder
    if folder.is_file():
        # Validate that the provided file is an MKV.  Metadata resolution
        # operates only on MKV containers.
        if folder.suffix.lower() != ".mkv":
            print_error(
                tr(
                    "cleanmkv.error.invalid_file_type",
                    default="File is not an MKV: {file}",
                    file=folder,
                )
            )
            return 1
        is_single_file = True
        selected_file = folder
        scan_root = folder.parent
    elif not folder.is_dir():
        # Neither a file nor a directory
        print_error(
            tr(
                "cleanmkv.error.folder_not_found",
                default="Folder not found: {folder}",
                folder=folder,
            )
        )
        return 1

    try:
        if is_single_file:
            # Build a release using only the selected file.  Scan the parent
            # directory for episodes then filter to the chosen file.  If no
            # matching episode is found, report an error.
            episodes = scan_nfo_folder(scan_root)
            episodes = [ep for ep in episodes if ep.file_path == selected_file]
            if not episodes:
                print_error(
                    tr(
                        "nfo.error.no_mkv",
                        default="No MKV files found in folder: {folder}",
                        folder=folder,
                    )
                )
                return 1
            release = build_release_nfo(scan_root, episodes)
        else:
            release = _build_release_from_folder(folder)
    except Exception as exc:
        print_exception_error(exc)
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

    if result.status == "missing_credentials":
        print_warning(
            tr("metadata.warning.missing_credentials", default="Metadata credentials are missing.")
        )
        print_info(tr("metadata.info.run_setup", default="Run: framekit setup"))
        print_info(tr("metadata.info.check_status", default="Or check status with: framekit md -s"))
        return 1

    if result.status == "unsupported_specials":
        print_warning(
            result.message
            or tr(
                "metadata.warning.unsupported_specials",
                default="Special season detected. Metadata is not supported for this case yet.",
            )
        )
        return 1

    if result.status == "no_candidates":
        print_warning(tr("metadata.warning.no_candidates", default="No metadata candidates found."))
        return 1

    if result.status == "cancelled":
        print_warning(
            tr("metadata.warning.selection_cancelled", default="Metadata selection cancelled.")
        )
        return 1

    if result.status != "resolved":
        print_error(
            result.message
            or tr("metadata.error.workflow_failed", default="Metadata workflow failed.")
        )
        return 1

    _print_resolved_metadata(result.resolved)
    print_success(tr("metadata.success.resolved", default="Metadata resolved successfully."))
    return 0


@click.command(
    "metadata", help=tr("cli.metadata.help", default="Search and resolve metadata for a folder.")
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
    "-d",
    "--doctor",
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
def metadata_command(
    path_parts: tuple[str, ...],
    auto_accept: bool,
    status_requested: bool,
    help_requested: bool,
    prompt_token: bool,
    set_token: str | None,
    clear_requested: bool,
) -> int:
    path_value = _join_path_parts(path_parts) or None
    return run_metadata_command(
        path=path_value,
        auto_accept=auto_accept,
        status_requested=status_requested,
        help_requested=help_requested,
        prompt_token=prompt_token,
        set_token=set_token,
        clear_requested=clear_requested,
    )
