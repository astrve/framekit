from __future__ import annotations

import sys
from pathlib import Path

from ouro.core.cli_helpers import join_path_parts
from ouro.core.http import redact_url
from ouro.core.i18n import tr
from ouro.core.paths import PathResolver
from ouro.core.settings import SettingsStore
from ouro.modules.nfo.formatting import format_bytes_human
from ouro.modules.torrent.payload import (
    TorrentPayload,
    discover_torrent_payload_candidates,
    resolve_torrent_payload,
)
from ouro.modules.torrent.service import (
    TorrentBuildOptions,
    TorrentService,
    is_valid_announce_url,
)
from ouro.ui.branding import print_module_banner

# Prefer rich_click if available; fall back to click when the rich integration is not installed.
from ouro.ui.click_helper import click
from ouro.ui.console import (
    print_error,
    print_exception_error,
    print_info,
    print_success,
    print_warning,
)
from ouro.ui.progress import ouro_progress
from ouro.ui.unified_selector import SelectorOption, confirm_choice
from ouro.ui.unified_selector import select_one as _select_one


def _read_piece_length_from_torrent(torrent_path: Path) -> int | None:
    """Read piece length from an existing .torrent file for cross-seeding."""
    try:
        raw = torrent_path.read_bytes()
    except OSError:
        return None
    try:
        decoded = _bdecode(raw)
    except (ValueError, KeyError):
        return None
    # Bencoded payloads are heterogeneous (int / bytes / list / dict). A
    # well-formed .torrent file has a top-level dict; defensively bail out
    # otherwise so static type checkers and runtime both treat the function
    # as "best-effort, returns None on any malformed input".
    if not isinstance(decoded, dict):
        return None
    info = decoded.get(b"info") or decoded.get("info")
    if not isinstance(info, dict):
        return None
    piece_length = info.get(b"piece length") or info.get("piece length")
    if isinstance(piece_length, int) and piece_length > 0:
        return piece_length
    return None


def _bdecode(data: bytes):
    """Minimal bencoding decoder for reading .torrent metadata."""

    def _decode(data: bytes, idx: int):
        if idx >= len(data):
            raise ValueError("Unexpected end of bencode payload")
        if data[idx : idx + 1] == b"i":
            end = data.index(b"e", idx + 1)
            return int(data[idx + 1 : end]), end + 1
        elif data[idx : idx + 1] == b"l":
            result = []
            idx += 1
            if idx >= len(data):
                raise ValueError("Unterminated bencode list")
            while data[idx : idx + 1] != b"e":
                val, idx = _decode(data, idx)
                result.append(val)
                if idx >= len(data):
                    raise ValueError("Unterminated bencode list")
            return result, idx + 1
        elif data[idx : idx + 1] == b"d":
            result = {}
            idx += 1
            if idx >= len(data):
                raise ValueError("Unterminated bencode dict")
            while data[idx : idx + 1] != b"e":
                key, idx = _decode(data, idx)
                val, idx = _decode(data, idx)
                result[key] = val
                if idx >= len(data):
                    raise ValueError("Unterminated bencode dict")
            return result, idx + 1
        elif data[idx : idx + 1].isdigit():
            colon = data.index(b":", idx)
            length = int(data[idx:colon])
            start = colon + 1
            end = start + length
            if end > len(data):
                raise ValueError("Truncated bencode byte string")
            return data[start:end], end
        else:
            raise ValueError(f"Invalid bencode at position {idx}")

    result, consumed = _decode(data, 0)
    if consumed != len(data):
        raise ValueError("Trailing bytes after valid bencode payload")
    return result


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
    target: Path, *, content_mode: str, select_content: bool, allow_ambiguous: bool = False
) -> tuple[TorrentPayload, str | None]:
    """Resolve torrent payload with optional ambiguity handling.

    Returns:
        A tuple of (TorrentPayload, warning_message).
    """
    if select_content:
        return (_select_payload_interactively(target), None)
    return resolve_torrent_payload(
        target, content_mode=content_mode, allow_ambiguous=allow_ambiguous
    )


_ENCRYPTED = "<encrypted>"


class _PayloadSelectionCancelled(RuntimeError):
    """Raised when user cancels interactive multi-group selection."""


def _raw_announce_urls(settings: dict) -> list[str]:
    torrent_settings = settings.setdefault("modules", {}).setdefault("torrent", {})
    urls = torrent_settings.get("announce_urls", [])
    if not isinstance(urls, list):
        return []
    return [str(item).strip() for item in urls if str(item).strip()]


