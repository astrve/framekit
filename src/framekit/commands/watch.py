"""Watch Mode CLI commands."""

import sys
from pathlib import Path

import click
from rich import box
from rich.table import Table

from framekit.core.cli_helpers import print_fatal, print_warning
from framekit.core.paths import get_config_dir, get_pipeline_presets_dir
from framekit.core.settings import SettingsStore
from framekit.modules.watch import WatchConfig, WatcherService
from framekit.modules.watch.service import (
    read_running_watcher_pid,
    stop_running_watcher,
)
from framekit.ui.console import console
from framekit.ui.timeline import reset_timeline, show_step
from framekit.ui.unified_selector import (
    SelectorOption,
    confirm_choice,
    text_input,
)
from framekit.ui.unified_selector import (
    select_many as _select_many,
)
from framekit.ui.unified_selector import (
    select_one as _select_one,
)

# ── Timeline helpers (shared from framekit.ui.timeline) ──────────────────────

_reset_timeline = reset_timeline
_show_step = show_step


# ── Preset helpers ──────────────────────────────────────────────────────────


def _get_available_presets() -> list[str]:
    presets: list[str] = []
    for preset_dir in [get_pipeline_presets_dir(), get_pipeline_presets_dir(get_config_dir())]:
        if preset_dir.exists():
            for f in sorted(preset_dir.glob("*.yaml")):
                if f.stem not in presets:
                    presets.append(f.stem)
    return presets


def _validate_preset(preset_name: str) -> bool:
    for preset_dir in [get_pipeline_presets_dir(), get_pipeline_presets_dir(get_config_dir())]:
        if (preset_dir / f"{preset_name}.yaml").exists():
            return True
    return False


def _show_available_presets() -> None:
    presets = _get_available_presets()
    if presets:
        console.print("Available presets: " + ", ".join(f"[cyan]{p}[/cyan]" for p in presets))
    else:
        console.print("[yellow]No pipeline presets found in Presets/Pipeline/[/yellow]")


# ── Settings helpers ────────────────────────────────────────────────────────


def _load_watch_data() -> tuple[SettingsStore, dict, list[dict]]:
    """Return (store, full_settings, folders_list)."""
    store = SettingsStore()
    settings = store.load()
    watch = settings.get("watch", {})
    folders = list(watch.get("folders", []))
    return store, settings, folders


def _save_watch_data(
    store: SettingsStore,
    settings: dict,
    folders: list[dict],
    notif: dict | None = None,
    enabled: bool | None = None,
) -> None:
    watch = settings.setdefault("watch", {})
    watch["folders"] = folders
    watch["enabled"] = len(folders) > 0 if enabled is None else enabled
    if notif is not None:
        watch["notifications"] = notif
    store.save(settings)


def _resolve_folder_input(folder: Path | None) -> Path | None:
    if folder is not None:
        return folder
    raw = text_input(title="Folder path to watch", mandatory=True)
    candidate = Path(raw)
    if not candidate.exists():
        print_fatal(f"Path does not exist: {raw}")
        return None
    if not candidate.is_dir():
        print_fatal("Path is not a directory")
        return None
    return candidate


def _is_duplicate_watch_folder(folders: list[dict], folder: Path) -> bool:
    return any(Path(fd.get("path", "")) == folder for fd in folders)


def _resolve_preset_input(
    *,
    preset: str | None,
    available_presets: list[str],
) -> str | None:
    if preset is None:
        selected = select_one(
            title="Select preset",
            entries=[
                SelectorOption(value=item, label=item, selected=(i == 0))
                for i, item in enumerate(available_presets)
            ],
        )
        return selected if selected else None
    if _validate_preset(preset):
        return preset
    print_fatal(f"Preset not found: {preset}")
    _show_available_presets()
    return None


def _notification_summary(notif: dict) -> tuple[str, str]:
    flags: list[str] = []
    if notif.get("on_watch_started"):
        flags.append("watch start")
    if notif.get("on_error"):
        flags.append("errors")
    if notif.get("on_start"):
        flags.append("file start")
    if notif.get("on_success"):
        flags.append("success")
    label = ", ".join(flags) if flags else "none"
    enabled = "[green]on[/green]" if notif.get("enabled", True) else "[red]off[/red]"
    return enabled, label


def _apply_enabled_folder_selection(folders: list[dict], enabled_set: set[int]) -> bool:
    changed = False
    for i, folder_data in enumerate(folders):
        new_state = i in enabled_set
        if folder_data.get("enabled", True) != new_state:
            folder_data["enabled"] = new_state
            changed = True
    return changed


