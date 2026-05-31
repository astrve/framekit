"""Non-interactive ``swirrl init`` command.

Drops a ``swirrl.yaml`` (and optionally a ``Presets/`` skeleton) in the
current working directory. Intended for CI/CD, scripting and headless
deployments — the inverse of ``swirrl setup``, which is interactive.
"""

from __future__ import annotations

from pathlib import Path

from swirrl.core.exceptions import SettingsError
from swirrl.core.i18n import tr
from swirrl.core.settings import DEFAULT_SETTINGS, SettingsStore
from swirrl.ui.click_helper import click
from swirrl.ui.console import console, print_error, print_info, print_success, print_warning

_DEFAULT_PRESET_DIRS = ("CleanMKV", "NFO", "Pipeline", "Prez")


def _settings_skeleton_minimal() -> dict:
    """A pared-down DEFAULT_SETTINGS with empty/secret fields blanked.

    ``--minimal`` flag uses this. The full DEFAULT_SETTINGS dict is what
    the regular flow writes.
    """
    from copy import deepcopy

    data = deepcopy(DEFAULT_SETTINGS)
    data["setup"]["completed"] = False
    data["setup"]["prompt_on_start"] = True
    return data


def _create_preset_dirs(base: Path) -> list[Path]:
    """Create ``Presets/<Module>/`` directories. Returns created paths."""
    created: list[Path] = []
    root = base / "Presets"
    root.mkdir(parents=True, exist_ok=True)
    for sub in _DEFAULT_PRESET_DIRS:
        target = root / sub
        if not target.exists():
            target.mkdir(parents=True, exist_ok=True)
            created.append(target)
    return created


def _resolve_init_target(
    *,
    target_dir: Path | None,
    force: bool,
) -> tuple[Path, Path] | None:
    base = (target_dir or Path.cwd()).resolve()
    base.mkdir(parents=True, exist_ok=True)
    yaml_path = base / "swirrl.yaml"
    if yaml_path.exists() and not force:
        print_error(
            tr(
                "init.error.already_exists",
                default="{path} already exists. Pass --force to overwrite.",
                path=str(yaml_path),
            )
        )
        return None
    return base, yaml_path


def _write_initial_settings(
    *,
    yaml_path: Path,
    minimal: bool,
    tmdb_token: str | None,
) -> dict | None:
    store = SettingsStore(yaml_path)
    data = _settings_skeleton_minimal() if minimal else None
    if data is not None:
        if tmdb_token:
            data["metadata"]["tmdb_read_access_token"] = tmdb_token.strip()
        store.save(data)
        return data

    store.ensure_exists()
    if tmdb_token:
        store.set("metadata.tmdb_read_access_token", tmdb_token.strip())
    return None


def _print_created_yaml(yaml_path: Path) -> None:
    print_success(
        tr(
            "init.success.yaml",
            default="Created {path}",
            path=str(yaml_path),
        )
    )


def _print_preset_creation_result(base: Path) -> None:
    created = _create_preset_dirs(base)
    if created:
        console.print(
            tr(
                "init.info.presets_created",
                default="Created [cyan]{count}[/cyan] preset director{plural}:",
                count=len(created),
                plural="ies" if len(created) > 1 else "y",
            )
        )
        for path in created:
            console.print(f"  • [dim]{path}[/dim]")
        return
    print_info(
        tr(
            "init.info.presets_exist",
            default="Presets/ already exists — left untouched.",
        )
    )


def _print_token_status(*, tmdb_token: str | None, minimal: bool) -> None:
    if not tmdb_token:
        return
    if not minimal:
        print_info(
            tr(
                "init.info.token_set",
                default=(
                    "TMDb read access token written in plaintext. Enable "
                    "security.enabled and run ``swirrl settings security "
                    "set-token`` to move it into the encrypted vault."
                ),
            )
        )
        return
    print_warning(
        tr(
            "init.warn.token_minimal",
            default=(
                "Token written but security is disabled in the minimal "
                "skeleton. Run ``swirrl settings security enable`` to "
                "protect it in the vault."
            ),
        )
    )


def _print_init_next_steps() -> None:
    console.print()
    print_info(
        tr(
            "init.info.next_steps",
            default=(
                "Next steps:\n"
                "  swirrl setup    # interactive configuration wizard\n"
                "  swirrl doctor   # validate tools and configuration\n"
                "  swirrl --help   # see all commands"
            ),
        )
    )


@click.command(
    "init",
    help=tr(
        "cli.init.help",
        default=(
            "Initialise a Swirrl workspace non-interactively.\n\n"
            "Drops a ``swirrl.yaml`` in the current directory and (unless "
            "``--minimal`` is passed) creates an empty ``Presets/`` tree. "
            "This is the headless counterpart of ``swirrl setup`` — it is "
            "safe to run from CI, Docker entrypoints, or shell scripts.\n\n"
            "Examples:\n"
            "  swirrl init                            # create swirrl.yaml + Presets/\n"
            "  swirrl init --force                    # overwrite existing files\n"
            "  swirrl init --minimal                  # no Presets, blank vault config\n"
            "  swirrl init --token eyJ.abc.xyz        # pre-fill TMDb v4 read token\n"
            "\n"
            "For an interactive walk-through use ``swirrl setup`` instead."
        ),
    ),
)
@click.option(
    "--force",
    is_flag=True,
    help=tr(
        "cli.init.force",
        default="Overwrite swirrl.yaml if it already exists.",
    ),
)
@click.option(
    "--minimal",
    is_flag=True,
    help=tr(
        "cli.init.minimal",
        default="Skip creating the Presets/ tree and use a blank config skeleton.",
    ),
)
@click.option(
    "--token",
    "tmdb_token",
    metavar="TOKEN",
    default=None,
    help=tr(
        "cli.init.token",
        default="Pre-fill metadata.tmdb_read_access_token with a v4 read token.",
    ),
)
@click.option(
    "--path",
    "target_dir",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help=tr(
        "cli.init.path",
        default="Target directory (default: current working directory).",
    ),
)
def init_command(
    force: bool,
    minimal: bool,
    tmdb_token: str | None,
    target_dir: Path | None,
) -> int:
    """Drop a project-local swirrl.yaml (and presets) in ``target_dir``."""
    target = _resolve_init_target(target_dir=target_dir, force=force)
    if target is None:
        return 1
    base, yaml_path = target

    try:
        data = _write_initial_settings(
            yaml_path=yaml_path,
            minimal=minimal,
            tmdb_token=tmdb_token,
        )
    except SettingsError as exc:
        print_error(
            tr(
                "init.error.write_failed",
                default="Failed to initialise {path}: {message}",
                path=str(yaml_path),
                message=str(exc),
            )
        )
        return 1

    _print_created_yaml(yaml_path)

    if not minimal:
        _print_preset_creation_result(base)
    _print_token_status(tmdb_token=tmdb_token, minimal=(data is not None))
    _print_init_next_steps()
    return 0
