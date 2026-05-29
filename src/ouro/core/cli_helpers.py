"""Common CLI helper functions used across commands."""

from __future__ import annotations

from ouro.ui.console import print_error, print_info, print_warning

__all__ = ["join_path_parts", "print_fatal", "print_warning"]


def join_path_parts(parts: tuple[str, ...]) -> str:
    """Join path parts, filtering out empty strings."""
    return " ".join(part for part in parts if part).strip()


def print_fatal(message: str, hint: str | None = None) -> None:
    """Print a fatal error message and optional remediation hint."""
    if message:
        print_error(message)
    if hint:
        print_info(hint)
