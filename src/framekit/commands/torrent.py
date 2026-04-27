from __future__ import annotations

from pathlib import Path

# Prefer rich_click if available; fall back to click when the rich integration is not installed.
try:
    import rich_click as click  # type: ignore[import-not-found]
except Exception:
    import click  # type: ignore[import-not-found]

from framekit.core.i18n import tr
from framekit.core.paths import PathResolver
from framekit.core.settings import SettingsStore
from framekit.modules.nfo.formatting import format_bytes_human
from framekit.modules.torrent.payload import (
    TorrentPayload,
    discover_torrent_payload_candidates,
    resolve_torrent_payload,
)
from framekit.modules.torrent.service import (
    TorrentBuildOptions,
    TorrentService,
    is_valid_announce_url,
)
from framekit.ui.branding import print_module_banner
from framekit.ui.console import print_error, print_exception_error, print_info, print_success
from framekit.ui.progress import framekit_progress
from framekit.ui.selector import SelectorOption, select_one


def _join_path_parts(parts: tuple[str, ...]) -> str:
    return " ".join(part for part in parts if part).strip()


def _parse_piece_length(value: str | None) -> int | None:
    raw = str(value or "auto").strip().lower()
    if raw in {"", "auto"}:
        return None
    multiplier = 1
    if raw.endswith("k"):
        multiplier = 1024
        raw = raw[:-1]
    elif raw.endswith("m"):
        multiplier = 1024 * 1024
        raw = raw[:-1]
    parsed = int(raw) * multiplier
    if parsed <= 0:
        raise ValueError(
            tr("torrent.error.invalid_piece_length", default="Piece length must be positive.")
        )
    return parsed


def _select_payload_interactively(target: Path) -> TorrentPayload:
    candidates = discover_torrent_payload_candidates(target)
    if not candidates:
        raise ValueError(
            tr("torrent.error.no_media", default="No media payload found for torrent creation.")
        )
    entries = [
        SelectorOption(
            value=str(index), label=candidate.label, hint=candidate.description, selected=False
        )
        for index, candidate in enumerate(candidates)
    ]
    chosen = select_one(
        title=tr("torrent.selector.content", default="Choose torrent content"),
        entries=entries,
        page_size=8,
    )
    candidate = candidates[int(str(chosen))]
    selected_set = {file.resolve() for file in candidate.files if file.exists()}
    ignored = tuple(
        sorted(
            (
                item
                for item in candidate.path.rglob("*")
                if item.is_file()
                and item.suffix.lower() != ".torrent"
                and item.resolve() not in selected_set
            ),
            key=lambda path: str(path).lower(),
        )
    )
    return TorrentPayload(
        path=candidate.path,
        files=candidate.files,
        name=candidate.name,
        ignored_files=ignored,
        mode="select",
    )


def _resolve_payload_or_error(
    target: Path, *, content_mode: str, select_content: bool
) -> TorrentPayload:
    if select_content:
        return _select_payload_interactively(target)
    return resolve_torrent_payload(target, content_mode=content_mode)


def _announce_urls(settings: dict) -> list[str]:
    torrent_settings = settings.setdefault("modules", {}).setdefault("torrent", {})
    urls = torrent_settings.get("announce_urls", [])
    result: list[str] = []
    if isinstance(urls, list):
        result = [str(item).strip() for item in urls if str(item).strip()]
    legacy = str(torrent_settings.get("announce", "") or "").strip()
    if legacy and legacy not in result:
        result.insert(0, legacy)
    return result


def _selected_announce(settings: dict) -> str:
    torrent_settings = settings.setdefault("modules", {}).setdefault("torrent", {})
    selected = str(torrent_settings.get("selected_announce", "") or "").strip()
    if selected:
        return selected
    urls = _announce_urls(settings)
    return urls[0] if urls else ""


def _save_announce_selection(store: SettingsStore, settings: dict, url: str) -> None:
    torrent_settings = settings.setdefault("modules", {}).setdefault("torrent", {})
    urls = _announce_urls(settings)
    if url not in urls:
        urls.append(url)
    torrent_settings["announce_urls"] = urls
    torrent_settings["selected_announce"] = url
    torrent_settings["announce"] = url
    store.save(settings)


