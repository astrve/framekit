"""Verbose mode configuration and utilities for enhanced logging.

This module provides a centralized way to manage verbosity levels across
the Framekit CLI, integrating with loguru for structured logging.

Verbosity Levels:
    - NORMAL (0): Standard output, warnings and errors only
    - VERBOSE (1): Detailed progress, file-by-file status
    - DEBUG (2): Debug information, show commands being executed
    - TRACE (3): Trace-level details, all subprocess output

Usage:
    # In CLI commands
    @click.option('--verbose', '-v', count=True)
    def my_command(verbose: int):
        configure_verbosity(verbose)
        # ... command logic

    # Check verbosity level
    if is_verbose():
        print_info("Detailed information")

    if should_show_commands():
        print_info(f"Running: {command}")
"""

from __future__ import annotations

import sys
from collections.abc import Generator
from contextlib import contextmanager, suppress
from enum import IntEnum

from loguru import logger


class VerbosityLevel(IntEnum):
    """Verbosity levels for CLI output."""

    NORMAL = 0  # Standard output
    VERBOSE = 1  # Detailed progress
    DEBUG = 2  # Debug information, show commands
    TRACE = 3  # Trace-level details, subprocess output

    @classmethod
    def from_count(cls, count: int) -> VerbosityLevel:
        """Convert Click count to VerbosityLevel.

        Args:
            count: Number of -v flags (0, 1, 2, 3+)

        Returns:
            Corresponding VerbosityLevel
        """
        if count <= 0:
            return cls.NORMAL
        elif count == 1:
            return cls.VERBOSE
        elif count == 2:
            return cls.DEBUG
        else:
            return cls.TRACE


# Global verbosity state
_current_verbosity: VerbosityLevel = VerbosityLevel.NORMAL
_loguru_handler_id: int | None = None


def _remove_verbose_handler() -> None:
    global _loguru_handler_id

    if _loguru_handler_id is None:
        return
    with suppress(Exception):
        logger.remove(_loguru_handler_id)
    _loguru_handler_id = None


def configure_verbosity(level: int | VerbosityLevel) -> None:
    """Configure verbosity level and loguru logging.

    Args:
        level: Verbosity level (int count or VerbosityLevel enum)
    """
    global _current_verbosity, _loguru_handler_id

    # Convert to VerbosityLevel if needed
    if isinstance(level, VerbosityLevel):
        _current_verbosity = level
    else:
        _current_verbosity = VerbosityLevel.from_count(level)

    # Configure loguru based on verbosity level
    log_level = get_log_level_string()

    # Remove existing handler if any
    _remove_verbose_handler()

    # Add new handler with appropriate level
    _loguru_handler_id = logger.add(
        sys.stderr,
        level=log_level,
        format="<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        colorize=True,
    )


def get_verbosity_level() -> VerbosityLevel:
    """Get current verbosity level.

    Returns:
        Current VerbosityLevel
    """
    return _current_verbosity


def reset_verbosity() -> None:
    """Reset verbosity to default (NORMAL) level."""
    global _current_verbosity, _loguru_handler_id

    _current_verbosity = VerbosityLevel.NORMAL

    _remove_verbose_handler()


def is_verbose() -> bool:
    """Check if any verbose mode is active.

    Returns:
        True if verbosity level is above NORMAL
    """
    return _current_verbosity > VerbosityLevel.NORMAL


def should_show_progress() -> bool:
    """Check if progress bars should be shown.

    Returns:
        True if progress bars should be displayed
    """
    # Show progress at all levels (can be disabled at TRACE if needed)
    return True


def should_show_commands() -> bool:
    """Check if commands should be displayed.

    Returns:
        True if commands (FFmpeg, mkvmerge, etc.) should be shown
    """
    return _current_verbosity >= VerbosityLevel.DEBUG


def should_show_subprocess_output() -> bool:
    """Check if subprocess output should be displayed.

    Returns:
        True if full subprocess output should be shown
    """
    return _current_verbosity >= VerbosityLevel.TRACE


def get_log_level_string() -> str:
    """Get loguru log level string for current verbosity.

    Returns:
        Log level string ('WARNING', 'INFO', 'DEBUG', 'TRACE')
    """
    if _current_verbosity == VerbosityLevel.NORMAL:
        return "WARNING"
    elif _current_verbosity == VerbosityLevel.VERBOSE:
        return "INFO"
    elif _current_verbosity == VerbosityLevel.DEBUG:
        return "DEBUG"
    else:  # TRACE
        return "TRACE"


@contextmanager
def verbosity_context(level: VerbosityLevel) -> Generator[None, None, None]:
    """Context manager for temporary verbosity level.

    Args:
        level: Temporary verbosity level

    Yields:
        None

    Example:
        with verbosity_context(VerbosityLevel.DEBUG):
            # Code runs with DEBUG verbosity
            pass
        # Verbosity restored to previous level
    """
    previous_level = _current_verbosity
    configure_verbosity(level)
    try:
        yield
    finally:
        configure_verbosity(previous_level)


def log_command(command: list[str] | str, *, tool: str = "command") -> None:
    """Log a command if verbosity level allows.

    Args:
        command: Command to log (list or string)
        tool: Tool name (e.g., 'ffmpeg', 'mkvmerge')
    """
    if should_show_commands():
        if isinstance(command, list):
            cmd_str = " ".join(command)
        else:
            cmd_str = command
        logger.debug(f"[{tool}] {cmd_str}")


def log_subprocess_output(output: str, *, tool: str = "subprocess") -> None:
    """Log subprocess output if verbosity level allows.

    Args:
        output: Subprocess output to log
        tool: Tool name
    """
    if should_show_subprocess_output():
        for line in output.splitlines():
            if line.strip():
                logger.trace(f"[{tool}] {line}")


def log_file_processing(file_path: str, *, status: str = "processing") -> None:
    """Log file processing status if verbose.

    Args:
        file_path: Path to file being processed
        status: Status message (e.g., 'processing', 'completed', 'skipped')
    """
    if is_verbose():
        logger.info(f"[{status}] {file_path}")
