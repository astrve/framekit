"""Input validation functions for setup wizard."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from swirrl.core.http import HttpClient
from swirrl.core.i18n import tr


class ValidationError(Exception):
    """Validation error exception."""


def validate_language_code(value: str) -> tuple[bool, str]:
    """Validate language code format.

    Args:
        value: Language code to validate (e.g., "en", "en-US", "fr-FR")

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not value:
        return False, tr("wizard.validation.language_required", default="Language code is required")

    # Accept formats: en, en-US, en_US
    pattern = r"^[a-z]{2}(-|_)?([A-Z]{2})?$"
    if not re.match(pattern, value, re.IGNORECASE):
        return False, tr(
            "wizard.validation.language_invalid",
            default="Invalid language code format. Use format like 'en' or 'en-US'",
        )

    return True, ""


def validate_tmdb_token(value: str) -> tuple[bool, str]:
    """Validate TMDb API token format.

    Args:
        value: TMDb token to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not value:
        return False, tr("wizard.validation.tmdb_token_required", default="TMDb token is required")

    # TMDb tokens are typically JWT format or 32-character hex strings
    if len(value) < 32:
        return False, tr(
            "wizard.validation.tmdb_token_too_short",
            default="TMDb token appears too short (minimum 32 characters)",
        )

    # Check for common JWT format (eyJ...)
    if value.startswith("eyJ") and value.count(".") >= 2:
        return True, ""

    # Check for hex format (32+ characters)
    if len(value) >= 32 and all(c in "0123456789abcdefABCDEF" for c in value):
        return True, ""

    # Accept any token that looks reasonable
    if len(value) >= 32:
        return True, ""

    return False, tr(
        "wizard.validation.tmdb_token_invalid",
        default="TMDb token format appears invalid",
    )


def test_tmdb_connection(token: str) -> tuple[bool, str]:
    """Test TMDb API connection with token.

    Args:
        token: TMDb API token

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        client = HttpClient()

        # Test with a simple API call
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get(
            "https://api.themoviedb.org/3/configuration",
            headers=headers,
        )

        if response.status_code == 200:
            return True, ""
        elif response.status_code == 401:
            return False, tr(
                "wizard.validation.tmdb_unauthorized",
                default="TMDb token is invalid or unauthorized",
            )
        else:
            return False, tr(
                "wizard.validation.tmdb_error",
                default=f"TMDb API error: {response.status_code}",
            )
    except Exception as e:
        return False, tr(
            "wizard.validation.tmdb_connection_failed",
            default=f"Failed to connect to TMDb API: {e!s}",
        )


def validate_url(value: str) -> tuple[bool, str]:
    """Validate URL format.

    Args:
        value: URL to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not value:
        return False, tr("wizard.validation.url_required", default="URL is required")

    try:
        result = urlparse(value)
        if not all([result.scheme, result.netloc]):
            return False, tr(
                "wizard.validation.url_invalid",
                default="Invalid URL format. Must include scheme (http/https) and domain",
            )

        if result.scheme not in ["http", "https"]:
            return False, tr(
                "wizard.validation.url_scheme_invalid",
                default="URL scheme must be http or https",
            )

        return True, ""
    except Exception:
        return False, tr("wizard.validation.url_parse_error", default="Failed to parse URL")


def validate_announce_url(value: str) -> tuple[bool, str]:
    """Validate torrent announce URL.

    Args:
        value: Announce URL to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    is_valid, error = validate_url(value)
    if not is_valid:
        return is_valid, error

    # Check if URL path contains "announce"
    result = urlparse(value)
    if "announce" not in result.path.lower():
        return False, tr(
            "wizard.validation.announce_url_invalid",
            default="Announce URL should contain '/announce' in the path",
        )

    return True, ""