def _print_vault_fix_hint() -> None:
    print_info(
        tr(
            "torrent.info.vault_fix",
            default="Solutions:\n"
            "  1. Run 'ouro settings security status' to check vault status\n"
            "  2. Run 'ouro settings security set-announces <url>' to reconfigure\n"
            "  3. Run 'ouro setup' to restore vault access",
        )
    )


def _prompt_save_announce_enabled(settings: dict) -> bool:
    torrent_settings = settings.setdefault("modules", {}).setdefault("torrent", {})
    return bool(torrent_settings.get("prompt_save_announce", True))


def _select_save_announce_action() -> str | None:
    try:
        selected = select_one(
            title=tr(
                "torrent.prompt.save_announce",
                default="Voulez-vous enregistrer cette announce pour les prochaines fois ?",
            ),
            entries=[
                SelectorOption(
                    value="yes",
                    label=tr("common.yes", default="Yes"),
                    hint=tr(
                        "torrent.prompt.save_announce.yes_hint",
                        default="Sauvegarder l'annonce sélectionnée dans le vault si la sécurité est activée.",
                    ),
                    selected=True,
                ),
                SelectorOption(
                    value="no",
                    label=tr("common.no", default="No"),
                    hint=tr(
                        "torrent.prompt.save_announce.no_hint",
                        default="Utiliser cette announce uniquement pour cette exécution.",
                    ),
                ),
                SelectorOption(
                    value="never",
                    label=tr(
                        "torrent.prompt.save_announce.never",
                        default="Non, ne plus afficher ce message",
                    ),
                    hint=tr(
                        "torrent.prompt.save_announce.never_hint",
                        default="Désactiver cette question dans ouro.yaml.",
                    ),
                ),
            ],
            page_size=6,
            default="no" if not sys.stdin.isatty() else None,
        )
    except (KeyboardInterrupt, EOFError):
        return None
    return str(selected) if selected else None


def _disable_save_announce_prompt(store: SettingsStore, settings: dict) -> None:
    settings.setdefault("modules", {}).setdefault("torrent", {})["prompt_save_announce"] = False
    store.save(settings)


def _maybe_save_prompted_announce(*, store: SettingsStore, settings: dict, url: str) -> None:
    if not _prompt_save_announce_enabled(settings):
        return

    action = _select_save_announce_action()
    if action == "yes":
        _save_announce_selection(store, settings, url)
        print_success(
            tr(
                "torrent.success.announce_saved_prompt",
                default="Announce URL saved. Continuing.",
            )
        )
        return

    if action == "never":
        _disable_save_announce_prompt(store, settings)
        print_info(
            tr(
                "torrent.info.save_announce_prompt_disabled",
                default="Cette question ne sera plus affichée.",
            )
        )
        return

    print_info(
        tr(
            "torrent.info.announce_not_saved",
            default="Announce utilisée pour cette exécution uniquement.",
        )
    )


def _decrypt_torrent_announces() -> list[str]:
    try:
        from ouro.core.settings import Settings

        decrypted = Settings().get_torrent_announces()
        if not decrypted:
            print_error(
                tr(
                    "torrent.error.vault_announces_unavailable",
                    default="Announce URLs are encrypted but vault is unavailable.",
                )
            )
            _print_vault_fix_hint()
        return decrypted
    except Exception as exc:
        print_error(
            tr(
                "torrent.error.announce_decrypt_failed",
                default="Failed to decrypt announce URLs: {error}",
                error=str(exc),
            )
        )
        _print_vault_fix_hint()
        return []


def _announce_urls(settings: dict) -> list[str]:
    torrent_settings = settings.setdefault("modules", {}).setdefault("torrent", {})
    result = _raw_announce_urls(settings)

    if result and len(result) == 1 and result[0] == _ENCRYPTED:
        result = _decrypt_torrent_announces()

    legacy = str(torrent_settings.get("announce", "") or "").strip()
    # Don't add legacy announce if it's the encrypted placeholder
    if legacy and legacy != _ENCRYPTED and legacy not in result:
        result.insert(0, legacy)
    return result


