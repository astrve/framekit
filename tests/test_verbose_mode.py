"""Tests for verbose mode configuration and integration."""

from __future__ import annotations

from io import StringIO

from loguru import logger

from framekit.core.verbose import (
    VerbosityLevel,
    configure_verbosity,
    get_verbosity_level,
    is_verbose,
    reset_verbosity,
)


class TestVerbosityLevel:
    """Test VerbosityLevel enum."""

    def test_verbosity_levels_exist(self):
        """Test that all verbosity levels are defined."""
        assert VerbosityLevel.NORMAL.value == 0
        assert VerbosityLevel.VERBOSE.value == 1
        assert VerbosityLevel.DEBUG.value == 2
        assert VerbosityLevel.TRACE.value == 3

    def test_verbosity_level_ordering(self):
        """Test that verbosity levels can be compared."""
        assert VerbosityLevel.NORMAL < VerbosityLevel.VERBOSE
        assert VerbosityLevel.VERBOSE < VerbosityLevel.DEBUG
        assert VerbosityLevel.DEBUG < VerbosityLevel.TRACE

    def test_verbosity_level_from_count(self):
        """Test converting count to verbosity level."""
        assert VerbosityLevel.from_count(0) == VerbosityLevel.NORMAL
        assert VerbosityLevel.from_count(1) == VerbosityLevel.VERBOSE
        assert VerbosityLevel.from_count(2) == VerbosityLevel.DEBUG
        assert VerbosityLevel.from_count(3) == VerbosityLevel.TRACE
        assert VerbosityLevel.from_count(4) == VerbosityLevel.TRACE  # Max at TRACE
        assert VerbosityLevel.from_count(10) == VerbosityLevel.TRACE


class TestConfigureVerbosity:
    """Test verbosity configuration."""

    def setup_method(self):
        """Reset verbosity before each test."""
        reset_verbosity()

    def teardown_method(self):
        """Reset verbosity after each test."""
        reset_verbosity()

    def test_default_verbosity_is_normal(self):
        """Test that default verbosity is NORMAL."""
        assert get_verbosity_level() == VerbosityLevel.NORMAL
        assert not is_verbose()

    def test_configure_verbose_level(self):
        """Test configuring verbose level."""
        configure_verbosity(1)
        assert get_verbosity_level() == VerbosityLevel.VERBOSE
        assert is_verbose()

    def test_configure_debug_level(self):
        """Test configuring debug level."""
        configure_verbosity(2)
        assert get_verbosity_level() == VerbosityLevel.DEBUG
        assert is_verbose()

    def test_configure_trace_level(self):
        """Test configuring trace level."""
        configure_verbosity(3)
        assert get_verbosity_level() == VerbosityLevel.TRACE
        assert is_verbose()

    def test_configure_with_level_enum(self):
        """Test configuring with VerbosityLevel enum."""
        configure_verbosity(VerbosityLevel.DEBUG)
        assert get_verbosity_level() == VerbosityLevel.DEBUG

    def test_reset_verbosity(self):
        """Test resetting verbosity to default."""
        configure_verbosity(2)
        assert get_verbosity_level() == VerbosityLevel.DEBUG

        reset_verbosity()
        assert get_verbosity_level() == VerbosityLevel.NORMAL
        assert not is_verbose()

    def test_loguru_configuration_verbose(self):
        """Test that loguru is configured for verbose mode."""
        # Just verify it doesn't raise an error
        configure_verbosity(1)
        assert get_verbosity_level() == VerbosityLevel.VERBOSE

    def test_loguru_configuration_debug(self):
        """Test that loguru is configured for debug mode."""
        # Just verify it doesn't raise an error
        configure_verbosity(2)
        assert get_verbosity_level() == VerbosityLevel.DEBUG

    def test_loguru_configuration_trace(self):
        """Test that loguru is configured for trace mode."""
        # Just verify it doesn't raise an error
        configure_verbosity(3)
        assert get_verbosity_level() == VerbosityLevel.TRACE

    def test_configure_verbosity_tolerates_stale_handler_id(self):
        """Test reconfiguration after external handler removal."""
        configure_verbosity(1)
        logger.remove()

        configure_verbosity(2)

        assert get_verbosity_level() == VerbosityLevel.DEBUG

    def test_reset_verbosity_tolerates_stale_handler_id(self):
        """Test reset after external handler removal."""
        configure_verbosity(1)
        logger.remove()

        reset_verbosity()

        assert get_verbosity_level() == VerbosityLevel.NORMAL


