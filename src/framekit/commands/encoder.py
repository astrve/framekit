"""CLI command for the Encoder module."""

from __future__ import annotations

from pathlib import Path

from rich.table import Table

from framekit.core.cli_helpers import join_path_parts
from framekit.core.settings import SettingsStore
from framekit.modules.encoder import EncoderService, EncoderValidator, PresetLoader
from framekit.ui.click_helper import click
from framekit.ui.console import console, print_error, print_info, print_success, print_warning


def _load_selected_preset(*, preset: str | None, preset_file: str | None, encoder_config: dict):
    loader = PresetLoader()
    if preset_file:
        return loader.load_preset(Path(preset_file))
    if preset:
        return loader.load_preset_by_name(preset)
    default_preset = encoder_config.get("default_preset", "")
    if default_preset:
        return loader.load_preset_by_name(default_preset)
    raise ValueError("No preset specified")


def _resolve_single_output(input_path: Path, output: str | None, encoder_config: dict) -> Path:
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return output_path
    output_dir_name = encoder_config.get("output_dir_name", "encoded")
    output_dir_path = input_path.parent / output_dir_name
    output_dir_path.mkdir(parents=True, exist_ok=True)
    return output_dir_path / f"{input_path.stem}_encoded{input_path.suffix}"


def _collect_video_files(input_path: Path, recursive: bool) -> list[Path]:
    if recursive:
        return list(input_path.rglob("*.mkv")) + list(input_path.rglob("*.mp4"))
    return list(input_path.glob("*.mkv")) + list(input_path.glob("*.mp4"))


def _resolve_batch_output_dir(
    input_path: Path, output_dir: str | None, encoder_config: dict
) -> Path:
    if output_dir:
        output_dir_path = Path(output_dir)
    else:
        output_dir_name = encoder_config.get("output_dir_name", "encoded")
        output_dir_path = input_path / output_dir_name
    output_dir_path.mkdir(parents=True, exist_ok=True)
    return output_dir_path


def _batch_output_path(
    *, input_root: Path, output_dir_path: Path, video_file: Path, recursive: bool
) -> Path:
    if recursive:
        rel_path = video_file.relative_to(input_root)
        output_file = (
            output_dir_path / rel_path.parent / f"{video_file.stem}_encoded{video_file.suffix}"
        )
        output_file.parent.mkdir(parents=True, exist_ok=True)
        return output_file
    return output_dir_path / f"{video_file.stem}_encoded{video_file.suffix}"


def _encode_directory(
    *,
    input_path: Path,
    output_dir_path: Path,
    recursive: bool,
    preset_obj,
    dry_run: bool,
    encoder_config: dict,
) -> int:
    video_files = _collect_video_files(input_path, recursive)
    if not video_files:
        print_warning("No video files found")
        return 0

    print_info(f"Found {len(video_files)} video file(s)")
    success_count = 0
    for video_file in video_files:
        output_file = _batch_output_path(
            input_root=input_path,
            output_dir_path=output_dir_path,
            video_file=video_file,
            recursive=recursive,
        )
        result = encode_single_file(video_file, output_file, preset_obj, dry_run, encoder_config)
        if result == 0:
            success_count += 1

    print_info(f"Completed: {success_count}/{len(video_files)} files encoded successfully")
    return 0 if success_count == len(video_files) else 1


def _build_encoder_service(preset, encoder_config: dict) -> EncoderService:
    ffmpeg_path = encoder_config.get("ffmpeg_path", "ffmpeg")
    ffprobe_path = encoder_config.get("ffprobe_path", "ffprobe")
    return EncoderService(preset, ffmpeg_path=ffmpeg_path, ffprobe_path=ffprobe_path)


def _print_encoder_init_error(exc: Exception) -> None:
    console.print("\n[bold red]✗ Failed to initialize encoder:[/bold red]")
    console.print(f"[red]  • {exc}[/red]")
    console.print("\n[yellow]Troubleshooting:[/yellow]")
    console.print("  1. Check if FFmpeg is installed: ffmpeg -version")
    console.print("  2. If FFmpeg is installed in a custom location, use:")
    console.print("     framekit settings set encoder.ffmpeg_path <path-to-ffmpeg>")
    console.print("  3. Run 'framekit encode check' to verify installation")


def _run_encoding(service: EncoderService, input_file: Path, output_file: Path):
    try:
        return service.encode(input_file, output_file, show_progress=True), None
    except KeyboardInterrupt:
        return None, "interrupted"
    except Exception as exc:
        return None, str(exc)