def _prompt_for_announce_and_save(settings: dict) -> str:
    """Interactively ask for an announce URL and optionally persist it.

    Triggered when the user runs ``ouro torrent`` without any announce
    configured. On a non-TTY (CI/headless) prints the error path the previous
    behaviour used and returns ``""``. On a TTY, prompts for a URL, validates it,
    then asks whether it should be saved via ``Settings`` (vault or plaintext
    depending on ``security.enabled``). The valid URL is returned even when the
    user chooses not to save it.

    Args:
        settings: Loaded settings dict from ``SettingsStore.load()``. The
            dict is mutated in place to reflect the saved announce so the
            rest of the command sees the new value.

    Returns:
        The validated announce URL, or ``""`` when the user cancelled or the
        terminal is non-interactive.
    """
    if not sys.stdin.isatty():
        print_error(
            tr(
                "torrent.error.no_announce",
                default=(
                    "No announce URL configured. Run "
                    "'ouro settings security set-announces' (with security "
                    "enabled) or pass '--announce <url>' on the command line."
                ),
            )
        )
        return ""

    print_warning(
        tr(
            "torrent.warning.no_announce_prompt",
            default=(
                "No announce URL is configured yet. Enter one now to continue "
                "(leave blank to abort)."
            ),
        )
    )
    raw = click.prompt(
        tr("torrent.prompt.announce", default="Announce URL"),
        default="",
        show_default=False,
    )
    url = raw.strip()
    if not url:
        print_info(
            tr("torrent.info.no_announce_aborted", default="No announce provided. Aborting.")
        )
        return ""

    if not is_valid_announce_url(url):
        print_error(
            tr(
                "torrent.error.invalid_announce",
                default="Tracker announce must be a valid http(s) or udp URL.",
            )
        )
        return ""

    try:
        _maybe_save_prompted_announce(store=SettingsStore(), settings=settings, url=url)
    except Exception as exc:
        print_error(
            tr(
                "torrent.error.save_announce_failed",
                default="Could not save announce URL: {error}",
                error=str(exc),
            )
        )
    return url


def _selected_announce(settings: dict) -> str:
    torrent_settings = settings.setdefault("modules", {}).setdefault("torrent", {})
    selected = str(torrent_settings.get("selected_announce", "") or "").strip()

    if selected == _ENCRYPTED:
        try:
            from ouro.core.settings import Settings

            url = Settings().get_selected_announce()
            if not url:
                print_error(
                    tr(
                        "torrent.error.vault_announce_unavailable",
                        default="Selected announce URL is encrypted but vault returned empty value.",
                    )
                )
                _print_vault_fix_hint()
            return url
        except Exception as exc:
            print_error(
                tr(
                    "torrent.error.announce_decrypt_failed",
                    default="Failed to decrypt announce URL: {error}",
                    error=str(exc),
                )
            )
            _print_vault_fix_hint()
            return ""

    if selected:
        return selected
    urls = _announce_urls(settings)
    return urls[0] if urls else ""


def _save_announce_selection(store: SettingsStore, settings: dict, url: str) -> None:
    from ouro.core.settings import Settings

    settings_obj = Settings()
    if settings_obj.is_security_enabled():
        settings_obj.set_selected_announce(url)
        # Reload mutated YAML into the caller's dict so subsequent reads see placeholder
        settings.clear()
        settings.update(store.load())
        return

    torrent_settings = settings.setdefault("modules", {}).setdefault("torrent", {})
    urls = _announce_urls(settings)
    if url not in urls:
        urls.append(url)
    torrent_settings["announce_urls"] = urls
    torrent_settings["selected_announce"] = url
    torrent_settings["announce"] = url
    store.save(settings)


def _print_announces(settings: dict) -> None:
    torrent_settings = settings.get("modules", {}).get("torrent", {})
    raw_urls = torrent_settings.get("announce_urls", [])
    raw_selected = str(torrent_settings.get("selected_announce", "") or "").strip()
    is_encrypted = (
        isinstance(raw_urls, list) and len(raw_urls) == 1 and raw_urls[0] == _ENCRYPTED
    ) or raw_selected == _ENCRYPTED

    selected = _selected_announce(settings)
    urls = _announce_urls(settings)

    if not urls:
        if is_encrypted:
            print_error(
                tr(
                    "torrent.error.vault_announces_locked",
                    default="Announce URLs are encrypted but vault is unavailable. Run `ouro setup` to restore access.",
                )
            )
        else:
            print_info(tr("torrent.announce.none", default="No announce URL configured."))
        return

    if is_encrypted:
        print_info(
            tr(
                "torrent.announce.encrypted_ok",
                default="Announce URLs are encrypted (vault unlocked).",
            )
        )
    for url in urls:
        marker = "*" if url == selected else "-"
        # SECURITY: Redact sensitive query parameters (passkey, authkey, etc.)
        redacted = redact_url(url)
        print_info(f"{marker} {redacted}")


