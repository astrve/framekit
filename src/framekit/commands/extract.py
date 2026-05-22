"""CLI commands for media extraction (subtitles, audio, video)."""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from framekit.core.i18n import tr
from framekit.core.tools import ToolRegistry
from framekit.core.verbose import configure_verbosity, is_verbose, log_file_processing
from framekit.modules.extract.models import (
    AudioExtractionOptions,
    AudioFormat,
    ExtractionOptions,
    SubtitleFormat,
    VideoCodec,
    VideoExtractionOptions,
)
from framekit.modules.extract.service import ExtractionService
from framekit.ui.branding import print_module_banner
from framekit.ui.click_helper import click
from framekit.ui.console import console, print_error, print_info, print_success, print_warning


@click.group("extract", context_settings={"help_option_names": ["-h", "--help"]})
def extract_command():
    """Beta commands for extracting and converting media streams.

    Supports extraction of subtitles, audio, and video streams with format conversion.
    """


@extract_command.command("subtitle", context_settings={"help_option_names": ["-h", "--help"]})
@click.argument(
    "files",
    nargs=-1,
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["srt", "ass", "vtt", "ssa", "original"]),
    default="original",
    help=tr("cli.extract.subtitle.format", default="Output subtitle format"),
)
@click.option(
    "--language",
    "-l",
    multiple=True,
    help=tr("cli.extract.subtitle.language", default="Filter by language code (e.g., eng, fra)"),
)
@click.option(
    "--all",
    "extract_all",
    is_flag=True,
    help=tr("cli.extract.subtitle.all", default="Extract all subtitle tracks"),
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help=tr("cli.extract.subtitle.output", default="Output directory"),
)
@click.option(
    "--no-forced",
    is_flag=True,
    help=tr("cli.extract.subtitle.no_forced", default="Exclude forced subtitle tracks"),
)
@click.option(
    "--no-sdh",
    is_flag=True,
    help=tr("cli.extract.subtitle.no_sdh", default="Exclude SDH/hearing impaired tracks"),
)
@click.option(
    "--verbose",
    "-v",
    count=True,
    help=tr("cli.extract.verbose", default="Increase verbosity (-v, -vv, -vvv)"),
)
def extract_subtitle_command(
    files: tuple[Path, ...],
    format: str,
    language: tuple[str, ...],
    extract_all: bool,
    output: Path | None,
    no_forced: bool,
    no_sdh: bool,
    verbose: int,
) -> None:
    """Extract subtitle tracks from video files.

    Examples:
        fk extract subtitle movie.mkv --format srt
        fk extract subtitle *.mkv --language eng --output ./subs
        fk extract subtitle movie.mkv --all
    """
    print_module_banner("Extract Subtitles")

    # Configure verbosity
    configure_verbosity(verbose)
    if is_verbose():
        logger.info(f"Processing {len(files)} file(s) with verbosity level {verbose}")

    # Initialize registry and service
    registry = ToolRegistry()
    service = ExtractionService(registry)

    # Build options
    subtitle_format = SubtitleFormat(format) if format != "original" else SubtitleFormat.ORIGINAL
    options = ExtractionOptions(
        output_format=subtitle_format,
        languages=list(language) if language else None,
        include_forced=not no_forced,
        include_sdh=not no_sdh,
        extract_all=extract_all,
        output_dir=output,
    )

    # Process files with progress
    print_info(f"Processing {len(files)} file(s)...")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Extracting subtitles...", total=len(files))

        def progress_callback(**kwargs):
            files_done = kwargs.get("files", 0)
            if files_done and is_verbose():
                current_file = kwargs.get("current_file", "")
                if current_file:
                    log_file_processing(current_file, status="extracted")
            progress.advance(task, files_done)

        report, _results = service.extract_subtitles(
            files=list(files),
            options=options,
            progress_callback=progress_callback,
        )

    # Print results
    if report.ok:
        print_success(f"Successfully extracted {report.modified} subtitle(s)")
    else:
        print_warning(f"Completed with {len(report.errors)} error(s)")
        for error in report.errors:
            print_error(f"  {error.message}")