def _validate_watch_folder_entry(fc, all_valid: bool) -> bool:
    if not fc.enabled:
        return all_valid
    console.print(f"[cyan]Folder:[/cyan] {fc.path!s}")
    if not fc.path.exists():
        console.print("  [red]FAIL - Folder does not exist[/red]")
        return False
    if not fc.path.is_dir():
        console.print("  [red]FAIL - Not a directory[/red]")
        return False
    try:
        list(fc.path.iterdir())
        console.print("  [green]OK - Accessible[/green]")
    except PermissionError:
        console.print("  [red]FAIL - Permission denied[/red]")
        return False

    if not fc.preset:
        console.print("  [dim]No preset specified[/dim]")
        console.print()
        return all_valid
    if _validate_preset(fc.preset):
        console.print(f"  [green]OK - Preset '{fc.preset}' found[/green]")
        console.print()
        return all_valid
    console.print(f"  [red]FAIL - Preset '{fc.preset}' not found[/red]")
    _show_available_presets()
    console.print()
    return False


def _print_existing_watch_folders(folders: list[dict]) -> None:
    if not folders:
        return
    console.print("[bold]Current folders:[/bold]")
    for folder_data in folders:
        status = (
            "[green]enabled[/green]" if folder_data.get("enabled", True) else "[red]disabled[/red]"
        )
        console.print(f"  - {folder_data.get('path')} ({folder_data.get('preset')}) [{status}]")
    console.print()


def _collect_watch_folders_setup(
    existing_folders: list[dict], available_presets: list[str]
) -> list[dict]:
    folders = list(existing_folders)
    while True:
        raw = text_input(title="Folder path (leave blank to skip)", mandatory=False)
        if not raw:
            if not folders:
                console.print(
                    "[yellow]No folders configured. Add at least one to use watch mode.[/yellow]"
                )
            break
        folder_path = Path(raw)
        if not folder_path.exists():
            console.print(f"  [red]Path does not exist:[/red] {raw}")
            continue
        if not folder_path.is_dir():
            console.print("  [red]Not a directory[/red]")
            continue

        preset_choice = select_one(
            title="Select preset for this folder",
            entries=[
                SelectorOption(value=preset, label=preset, selected=(i == 0))
                for i, preset in enumerate(available_presets)
            ],
        )
        if not preset_choice:
            continue
        folders.append({"path": str(folder_path), "preset": preset_choice, "enabled": True})
        console.print(
            f"  [green]Added:[/green] {folder_path!s} [green]->[/green] {preset_choice}\n"
        )
        if not confirm_choice(title="Add another folder?", default=False):
            break
    return folders


def _collect_watch_notifications_setup(settings: dict) -> dict:
    notif_data = settings.get("watch", {}).get("notifications", {})
    notif_enabled = confirm_choice(title="Enable desktop notifications?", default=True)
    if not notif_enabled:
        return {
            "enabled": False,
            "on_watch_started": False,
            "on_error": False,
            "on_start": False,
            "on_success": False,
        }

    notif_entries = [
        SelectorOption(
            value="on_watch_started",
            label="Watch mode started/stopped",
            selected=notif_data.get("on_watch_started", True),
        ),
        SelectorOption(
            value="on_error",
            label="Processing error",
            selected=notif_data.get("on_error", True),
        ),
        SelectorOption(
            value="on_start",
            label="File processing begins",
            selected=notif_data.get("on_start", False),
        ),
        SelectorOption(
            value="on_success",
            label="Processing success",
            selected=notif_data.get("on_success", False),
        ),
    ]
    selected_notifs = select_many(
        title="Notifications to enable (Space to toggle, Enter to confirm)",
        entries=notif_entries,
    )
    return {
        "enabled": True,
        "on_watch_started": "on_watch_started" in selected_notifs,
        "on_error": "on_error" in selected_notifs,
        "on_start": "on_start" in selected_notifs,
        "on_success": "on_success" in selected_notifs,
    }


def _validate_enabled_folders_for_start(enabled_folders: list[dict]) -> bool:
    invalid = [
        (folder_data, folder_data.get("preset", ""))
        for folder_data in enabled_folders
        if not _validate_preset(folder_data.get("preset", ""))
    ]
    if not invalid:
        return True
    for folder_data, preset in invalid:
        console.print(f"[red]Invalid preset '{preset}' for:[/red] {folder_data.get('path')}")
    _show_available_presets()
    console.print(
        "Fix with: [cyan]framekit watch remove[/cyan] then [cyan]framekit watch add[/cyan]"
    )
    return False


