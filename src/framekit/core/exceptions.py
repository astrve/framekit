from __future__ import annotations

from typing import Any


class FramekitError(Exception):
    """Base exception for user-facing Framekit failures.

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

    def with_suggestions(self, *hints: str) -> FramekitError:
        """Return ``self`` after appending recovery hints.

        Helper for raising sites that want a fluent style::

            raise FramekitConfigError("vault not initialised").with_suggestions(
                "Run: framekit settings security enable",
                "Then: framekit settings security set-token",
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


class HeadlessAmbiguityError(RuntimeError):
    """Raised when headless mode requires an interactive choice."""


# Backward-compatible aliases used by existing modules/tests.
class SettingsError(FramekitConfigError):
    """Raised when settings cannot be read, written, or validated."""


class ToolError(FramekitExternalToolError):
    """Raised when an external tool cannot be resolved or executed."""


class ValidationError(FramekitUserInputError):
    """Raised when user input or configuration is invalid."""