def _print_announces(settings: dict) -> None:
    selected = _selected_announce(settings)
    urls = _announce_urls(settings)
    if not urls:
        print_info(tr("torrent.announce.none", default="No announce URL configured."))
        return
    for url in urls:
        marker = "*" if url == selected else "-"
        print_info(f"{marker} {url}")


def run_torrent_config_command(
    *,
    add_announce: str | None,
    set_announce: str | None,
    list_announces: bool,
    select_announce: bool,
) -> int:
    store = SettingsStore()
    settings = store.load()
    print_module_banner("Torrent")

    if list_announces:
        _print_announces(settings)
        return 0

    requested = add_announce or set_announce
    if requested:
        url = requested.strip()
        if not is_valid_announce_url(url):
            print_error(
                tr(
                    "torrent.error.invalid_announce",
                    default="Tracker announce must be a valid http(s) or udp URL.",
                )
            )
            return 1
        _save_announce_selection(store, settings, url)
        print_success(
            tr("torrent.success.announce_saved", default="Announce URL saved: {url}", url=url)
        )
        return 0

    if select_announce:
        urls = _announce_urls(settings)
        if not urls:
            print_error(tr("torrent.error.no_announces", default="No announce URL configured yet."))
            return 1
        try:
            chosen = select_one(
                title=tr("torrent.selector.announce", default="Torrent announce URL"),
                entries=[SelectorOption(value=url, label=url, selected=False) for url in urls],
                page_size=8,
            )
        except KeyboardInterrupt:
            return 1
        if chosen:
            _save_announce_selection(store, settings, str(chosen))
            print_success(
                tr(
                    "torrent.success.announce_selected",
                    default="Selected announce URL: {url}",
                    url=chosen,
                )
            )
            return 0

    _print_announces(settings)
    return 0


def run_torrent_command(
    *,
    path: str | None,
    output: str | None,
    announce: str | None,
    private: bool | None,
    piece_length: str | None,
    dry_run: bool,
    content_mode: str = "auto",
    select_content: bool = False,
    add_announce: str | None = None,
    set_announce: str | None = None,
    list_announces: bool = False,
    select_announce: bool = False,
) -> int:
    if add_announce or set_announce or list_announces or select_announce:
        return run_torrent_config_command(
            add_announce=add_announce,
            set_announce=set_announce,
            list_announces=list_announces,
            select_announce=select_announce,
        )

    store = SettingsStore()
    settings = store.load()
    resolver = PathResolver(settings)

    print_module_banner("Torrent")

    target = resolver.resolve_start_folder("torrent", path or None)
    if path:
        target = Path(path)
    if not target.exists():
        print_error(
            tr("torrent.error.path_not_found", default="Path not found: {path}", path=target)
        )
        return 1

    torrent_settings = settings.setdefault("modules", {}).setdefault("torrent", {})
    final_announce = announce.strip() if announce is not None else _selected_announce(settings)
    if final_announce and not is_valid_announce_url(final_announce):
        print_error(
            tr(
                "torrent.error.invalid_announce",
                default="Tracker announce must be a valid http(s) or udp URL.",
            )
        )
        return 1
    final_private = bool(torrent_settings.get("private", True)) if private is None else private

    try:
        payload = _resolve_payload_or_error(
            target, content_mode=content_mode, select_content=select_content
        )
        payload_files = list(payload.files)
        total_size = sum(path.stat().st_size for path in payload_files)
        with framekit_progress(
            tr("torrent.progress.hashing", default="Hashing torrent payload"),
            total=total_size,
            unit="bytes",
            total_files=len(payload_files) if len(payload_files) > 1 else None,
        ) as advance:
            options = TorrentBuildOptions(
                announce=final_announce,
                private=final_private,
                piece_length=_parse_piece_length(
                    piece_length or str(torrent_settings.get("piece_length", "auto") or "auto")
                ),
                output_path=Path(output) if output else None,
                progress_callback=advance,
                payload_files=tuple(payload_files),
                payload_name=payload.name,
            )
            _report, result = TorrentService().build(
                payload.path, options=options, write=not dry_run
            )
    except Exception as exc:
        print_exception_error(exc)
        return 1

    print_info(tr("common.source", default="Source") + f": {payload.path}")
    print_info(tr("torrent.info.content_mode", default="Content mode") + f": {payload.mode}")
    if payload.ignored_files:
        print_info(
            tr("torrent.info.ignored_files", default="Ignored files")
            + f": {len(payload.ignored_files)}"
        )
    print_info(tr("common.files", default="Files") + f": {result.files_count}")
    print_info(
        tr("common.size", default="Size")
        + f": {format_bytes_human(getattr(result, 'total_size', total_size))}"
    )
    print_info(
        tr("torrent.info.piece_length", default="Piece length")
        + f": {format_bytes_human(result.piece_length)}"
    )
    print_info(tr("torrent.info.pieces", default="Pieces") + f": {result.pieces_count}")

    if dry_run:
        print_success(tr("torrent.success.dry_run", default="Torrent dry-run completed."))
    else:
        print_success(
            tr(
                "torrent.success.written",
                default="Torrent written: {path}",
                path=result.output_path,
            )
        )

    torrent_settings["last_folder"] = str(
        payload.path if payload.path.is_dir() else payload.path.parent
    )
    store.save(settings)
    return 0


