"""Tests for structured error reporting."""

from __future__ import annotations

from swirrl.core.error_reporting import (
    ErrorReport,
    ErrorReporter,
    ErrorSeverity,
)


class TestErrorSeverity:
    """Test error severity enum."""

    def test_severity_levels(self):
        """Test severity level values."""
        assert ErrorSeverity.CRITICAL.value == "critical"
        assert ErrorSeverity.ERROR.value == "error"
        assert ErrorSeverity.WARNING.value == "warning"
        assert ErrorSeverity.INFO.value == "info"

    def test_severity_ordering(self):
        """Test severity can be compared."""
        assert ErrorSeverity.CRITICAL > ErrorSeverity.ERROR
        assert ErrorSeverity.ERROR > ErrorSeverity.WARNING
        assert ErrorSeverity.WARNING > ErrorSeverity.INFO


class TestErrorReport:
    """Test error report dataclass."""

    def test_error_report_creation(self):
        """Test creating an error report."""
        report = ErrorReport(
            code="E001",
            message="Test error",
            severity=ErrorSeverity.ERROR,
        )
        assert report.code == "E001"
        assert report.message == "Test error"
        assert report.severity == ErrorSeverity.ERROR
        assert report.context == {}
        assert report.suggestions == []
        assert report.stack_trace is None

    def test_error_report_with_context(self):
        """Test error report with context."""
        report = ErrorReport(
            code="E002",
            message="File not found",
            severity=ErrorSeverity.ERROR,
            context={"file": "test.mkv", "path": "/tmp"},
        )
        assert report.context["file"] == "test.mkv"
        assert report.context["path"] == "/tmp"

    def test_error_report_with_suggestions(self):
        """Test error report with suggestions."""
        report = ErrorReport(
            code="E003",
            message="Invalid configuration",
            severity=ErrorSeverity.ERROR,
            suggestions=[
                "Check your config file",
                "Run setup wizard",
            ],
        )
        assert len(report.suggestions) == 2
        assert "Check your config file" in report.suggestions

    def test_error_report_with_stack_trace(self):
        """Test error report with stack trace."""
        report = ErrorReport(
            code="E004",
            message="Unexpected error",
            severity=ErrorSeverity.CRITICAL,
            stack_trace="Traceback...",
        )
        assert report.stack_trace == "Traceback..."

    def test_error_report_to_dict(self):
        """Test converting error report to dict."""
        report = ErrorReport(
            code="E005",
            message="Test",
            severity=ErrorSeverity.WARNING,
            context={"key": "value"},
        )
        data = report.to_dict()
        assert data["code"] == "E005"
        assert data["message"] == "Test"
        assert data["severity"] == "warning"
        assert data["context"]["key"] == "value"


