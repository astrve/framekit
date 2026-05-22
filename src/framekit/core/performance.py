"""Performance profiling and optimization utilities."""

from __future__ import annotations

import functools
import gc
import os
import time
import tracemalloc
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from framekit.core.diagnostics import log_event

F = TypeVar("F", bound=Callable[..., Any])


class PerformanceMetrics:
    """Store and track performance metrics."""

    def __init__(self) -> None:
        """Initialize performance metrics."""
        self._metrics: dict[str, list[dict[str, Any]]] = {}
        self._enabled = os.getenv("FRAMEKIT_PROFILE", "0") == "1"

    def record(self, operation: str, duration: float, **kwargs: Any) -> None:
        """Record a performance metric."""
        if not self._enabled:
            return

        if operation not in self._metrics:
            self._metrics[operation] = []

        self._metrics[operation].append(
            {
                "duration": duration,
                "timestamp": time.time(),
                **kwargs,
            }
        )

    def get_stats(self, operation: str | None = None) -> dict[str, Any]:
        """Get performance statistics."""
        if operation:
            metrics = self._metrics.get(operation, [])
            if not metrics:
                return {}

            durations = [m["duration"] for m in metrics]
            return {
                "count": len(durations),
                "total": sum(durations),
                "avg": sum(durations) / len(durations),
                "min": min(durations),
                "max": max(durations),
            }

        return {op: self.get_stats(op) for op in self._metrics}

    def clear(self) -> None:
        """Clear all metrics."""
        self._metrics.clear()


# Global metrics instance
_metrics = PerformanceMetrics()


def get_metrics() -> PerformanceMetrics:
    """Get the global performance metrics instance."""
    return _metrics


def profile_time(operation: str | None = None, threshold: float | None = None) -> Callable[[F], F]:
    """Decorator to profile execution time of a function.

    Args:
        operation: Name of the operation (defaults to function name)
        threshold: Log warning if execution exceeds this threshold (seconds)

    Example:
        @profile_time("scan_folder", threshold=5.0)
        def scan_folder(path):
            ...
    """

    def decorator(func: F) -> F:
        op_name = operation or func.__name__

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.perf_counter() - start
                _metrics.record(op_name, duration)

                if threshold and duration > threshold:
                    log_event(
                        "WARNING",
                        f"Slow operation: {op_name}",
                        duration=duration,
                        threshold=threshold,
                    )

        return wrapper  # type: ignore

    return decorator


def profile_memory(operation: str | None = None) -> Callable[[F], F]:
    """Decorator to profile memory usage of a function.

    Args:
        operation: Name of the operation (defaults to function name)

    Example:
        @profile_memory("load_large_file")
        def load_large_file(path):
            ...
    """

    def decorator(func: F) -> F:
        op_name = operation or func.__name__

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            tracemalloc.start()
            try:
                result = func(*args, **kwargs)
                current, peak = tracemalloc.get_traced_memory()

                log_event(
                    "DEBUG",
                    f"Memory usage: {op_name}",
                    current_mb=current / 1024 / 1024,
                    peak_mb=peak / 1024 / 1024,
                )

                return result
            finally:
                tracemalloc.stop()

        return wrapper  # type: ignore

    return decorator


def clear_memory() -> None:
    """Force garbage collection to free memory."""
    gc.collect()


def get_file_size_mb(path: Path) -> float:
    """Get file size in megabytes."""
    return path.stat().st_size / 1024 / 1024


class StreamingFileReader:
    """Read large files in chunks to avoid loading entire file into memory."""

    def __init__(self, path: Path, chunk_size: int = 8192 * 1024) -> None:
        """Initialize streaming file reader.

        Args:
            path: Path to file
            chunk_size: Size of chunks to read (default: 8MB)
        """
        self.path = path
        self.chunk_size = chunk_size

    def read_chunks(self) -> Any:
        """Read file in chunks."""
        with open(self.path, "rb") as f:
            while True:
                chunk = f.read(self.chunk_size)
                if not chunk:
                    break
                yield chunk


class LazyImporter:
    """Lazy import modules to reduce startup time.

    Security: Only allows importing from a whitelist of known safe modules
    to prevent arbitrary code execution via dynamic imports.
    """

    # Whitelist of allowed modules for lazy import
    _ALLOWED_MODULES = frozenset(
        {
            "jinja2",
            "rich",
            "click",
            "httpx",
            "PIL",
            "pymediainfo",
            "guessit",
            "babelfish",
            "pycountry",
        }
    )

    def __init__(self, module_name: str) -> None:
        """Initialize lazy importer.

        Args:
            module_name: Name of module to import (must be in whitelist)

        Raises:
            ValueError: If module_name is not in the whitelist
        """
        if module_name not in self._ALLOWED_MODULES:
            raise ValueError(
                f"Module '{module_name}' is not in the allowed modules whitelist. "
                f"Allowed modules: {sorted(self._ALLOWED_MODULES)}"
            )
        self.module_name = module_name
        self._module = None

    def __getattr__(self, name: str) -> Any:
        """Import module on first attribute access."""
        if self._module is None:
            import importlib

            # Justification: module_name is validated against a whitelist in __init__
            # nosemgrep: python.lang.security.audit.non-literal-import.non-literal-import
            self._module = importlib.import_module(self.module_name)
        return getattr(self._module, name)


def lazy_import(module_name: str) -> LazyImporter:
    """Create a lazy importer for a module.

    Security: Only modules in the whitelist can be imported.

    Example:
        jinja2 = lazy_import("jinja2")
        # Module is not imported until first use
        env = jinja2.Environment()

    Raises:
        ValueError: If module_name is not in the whitelist
    """
    return LazyImporter(module_name)