def _select_folders_for_start(enabled_folders: list[dict], start_all: bool) -> list[dict]:
    if start_all or len(enabled_folders) == 1 or not sys.stdin.isatty():
        return enabled_folders
    chosen_indices = select_many(
        title="Select folders to start (Space to toggle, Enter to confirm)",
        entries=[
            SelectorOption(
                value=i,
                label=folder_data.get("path", "?"),
                hint=folder_data.get("preset", ""),
                selected=True,
            )
            for i, folder_data in enumerate(enabled_folders)
        ],
    )
    if not chosen_indices:
        console.print("[yellow]Nothing selected[/yellow]")
        return []
    return [enabled_folders[i] for i in chosen_indices]


def _print_watch_start_table(selected_folders: list[dict]) -> None:
    table = Table(title="Watching", box=box.SIMPLE)
    table.add_column("Path", style="cyan")
    table.add_column("Preset", style="yellow")
    for folder_data in selected_folders:
        table.add_row(str(folder_data.get("path", "")), folder_data.get("preset", ""))
    console.print(table)
    console.print("[yellow]Press Ctrl+C to stop[/yellow]\n")


def _run_watch_service(
    service: WatcherService, no_status_updates: bool, status_interval: int
) -> None:
    if not no_status_updates:
        service.handler.status_update_interval = status_interval
        service.handler.start_periodic_status()
    try:
        service.start()
    finally:
        if not no_status_updates:
            service.handler.stop_periodic_status()


# ── CLI group ───────────────────────────────────────────────────────────────


@click.group(name="watch")
def watch_group():
    """Beta folder watcher for automatic video processing."""


# ── setup ───────────────────────────────────────────────────────────────────


@watch_group.command(name="setup")
def setup_command():
    """Interactive setup wizard for watch mode.

    Guides you through adding folders, choosing presets and configuring
    notifications. Saves the result to framekit.yaml.
    """
    _reset_timeline()
    steps = ["Folders", "Notifications", "Save"]

    try:
        store, settings, existing_folders = _load_watch_data()
        available_presets = _get_available_presets()

        if not available_presets:
            print_fatal(
                "No pipeline presets found", "Create at least one preset in Presets/Pipeline/ first"
            )
            return

        # ── Step 1: Folders ──────────────────────────────────────────────
        _show_step(
            "Step 1 - Folders",
            "Add one or more folders to monitor.\n"
            "New video files dropped there will be processed automatically.",
            "Folders",
            steps,
        )

        _print_existing_watch_folders(existing_folders)
        folders = _collect_watch_folders_setup(existing_folders, available_presets)

        # ── Step 2: Notifications ────────────────────────────────────────
        _show_step(
            "Step 2 - Notifications",
            "Choose which events trigger desktop notifications.",
            "Notifications",
            steps,
        )

        notif = _collect_watch_notifications_setup(settings)

        # ── Step 3: Save ─────────────────────────────────────────────────
        _show_step("Step 3 - Save", "Saving your watch configuration.", "Save", steps)

        _save_watch_data(store, settings, folders, notif=notif)

        console.print("\n[green]Watch configuration saved.[/green]")
        if folders:
            console.print("Start with: [cyan]framekit watch start[/cyan]")
        else:
            console.print("Add folders with: [cyan]framekit watch add[/cyan]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Setup cancelled[/yellow]")
    except Exception as e:
        print_fatal(str(e), "Check that framekit.yaml is writable")


# ── add ─────────────────────────────────────────────────────────────────────


@watch_group.command(name="add")
@click.option(
    "--folder",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Folder path (skips interactive prompt)",
)
@click.option("--preset", type=str, default=None, help="Preset name (skips interactive prompt)")
def add_command(folder: Path | None, preset: str | None):
    """Add a folder to the watch list."""
    try:
        store, settings, folders = _load_watch_data()
        available_presets = _get_available_presets()

        if not available_presets:
            print_fatal("No pipeline presets found", "Create a preset in Presets/Pipeline/ first")
            return

        folder = _resolve_folder_input(folder)
        if folder is None:
            return

        if _is_duplicate_watch_folder(folders, folder):
            console.print(f"[yellow]Already watching:[/yellow] {folder!s}")
            return

        resolved_preset = _resolve_preset_input(preset=preset, available_presets=available_presets)
        if not resolved_preset:
            return

        folders.append({"path": str(folder), "preset": resolved_preset, "enabled": True})
        _save_watch_data(store, settings, folders)

        console.print(f"[green]Added:[/green] {folder!s} [green]->[/green] {resolved_preset}")
        console.print("Start with: [cyan]framekit watch start[/cyan]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled[/yellow]")
    except Exception as e:
        print_fatal(str(e))