def run_torrent_config_command(
    *,
    add_announce: str | None,
    set_announce: str | None,
    list_announces: bool,
    select_announce: bool,
) -> int:
    """Run torrent config command."""
    store = SettingsStore()
    settings = store.load()
    print_module_banner("Torrent")

    if list_announces:
        _print_announces(settings)
        return 0

    requested = add_announce or set_announce
    if requested:
        url = requested.strip()
        if url != _ENCRYPTED and not is_valid_announce_url(url):
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
        return _handle_select_announce(store, settings)

    _print_announces(settings)
    return 0


def _handle_select_announce(store: SettingsStore, settings: dict) -> int:
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
    if not chosen:
        return 0
    _save_announce_selection(store, settings, str(chosen))
    print_success(
        tr(
            "torrent.success.announce_selected",
            default="Selected announce URL: {url}",
            url=chosen,
        )
    )
    return 0


def _resolve_payload_for_mode(
    *,
    target: Path,
    content_mode: str,
    select_content: bool,
    is_headless: bool,
) -> tuple[TorrentPayload, str | None]:
    try:
        return _resolve_payload_or_error(
            target, content_mode=content_mode, select_content=select_content, allow_ambiguous=False
        )
    except ValueError as exc:
        error_msg = str(exc)
        if "Multiple media groups detected" not in error_msg:
            raise

        if is_headless:
            print_warning(error_msg)
            print_warning(
                tr(
                    "torrent.warning.proceeding_headless",
                    default="Proceeding with first group in headless mode.",
                )
            )
            return _resolve_payload_or_error(
                target,
                content_mode=content_mode,
                select_content=select_content,
                allow_ambiguous=True,
            )

        print_error(error_msg)
        print_info(
            tr(
                "torrent.info.multi_group_prompt",
                default="The first group will be used if you proceed.",
            )
        )
        confirmed = confirm_choice(
            title=tr(
                "torrent.confirm.proceed_anyway",
                default="Do you want to proceed anyway?",
            ),
            default=False,
        )
        if not confirmed:
            print_info(tr("common.cancelled", default="Cancelled."))
            raise _PayloadSelectionCancelled("cancelled") from None
        return _resolve_payload_or_error(
            target,
            content_mode=content_mode,
            select_content=select_content,
            allow_ambiguous=True,
        )


def _resolve_effective_piece_length(
    *,
    cross_seed_torrent: str | None,
    piece_length: str | None,
    torrent_settings: dict,
) -> int | None:
    if cross_seed_torrent:
        cs_path = Path(cross_seed_torrent)
        effective_piece_length = _read_piece_length_from_torrent(cs_path)
        if effective_piece_length is None:
            raise ValueError(
                tr(
                    "torrent.error.cross_seed_read_failed",
                    default="Could not read piece length from: {path}",
                    path=cs_path,
                )
            )
        print_info(
            tr(
                "torrent.info.cross_seed_piece_length",
                default="Cross-seed: using piece length {size} from {path}",
                size=format_bytes_human(effective_piece_length),
                path=cs_path.name,
            )
        )
        return effective_piece_length

    return _parse_piece_length(
        piece_length or str(torrent_settings.get("piece_length", "auto") or "auto")
    )


def _resolve_torrent_target(path: str | None, resolver: PathResolver) -> Path:
    target = Path(path) if path else resolver.resolve_start_folder("torrent", path or None)
    if not target.exists():
        raise FileNotFoundError(
            tr("torrent.error.path_not_found", default="Path not found: {path}", path=target)
        )
    return target


def _resolve_announce_and_private(
    *,
    settings: dict,
    announce: str | None,
    private: bool | None,
) -> tuple[str, bool, dict]:
    torrent_settings = settings.setdefault("modules", {}).setdefault("torrent", {})
    final_announce = announce.strip() if announce is not None else _selected_announce(settings)
    if not final_announce:
        final_announce = _prompt_for_announce_and_save(settings)
    if not final_announce:
        raise ValueError("missing_announce")
    if not is_valid_announce_url(final_announce):
        raise ValueError("invalid_announce")

    final_private = bool(torrent_settings.get("private", True)) if private is None else private
    return final_announce, final_private, torrent_settings