@click.command("torrent", help=tr("cli.torrent.help", default="Create a .torrent file."))
@click.argument("path_parts", nargs=-1)
@click.option(
    "-o", "--output", help=tr("cli.torrent.option.output", default="Output .torrent path.")
)
@click.option(
    "-a", "--announce", help=tr("cli.torrent.option.announce", default="Tracker announce URL.")
)
@click.option(
    "--private/--public",
    "private",
    default=None,
    help=tr("cli.torrent.option.private", default="Set private flag."),
)
@click.option(
    "--piece-length",
    help=tr("cli.torrent.option.piece_length", default="Piece length: auto, 512K, 1M, 2097152."),
)
@click.option(
    "--dry-run",
    is_flag=True,
    help=tr("cli.torrent.option.dry_run", default="Hash and preview without writing."),
)
@click.option(
    "--content",
    "content_mode",
    type=click.Choice(["auto", "media", "folder"]),
    default="auto",
    show_default=True,
    help=tr("cli.torrent.option.content", default="Torrent content resolution mode."),
)
@click.option(
    "--select-content",
    is_flag=True,
    help=tr(
        "cli.torrent.option.select_content", default="Interactively choose the torrent payload."
    ),
)
@click.option(
    "--set-announce",
    help=tr(
        "cli.torrent.option.set_announce",
        default="Save and select the default tracker announce URL.",
    ),
)
@click.option(
    "--add-announce",
    help=tr(
        "cli.torrent.option.add_announce",
        default="Add an announce URL to the saved list and select it.",
    ),
)
@click.option(
    "--list-announces",
    is_flag=True,
    help=tr("cli.torrent.option.list_announces", default="List configured announce URLs."),
)
@click.option(
    "--select-announce",
    is_flag=True,
    help=tr(
        "cli.torrent.option.select_announce",
        default="Choose the default announce URL interactively.",
    ),
)
def torrent_command(
    path_parts: tuple[str, ...],
    output: str | None,
    announce: str | None,
    private: bool | None,
    piece_length: str | None,
    dry_run: bool,
    content_mode: str = "auto",
    select_content: bool = False,
    add_announce: str | None = None,
    set_announce: str | None = None,
    list_announces: bool = False,
    select_announce: bool = False,
) -> int:
    return run_torrent_command(
        path=_join_path_parts(path_parts) or None,
        output=output,
        announce=announce,
        private=private,
        piece_length=piece_length,
        dry_run=dry_run,
        content_mode=content_mode,
        select_content=select_content,
        add_announce=add_announce,
        set_announce=set_announce,
        list_announces=list_announces,
        select_announce=select_announce,
    )
