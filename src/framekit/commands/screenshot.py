"""Screenshot extraction CLI command."""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from rich import box
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from framekit.core.i18n import tr
from framekit.core.models.screenshot import ScreenshotConfig
from framekit.core.verbose import configure_verbosity, is_verbose, log_file_processing
from framekit.modules.screenshot.service import ScreenshotService
from framekit.ui.branding import print_module_banner
from framekit.ui.click_helper import click
from framekit.ui.console import console, print_error, print_info, print_success, print_warning
from framekit.ui.unified_selector import SelectorOption
from framekit.ui.unified_selector import select_many as _select_many


def _scan_directory_for_mkvs(directory: Path, recursive: bool = False) -> list[Path]:
    """Scan directory for MKV files.

    Args:
        directory: Directory to scan
        recursive: Whether to scan recursively

    Returns:
        List of MKV file paths found
    """
    mkv_files: list[Path] = []

    if recursive:
        # Recursive scan using rglob
        mkv_files = sorted(directory.rglob("*.mkv"))
    else:
        # Top-level scan only
        mkv_files = sorted(directory.glob("*.mkv"))

    return mkv_files


def _expand_paths_to_videos(
    paths: list[Path],
    recursive: bool = False,
    process_all: bool = False,
) -> list[Path]:
    """Expand paths (files and directories) to list of video files.

    Args:
        paths: List of file and/or directory paths
        recursive: Whether to scan directories recursively
        process_all: Whether to process all files without interaction

    Returns:
        List of valid MKV file paths

    Raises:
        click.Abort: If user cancels selection or no files found
    """
    all_videos: list[Path] = []

    for path in paths:
        if not path.exists():
            print_error(f"Path not found: {path}")
            continue

        if path.is_file():
            # Direct file path - validate it's an MKV
            if path.suffix.lower() == ".mkv":
                all_videos.append(path)
            else:
                print_warning(f"Skipping non-MKV file: {path}")
        elif path.is_dir():
            # Directory - scan for MKV files
            mkv_files = _scan_directory_for_mkvs(path, recursive=recursive)

            if not mkv_files:
                print_warning(f"No MKV files found in directory: {path}")
                continue

            if len(mkv_files) == 1:
                # Single file - auto-process
                print_info(f"Found 1 MKV file in {path}, processing automatically")
                all_videos.extend(mkv_files)
            elif process_all:
                # Process all without interaction
                print_info(f"Found {len(mkv_files)} MKV files in {path}, processing all")
                all_videos.extend(mkv_files)
            else:
                # Multiple files - show interactive selector
                print_info(f"Found {len(mkv_files)} MKV files in {path}")
                selected = _select_videos_interactive(mkv_files, directory=path)
                if not selected:
                    print_warning("No files selected, skipping directory")
                    continue
                all_videos.extend(selected)
        else:
            print_warning(f"Skipping invalid path: {path}")

    return all_videos


def _select_videos_interactive(mkv_files: list[Path], directory: Path) -> list[Path]:
    """Show interactive selector for multiple MKV files.

    Args:
        mkv_files: List of MKV files to choose from
        directory: Parent directory for display

    Returns:
        List of selected file paths (empty if cancelled)
    """
    # Create selector options
    options = [
        SelectorOption(
            value=mkv_file,
            label=mkv_file.name,
            hint=_format_file_size(mkv_file.stat().st_size),
        )
        for mkv_file in mkv_files
    ]

    try:
        selected = select_many(
            title=f"Select MKV files from {directory.name}",  # nosec B608
            entries=options,
            page_size=10,
            minimal_count=1,
        )
        return selected
    except KeyboardInterrupt:
        # User cancelled
        raise click.Abort() from None


def _parse_manual_timestamps(raw: str) -> list[float]:
    return [float(ts.strip()) for ts in raw.split(",")]


def _manual_mode_video_list(valid_videos: list[Path]) -> list[Path]:
    if len(valid_videos) <= 1:
        return valid_videos
    print_warning("Manual timestamps mode only supports single video")
    print_info(f"Processing only: {valid_videos[0]}")
    return [valid_videos[0]]


def _run_manual_screenshot_mode(
    *,
    service: ScreenshotService,
    valid_videos: list[Path],
    output_dir: Path,
    config: ScreenshotConfig,
    release_name: str | None,
    timestamps: str,
) -> None:
    try:
        timestamp_list = _parse_manual_timestamps(timestamps)
    except ValueError as exc:
        print_error(f"Invalid timestamp format: {exc}")
        raise click.Abort() from exc

    valid_videos = _manual_mode_video_list(valid_videos)
    video_path = valid_videos[0]
    print_info(f"Extracting {len(timestamp_list)} screenshots at specific timestamps")
    print_info(f"Output directory: {output_dir}")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Extracting screenshots...", total=len(timestamp_list))

        def progress_callback(message: str, current: int, total: int) -> None:
            if is_verbose():
                logger.info(f"Screenshot progress: {message} ({current}/{total})")
            progress.update(task, completed=current, description=message)

        result = service.extract_from_timestamps(
            video_path=video_path,
            timestamps=timestamp_list,
            output_dir=output_dir,
            config=config,
            release_name=release_name,
            progress_callback=progress_callback,
        )

    if is_verbose():
        log_file_processing(str(video_path), status="completed")
    _display_single_result(result)


