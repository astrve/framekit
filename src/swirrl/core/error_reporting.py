"""Structured error reporting with actionable suggestions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class ErrorSeverity(Enum):
    """Error severity levels."""

    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    def __lt__(self, other: ErrorSeverity) -> bool:
        """Compare severity levels."""
        order = [self.INFO, self.WARNING, self.ERROR, self.CRITICAL]
        return order.index(self) < order.index(other)

    def __gt__(self, other: ErrorSeverity) -> bool:
        """Compare severity levels."""
        order = [self.INFO, self.WARNING, self.ERROR, self.CRITICAL]
        return order.index(self) > order.index(other)


@dataclass(slots=True)
class ErrorReport:
    """Structured error report with context and suggestions."""

    code: str
    message: str
    severity: ErrorSeverity
    context: dict[str, Any] = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)
    stack_trace: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert error report to dictionary."""
        data = asdict(self)
        data["severity"] = self.severity.value
        return data


class ErrorReporter:
    """Collects and manages error reports."""

    def __init__(self) -> None:
        """Initialize error reporter."""
        self.errors: list[ErrorReport] = []

    def add_error(
        self,
        code: str,
        message: str,
        severity: ErrorSeverity,
        *,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        stack_trace: str | None = None,
    ) -> None:
        """Add an error report."""
        self.errors.append(
            ErrorReport(
                code=code,
                message=message,
                severity=severity,
                context=context or {},
                suggestions=suggestions or [],
                stack_trace=stack_trace,
            )
        )

    def add_warning(
        self,
        code: str,
        message: str,
        *,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
    ) -> None:
        """Add a warning."""
        self.add_error(
            code=code,
            message=message,
            severity=ErrorSeverity.WARNING,
            context=context,
            suggestions=suggestions,
        )

    def add_info(
        self,
        code: str,
        message: str,
        *,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
    ) -> None:
        """Add an info message."""
        self.add_error(
            code=code,
            message=message,
            severity=ErrorSeverity.INFO,
            context=context,
            suggestions=suggestions,
        )

    def has_errors(self) -> bool:
        """Check if any errors have been reported."""
        return len(self.errors) > 0

    def has_critical_errors(self) -> bool:
        """Check if any critical errors have been reported."""
        return any(e.severity == ErrorSeverity.CRITICAL for e in self.errors)

    def get_errors_by_severity(self, severity: ErrorSeverity) -> list[ErrorReport]:
        """Get errors filtered by severity."""
        return [e for e in self.errors if e.severity == severity]

    def get_critical_errors(self) -> list[ErrorReport]:
        """Get only critical errors."""
        return self.get_errors_by_severity(ErrorSeverity.CRITICAL)

    def clear(self) -> None:
        """Clear all errors."""
        self.errors.clear()

    def get_summary(self) -> dict[str, int]:
        """Get error summary by severity."""
        return {
            "total": len(self.errors),
            "critical": len(self.get_errors_by_severity(ErrorSeverity.CRITICAL)),
            "errors": len(self.get_errors_by_severity(ErrorSeverity.ERROR)),
            "warnings": len(self.get_errors_by_severity(ErrorSeverity.WARNING)),
            "info": len(self.get_errors_by_severity(ErrorSeverity.INFO)),
        }

    def format_errors(self, *, include_stack_trace: bool = False) -> str:
        """Format errors for display."""
        if not self.errors:
            return "No errors reported."

        lines: list[str] = []
        for error in self.errors:
            # Severity and code
            severity_str = error.severity.value.upper()
            lines.append(f"[{severity_str}] {error.code}: {error.message}")

            # Context
            if error.context:
                lines.append("  Context:")
                for key, value in error.context.items():
                    lines.append(f"    {key}: {value}")

            # Suggestions
            if error.suggestions:
                lines.append("  Suggestions:")
                for suggestion in error.suggestions:
                    lines.append(f"    - {suggestion}")

            # Stack trace
            if include_stack_trace and error.stack_trace:
                lines.append("  Stack Trace:")
                for line in error.stack_trace.split("\n"):
                    lines.append(f"    {line}")

            lines.append("")  # Empty line between errors

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert reporter to dictionary."""
        return {
            "errors": [e.to_dict() for e in self.errors],
            "summary": self.get_summary(),
        }


def suggest_for_error(code: str, context: dict[str, Any]) -> list[str]:
    """Generate actionable suggestions for common error codes."""
    suggestions: list[str] = []

    if code == "E_FILE_NOT_FOUND":
        file = context.get("file", "the file")
        suggestions.extend(
            [
                f"Check if {file} exists",
                "Verify the file path is correct",
                "Ensure you have read permissions",
            ]
        )

    elif code == "E_TOOL_NOT_FOUND":
        tool = context.get("tool", "the tool")
        suggestions.extend(
            [
                f"Install {tool} on your system",
                f"Add {tool} to your PATH",
                "Run 'swirrl doctor' to check tool availability",
                "Configure tool path in settings",
            ]
        )

    elif code == "E_PERMISSION_DENIED":
        file = context.get("file", "the file")
        suggestions.extend(
            [
                f"Check file permissions for {file}",
                "Run with appropriate user privileges",
                "Ensure the file is not locked by another process",
            ]
        )

    elif code == "E_INVALID_CONFIG":
        key = context.get("key", "configuration")
        suggestions.extend(
            [
                f"Check the '{key}' setting in your config",
                "Run 'swirrl settings' to view current configuration",
                "Reset to defaults with 'swirrl setup --reset'",
                "Refer to documentation for valid values",
            ]
        )

    elif code == "E_METADATA_NOT_FOUND":
        suggestions.extend(
            [
                "Check your internet connection",
                "Verify API credentials in settings",
                "Try a different metadata provider",
                "Search with more specific terms",
            ]
        )

    elif code == "E_ENCODING_FAILED":
        suggestions.extend(
            [
                "Check if the input file is corrupted",
                "Verify ffmpeg is installed and working",
                "Try different encoding settings",
                "Check available disk space",
            ]
        )

    elif code == "E_INVALID_INPUT":
        suggestions.extend(
            [
                "Check the input format",
                "Refer to command help with --help",
                "Ensure all required parameters are provided",
            ]
        )

    else:
        # Generic suggestions
        suggestions.extend(
            [
                "Check the error message for details",
                "Run with --verbose for more information",
                "Consult the documentation",
                "Report this issue if it persists",
            ]
        )

    return suggestions