class TestErrorReporter:
    """Test error reporter class."""

    def test_reporter_initialization(self):
        """Test reporter initialization."""
        reporter = ErrorReporter()
        assert not reporter.has_errors()
        assert len(reporter.errors) == 0

    def test_add_error(self):
        """Test adding an error."""
        reporter = ErrorReporter()
        reporter.add_error(
            code="E001",
            message="Test error",
            severity=ErrorSeverity.ERROR,
        )
        assert reporter.has_errors()
        assert len(reporter.errors) == 1
        assert reporter.errors[0].code == "E001"

    def test_add_error_with_context(self):
        """Test adding error with context."""
        reporter = ErrorReporter()
        reporter.add_error(
            code="E002",
            message="File error",
            severity=ErrorSeverity.ERROR,
            context={"file": "test.mkv"},
        )
        assert reporter.errors[0].context["file"] == "test.mkv"

    def test_add_error_with_suggestions(self):
        """Test adding error with suggestions."""
        reporter = ErrorReporter()
        reporter.add_error(
            code="E003",
            message="Config error",
            severity=ErrorSeverity.ERROR,
            suggestions=["Fix config", "Run setup"],
        )
        assert len(reporter.errors[0].suggestions) == 2

    def test_add_warning(self):
        """Test adding a warning."""
        reporter = ErrorReporter()
        reporter.add_warning(
            code="W001",
            message="Test warning",
        )
        assert reporter.has_errors()  # Warnings count as errors
        assert reporter.errors[0].severity == ErrorSeverity.WARNING

    def test_add_info(self):
        """Test adding an info message."""
        reporter = ErrorReporter()
        reporter.add_info(
            code="I001",
            message="Test info",
        )
        assert reporter.has_errors()
        assert reporter.errors[0].severity == ErrorSeverity.INFO

    def test_get_errors_by_severity(self):
        """Test filtering errors by severity."""
        reporter = ErrorReporter()
        reporter.add_error("E001", "Error 1", ErrorSeverity.CRITICAL)
        reporter.add_error("E002", "Error 2", ErrorSeverity.ERROR)
        reporter.add_warning("W001", "Warning 1")
        reporter.add_info("I001", "Info 1")

        critical = reporter.get_errors_by_severity(ErrorSeverity.CRITICAL)
        assert len(critical) == 1
        assert critical[0].code == "E001"

        warnings = reporter.get_errors_by_severity(ErrorSeverity.WARNING)
        assert len(warnings) == 1
        assert warnings[0].code == "W001"

    def test_get_critical_errors(self):
        """Test getting only critical errors."""
        reporter = ErrorReporter()
        reporter.add_error("E001", "Critical", ErrorSeverity.CRITICAL)
        reporter.add_error("E002", "Error", ErrorSeverity.ERROR)

        critical = reporter.get_critical_errors()
        assert len(critical) == 1
        assert critical[0].severity == ErrorSeverity.CRITICAL

    def test_has_critical_errors(self):
        """Test checking for critical errors."""
        reporter = ErrorReporter()
        assert not reporter.has_critical_errors()

        reporter.add_error("E001", "Error", ErrorSeverity.ERROR)
        assert not reporter.has_critical_errors()

        reporter.add_error("E002", "Critical", ErrorSeverity.CRITICAL)
        assert reporter.has_critical_errors()

    def test_clear_errors(self):
        """Test clearing all errors."""
        reporter = ErrorReporter()
        reporter.add_error("E001", "Error", ErrorSeverity.ERROR)
        assert reporter.has_errors()

        reporter.clear()
        assert not reporter.has_errors()
        assert len(reporter.errors) == 0

    def test_get_summary(self):
        """Test getting error summary."""
        reporter = ErrorReporter()
        reporter.add_error("E001", "Critical", ErrorSeverity.CRITICAL)
        reporter.add_error("E002", "Error", ErrorSeverity.ERROR)
        reporter.add_warning("W001", "Warning")
        reporter.add_info("I001", "Info")

        summary = reporter.get_summary()
        assert summary["total"] == 4
        assert summary["critical"] == 1
        assert summary["errors"] == 1
        assert summary["warnings"] == 1
        assert summary["info"] == 1

    def test_format_errors(self):
        """Test formatting errors for display."""
        reporter = ErrorReporter()
        reporter.add_error(
            code="E001",
            message="Test error",
            severity=ErrorSeverity.ERROR,
            context={"file": "test.mkv"},
            suggestions=["Try again", "Check file"],
        )

        formatted = reporter.format_errors()
        assert "E001" in formatted
        assert "Test error" in formatted
        assert "test.mkv" in formatted
        assert "Try again" in formatted

    def test_format_errors_with_stack_trace(self):
        """Test formatting errors with stack trace."""
        reporter = ErrorReporter()
        reporter.add_error(
            code="E001",
            message="Critical error",
            severity=ErrorSeverity.CRITICAL,
            stack_trace="Traceback (most recent call last):\n  ...",
        )

        formatted = reporter.format_errors(include_stack_trace=True)
        assert "Traceback" in formatted

    def test_to_dict(self):
        """Test converting reporter to dict."""
        reporter = ErrorReporter()
        reporter.add_error("E001", "Error", ErrorSeverity.ERROR)
        reporter.add_warning("W001", "Warning")

        data = reporter.to_dict()
        assert "errors" in data
        assert "summary" in data
        assert len(data["errors"]) == 2


class TestErrorSuggestions:
    """Test error suggestion generation."""

    def test_suggest_for_file_not_found(self):
        """Test suggestions for file not found errors."""
        from swirrl.core.error_reporting import suggest_for_error

        suggestions = suggest_for_error(
            code="E_FILE_NOT_FOUND",
            context={"file": "test.mkv"},
        )
        assert len(suggestions) > 0
        assert any("path" in s.lower() for s in suggestions)

    def test_suggest_for_tool_not_found(self):
        """Test suggestions for tool not found errors."""
        from swirrl.core.error_reporting import suggest_for_error

        suggestions = suggest_for_error(
            code="E_TOOL_NOT_FOUND",
            context={"tool": "mkvmerge"},
        )
        assert len(suggestions) > 0
        assert any("install" in s.lower() for s in suggestions)

    def test_suggest_for_permission_denied(self):
        """Test suggestions for permission errors."""
        from swirrl.core.error_reporting import suggest_for_error

        suggestions = suggest_for_error(
            code="E_PERMISSION_DENIED",
            context={"file": "test.mkv"},
        )
        assert len(suggestions) > 0
        assert any("permission" in s.lower() for s in suggestions)

    def test_suggest_for_invalid_config(self):
        """Test suggestions for config errors."""
        from swirrl.core.error_reporting import suggest_for_error

        suggestions = suggest_for_error(
            code="E_INVALID_CONFIG",
            context={"key": "metadata.provider"},
        )
        assert len(suggestions) > 0
        assert any("config" in s.lower() or "settings" in s.lower() for s in suggestions)

    def test_suggest_generic(self):
        """Test generic suggestions for unknown errors."""
        from swirrl.core.error_reporting import suggest_for_error

        suggestions = suggest_for_error(
            code="E_UNKNOWN",
            context={},
        )
        assert len(suggestions) > 0