# ── remove ───────────────────────────────────────────────────────────────────


@watch_group.command(name="remove")
def remove_command():
    """Remove a folder from the watch list."""
    try:
        store, settings, folders = _load_watch_data()

        if not folders:
            console.print("[yellow]No folders configured[/yellow]")
            console.print("Add one with: [cyan]framekit watch add[/cyan]")
            return

        to_remove = select_one(
            title="Select folder to remove",
            entries=[
                SelectorOption(
                    value=i,
                    label=fd.get("path", "?"),
                    hint=fd.get("preset", ""),
                )
                for i, fd in enumerate(folders)
            ],
        )
        if to_remove is None:
            return

        removed = folders.pop(to_remove)
        confirmed = confirm_choice(title=f"Remove '{removed.get('path')}'?", default=True)
        if not confirmed:
            console.print("[yellow]Cancelled[/yellow]")
            return

        _save_watch_data(store, settings, folders)
        console.print(f"[green]Removed:[/green] {removed.get('path')}")

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled[/yellow]")
    except Exception as e:
        print_fatal(str(e))


# ── list ────────────────────────────────────────────────────────────────────


@watch_group.command(name="list")
def list_command():
    """View and interactively enable/disable watched folders.

    Selected folders are enabled; unselected are disabled.
    """
    try:
        store, settings, folders = _load_watch_data()

        if not folders:
            console.print("[yellow]No folders configured[/yellow]")
            console.print("Add one with: [cyan]framekit watch add[/cyan]")
            return

        notif = settings.get("watch", {}).get("notifications", {})

        # Summary table
        table = Table(title="Watch Folders", box=box.SIMPLE)
        table.add_column("Path", style="cyan")
        table.add_column("Preset", style="yellow")
        table.add_column("State")
        for fd in folders:
            state = "[green]enabled[/green]" if fd.get("enabled", True) else "[red]disabled[/red]"
            table.add_row(str(fd.get("path", "")), fd.get("preset", ""), state)
        console.print(table)

        notif_enabled, notif_label = _notification_summary(notif)
        console.print(f"Notifications: {notif_enabled} ({notif_label})\n")

        if not sys.stdin.isatty():
            console.print("[dim]Interactive mode unavailable in this terminal[/dim]")
            return

        # Interactive toggle
        enabled_set = select_many(
            title="Toggle folders (selected = enabled, Space to toggle, Enter to confirm)",
            entries=[
                SelectorOption(
                    value=i,
                    label=fd.get("path", "?"),
                    hint=fd.get("preset", ""),
                    selected=fd.get("enabled", True),
                )
                for i, fd in enumerate(folders)
            ],
        )

        changed = _apply_enabled_folder_selection(folders, set(enabled_set))

        if changed:
            _save_watch_data(store, settings, folders)
            console.print("[green]Saved[/green]")
        else:
            console.print("[dim]No changes[/dim]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled[/yellow]")
    except Exception as e:
        print_fatal(str(e))


# ── start ────────────────────────────────────────────────────────────────────


@watch_group.command(name="start")
@click.option("--all", "start_all", is_flag=True, help="Start all enabled folders without prompt")
@click.option("--no-status-updates", is_flag=True, help="Disable periodic status updates")
@click.option(
    "--status-interval", type=int, default=30, help="Status interval in seconds (default: 30)"
)
def start_command(start_all: bool, no_status_updates: bool, status_interval: int):
    r"""Start watching folders for new video files.

    \b
    Examples:
      framekit watch start           # choose folders interactively
      framekit watch start --all     # start all enabled folders
    """
    try:
        _store, settings, all_folders = _load_watch_data()

        enabled_folders = [fd for fd in all_folders if fd.get("enabled", True)]
        if not enabled_folders:
            console.print("[yellow]No enabled folders[/yellow]")
            console.print("Add one with: [cyan]framekit watch add[/cyan]")
            console.print("Or enable folders with: [cyan]framekit watch list[/cyan]")
            return

        if not _validate_enabled_folders_for_start(enabled_folders):
            return

        selected_folders = _select_folders_for_start(enabled_folders, start_all)
        if not selected_folders:
            return

        watch_config_data = {
            "enabled": True,
            "folders": selected_folders,
            "notifications": settings.get("watch", {}).get("notifications", {}),
        }
        config = WatchConfig.from_dict(watch_config_data)

        console.print("[green]Starting watch mode...[/green]")
        _print_watch_start_table(selected_folders)
        _run_watch_service(WatcherService(config), no_status_updates, status_interval)

    except KeyboardInterrupt:
        console.print("\n[yellow]Watch mode stopped[/yellow]")
    except Exception as e:
        print_fatal(str(e), "Check your configuration with: framekit watch test")