def _print_encoding_success(result) -> None:
    console.print("\n[bold green]✓ Encoding successful![/bold green]")
    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Input size", f"{result.input_size / (1024**3):.2f} GB")
    table.add_row("Output size", f"{result.output_size / (1024**3):.2f} GB")
    table.add_row(
        "Space saved", f"{result.space_saved_gb:.2f} GB ({result.compression_ratio:.1f}%)"
    )
    table.add_row("Encoding time", f"{result.duration:.1f}s")
    if result.avg_fps > 0:
        table.add_row("Average FPS", f"{result.avg_fps:.1f}")
    console.print(table)
    if result.warnings:
        console.print("\n[yellow]Warnings:[/yellow]")
        for warning in result.warnings:
            console.print(f"  • {warning}")


def _print_encoding_failure(errors: list[str]) -> None:
    console.print("\n[bold red]✗ Encoding failed![/bold red]")
    for error in errors:
        console.print(f"[red]  • {error}[/red]")


@click.group("encode", help="Video encoding with optimized h264/h265 presets")
def encode_group() -> None:
    """Encoder command group."""


@encode_group.command("run")
@click.argument("path_parts", nargs=-1)
@click.option("--preset", "-p", help="Preset name (e.g., films, series)")
@click.option("--preset-file", type=click.Path(exists=True), help="Custom preset YAML file")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option("--output-dir", type=click.Path(), help="Output directory for batch encoding")
@click.option("--recursive", "-r", is_flag=True, help="Process directories recursively")
@click.option("--dry-run", is_flag=True, help="Show what would be done without encoding")
def encode_command(
    path_parts: tuple[str, ...],
    preset: str | None,
    preset_file: str | None,
    output: str | None,
    output_dir: str | None,
    recursive: bool,
    dry_run: bool,
) -> int:
    """Encode video file(s) using a preset.

    Examples:
        framekit encode run input.mkv --preset films
        framekit encode run input.mkv --preset-file custom.yaml --output output.mkv
        framekit encode run folder/ --preset series --recursive --output-dir encoded/
    """
    store = SettingsStore()
    settings = store.load()
    encoder_config = settings.get("encoder", {})

    input_path_str = join_path_parts(path_parts)
    if not input_path_str:
        print_error("No input path specified")
        return 1

    input_path = Path(input_path_str)

    try:
        preset_obj = _load_selected_preset(
            preset=preset,
            preset_file=preset_file,
            encoder_config=encoder_config,
        )
    except FileNotFoundError:
        selected_name = preset or encoder_config.get("default_preset", "")
        print_error(f"Preset '{selected_name}' not found")
        print_info("Use 'framekit encode list-presets' to see available presets")
        return 1
    except ValueError:
        print_error("No preset specified")
        print_info("Use --preset or --preset-file to specify a preset")
        return 1
    except Exception as e:
        print_error(f"Failed to load preset: {e}")
        return 1

    # Check if input exists
    if not input_path.exists():
        print_error(f"Input path not found: {input_path}")
        return 1

    if input_path.is_file():
        output_path = _resolve_single_output(input_path, output, encoder_config)
        return encode_single_file(input_path, output_path, preset_obj, dry_run, encoder_config)

    if input_path.is_dir():
        output_dir_path = _resolve_batch_output_dir(input_path, output_dir, encoder_config)
        return _encode_directory(
            input_path=input_path,
            output_dir_path=output_dir_path,
            recursive=recursive,
            preset_obj=preset_obj,
            dry_run=dry_run,
            encoder_config=encoder_config,
        )

    print_error(f"Invalid input path: {input_path}")
    return 1


def encode_single_file(
    input_file: Path, output_file: Path, preset, dry_run: bool, encoder_config: dict
) -> int:
    """Encode a single file."""
    console.print(f"\n[bold cyan]Encoding:[/bold cyan] {input_file.name}")
    console.print(f"[bold cyan]Preset:[/bold cyan] {preset.name}")
    console.print(f"[bold cyan]Output:[/bold cyan] {output_file}")

    if dry_run:
        console.print("[yellow]Dry run - skipping actual encoding[/yellow]")
        return 0

    try:
        service = _build_encoder_service(preset, encoder_config)
    except RuntimeError as e:
        _print_encoder_init_error(e)
        return 1
    except Exception as e:
        console.print("\n[bold red]✗ Unexpected error:[/bold red]")
        console.print(f"[red]  • {e}[/red]")
        return 1

    result, encode_error = _run_encoding(service, input_file, output_file)
    if encode_error == "interrupted":
        console.print("\n[yellow]Encoding interrupted by user[/yellow]")
        return 1
    if encode_error:
        console.print("\n[bold red]✗ Encoding error:[/bold red]")
        console.print(f"[red]  • {encode_error}[/red]")
        return 1
    if result is None:
        return 1

    if result.success:
        _print_encoding_success(result)
        return 0
    _print_encoding_failure(result.errors)
    return 1


