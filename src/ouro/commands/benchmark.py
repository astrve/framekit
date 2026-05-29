"""Benchmark command for performance testing."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ouro.core.diagnostics import log_event
from ouro.core.i18n import tr
from ouro.core.performance import get_metrics
from ouro.ui.click_helper import click
from ouro.ui.console import console, print_info


def _format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 0.001:
        return f"{seconds * 1000000:.0f}µs"
    if seconds < 1:
        return f"{seconds * 1000:.1f}ms"
    if seconds < 60:
        return f"{seconds:.2f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.1f}s"


def _format_size(bytes_val: int | float) -> str:  # pyright: ignore[reportUnusedFunction]  # Utility helper kept for ad-hoc benchmarking output
    """Format size in human-readable format."""
    size = float(bytes_val)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}PB"


def _benchmark_import_time(iterations: int) -> dict[str, Any]:
    console.print("[bold]1. Import Performance[/bold]")
    import_times = []
    for i in range(iterations):
        start = time.perf_counter()
        # Simulate fresh import by clearing module cache
        import sys

        modules_to_clear = [m for m in sys.modules if m.startswith("ouro")]
        for mod in modules_to_clear:
            if mod not in ["ouro", "ouro.commands", "ouro.commands.benchmark"]:
                sys.modules.pop(mod, None)
        duration = time.perf_counter() - start
        import_times.append(duration)
        console.print(f"  Iteration {i + 1}: {_format_duration(duration)}")
    avg_import = sum(import_times) / len(import_times)
    console.print(f"  [green]Average: {_format_duration(avg_import)}[/green]")
    console.print()
    return {
        "avg": avg_import,
        "min": min(import_times),
        "max": max(import_times),
        "iterations": import_times,
    }


def _benchmark_settings_load(iterations: int) -> dict[str, Any]:
    console.print("[bold]2. Settings Load Performance[/bold]")
    from ouro.core.settings import SettingsStore

    settings_times = []
    for i in range(iterations):
        start = time.perf_counter()
        store = SettingsStore()
        store.load()
        duration = time.perf_counter() - start
        settings_times.append(duration)
        console.print(f"  Iteration {i + 1}: {_format_duration(duration)}")
    avg_settings = sum(settings_times) / len(settings_times)
    console.print(f"  [green]Average: {_format_duration(avg_settings)}[/green]")
    console.print()
    return {
        "avg": avg_settings,
        "min": min(settings_times),
        "max": max(settings_times),
        "iterations": settings_times,
    }


def _scan_benchmark(
    *,
    folder: Path,
    iterations: int,
    parallel: bool,
) -> dict[str, Any]:
    from ouro.core.tools import ToolRegistry
    from ouro.modules.cleanmkv.scanner import scan_folder

    registry = ToolRegistry()
    label = "Parallel" if parallel else "Sequential"
    console.print(f"  [cyan]{label} scanning:[/cyan]")
    timings = []
    for i in range(iterations):
        start = time.perf_counter()
        scans = scan_folder(folder, registry, parallel=parallel)
        duration = time.perf_counter() - start
        timings.append(duration)
        console.print(f"    Iteration {i + 1}: {_format_duration(duration)} ({len(scans)} files)")
    avg_duration = sum(timings) / len(timings)
    console.print(f"    [green]Average: {_format_duration(avg_duration)}[/green]")
    return {
        "avg": avg_duration,
        "min": min(timings),
        "max": max(timings),
        "iterations": timings,
    }


def _benchmark_file_scanning(folder: Path, iterations: int) -> dict[str, dict[str, Any]]:
    console.print("[bold]3. File Scanning Performance[/bold]")
    sequential = _scan_benchmark(folder=folder, iterations=iterations, parallel=False)
    parallel = _scan_benchmark(folder=folder, iterations=iterations, parallel=True)
    if sequential["avg"] > 0:
        speedup = sequential["avg"] / parallel["avg"]
        console.print(f"    [bold green]Speedup: {speedup:.2f}x[/bold green]")
    console.print()
    return {
        "scan_sequential": sequential,
        "scan_parallel": parallel,
    }


def _print_recorded_metrics(stats: dict[str, Any]) -> None:
    if not stats:
        return
    console.print("[bold]4. Recorded Performance Metrics[/bold]")
    for operation, op_stats in stats.items():
        if not op_stats:
            continue
        console.print(f"  [cyan]{operation}:[/cyan]")
        console.print(f"    Count: {op_stats['count']}")
        console.print(f"    Total: {_format_duration(op_stats['total'])}")
        console.print(f"    Average: {_format_duration(op_stats['avg'])}")
        console.print(f"    Min: {_format_duration(op_stats['min'])}")
        console.print(f"    Max: {_format_duration(op_stats['max'])}")
    console.print()


def _print_benchmark_summary(results: dict[str, dict[str, Any]], *, folder: Path | None) -> None:
    console.print("[bold]Summary[/bold]")
    console.print(f"  Import time: {_format_duration(results['import_time']['avg'])}")
    console.print(f"  Settings load: {_format_duration(results['settings_load']['avg'])}")
    if folder and "scan_parallel" in results:
        console.print(
            f"  File scanning (parallel): {_format_duration(results['scan_parallel']['avg'])}"
        )
    console.print()


def _export_benchmark_results(
    *,
    export: Path | None,
    iterations: int,
    results: dict[str, dict[str, Any]],
    metrics_stats: dict[str, Any],
) -> None:
    if not export:
        return
    import json

    export_data = {
        "timestamp": time.time(),
        "iterations": iterations,
        "results": results,
        "metrics": metrics_stats,
    }
    export.write_text(json.dumps(export_data, indent=2))
    print_info(
        tr(
            "benchmark.exported",
            default="Results exported to: {path}",
            path=str(export),
        )
    )


@click.command(
    "benchmark",
    help=tr(
        "cli.benchmark.help",
        default=(
            "Run performance benchmarks and analyze Ouro's speed.\n\n"
            "The benchmark command measures import times, settings load performance, file scanning "
            "speed, and other operations to help identify bottlenecks and optimization opportunities.\n\n"
            "Quick examples:\n"
            "  ouro doctor benchmark                     # Run basic benchmarks\n"
            "  ouro doc benchmark --folder <path>        # Include file scanning tests\n"
            "  ouro doctor benchmark --iterations 5      # More iterations for accuracy\n"
            "  ouro doc benchmark --export results.json  # Save results to file\n\n"
            "Benchmarks performed:\n"
            "  • Module import time\n"
            "  • Settings load performance\n"
            "  • File scanning (sequential vs parallel)\n"
            "  • Recorded performance metrics\n\n"
            "Features:\n"
            "  • Multiple iterations for statistical accuracy\n"
            "  • Parallel vs sequential comparison\n"
            "  • JSON export for tracking over time\n"
            "  • Performance metrics integration\n\n"
            "Best practices:\n"
            "  • Run on representative test folders\n"
            "  • Use multiple iterations (3-5) for accuracy\n"
            "  • Export results to track performance over time\n"
            "  • Compare before/after optimization changes\n\n"
            "Note: This is a subcommand of 'doctor'. Use 'ouro doctor' for health checks."
        ),
    ),
)
@click.option(
    "--folder",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help=tr(
        "cli.benchmark.folder_help",
        default="Test folder with sample releases",
    ),
)
@click.option(
    "--iterations",
    type=int,
    default=3,
    help=tr(
        "cli.benchmark.iterations_help",
        default="Number of iterations for each test",
    ),
)
@click.option(
    "--export",
    type=click.Path(dir_okay=False, path_type=Path),
    help=tr(
        "cli.benchmark.export_help",
        default="Export results to JSON file",
    ),
)
def benchmark_command(
    folder: Path | None,
    iterations: int,
    export: Path | None,
) -> None:
    """Run performance benchmarks."""
    console.print()
    console.print("[bold cyan]Ouro Performance Benchmark[/bold cyan]")
    console.print()

    results: dict[str, dict[str, Any]] = {}
    results["import_time"] = _benchmark_import_time(iterations)
    results["settings_load"] = _benchmark_settings_load(iterations)
    if folder:
        results.update(_benchmark_file_scanning(folder, iterations))

    metrics = get_metrics()
    stats = metrics.get_stats()
    _print_recorded_metrics(stats)
    _print_benchmark_summary(results, folder=folder)
    _export_benchmark_results(
        export=export,
        iterations=iterations,
        results=results,
        metrics_stats=stats,
    )
    log_event("INFO", "Benchmark completed", results=results)