@extract_command.command("audio", context_settings={"help_option_names": ["-h", "--help"]})
@click.argument(
    "files",
    nargs=-1,
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["aac", "mp3", "flac", "opus", "ac3", "original"]),
    default="original",
    help=tr("cli.extract.audio.format", default="Output audio format"),
)
@click.option(
    "--language",
    "-l",
    multiple=True,
    help=tr("cli.extract.audio.language", default="Filter by language code"),
)
@click.option(
    "--bitrate",
    "-b",
    help=tr("cli.extract.audio.bitrate", default="Target bitrate (e.g., 192k, 320k)"),
)
@click.option(
    "--normalize",
    is_flag=True,
    help=tr("cli.extract.audio.normalize", default="Apply audio normalization"),
)
@click.option(
    "--all",
    "extract_all",
    is_flag=True,
    help=tr("cli.extract.audio.all", default="Extract all audio tracks"),
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help=tr("cli.extract.audio.output", default="Output directory"),
)
@click.option(
    "--verbose",
    "-v",
    count=True,
    help=tr("cli.extract.verbose", default="Increase verbosity (-v, -vv, -vvv)"),
)
def extract_audio_command(
    files: tuple[Path, ...],
    format: str,
    language: tuple[str, ...],
    bitrate: str | None,
    normalize: bool,
    extract_all: bool,
    output: Path | None,
    verbose: int,
) -> None:
    """Extract audio tracks from video files.

    Examples:
        fk extract audio movie.mkv --format aac
        fk extract audio movie.mkv --format mp3 --bitrate 320k
        fk extract audio movie.mkv --normalize
    """
    print_module_banner("Extract Audio")

    # Configure verbosity
    configure_verbosity(verbose)
    if is_verbose():
        logger.info(f"Processing {len(files)} file(s) with verbosity level {verbose}")

    # Initialize registry and service
    registry = ToolRegistry()
    service = ExtractionService(registry)

    # Build options
    audio_format = AudioFormat(format) if format != "original" else AudioFormat.ORIGINAL
    options = AudioExtractionOptions(
        output_format=audio_format,
        languages=list(language) if language else None,
        bitrate=bitrate,
        normalize=normalize,
        extract_all=extract_all,
        output_dir=output,
    )

    # Process files with progress
    print_info(f"Processing {len(files)} file(s)...")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Extracting audio...", total=len(files))

        def progress_callback(**kwargs):
            files_done = kwargs.get("files", 0)
            if files_done and is_verbose():
                current_file = kwargs.get("current_file", "")
                if current_file:
                    log_file_processing(current_file, status="extracted")
            progress.advance(task, files_done)

        report, _results = service.extract_audio(
            files=list(files),
            options=options,
            progress_callback=progress_callback,
        )

    # Print results
    if report.ok:
        print_success(f"Successfully extracted {report.modified} audio track(s)")
    else:
        print_warning(f"Completed with {len(report.errors)} error(s)")
        for error in report.errors:
            print_error(f"  {error.message}")


@extract_command.command("video", context_settings={"help_option_names": ["-h", "--help"]})
@click.argument(
    "files",
    nargs=-1,
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
@click.option(
    "--codec",
    "-c",
    type=click.Choice(["h264", "h265", "vp9", "av1", "copy"]),
    default="copy",
    help=tr("cli.extract.video.codec", default="Output video codec"),
)
@click.option(
    "--crf",
    type=int,
    help=tr("cli.extract.video.crf", default="Quality (CRF value, lower = better)"),
)
@click.option(
    "--preset",
    type=click.Choice(["ultrafast", "fast", "medium", "slow", "veryslow"]),
    default="medium",
    help=tr("cli.extract.video.preset", default="Encoding preset"),
)
@click.option(
    "--width",
    "-w",
    type=int,
    help=tr("cli.extract.video.width", default="Target width in pixels"),
)
@click.option(
    "--height",
    "-H",
    type=int,
    help=tr("cli.extract.video.height", default="Target height in pixels"),
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help=tr("cli.extract.video.output", default="Output directory"),
)
@click.option(
    "--verbose",
    "-v",
    count=True,
    help=tr("cli.extract.verbose", default="Increase verbosity (-v, -vv, -vvv)"),
)
def extract_video_command(
    files: tuple[Path, ...],
    codec: str,
    crf: int | None,
    preset: str,
    width: int | None,
    height: int | None,
    output: Path | None,
    verbose: int,
) -> None:
    """Extract video streams from files.

    Examples:
        fk extract video movie.mkv --codec copy
        fk extract video movie.mkv --codec h265 --crf 28
        fk extract video movie.mkv --width 1920 --height 1080
    """
    print_module_banner("Extract Video")

    # Configure verbosity
    configure_verbosity(verbose)
    if is_verbose():
        logger.info(f"Processing {len(files)} file(s) with verbosity level {verbose}")

    # Initialize registry and service
    registry = ToolRegistry()
    service = ExtractionService(registry)

    # Build options
    video_codec = VideoCodec(codec)
    options = VideoExtractionOptions(
        output_codec=video_codec,
        crf=crf,
        preset=preset,
        width=width,
        height=height,
        output_dir=output,
    )

    # Process files with progress
    print_info(f"Processing {len(files)} file(s)...")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Extracting video...", total=len(files))

        def progress_callback(**kwargs):
            files_done = kwargs.get("files", 0)
            if files_done and is_verbose():
                current_file = kwargs.get("current_file", "")
                if current_file:
                    log_file_processing(current_file, status="extracted")
            progress.advance(task, files_done)

        report, _results = service.extract_video(
            files=list(files),
            options=options,
            progress_callback=progress_callback,
        )

    # Print results
    if report.ok:
        print_success(f"Successfully extracted {report.modified} video stream(s)")
    else:
        print_warning(f"Completed with {len(report.errors)} error(s)")
        for error in report.errors:
            print_error(f"  {error.message}")