def _build_torrent_with_progress(
    *,
    payload: TorrentPayload,
    output: str | None,
    final_announce: str,
    final_private: bool,
    effective_piece_length: int | None,
    dry_run: bool,
):
    payload_files = list(payload.files)
    total_size = sum(path.stat().st_size for path in payload_files)
    with ouro_progress(
        tr("torrent.progress.hashing", default="Hashing torrent payload"),
        total=total_size,
        unit="bytes",
        total_files=len(payload_files) if len(payload_files) > 1 else None,
    ) as advance:
        options = TorrentBuildOptions(
            announce=final_announce,
            private=final_private,
            piece_length=effective_piece_length,
            output_path=Path(output) if output else None,
            progress_callback=advance,
            payload_files=tuple(payload_files),
            payload_name=payload.name,
        )
        _report, result = TorrentService().build(payload.path, options=options, write=not dry_run)
    return result, total_size


def _print_torrent_result(payload: TorrentPayload, result, total_size: int, dry_run: bool) -> None:
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


def _try_resolve_torrent_target(
    path: str | None, resolver: PathResolver
) -> tuple[int | None, Path | None]:
    try:
        return None, _resolve_torrent_target(path, resolver)
    except FileNotFoundError as exc:
        print_error(str(exc))
        return 1, None


def _try_resolve_announce_and_private(
    *,
    settings: dict,
    announce: str | None,
    private: bool | None,
):
    try:
        final_announce, final_private, torrent_settings = _resolve_announce_and_private(
            settings=settings,
            announce=announce,
            private=private,
        )
        return None, final_announce, final_private, torrent_settings
    except ValueError as exc:
        if str(exc) != "missing_announce":
            print_error(
                tr(
                    "torrent.error.invalid_announce",
                    default="Tracker announce must be a valid http(s) or udp URL.",
                )
            )
        return 1, "", False, {}


def _try_resolve_payload(
    *,
    target: Path,
    content_mode: str,
    select_content: bool,
):
    try:
        payload, warning = _resolve_payload_for_mode(
            target=target,
            content_mode=content_mode,
            select_content=select_content,
            is_headless=not sys.stdin.isatty(),
        )
        return None, payload, warning
    except (KeyboardInterrupt, _PayloadSelectionCancelled):
        return 1, None, None
    except Exception as exc:
        print_exception_error(exc)
        return 1, None, None


def _try_resolve_piece_length(
    *,
    cross_seed_torrent: str | None,
    piece_length: str | None,
    torrent_settings: dict,
) -> tuple[int | None, int | None]:
    try:
        resolved = _resolve_effective_piece_length(
            cross_seed_torrent=cross_seed_torrent,
            piece_length=piece_length,
            torrent_settings=torrent_settings,
        )
        return None, resolved
    except ValueError as exc:
        print_error(str(exc))
        return 1, None


def _try_build_torrent(
    *,
    payload: TorrentPayload,
    output: str | None,
    final_announce: str,
    final_private: bool,
    effective_piece_length: int | None,
    dry_run: bool,
):
    try:
        result, total_size = _build_torrent_with_progress(
            payload=payload,
            output=output,
            final_announce=final_announce,
            final_private=final_private,
            effective_piece_length=effective_piece_length,
            dry_run=dry_run,
        )
        return None, result, total_size
    except Exception as exc:
        print_exception_error(exc)
        return 1, None, None


def _handle_torrent_config_request(
    *,
    add_announce: str | None,
    set_announce: str | None,
    list_announces: bool,
    select_announce: bool,
) -> int | None:
    if not any([add_announce, set_announce, list_announces, select_announce]):
        return None
    return run_torrent_config_command(
        add_announce=add_announce,
        set_announce=set_announce,
        list_announces=list_announces,
        select_announce=select_announce,
    )


def _is_build_failed(build_code: int | None, result, total_size: int | None) -> bool:
    return build_code is not None or result is None or total_size is None


