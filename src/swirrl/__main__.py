from __future__ import annotations

import sys

import click


def _force_utf8_stdio() -> None:
    """Force UTF-8 encoding on stdout/stderr.

    On Windows, when the swirrl binary is launched from a non-Unicode
    terminal (or from a pipe, or from a Python launcher with the default
    ``cp1252`` codepage), characters such as ``→``, ``✓`` and the rich-click
    help arrows fail with ``UnicodeEncodeError: 'charmap' codec can't encode``.

    Reconfigure the streams to UTF-8 + replace-errors before any output is
    produced so the rendering library always succeeds. POSIX terminals
    already use UTF-8 in 2026; this is a no-op there.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            # Stream cannot be reconfigured (already closed, exotic wrapper).
            continue


def _apply_color_preferences(argv: list[str]) -> list[str]:
    """Respect ``--no-color`` / ``--color`` and the ``NO_COLOR`` env var.

    Detects the flag on the command line before Click sees it (Click would
    swallow it as an unknown option on the root group). Sets the standard
    ``NO_COLOR=1`` env var, which both Rich and Click already honour.
    Returns the argv list with the flag stripped.
    """
    import os

    cleaned: list[str] = []
    force_no_color: bool | None = None
    for arg in argv:
        if arg in ("--no-color", "--no-colour"):
            force_no_color = True
            continue
        if arg in ("--color", "--colour"):
            force_no_color = False
            continue
        cleaned.append(arg)

    if force_no_color is True:
        os.environ["NO_COLOR"] = "1"
    elif force_no_color is False:
        os.environ.pop("NO_COLOR", None)
    # Auto-detect: non-TTY stdout → suppress colour unless explicit --color.
    elif not sys.stdout.isatty() and "NO_COLOR" not in os.environ:
        os.environ["NO_COLOR"] = "1"

    return cleaned


def _apply_dry_run(argv: list[str]) -> list[str]:
    """Promote a leading ``--dry-run`` to ``SWIRRL_DRY_RUN=1``.

    When ``--dry-run`` appears *before* the subcommand name it is a global
    shorthand (``swirrl --dry-run pipeline …``).  We strip it from argv so
    the Click group does not reject it and expose the intent via the env var.

    When it appears *after* the subcommand name it belongs to that
    subcommand's own Click option and must stay in argv so Click sees it.
    """
    import os

    if "--dry-run" not in argv:
        return argv

    first_flag_end = 0
    for i, arg in enumerate(argv):
        if arg.startswith("-"):
            first_flag_end = i + 1
        else:
            break

    leading = argv[:first_flag_end]
    rest = argv[first_flag_end:]

    if "--dry-run" in leading:
        os.environ["SWIRRL_DRY_RUN"] = "1"
        return [a for a in leading if a != "--dry-run"] + rest

    os.environ["SWIRRL_DRY_RUN"] = "1"
    return argv


def _apply_auto_yes(argv: list[str]) -> list[str]:
    """Promote a leading ``--yes`` / ``-y`` to ``SWIRRL_AUTO_YES=1``.

    When the flag is present at the root, every confirmation prompt
    surfaced through :func:`swirrl.core.destructive.confirm_destructive`
    auto-approves. Sub-command-local ``-y`` flags (metadata, batch, etc.)
    still work because they consume their own option.
    """
    import os

    if "--yes" in argv or "-y" in argv:
        os.environ["SWIRRL_AUTO_YES"] = "1"
        return [arg for arg in argv if arg not in {"--yes", "-y"}]
    return argv


_force_utf8_stdio()

# The imports below intentionally run AFTER ``_force_utf8_stdio()``. ``loguru``
# and ``rich`` capture a reference to ``sys.stderr`` at import time, so we
# reconfigure the streams first to keep their output on UTF-8 terminals.

from swirrl.core.diagnostics import (  # noqa: E402
    configure_diagnostics,
    configure_from_environment,
    is_debug_enabled,
    log_event,
    log_exception,
)
from swirrl.core.exceptions import SwirrlError  # noqa: E402
from swirrl.core.i18n import set_locale, tr  # noqa: E402
from swirrl.core.settings import SettingsStore  # noqa: E402
from swirrl.ui.console import console, print_error  # noqa: E402


def _load_locale_from_settings() -> None:
    try:
        settings = SettingsStore().load()
    except Exception:
        return

    locale_value = settings.get("general", {}).get("locale", "")
    if isinstance(locale_value, str) and locale_value.strip():
        set_locale(locale_value)


def _extract_diagnostics_args(argv: list[str]) -> tuple[list[str], bool | None, str | None]:
    cleaned: list[str] = []
    debug: bool | None = None
    log_file: str | None = None
    index = 0

    while index < len(argv):
        arg = argv[index]
        if arg == "--debug":
            debug = True
            index += 1
            continue
        if arg == "--no-debug":
            debug = False
            index += 1
            continue
        if arg == "--log-file" and index + 1 < len(argv):
            log_file = argv[index + 1]
            index += 2
            continue
        if arg.startswith("--log-file="):
            log_file = arg.split("=", 1)[1]
            index += 1
            continue

        cleaned.append(arg)
        index += 1

    return cleaned, debug, log_file


def _print_traceback_if_debug(exc: BaseException) -> None:
    log_exception(exc)
    if is_debug_enabled():
        console.print_exception(show_locals=False)


def _print_suggestions_for(exc: BaseException) -> None:
    """Append a ``Suggestions:`` block after a user-facing error, when relevant.

    Uses the explicit ``suggestions`` tuple on :class:`SwirrlError` when
    present, otherwise falls back to heuristic matching. Never raises.
    """
    try:
        from swirrl.core.error_suggestions import derive_suggestions

        hints = derive_suggestions(exc)
    except Exception:
        hints = ()

    if not hints:
        return

    console.print()
    console.print(
        tr("runtime.suggestions_header", default="[bold yellow]Suggestions:[/bold yellow]")
    )
    for hint in hints:
        console.print(f"  • {hint}")


def _friendly_click_message(exc: click.ClickException) -> str:
    message = exc.format_message()
    if "requires an argument" not in message:
        return message

    hints = {
        "--preset": "You need to choose a Prez preset, for example: default, compact, detailed, technical, tracker or premium.",
        "--announce": "You need to provide a tracker announce URL, for example: https://tracker.example/announce or udp://tracker.example:6969/announce.",
        "--template": "You need to provide a template name. Use --list-templates first if needed.",
        "--html-template": "You need to provide an HTML Prez template. Use swirrl prez --list-templates first if needed.",
        "--bbcode-template": "You need to provide a BBCode Prez template. Use swirrl prez --list-templates first if needed.",
        "--output-dir": "You need to provide an output folder path.",
        "--modules": "You need to provide a comma-separated list, for example: renamer,cleanmkv,nfo,torrent,prez.",
        "--locale": "You need to choose one of: auto, en, fr, es.",
    }
    for option, hint in hints.items():
        if option in message:
            return f"{message} {hint}"
    return f"{message} Add a value after the option or remove the option."


def _version_requested(args: list[str]) -> bool:
    return "--version" in args or "-V" in args


def _resolve_swirrl_version() -> str:
    try:
        from importlib import metadata as importlib_metadata

        for distribution_name in ("swirrl-auto", "swirrl"):
            try:
                version = importlib_metadata.version(distribution_name)
                if version:
                    return version
            except importlib_metadata.PackageNotFoundError:
                continue
            except Exception:  # nosec B112
                continue

        from swirrl import __version__ as fallback_version

        return fallback_version
    except Exception:
        return "unknown"


def _print_version_and_exit() -> int:
    sys.stdout.write(f"swirrl, version {_resolve_swirrl_version()}\n")
    return 0


def _run_update_check_background() -> None:
    # Update checks must never break the CLI.
    try:
        from swirrl.core.update_check import start_background_update_check

        start_background_update_check()
    except Exception:  # nosec B110
        pass


def _run_cli(args: list[str]) -> int:
    from swirrl.commands.main import cli
    from swirrl.commands.setup import maybe_offer_first_time_setup
    from swirrl.core.paths import get_legacy_config_warning

    legacy_warning = get_legacy_config_warning()
    if legacy_warning:
        console.print(f"[yellow]{legacy_warning}[/yellow]")

    maybe_offer_first_time_setup()
    result = cli.main(
        args=args,
        prog_name="swirrl",
        standalone_mode=False,
    )
    return int(result) if isinstance(result, int) else 0


def main() -> int:
    # Extract diagnostics flags such as --debug and --log-file without consuming other
    # arguments. We do this early so that we can handle the --version flag
    # ourselves before performing any I/O or creating user settings files.
    args, debug, log_file = _extract_diagnostics_args(sys.argv[1:])
    args = _apply_color_preferences(args)
    args = _apply_dry_run(args)
    args = _apply_auto_yes(args)

    # Avoid loading locale/settings when only version was requested.
    if _version_requested(args):
        return _print_version_and_exit()

    configure_from_environment()
    configure_diagnostics(debug=debug, log_file=log_file)

    try:
        log_event("INFO", "Swirrl command started", argv=args)
        _load_locale_from_settings()
        _run_update_check_background()
        exit_code = _run_cli(args)
        log_event("INFO", "Swirrl command completed", exit_code=exit_code)
        return exit_code

    except click.ClickException as exc:
        _print_traceback_if_debug(exc)
        print_error(_friendly_click_message(exc))
        return exc.exit_code

    except SwirrlError as exc:
        _print_traceback_if_debug(exc)
        print_error(
            tr(
                exc.message_key or "runtime.swirrl_error",
                default=str(exc),
                message=str(exc),
                **exc.context,
            )
        )
        _print_suggestions_for(exc)
        return exc.exit_code

    except click.Abort:
        print_error(tr("runtime.aborted", default="Aborted."))
        return 1

    except KeyboardInterrupt:
        print_error(tr("runtime.interrupted", default="Interrupted."))
        return 1

    except Exception as exc:
        _print_traceback_if_debug(exc)
        print_error(
            tr(
                "runtime.unknown_error",
                default="Unexpected error: {message}",
                message=str(exc),
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
