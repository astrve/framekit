from __future__ import annotations

import sys

import click

from framekit.core.diagnostics import (
    configure_diagnostics,
    configure_from_environment,
    is_debug_enabled,
    log_event,
    log_exception,
)
from framekit.core.exceptions import FramekitError
from framekit.core.i18n import set_locale, tr
from framekit.core.settings import SettingsStore
from framekit.ui.console import console, print_error


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


def _friendly_click_message(exc: click.ClickException) -> str:
    message = exc.format_message()
    if "requires an argument" not in message:
        return message

    hints = {
        "--preset": "You need to choose a Prez preset, for example: default, compact, detailed, technical, tracker or premium.",
        "--announce": "You need to provide a tracker announce URL, for example: https://tracker.example/announce or udp://tracker.example:6969/announce.",
        "--template": "You need to provide a template name. Use --list-templates first if needed.",
        "--html-template": "You need to provide an HTML Prez template. Use fk prez --list-templates first if needed.",
        "--bbcode-template": "You need to provide a BBCode Prez template. Use fk prez --list-templates first if needed.",
        "--output-dir": "You need to provide an output folder path.",
        "--modules": "You need to provide a comma-separated list, for example: renamer,cleanmkv,nfo,torrent,prez.",
        "--locale": "You need to choose one of: auto, en, fr, es.",
    }
    for option, hint in hints.items():
        if option in message:
            return f"{message} {hint}"
    return f"{message} Add a value after the option or remove the option."


def main() -> int:
    args, debug, log_file = _extract_diagnostics_args(sys.argv[1:])
    configure_from_environment()
    configure_diagnostics(debug=debug, log_file=log_file)

    try:
        log_event("INFO", "Framekit command started", argv=args)
        _load_locale_from_settings()

        from framekit.commands.main import cli
        from framekit.commands.setup import maybe_offer_first_time_setup

        maybe_offer_first_time_setup()

        result = cli.main(
            args=args,
            prog_name="framekit",
            standalone_mode=False,
        )
        exit_code = int(result) if isinstance(result, int) else 0
        log_event("INFO", "Framekit command completed", exit_code=exit_code)
        return exit_code

    except click.ClickException as exc:
        _print_traceback_if_debug(exc)
        print_error(_friendly_click_message(exc))
        return exc.exit_code

    except FramekitError as exc:
        _print_traceback_if_debug(exc)
        print_error(
            tr(
                exc.message_key or "runtime.framekit_error",
                default=str(exc),
                message=str(exc),
                **exc.context,
            )
        )
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
