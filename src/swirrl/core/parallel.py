"""Parallel processing utilities for performance optimization."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, TypeVar

from swirrl.core.diagnostics import log_event
from swirrl.core.performance import profile_time

T = TypeVar("T")
R = TypeVar("R")


def get_optimal_worker_count(max_workers: int | None = None) -> int:
    """Get optimal number of workers based on CPU count.

    Args:
        max_workers: Maximum workers to use (None = auto-detect)

    Returns:
        Optimal worker count
    """
    cpu_count = os.cpu_count() or 4

    if max_workers is None:
        # Use 75% of available CPUs by default
        return max(1, int(cpu_count * 0.75))

    return min(max_workers, cpu_count)


@profile_time("parallel_map")
def parallel_map(
    func: Callable[[T], R],
    items: Iterable[T],
    *,
    max_workers: int | None = None,
    use_processes: bool = False,
    desc: str | None = None,
) -> list[R]:
    """Apply a function to items in parallel.

    Args:
        func: Function to apply to each item
        items: Items to process
        max_workers: Maximum number of workers (None = auto-detect)
        use_processes: Use processes instead of threads
        desc: Description for logging

    Returns:
        List of results in original order
    """
    items_list = list(items)
    if not items_list:
        return []

    # For small lists, don't use parallelization
    if len(items_list) < 3:
        return [func(item) for item in items_list]

    workers = get_optimal_worker_count(max_workers)
    executor_class = ProcessPoolExecutor if use_processes else ThreadPoolExecutor

    log_event(
        "DEBUG",
        f"Parallel processing: {desc or 'items'}",
        count=len(items_list),
        workers=workers,
        use_processes=use_processes,
    )

    with executor_class(max_workers=workers) as executor:
        futures = [executor.submit(func, item) for item in items_list]
        try:
            results = [future.result() for future in futures]
        except BaseException:
            # Cancel anything not yet started so the executor shuts down
            # quickly. Already-running futures will still complete, but the
            # caller gets the first exception immediately and no result of a
            # later future is silently dropped on the floor.
            for pending in futures:
                pending.cancel()
            raise

    return results


@profile_time("parallel_map_unordered")
def parallel_map_unordered(
    func: Callable[[T], R],
    items: Iterable[T],
    *,
    max_workers: int | None = None,
    use_processes: bool = False,
    desc: str | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[R]:
    """Apply a function to items in parallel (results may be out of order).

    This is faster than parallel_map when order doesn't matter.

    Args:
        func: Function to apply to each item
        items: Items to process
        max_workers: Maximum number of workers (None = auto-detect)
        use_processes: Use processes instead of threads
        desc: Description for logging
        progress_callback: Optional callback(completed, total)

    Returns:
        List of results (order not guaranteed)
    """
    items_list = list(items)
    if not items_list:
        return []

    # For small lists, don't use parallelization
    if len(items_list) < 3:
        results = []
        for idx, item in enumerate(items_list, 1):
            results.append(func(item))
            if progress_callback:
                progress_callback(idx, len(items_list))
        return results

    workers = get_optimal_worker_count(max_workers)
    executor_class = ProcessPoolExecutor if use_processes else ThreadPoolExecutor

    log_event(
        "DEBUG",
        f"Parallel processing (unordered): {desc or 'items'}",
        count=len(items_list),
        workers=workers,
        use_processes=use_processes,
    )

    results = []
    with executor_class(max_workers=workers) as executor:
        futures = {executor.submit(func, item): item for item in items_list}

        for idx, future in enumerate(as_completed(futures), 1):
            results.append(future.result())
            if progress_callback:
                progress_callback(idx, len(items_list))

    return results


def parallel_scan_files(
    paths: list[Path],
    scan_func: Callable[[Path], T],
    *,
    max_workers: int | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[T]:
    """Scan multiple files in parallel.

    Args:
        paths: List of file paths to scan
        scan_func: Function to scan a single file
        max_workers: Maximum number of workers
        progress_callback: Optional callback(completed, total)

    Returns:
        List of scan results
    """
    return parallel_map_unordered(
        scan_func,
        paths,
        max_workers=max_workers,
        use_processes=False,  # I/O-bound, use threads
        desc="file scanning",
        progress_callback=progress_callback,
    )


def batch_process(
    items: list[T],
    process_func: Callable[[T], R],
    *,
    batch_size: int = 10,
    max_workers: int | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[R]:
    """Process items in batches with parallelization.

    Args:
        items: Items to process
        process_func: Function to process a single item
        batch_size: Number of items per batch
        max_workers: Maximum number of workers
        progress_callback: Optional callback(completed, total)

    Returns:
        List of results
    """
    if not items:
        return []

    # Create batches
    batches = [items[i : i + batch_size] for i in range(0, len(items), batch_size)]

    def process_batch(batch: list[T]) -> list[R]:
        """Process a single batch."""
        return [process_func(item) for item in batch]

    # Process batches in parallel
    batch_results = parallel_map_unordered(
        process_batch,
        batches,
        max_workers=max_workers,
        use_processes=False,
        desc=f"batch processing ({len(batches)} batches)",
    )

    # Flatten results
    results = []
    completed = 0
    for batch_result in batch_results:
        results.extend(batch_result)
        completed += len(batch_result)
        if progress_callback:
            progress_callback(completed, len(items))

    return results


class ParallelProcessor:
    """Reusable parallel processor with configurable settings."""

    def __init__(
        self,
        max_workers: int | None = None,
        use_processes: bool = False,
    ) -> None:
        """Initialize parallel processor.

        Args:
            max_workers: Maximum number of workers
            use_processes: Use processes instead of threads
        """
        self.max_workers = get_optimal_worker_count(max_workers)
        self.use_processes = use_processes
        self._executor = None

    def __enter__(self) -> ParallelProcessor:
        """Enter context manager."""
        executor_class = ProcessPoolExecutor if self.use_processes else ThreadPoolExecutor
        self._executor = executor_class(max_workers=self.max_workers)
        return self

    def __exit__(self, *args: Any) -> None:
        """Exit context manager."""
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None

    def map(
        self,
        func: Callable[[T], R],
        items: Iterable[T],
    ) -> list[R]:
        """Map function over items in parallel.

        Args:
            func: Function to apply
            items: Items to process

        Returns:
            List of results
        """
        if not self._executor:
            raise RuntimeError("ParallelProcessor must be used as context manager")

        items_list = list(items)
        if not items_list:
            return []

        futures = [self._executor.submit(func, item) for item in items_list]
        try:
            return [future.result() for future in futures]
        except BaseException:
            for pending in futures:
                pending.cancel()
            raise

    def map_unordered(
        self,
        func: Callable[[T], R],
        items: Iterable[T],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[R]:
        """Map function over items in parallel (unordered results).

        Args:
            func: Function to apply
            items: Items to process
            progress_callback: Optional callback(completed, total)

        Returns:
            List of results (order not guaranteed)
        """
        if not self._executor:
            raise RuntimeError("ParallelProcessor must be used as context manager")

        items_list = list(items)
        if not items_list:
            return []

        futures = {self._executor.submit(func, item): item for item in items_list}
        results = []

        for idx, future in enumerate(as_completed(futures), 1):
            results.append(future.result())
            if progress_callback:
                progress_callback(idx, len(items_list))

        return results