def _execute_torrent_pipeline(
    *,
    settings: dict,
    resolver: PathResolver,
    path: str | None,
    output: str | None,
    announce: str | None,
    private: bool | None,
    piece_length: str | None,
    dry_run: bool,
    content_mode: str,
    select_content: bool,
    cross_seed_torrent: str | None,
) -> int:
    target_code, target = _try_resolve_torrent_target(path, resolver)
    if target_code is not None:
        return 1
    if target is None:
        return 1

    announce_code, final_announce, final_private, torrent_settings = (
        _try_resolve_announce_and_private(
            settings=settings,
            announce=announce,
            private=private,
        )
    )
    if announce_code is not None:
        return 1

    payload_code, payload, warning = _try_resolve_payload(
        target=target,
        content_mode=content_mode,
        select_content=select_content,
    )
    if payload_code is not None:
        return 1
    assert payload is not None, "payload should be available on successful resolution"  # nosec B101
    if warning:
        print_warning(warning)

    piece_code, effective_piece_length = _try_resolve_piece_length(
        cross_seed_torrent=cross_seed_torrent,
        piece_length=piece_length,
        torrent_settings=torrent_settings,
    )
    if piece_code is not None:
        return 1

    build_code, result, total_size = _try_build_torrent(
        payload=payload,
        output=output,
        final_announce=final_announce,
        final_private=final_private,
        effective_piece_length=effective_piece_length,
        dry_run=dry_run,
    )
    if _is_build_failed(build_code, result, total_size):
        return 1

    assert total_size is not None, "total_size should be set on successful torrent build"  # nosec B101
    _print_torrent_result(payload, result, total_size, dry_run)
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
    cross_seed_torrent: str | None = None,
) -> int:
    """Run torrent command."""
    config_result = _handle_torrent_config_request(
        add_announce=add_announce,
        set_announce=set_announce,
        list_announces=list_announces,
        select_announce=select_announce,
    )
    if config_result is not None:
        return config_result

    store = SettingsStore()
    settings = store.load()
    resolver = PathResolver(settings)
    print_module_banner("Torrent")
    return _execute_torrent_pipeline(
        settings=settings,
        resolver=resolver,
        path=path,
        output=output,
        announce=announce,
        private=private,
        piece_length=piece_length,
        dry_run=dry_run,
        content_mode=content_mode,
        select_content=select_content,
        cross_seed_torrent=cross_seed_torrent,
    )


@click.command(
    "torrent",
    help=tr(
        "cli.torrent.help",
        default=(
            "Create .torrent files with intelligent payload detection and tracker configuration.\n\n"
            "The torrent command automatically detects media files, creates optimized piece sizes, "
            "and generates .torrent files ready for tracker upload.\n\n"
            "Quick examples:\n"
            "  ouro torrent <folder>                     # Auto-detect media payload\n"
            "  ouro tor <folder> --announce <url>        # Specify tracker URL\n"
            "  ouro torrent <folder> --select-content    # Interactive payload selection\n"
            "  ouro tor <folder> --content media         # Force media-only mode\n"
            "  ouro torrent --set-announce <url>         # Save default announce URL\n\n"
            "Setup:\n"
            "  1. Add tracker announce URL: ouro tor --add-announce <url>\n"
            "  2. Select default: ouro tor --select-announce\n"
            "  3. Create torrent: ouro tor <folder>\n\n"
            "Features:\n"
            "  • Automatic media file detection\n"
            "  • Multi-group handling\n"
            "  • Optimal piece size calculation\n"
            "  • Private/public flag support\n"
            "  • Multiple announce URL profiles\n\n"
            "Best practices:\n"
            "  • Use --select-content for ambiguous folders\n"
            "  • Save announce URLs for quick reuse\n"
            "  • Use --dry-run to preview without creating\n"
            "  • Check piece size for optimal seeding\n\n"
            "Related commands: pipeline, batch"
        ),
    ),
)
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
    "-p",
    "--piece-length",
    help=tr("cli.torrent.option.piece_length", default="Piece length: auto, 512K, 1M, 2097152."),
)
@click.option(
    "-d",
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
    "-s",
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
    "-S",
    "--select-announce",
    is_flag=True,
    help=tr(
        "cli.torrent.option.select_announce",
        default="Choose the default announce URL interactively.",
    ),
)
@click.option(
    "-x",
    "--cross-seed",
    "cross_seed_torrent",
    type=click.Path(exists=True),
    help=tr(
        "cli.torrent.option.cross_seed",
        default="Match piece length from an existing .torrent file for cross-seeding.",
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
    cross_seed_torrent: str | None = None,
) -> int:
    """Handle torrent command."""
    return run_torrent_command(
        path=join_path_parts(path_parts) or None,
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
        cross_seed_torrent=cross_seed_torrent,
    )


select_one = _select_one  # backwards-compatible patch target for tests