def _run_auto_screenshot_mode(
    *,
    service: ScreenshotService,
    valid_videos: list[Path],
    output_dir: Path,
    config: ScreenshotConfig,
    release_name: str | None,
    count: int,
) -> None:
    print_info(f"Extracting {count} screenshots per video")
    print_info(f"Output directory: {output_dir}")
    print_info(f"Processing {len(valid_videos)} video(s)")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Processing videos...", total=len(valid_videos))

        def progress_callback(message: str, current: int, total: int) -> None:
            if is_verbose():
                logger.info(f"Batch progress: {message} ({current}/{total})")
            progress.update(task, completed=current, description=message)

        report = service.extract_screenshots(
            video_paths=valid_videos,
            output_dir=output_dir,
            config=config,
            release_name=release_name,
            progress_callback=progress_callback,
        )

    if is_verbose():
        logger.info(f"Processed {len(valid_videos)} videos")
    _display_report(report)


@click.command(
    "screenshot",
    help=tr(
        "cli.screenshot.help",
        default=(
            "Extract screenshots from video files using FFmpeg.\n\n"
            "Automatically selects evenly distributed frames, avoiding black frames "
            "and intro/outro sections.\n\n"
            "Examples:\n"
            "  fk screenshot video.mkv                    # Extract 6 screenshots\n"
            "  fk screenshot video.mkv --count 10         # Extract 10 screenshots\n"
            "  fk screenshot video.mkv --timestamps 120,240,360  # Specific times\n"
            "  fk screenshot *.mkv --output ./screens     # Batch processing\n"
        ),
    ),
)
@click.argument(
    "videos",
    nargs=-1,
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
@click.option(
    "--count",
    "-n",
    type=int,
    default=6,
    help=tr("cli.screenshot.count", default="Number of screenshots to extract"),
)
@click.option(
    "--width",
    "-w",
    type=int,
    help=tr("cli.screenshot.width", default="Screenshot width (maintains aspect ratio)"),
)
@click.option(
    "--quality",
    "-q",
    type=int,
    default=2,
    help=tr("cli.screenshot.quality", default="JPEG quality (1-31, lower is better)"),
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["png", "jpg", "jpeg"]),
    default="png",
    help=tr("cli.screenshot.format", default="Output format"),
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help=tr("cli.screenshot.output", default="Output directory"),
)
@click.option(
    "--timestamps",
    "-t",
    help=tr(
        "cli.screenshot.timestamps",
        default="Comma-separated timestamps in seconds (e.g., 120,240,360)",
    ),
)
@click.option(
    "--release-name",
    "-r",
    help=tr("cli.screenshot.release_name", default="Release name for filenames"),
)
@click.option(
    "--skip-intro",
    type=int,
    default=60,
    help=tr(
        "cli.screenshot.skip_intro", default="Skip intro seconds (legacy, use --skip-start-percent)"
    ),
)
@click.option(
    "--skip-outro",
    type=int,
    default=120,
    help=tr(
        "cli.screenshot.skip_outro", default="Skip outro seconds (legacy, use --skip-end-percent)"
    ),
)
@click.option(
    "--skip-start-percent",
    type=float,
    default=5.0,
    help=tr("cli.screenshot.skip_start_percent", default="Skip N% from video start (default: 5%)"),
)
@click.option(
    "--skip-end-percent",
    type=float,
    default=5.0,
    help=tr("cli.screenshot.skip_end_percent", default="Skip N% from video end (default: 5%)"),
)
@click.option(
    "--no-black-detection",
    is_flag=True,
    help=tr("cli.screenshot.no_black_detection", default="Disable black frame detection"),
)
@click.option(
    "--all",
    is_flag=True,
    help=tr("cli.screenshot.all", default="Process all MKV files in directory without interaction"),
)
@click.option(
    "--recursive",
    is_flag=True,
    help=tr("cli.screenshot.recursive", default="Recursively scan subdirectories for MKV files"),
)
@click.option(
    "--verbose",
    "-v",
    count=True,
    help=tr("cli.screenshot.verbose", default="Increase verbosity (-v, -vv, -vvv)"),
)
def screenshot_command(
    videos: tuple[Path, ...],
    count: int,
    width: int | None,
    quality: int,
    format: str,
    output: Path | None,
    timestamps: str | None,
    release_name: str | None,
    skip_intro: int,
    skip_outro: int,
    skip_start_percent: float,
    skip_end_percent: float,
    no_black_detection: bool,
    all: bool,
    recursive: bool,
    verbose: int,
) -> None:
    """Extract screenshots from video files."""
    print_module_banner("Screenshot Extractor")

    # Configure verbosity
    configure_verbosity(verbose)
    if is_verbose():
        logger.info(f"Screenshot extraction with verbosity level {verbose}")

    # Convert videos tuple to list and expand directories
    video_paths = list(videos)

    # Expand directories to MKV files
    valid_videos = _expand_paths_to_videos(video_paths, recursive=recursive, process_all=all)

    if not valid_videos:
        print_error("No valid MKV files found")
        raise click.Abort()

    # Determine output directory
    if output:
        output_dir = output
    else:
        # Use parent directory of first video
        output_dir = valid_videos[0].parent

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Normalize format and ensure type safety
    screenshot_format: str = format
    if screenshot_format == "jpeg":
        screenshot_format = "jpg"

    # Create configuration
    config = ScreenshotConfig(
        count=count,
        width=width,
        quality=quality,
        format=screenshot_format,  # type: ignore[arg-type]
        skip_start_seconds=skip_intro,
        skip_end_seconds=skip_outro,
        skip_start_percent=skip_start_percent,
        skip_end_percent=skip_end_percent,
        avoid_black_frames=not no_black_detection,
    )

    # Initialize service
    service = ScreenshotService()

    if timestamps:
        _run_manual_screenshot_mode(
            service=service,
            valid_videos=valid_videos,
            output_dir=output_dir,
            config=config,
            release_name=release_name,
            timestamps=timestamps,
        )
        return

    _run_auto_screenshot_mode(
        service=service,
        valid_videos=valid_videos,
        output_dir=output_dir,
        config=config,
        release_name=release_name,
        count=count,
    )


