"""Screenshot filename generation and sanitization utilities."""

from __future__ import annotations

import re
from pathlib import Path

# Windows reserved filenames
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}

# Maximum filename length (conservative limit for cross-platform compatibility)
MAX_FILENAME_LENGTH = 200


def sanitize_release_name(name: str) -> str:
    r"""Sanitize release name for use in filenames.

    Removes or replaces characters that are:
    - Invalid in filenames (: / \\ * ? " < > |)
    - Potential security risks (null bytes, newlines, path traversal)
    - Windows reserved names

    Args:
        name: Release name to sanitize

    Returns:
        Sanitized filename-safe string, or "untitled" if empty
    """
    if not name or not name.strip():
        return "untitled"

    # Remove null bytes and control characters
    name = name.replace("\x00", "")
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)

    # Remove newlines and carriage returns
    name = name.replace("\n", "").replace("\r", "")

    # Remove path traversal attempts
    name = name.replace("..", "")

    # Remove characters invalid in filenames
    # Windows: < > : " / \ | ? *
    # Also remove quotes and angle brackets for safety
    invalid_chars = r'[<>:"/\\|?*\']'
    name = re.sub(invalid_chars, "", name)

    # Collapse multiple spaces into single space
    name = re.sub(r"\s+", " ", name)

    # Trim whitespace
    name = name.strip()

    # Remove leading/trailing dots and spaces (Windows compatibility)
    name = name.strip(". ")

    # Check if empty after sanitization
    if not name:
        return "untitled"

    # Check for Windows reserved names
    name_upper = name.upper()
    if name_upper in WINDOWS_RESERVED_NAMES:
        name = f"{name}_file"

    # Truncate to maximum length
    if len(name) > MAX_FILENAME_LENGTH:
        name = name[:MAX_FILENAME_LENGTH].rstrip()

    return name


def generate_screenshot_filename(release_name: str, index: int, format: str = "png") -> str:
    """Generate screenshot filename following the pattern.

    Pattern: {release_name}_screenshot_{index:03d}.{format}

    Args:
        release_name: Release name (will be sanitized)
        index: Screenshot index (1-based)
        format: File format (png or jpg)

    Returns:
        Generated filename
    """
    # Sanitize release name
    safe_name = sanitize_release_name(release_name)

    # Format index with zero padding (3 digits)
    index_str = f"{index:03d}"

    # Construct filename
    filename = f"{safe_name}_screenshot_{index_str}.{format}"

    return filename


def get_unique_filename(
    output_dir: Path, release_name: str, index: int, format: str = "png"
) -> Path:
    """Generate unique filename, incrementing if collision exists.

    If the generated filename already exists, increments the index
    until a unique filename is found.

    Args:
        output_dir: Output directory
        release_name: Release name
        index: Starting index
        format: File format

    Returns:
        Path to unique filename
    """
    # Try the initial filename
    filename = generate_screenshot_filename(release_name, index, format)
    output_path = output_dir / filename

    # If no collision, return immediately
    if not output_path.exists():
        return output_path

    # Find next available index
    current_index = index
    max_attempts = 1000  # Prevent infinite loop

    for _ in range(max_attempts):
        current_index += 1
        filename = generate_screenshot_filename(release_name, current_index, format)
        output_path = output_dir / filename

        if not output_path.exists():
            return output_path

    # Fallback: use timestamp if we somehow exhaust attempts
    import time

    timestamp = int(time.time() * 1000)
    safe_name = sanitize_release_name(release_name)
    filename = f"{safe_name}_screenshot_{timestamp}.{format}"
    return output_dir / filename
