"""Error types and categorization for batch processing."""

from __future__ import annotations

from enum import StrEnum


class BatchErrorType(StrEnum):
    """Categories of batch processing errors."""

    INCOMPATIBLE_FILE = "incompatible_file"
    MISSING_TRACK = "missing_track"
    MISSING_PRESET = "missing_preset"
    PERMISSION_ERROR = "permission_error"
    CORRUPTED_FILE = "corrupted_file"
    TOOL_ERROR = "tool_error"
    VALIDATION_ERROR = "validation_error"
    UNEXPECTED_ERROR = "unexpected_error"


# Error messages and hints for each error type
ERROR_HINTS = {
    BatchErrorType.INCOMPATIBLE_FILE: (
        "This file format or structure is not compatible with the selected preset. "
        "Check if the file has the required audio/subtitle tracks."
    ),
    BatchErrorType.MISSING_TRACK: (
        "The file is missing required audio or subtitle tracks for this preset. "
        "Use a different preset or add the missing tracks."
    ),
    BatchErrorType.MISSING_PRESET: (
        "The specified preset file was not found. "
        "Check the preset name and ensure it exists in the Presets directory."
    ),
    BatchErrorType.PERMISSION_ERROR: (
        "Cannot access the file due to permission restrictions. "
        "Check file ownership and permissions, or run with appropriate privileges."
    ),
    BatchErrorType.CORRUPTED_FILE: (
        "The file appears to be corrupted or incomplete. "
        "Try re-downloading or re-encoding the file."
    ),
    BatchErrorType.TOOL_ERROR: (
        "An external tool (mkvmerge, ffmpeg, etc.) failed. "
        "Check that all required tools are installed and accessible."
    ),
    BatchErrorType.VALIDATION_ERROR: (
        "The file or configuration failed validation checks. "
        "Review the error details and correct the issue."
    ),
    BatchErrorType.UNEXPECTED_ERROR: (
        "An unexpected error occurred. Check the logs for more details or report this issue."
    ),
}


def get_error_hint(error_type: BatchErrorType) -> str:
    """Get a user-friendly hint for an error type.

    Args:
        error_type: The error type

    Returns:
        A helpful hint message
    """
    return ERROR_HINTS.get(error_type, ERROR_HINTS[BatchErrorType.UNEXPECTED_ERROR])
