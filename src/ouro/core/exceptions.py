from __future__ import annotations

from typing import Any


class OuroError(Exception):
    """Base exception for user-facing Ouro failures.

    ``message_key`` and ``context`` are optional hooks for the i18n layer. The
    project can still raise plain messages today while moving progressively to
    translated errors later.

    ``suggestions`` is a list of short, actionable recovery hints to display
    alongside the error. Mirrors the UX of ``gh``/``cargo``: tell the user
    what went wrong *and* what to try next. The handler in ``__main__``
    formats them as a ``Suggestions:`` block under the error line.
    """

    def __init__(
        self,
        message: str = "",
        *,
        message_key: str | None = None,
        exit_code: int = 1,
        suggestions: tuple[str, ...] | list[str] | None = None,
        **context: Any,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.message_key = message_key
        self.context = context
        self.exit_code = exit_code
        self.suggestions: tuple[str, ...] = tuple(suggestions or ())

    def with_suggestions(self, *hints: str) -> OuroError:
        """Return ``self`` after appending recovery hints.

        Helper for raising sites that want a fluent style::

            raise OuroConfigError("vault not initialised").with_suggestions(
                "Run: ouro settings security enable",
                "Then: ouro settings security set-token",
            )
        """
        deduped: list[str] = list(self.suggestions)
        for hint in hints:
            if hint and hint not in deduped:
                deduped.append(hint)
        self.suggestions = tuple(deduped)
        return self

    def __str__(self) -> str:
        """Return a human-readable representation of the error."""
        return self.message or self.message_key or self.__class__.__name__


class OuroConfigError(OuroError):
    """Raised when configuration or local state is invalid."""


class OuroUserInputError(OuroError):
    """Raised when user input cannot be accepted as-is."""


class OuroExternalToolError(OuroError):
    """Raised when an external tool cannot be resolved or executed."""


class OuroMetadataError(OuroError):
    """Raised when metadata lookup or resolution fails."""


class OuroHttpError(OuroError):
    """Raised by the shared HTTP client."""


class HeadlessAmbiguityError(RuntimeError):
    """Raised when headless mode requires an interactive choice."""


# Backward-compatible aliases used by existing modules/tests.
class SettingsError(OuroConfigError):
    """Raised when settings cannot be read, written, or validated."""


class ToolError(OuroExternalToolError):
    """Raised when an external tool cannot be resolved or executed."""


class ValidationError(OuroUserInputError):
    """Raised when user input or configuration is invalid."""