@encode_group.command("list-presets")
def list_presets_command() -> int:
    """List all available encoding presets."""
    loader = PresetLoader()
    presets = loader.list_presets()

    console.print("\n[bold cyan]Available Encoding Presets[/bold cyan]\n")

    # h264 to h265
    if presets["h264_to_h265"]:
        console.print("[bold]h264 -> h265:[/bold]")
        for preset_name in sorted(presets["h264_to_h265"]):
            try:
                info = loader.get_preset_info(preset_name)
                aliases = info.get("aliases", [])
                if aliases:
                    aliases_str = f" [dim](aliases: {', '.join(aliases)})[/dim]"
                else:
                    aliases_str = ""
                console.print(f"  - [cyan]{preset_name}[/cyan]: {info['description']}{aliases_str}")
            except Exception:
                console.print(f"  - [cyan]{preset_name}[/cyan]")
        console.print()

    # h265 to h264
    if presets["h265_to_h264"]:
        console.print("[bold]h265 -> h264:[/bold]")
        for preset_name in sorted(presets["h265_to_h264"]):
            try:
                info = loader.get_preset_info(preset_name)
                aliases = info.get("aliases", [])
                if aliases:
                    aliases_str = f" [dim](aliases: {', '.join(aliases)})[/dim]"
                else:
                    aliases_str = ""
                console.print(f"  - [cyan]{preset_name}[/cyan]: {info['description']}{aliases_str}")
            except Exception:
                console.print(f"  - [cyan]{preset_name}[/cyan]")
        console.print()

    return 0


@encode_group.command("show-preset")
@click.argument("preset")
def show_preset_command(preset: str) -> int:
    """Show detailed information about a preset."""
    loader = PresetLoader()

    try:
        preset_obj = loader.load_preset_by_name(preset)
    except FileNotFoundError:
        print_error(f"Preset '{preset}' not found")
        return 1

    # Display preset details
    console.print(f"\n[bold cyan]{preset_obj.name}[/bold cyan]")
    console.print(f"{preset_obj.description}\n")

    table = Table(show_header=False, box=None)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Source Codec", preset_obj.source_codec)
    table.add_row("Target Codec", preset_obj.target_codec)
    table.add_row("Encoder", preset_obj.encoder)
    table.add_row("", "")
    table.add_row("[bold]Video Settings[/bold]", "")
    table.add_row("  CRF", str(preset_obj.video.crf))
    table.add_row("  Preset", preset_obj.video.preset)
    if preset_obj.video.tune:
        table.add_row("  Tune", preset_obj.video.tune)
    table.add_row("  Profile", preset_obj.video.profile)
    table.add_row("  Level", preset_obj.video.level)
    table.add_row("  Pixel Format", preset_obj.video.pix_fmt)

    if preset_obj.advanced.x265_params or preset_obj.advanced.x264_params:
        table.add_row("", "")
        table.add_row("[bold]Advanced[/bold]", "")
        params = preset_obj.advanced.x265_params or preset_obj.advanced.x264_params
        for param in params:
            table.add_row("  ", param)

    console.print(table)
    console.print()

    return 0


@encode_group.command("create-preset")
@click.argument("output", type=click.Path())
@click.option(
    "--type",
    "-t",
    "preset_type",
    default="h264_to_h265",
    type=click.Choice(["h264_to_h265", "h265_to_h264"]),
    help="Preset type",
)
def create_preset_command(output: str, preset_type: str) -> int:
    """Create a preset template file."""
    loader = PresetLoader()
    output_path = Path(output)

    try:
        loader.create_preset_template(output_path, preset_type)
        print_success(f"Preset template created: {output_path}")
        print_info("\nEdit the file to customize the preset, then use it with:")
        print_info(f"  framekit encode run input.mkv --preset-file {output_path}")
        return 0
    except Exception as e:
        print_error(f"Failed to create preset: {e}")
        return 1


@encode_group.command("check")
def check_command() -> int:
    """Check if ffmpeg is available and working."""
    validator = EncoderValidator()

    console.print("\n[bold cyan]Checking encoder dependencies...[/bold cyan]\n")

    # Check ffmpeg
    ffmpeg_result = validator.check_ffmpeg_available()
    if ffmpeg_result.valid:
        console.print("[green]OK[/green] ffmpeg is available")
    else:
        console.print("[red]FAIL[/red] ffmpeg is not available")
        for error in ffmpeg_result.errors:
            console.print(f"  [red]{error}[/red]")

    # Check ffprobe
    ffprobe_result = validator.check_ffprobe_available()
    if ffprobe_result.valid:
        console.print("[green]OK[/green] ffprobe is available")
    else:
        console.print("[red]FAIL[/red] ffprobe is not available")
        for error in ffprobe_result.errors:
            console.print(f"  [red]{error}[/red]")

    console.print()

    if not (ffmpeg_result.valid and ffprobe_result.valid):
        console.print("[yellow]Please install ffmpeg to use the encoder module.[/yellow]")
        console.print("Visit: https://ffmpeg.org/download.html")
        return 1

    return 0
