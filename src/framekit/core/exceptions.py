from __future__ import annotations

from typing import Any


class FramekitError(Exception):
    """Base exception for user-facing Framekit failures.

    ``message_key`` and ``context`` are optional hooks for the i18n layer. The
    project can still raise plain messages today while moving progressively to
    translated errors later.
    """

    def __init__(
        self,
        message: str = "",
        *,
        message_key: str | None = None,
        exit_code: int = 1,
        **context: Any,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.message_key = message_key
        self.context = context
        self.exit_code = exit_code

    def __str__(self) -> str:
        return self.message or self.message_key or self.__class__.__name__


class FramekitConfigError(FramekitError):
    """Raised when configuration or local state is invalid."""


class FramekitUserInputError(FramekitError):
    """Raised when user input cannot be accepted as-is."""


class FramekitExternalToolError(FramekitError):
    """Raised when an external tool cannot be resolved or executed."""


class FramekitMetadataError(FramekitError):
    """Raised when metadata lookup or resolution fails."""


class FramekitHttpError(FramekitError):
    """Raised by the shared HTTP client."""


# Backward-compatible aliases used by existing modules/tests.
class SettingsError(FramekitConfigError):
    """Raised when settings cannot be read, written, or validated."""


class ToolError(FramekitExternalToolError):
    """Raised when an external tool cannot be resolved or executed."""


class ValidationError(FramekitUserInputError):
    """Raised when user input or configuration is invalid."""