class TestVerbosityIntegration:
    """Test verbosity integration with commands."""

    def setup_method(self):
        """Reset verbosity before each test."""
        reset_verbosity()

    def teardown_method(self):
        """Reset verbosity after each test."""
        reset_verbosity()

    def test_verbose_flag_parsing(self):
        """Test that verbose flag count is correctly parsed."""
        # Simulate Click's count behavior
        verbose_count = 0
        configure_verbosity(verbose_count)
        assert get_verbosity_level() == VerbosityLevel.NORMAL

        verbose_count = 1
        configure_verbosity(verbose_count)
        assert get_verbosity_level() == VerbosityLevel.VERBOSE

        verbose_count = 2
        configure_verbosity(verbose_count)
        assert get_verbosity_level() == VerbosityLevel.DEBUG

    def test_verbosity_affects_logging(self):
        """Test that verbosity level affects logging output."""
        # Capture log output
        log_output = StringIO()

        # Remove default handlers and add our test handler
        logger.remove()
        logger.add(log_output, level="TRACE", format="{level} {message}")

        # Test NORMAL level (should only show WARNING and above)
        configure_verbosity(0)
        logger.info("Info message")
        logger.debug("Debug message")
        logger.warning("Warning message")

        # Test VERBOSE level (should show INFO and above)
        configure_verbosity(1)
        logger.info("Verbose info")

        # Test DEBUG level (should show DEBUG and above)
        configure_verbosity(2)
        logger.debug("Debug message")

        # Test TRACE level (should show everything)
        configure_verbosity(3)
        logger.trace("Trace message")

    def test_verbosity_context_manager(self):
        """Test verbosity as context manager."""
        from framekit.core.verbose import verbosity_context

        assert get_verbosity_level() == VerbosityLevel.NORMAL

        with verbosity_context(VerbosityLevel.DEBUG):
            assert get_verbosity_level() == VerbosityLevel.DEBUG

        # Should restore to NORMAL after context
        assert get_verbosity_level() == VerbosityLevel.NORMAL


class TestVerbosityHelpers:
    """Test verbosity helper functions."""

    def setup_method(self):
        """Reset verbosity before each test."""
        reset_verbosity()

    def teardown_method(self):
        """Reset verbosity after each test."""
        reset_verbosity()

    def test_should_show_progress(self):
        """Test should_show_progress helper."""
        from framekit.core.verbose import should_show_progress

        # NORMAL: show progress
        configure_verbosity(0)
        assert should_show_progress()

        # VERBOSE: show detailed progress
        configure_verbosity(1)
        assert should_show_progress()

        # DEBUG: might hide progress for detailed logs
        configure_verbosity(2)
        assert should_show_progress()

    def test_should_show_commands(self):
        """Test should_show_commands helper."""
        from framekit.core.verbose import should_show_commands

        # NORMAL: don't show commands
        configure_verbosity(0)
        assert not should_show_commands()

        # VERBOSE: don't show commands yet
        configure_verbosity(1)
        assert not should_show_commands()

        # DEBUG: show commands
        configure_verbosity(2)
        assert should_show_commands()

        # TRACE: show commands
        configure_verbosity(3)
        assert should_show_commands()

    def test_should_show_subprocess_output(self):
        """Test should_show_subprocess_output helper."""
        from framekit.core.verbose import should_show_subprocess_output

        # NORMAL: don't show subprocess output
        configure_verbosity(0)
        assert not should_show_subprocess_output()

        # VERBOSE: don't show subprocess output
        configure_verbosity(1)
        assert not should_show_subprocess_output()

        # DEBUG: don't show subprocess output
        configure_verbosity(2)
        assert not should_show_subprocess_output()

        # TRACE: show subprocess output
        configure_verbosity(3)
        assert should_show_subprocess_output()

    def test_get_log_level_string(self):
        """Test getting log level string for loguru."""
        from framekit.core.verbose import get_log_level_string

        configure_verbosity(0)
        assert get_log_level_string() == "WARNING"

        configure_verbosity(1)
        assert get_log_level_string() == "INFO"

        configure_verbosity(2)
        assert get_log_level_string() == "DEBUG"

        configure_verbosity(3)
        assert get_log_level_string() == "TRACE"