def validate_path(
    value: str, must_exist: bool = False, must_be_writable: bool = False
) -> tuple[bool, str]:
    """Validate file system path.

    Args:
        value: Path to validate
        must_exist: If True, path must exist
        must_be_writable: If True, path must be writable

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not value:
        return False, tr("wizard.validation.path_required", default="Path is required")

    try:
        path = _resolved_path(value)

        exists_error = _validate_existing_path_requirement(path, must_exist=must_exist)
        if exists_error is not None:
            return exists_error

        writable_error = _validate_writable_requirement(path, must_be_writable=must_be_writable)
        if writable_error is not None:
            return writable_error

        return True, ""
    except Exception as e:
        return False, tr(
            "wizard.validation.path_error",
            default=f"Path validation error: {e!s}",
        )


def _resolved_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _validate_existing_path_requirement(path: Path, *, must_exist: bool) -> tuple[bool, str] | None:
    if not must_exist or path.exists():
        return None
    return False, tr(
        "wizard.validation.path_not_exists",
        default=f"Path does not exist: {path}",
    )


def _validate_writable_requirement(
    path: Path,
    *,
    must_be_writable: bool,
) -> tuple[bool, str] | None:
    if not must_be_writable:
        return None
    if path.exists():
        return _validate_existing_writable_path(path)
    return _validate_missing_writable_path(path)


def _validate_existing_writable_path(path: Path) -> tuple[bool, str] | None:
    if not path.is_dir():
        return False, tr(
            "wizard.validation.path_not_directory",
            default=f"Path is not a directory: {path}",
        )
    if _can_write_in_directory(path):
        return None
    return False, tr(
        "wizard.validation.path_not_writable",
        default=f"Path is not writable: {path}",
    )


def _validate_missing_writable_path(path: Path) -> tuple[bool, str] | None:
    parent = path.parent
    if not parent.exists():
        return False, tr(
            "wizard.validation.path_parent_not_exists",
            default=f"Parent directory does not exist: {parent}",
        )
    if not parent.is_dir():
        return False, tr(
            "wizard.validation.path_parent_not_directory",
            default=f"Parent is not a directory: {parent}",
        )
    return None


def _can_write_in_directory(path: Path) -> bool:
    test_file = path / ".swirrl_write_test"
    try:
        test_file.touch()
        test_file.unlink()
        return True
    except Exception:
        return False


def validate_integer(
    value: Any,
    min_value: int | None = None,
    max_value: int | None = None,
) -> tuple[bool, str]:
    """Validate integer value.

    Args:
        value: Value to validate
        min_value: Minimum allowed value
        max_value: Maximum allowed value

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        int_value = int(value)

        if min_value is not None and int_value < min_value:
            return False, tr(
                "wizard.validation.integer_too_small",
                default=f"Value must be at least {min_value}",
                min=min_value,
            )

        if max_value is not None and int_value > max_value:
            return False, tr(
                "wizard.validation.integer_too_large",
                default=f"Value must be at most {max_value}",
                max=max_value,
            )

        return True, ""
    except (ValueError, TypeError):
        return False, tr(
            "wizard.validation.integer_invalid",
            default="Value must be a valid integer",
        )


def validate_boolean(value: Any) -> tuple[bool, str]:
    """Validate boolean value.

    Args:
        value: Value to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if isinstance(value, bool):
        return True, ""

    if isinstance(value, str):
        normalized = value.lower().strip()
        if normalized in ["true", "yes", "1", "on", "enabled"]:
            return True, ""
        if normalized in ["false", "no", "0", "off", "disabled"]:
            return True, ""

    return False, tr(
        "wizard.validation.boolean_invalid",
        default="Value must be true/false, yes/no, or 1/0",
    )


def validate_choice(value: str, choices: list[str]) -> tuple[bool, str]:
    """Validate value is in allowed choices.

    Args:
        value: Value to validate
        choices: List of allowed choices

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not value:
        return False, tr("wizard.validation.choice_required", default="A choice is required")

    if value not in choices:
        return False, tr(
            "wizard.validation.choice_invalid",
            default=f"Invalid choice. Must be one of: {', '.join(choices)}",
            choices=", ".join(choices),
        )

    return True, ""


def validate_memory_size(value: Any) -> tuple[bool, str]:
    """Validate memory size value (in MB).

    Args:
        value: Memory size to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    is_valid, error = validate_integer(value, min_value=1, max_value=100000)
    if not is_valid:
        return is_valid, error

    int_value = int(value)

    # Warn if value seems unreasonable
    if int_value < 10:
        return False, tr(
            "wizard.validation.memory_too_small",
            default="Memory size seems too small (minimum 10 MB recommended)",
        )

    if int_value > 10000:
        return False, tr(
            "wizard.validation.memory_too_large",
            default="Memory size seems too large (maximum 10000 MB recommended)",
        )

    return True, ""


def validate_worker_count(value: Any) -> tuple[bool, str]:
    """Validate worker count for parallel processing.

    Args:
        value: Worker count to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    is_valid, error = validate_integer(value, min_value=1, max_value=32)
    if not is_valid:
        return is_valid, error

    int_value = int(value)

    # Recommend reasonable values
    if int_value > 16:
        return False, tr(
            "wizard.validation.workers_too_many",
            default="Worker count seems high (maximum 16 recommended for most systems)",
        )

    return True, ""