# ── status ───────────────────────────────────────────────────────────────────


@watch_group.command(name="status")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def status_command(json_output: bool):
    """Show watch mode status."""
    try:
        _store, settings, folders = _load_watch_data()
        watch_config_data = settings.get("watch", {})

        if not folders:
            console.print("[yellow]No watch configuration[/yellow]")
            console.print("Run: [cyan]framekit watch add[/cyan]")
            return

        config = WatchConfig.from_dict(watch_config_data)
        service = WatcherService(config)
        service.display_status(json_output=json_output)

    except Exception as e:
        print_fatal(str(e), "Verify watch configuration in framekit.yaml")


# ── stop ─────────────────────────────────────────────────────────────────────


@watch_group.command(name="stop")
@click.option(
    "--timeout",
    type=float,
    default=10.0,
    show_default=True,
    help="Seconds to wait for graceful shutdown before reporting failure.",
)
def stop_command(timeout: float) -> None:
    """Stop a watch session started in the current working directory.

    Looks for ``.framekit_watch.pid`` next to the active framekit.yaml and
    signals that process to shut down gracefully. Falls back to a reminder
    about Ctrl+C when no PID file is found (e.g. for a watcher running in a
    foreground terminal under a different working directory).
    """
    pid = read_running_watcher_pid()
    if pid is None:
        console.print("[yellow]No running watch session found in this directory.[/yellow]")
        console.print(
            "If the watcher is running in another terminal, focus that window "
            "and press [cyan]Ctrl+C[/cyan] to stop it."
        )
        return

    console.print(f"Sending stop signal to watch process [cyan]{pid}[/cyan]...")
    if stop_running_watcher(timeout_seconds=timeout):
        console.print("[green]Watch mode stopped.[/green]")
        return

    print_warning(
        f"Watch process {pid} did not exit within {timeout:.1f}s. "
        "Use [cyan]Ctrl+C[/cyan] in the watcher terminal as a fallback."
    )


# ── test ─────────────────────────────────────────────────────────────────────


@watch_group.command(name="test")
@click.option(
    "--folder",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Folder to test",
)
@click.option("--preset", type=str, default=None, help="Preset to validate (optional)")
def test_command(folder: Path | None, preset: str | None):
    r"""Test watch configuration and dependencies.

    \b
    Examples:
      framekit watch test
      framekit watch test --folder D:\\downloads --preset multi_fr
    """
    try:
        _store, settings, folders = _load_watch_data()

        if folder:
            folders = [{"path": str(folder), "preset": preset or "", "enabled": True}]

        if not folders:
            print_fatal(
                "No watch configuration found", "Run 'framekit watch add' or 'framekit watch setup'"
            )
            return

        config = WatchConfig.from_dict(
            {
                "enabled": True,
                "folders": folders,
                "notifications": settings.get("watch", {}).get("notifications", {}),
            }
        )

        console.print("[bold]Testing watch configuration...[/bold]\n")

        all_valid = True
        for fc in config.folders:
            all_valid = _validate_watch_folder_entry(fc, all_valid)

        console.print("[bold]Dependencies:[/bold]")
        try:
            import desktop_notifier  # noqa: F401  # pyright: ignore[reportUnusedImport]  # Probe for optional dependency availability

            console.print("  [green]OK - desktop-notifier available[/green]")
        except ImportError:
            console.print("  [yellow]WARN - desktop-notifier not installed[/yellow]")
            console.print("    pip install desktop-notifier")
        console.print()

        if all_valid:
            console.print("[green]Configuration is valid[/green]")
        else:
            print_fatal("Configuration has errors - run 'framekit watch setup' to fix")

    except Exception as e:
        print_fatal(str(e), "Verify watch configuration and dependencies")


select_one = _select_one  # backwards-compatible patch target for tests

select_many = _select_many  # backwards-compatible patch target for tests