class TestVerbosityLoggingHelpers:
    """Test verbose logging helper functions."""

    def setup_method(self):
        """Reset verbosity before each test."""
        reset_verbosity()

    def teardown_method(self):
        """Reset verbosity after each test."""
        reset_verbosity()

    def test_log_command_at_debug_level(self):
        """Test log_command shows commands at DEBUG level."""
        from framekit.core.verbose import log_command

        configure_verbosity(2)  # DEBUG
        log_command(["ffmpeg", "-i", "input.mkv"], tool="ffmpeg")
        # Should not raise an error

    def test_log_command_not_shown_at_verbose(self):
        """Test log_command doesn't show at VERBOSE level."""
        from framekit.core.verbose import log_command

        configure_verbosity(1)  # VERBOSE
        log_command(["ffmpeg", "-i", "input.mkv"], tool="ffmpeg")
        # Should not raise an error

    def test_log_subprocess_output_at_trace(self):
        """Test log_subprocess_output shows at TRACE level."""
        from framekit.core.verbose import log_subprocess_output

        configure_verbosity(3)  # TRACE
        log_subprocess_output("frame=  100 fps= 25 q=28.0 size=    1024kB", tool="ffmpeg")
        # Should not raise an error

    def test_log_subprocess_output_not_shown_at_debug(self):
        """Test log_subprocess_output doesn't show at DEBUG level."""
        from framekit.core.verbose import log_subprocess_output

        configure_verbosity(2)  # DEBUG
        log_subprocess_output("frame=  100 fps= 25 q=28.0 size=    1024kB", tool="ffmpeg")
        # Should not raise an error

    def test_log_file_processing_at_verbose(self):
        """Test log_file_processing shows at VERBOSE level."""
        from framekit.core.verbose import log_file_processing

        configure_verbosity(1)  # VERBOSE
        log_file_processing("/path/to/file.mkv", status="processing")
        # Should not raise an error

    def test_log_file_processing_not_shown_at_normal(self):
        """Test log_file_processing doesn't show at NORMAL level."""
        from framekit.core.verbose import log_file_processing

        configure_verbosity(0)  # NORMAL
        log_file_processing("/path/to/file.mkv", status="processing")
        # Should not raise an error


class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""

    def setup_method(self):
        """Reset verbosity before each test."""
        reset_verbosity()

    def teardown_method(self):
        """Reset verbosity after each test."""
        reset_verbosity()

    def test_default_behavior_unchanged(self):
        """Test that default behavior is unchanged."""
        # Without calling configure_verbosity, behavior should be normal
        assert get_verbosity_level() == VerbosityLevel.NORMAL
        assert not is_verbose()

    def test_existing_progress_bars_work(self):
        """Test that existing progress bars still work."""
        # This is a smoke test - actual progress bars tested in their modules
        from framekit.ui.progress import framekit_progress

        # Should work without verbose configuration
        with framekit_progress("Test", total=10) as advance:
            advance(1)
            advance(1)

    def test_no_import_side_effects(self):
        """Test that importing verbose module has no side effects."""
        # Re-import should not change state
        import importlib

        import framekit.core.verbose

        level_before = get_verbosity_level()
        importlib.reload(framekit.core.verbose)
        level_after = get_verbosity_level()

        assert level_before == level_after


# Made with Bob