def _display_single_result(result: ScreenshotResult) -> None:
    """Display result for single video extraction.

    Args:
        result: Screenshot extraction result
    """
    if result.success:
        print_success(f"Successfully extracted {len(result.screenshots)} screenshots")

        # Show screenshots table
        table = Table(
            title="Extracted Screenshots",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("#", style="dim", width=4)
        table.add_column("Timestamp", style="cyan")
        table.add_column("Filename", style="green")
        table.add_column("Size", style="yellow", justify="right")

        # ``strict=False``: ``result.screenshots`` and ``result.metadata``
        # can differ in length when an individual screenshot is filtered out
        # by black-frame detection but its metadata slot is still emitted.
        for idx, (screenshot, metadata) in enumerate(
            zip(result.screenshots, result.metadata, strict=False), start=1
        ):
            timestamp_str = _format_timestamp(metadata.timestamp_seconds)
            size_str = _format_file_size(metadata.file_size_bytes)

            table.add_row(
                str(idx),
                timestamp_str,
                screenshot.name,
                size_str,
            )

        console.print(table)
        print_info(f"Output directory: {result.output_dir}")
    else:
        print_error(f"Failed to extract screenshots: {result.error}")


def _display_report(report: ScreenshotReport) -> None:
    """Display report for batch extraction.

    Args:
        report: Screenshot extraction report
    """
    # Summary panel
    summary_lines = [
        f"Videos processed: {report.total_videos}",
        f"Screenshots extracted: {report.total_screenshots}",
        f"Failures: {report.total_failures}",
        f"Success rate: {report.success_rate * 100:.1f}%",
        f"Elapsed time: {report.elapsed_seconds:.2f}s",
    ]

    panel_style = "green" if report.total_failures == 0 else "yellow"
    console.print(
        Panel(
            "\n".join(summary_lines),
            title="Screenshot Extraction Summary",
            border_style=panel_style,
        )
    )

    # Results table
    if report.results:
        table = Table(
            title="Extraction Results",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Video", style="cyan")
        table.add_column("Screenshots", justify="right", style="green")
        table.add_column("Status", justify="center")
        table.add_column("Duration", justify="right", style="yellow")

        for result in report.results:
            status = "✓" if result.success else "✗"
            status_style = "green" if result.success else "red"

            duration_str = _format_timestamp(result.duration_seconds)

            table.add_row(
                result.video_path.name,
                str(len(result.screenshots)),
                f"[{status_style}]{status}[/{status_style}]",
                duration_str,
            )

        console.print(table)

    # Show errors if any
    errors = [r for r in report.results if not r.success]
    if errors:
        print_warning(f"\n{len(errors)} video(s) failed:")
        for result in errors:
            print_error(f"  • {result.video_path.name}: {result.error}")


def _format_timestamp(seconds: float) -> str:
    """Format timestamp as HH:MM:SS.

    Args:
        seconds: Timestamp in seconds

    Returns:
        Formatted timestamp string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _format_file_size(bytes: int) -> str:
    """Format file size in human-readable format.

    Args:
        bytes: File size in bytes

    Returns:
        Formatted file size string
    """
    size = float(bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


# Import at end to avoid circular dependency
from framekit.core.models.screenshot import ScreenshotReport, ScreenshotResult  # noqa: E402

select_many = _select_many  # backwards-compatible patch target for tests
