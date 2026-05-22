"""Browse command for interactive file selection."""

from __future__ import annotations

from pathlib import Path

from framekit.core.cli_helpers import join_path_parts
from framekit.core.file_browser import BrowserConfig
from framekit.core.path_validation import validate_directory_path
from framekit.ui.click_helper import click
from framekit.ui.console import console, print_error, print_info
from framekit.ui.file_browser import FileBrowserTUI


def _resolve_start_directory(path: str | None) -> Path:
    if not path:
        return Path.cwd()
    return validate_directory_path(path, must_exist=True, strict=False)


def _parse_filter_extensions(filter_ext: str | None) -> list[str] | None:
    if not filter_ext:
        return None
    extensions = [ext.strip() for ext in filter_ext.split(",")]
    return [ext if ext.startswith(".") else f".{ext}" for ext in extensions]


def _run_browser(config: BrowserConfig) -> list[Path]:
    tui = FileBrowserTUI(config)
    return tui.run()


def _print_selected_paths(selected_paths: list[Path]) -> int:
    if not selected_paths:
        print_info("No files selected")
        return 0
    for selected_path in selected_paths:
        console.print(str(selected_path))
    return 0


def run_browse_command(
    path: str | None,
    filter_ext: str | None,
    multi: bool,
    directories_only: bool,
    show_hidden: bool,
) -> int:
    """Run the browse command.

    Args:
        path: Starting directory path
        filter_ext: File extension filter (comma-separated)
        multi: Enable multi-select mode
        directories_only: Show only directories
        show_hidden: Show hidden files

    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        start_dir = _resolve_start_directory(path)
    except Exception as exc:
        print_error(f"Invalid directory: {exc}")
        return 1
    filter_extensions = _parse_filter_extensions(filter_ext)

    config = BrowserConfig(
        start_directory=start_dir,
        filter_extensions=filter_extensions,
        multi_select=multi,
        show_hidden=show_hidden,
        directories_only=directories_only,
    )

    try:
        selected_paths = _run_browser(config)
        return _print_selected_paths(selected_paths)
    except RuntimeError as exc:
        print_error(str(exc))
        return 1
    except KeyboardInterrupt:
        print_info("Cancelled")
        return 0
    except Exception as exc:
        print_error(f"Error running file browser: {exc}")
        return 1


@click.command("browse", help="Interactive file browser for selecting files and directories.")
@click.argument("path_parts", nargs=-1)
@click.option(
    "-f",
    "--filter",
    "filter_ext",
    help="Filter by file extension (e.g., '.mkv' or 'mkv,.mp4')",
    default=None,
)
@click.option("-m", "--multi", is_flag=True, help="Enable multi-select mode")
@click.option("-d", "--directories-only", is_flag=True, help="Show only directories")
@click.option("--show-hidden", is_flag=True, help="Show hidden files and directories")
def browse_command(
    path_parts: tuple[str, ...],
    filter_ext: str | None,
    multi: bool,
    directories_only: bool,
    show_hidden: bool,
) -> int:
    """Interactive file browser command.

    Browse and select files interactively using keyboard navigation.

    Examples:
        fk browse                          # Browse current directory
        fk browse /path/to/dir             # Browse specific directory
        fk browse --filter .mkv            # Filter by extension
        fk browse --filter .mkv,.mp4       # Multiple extensions
        fk browse --multi                  # Multi-select mode
        fk browse --directories-only       # Show only directories
    """
    path = join_path_parts(path_parts) or None
    return run_browse_command(path, filter_ext, multi, directories_only, show_hidden)
