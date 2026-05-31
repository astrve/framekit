"""Tests for browse CLI command."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from swirrl.commands.browse import browse_command


@pytest.fixture
def cli_runner():
    """Create CLI runner."""
    return CliRunner()


@pytest.fixture
def mock_file_system(tmp_path):
    """Create mock file system for CLI tests."""
    # Create directory structure
    (tmp_path / "dir1").mkdir()
    (tmp_path / "file1.mkv").write_text("test")
    (tmp_path / "file2.mp4").write_text("test")
    (tmp_path / "file3.txt").write_text("test")

    return tmp_path


class TestBrowseCommand:
    """Test browse CLI command."""

    def test_command_registered(self, cli_runner):
        """Test that browse command is registered."""
        result = cli_runner.invoke(browse_command, ["--help"])
        assert result.exit_code == 0
        assert "browse" in result.output.lower() or "file" in result.output.lower()

    def test_help_text(self, cli_runner):
        """Test help text is informative."""
        result = cli_runner.invoke(browse_command, ["--help"])
        assert result.exit_code == 0
        assert "--filter" in result.output or "filter" in result.output.lower()

    @patch("swirrl.commands.browse.FileBrowserTUI")
    def test_non_tty_error(self, mock_tui_class, cli_runner, mock_file_system):
        """Test error when not running in TTY."""
        mock_tui = MagicMock()
        mock_tui.run.side_effect = RuntimeError(
            "Interactive file browser is not available in headless mode (no TTY)."
        )
        mock_tui_class.return_value = mock_tui

        result = cli_runner.invoke(browse_command, [str(mock_file_system)])

        # Click catches exceptions, so check output for error message
        assert (
            "tty" in result.output.lower()
            or "interactive" in result.output.lower()
            or "error" in result.output.lower()
        )

    def test_filter_option_parsing(self, cli_runner):
        """Test filter option is parsed correctly."""
        result = cli_runner.invoke(browse_command, ["--help"])
        assert result.exit_code == 0
        # Check that filter option exists
        assert "--filter" in result.output

    def test_multi_option_parsing(self, cli_runner):
        """Test multi-select option is parsed correctly."""
        result = cli_runner.invoke(browse_command, ["--help"])
        assert result.exit_code == 0
        # Check that multi option exists
        assert "--multi" in result.output

    def test_start_dir_option_parsing(self, cli_runner):
        """Test start directory option is parsed correctly."""
        result = cli_runner.invoke(browse_command, ["--help"])
        assert result.exit_code == 0
        # PATH argument should be present
        assert "PATH" in result.output or "path" in result.output.lower()

    @patch("sys.stdin.isatty")
    @patch("swirrl.commands.browse.FileBrowserTUI")
    def test_browse_with_filter(self, mock_tui_class, mock_isatty, cli_runner, mock_file_system):
        """Test browse with file filter."""
        mock_isatty.return_value = True
        mock_tui = MagicMock()
        mock_tui.run.return_value = [mock_file_system / "file1.mkv"]
        mock_tui_class.return_value = mock_tui

        result = cli_runner.invoke(browse_command, [str(mock_file_system), "--filter", ".mkv"])

        # Should succeed
        assert result.exit_code == 0
        # TUI should be created with filter
        mock_tui_class.assert_called_once()
        # Check the config passed to TUI constructor
        call_args = mock_tui_class.call_args[0]
        config = call_args[0]
        assert config.filter_extensions == [".mkv"]

    @patch("sys.stdin.isatty")
    @patch("swirrl.commands.browse.FileBrowserTUI")
    def test_browse_multi_select(self, mock_tui_class, mock_isatty, cli_runner, mock_file_system):
        """Test browse with multi-select enabled."""
        mock_isatty.return_value = True
        mock_tui = MagicMock()
        mock_tui.run.return_value = [mock_file_system / "file1.mkv", mock_file_system / "file2.mp4"]
        mock_tui_class.return_value = mock_tui

        result = cli_runner.invoke(browse_command, [str(mock_file_system), "--multi"])

        assert result.exit_code == 0
        # TUI should be created with multi-select
        mock_tui_class.assert_called_once()
        # Check the config passed to TUI constructor
        call_args = mock_tui_class.call_args[0]
        config = call_args[0]
        assert config.multi_select is True

    @patch("sys.stdin.isatty")
    @patch("swirrl.commands.browse.FileBrowserTUI")
    def test_browse_output_format(self, mock_tui_class, mock_isatty, cli_runner, mock_file_system):
        """Test browse output format."""
        mock_isatty.return_value = True
        mock_tui = MagicMock()
        selected_files = [mock_file_system / "file1.mkv", mock_file_system / "file2.mp4"]
        mock_tui.run.return_value = selected_files
        mock_tui_class.return_value = mock_tui

        result = cli_runner.invoke(browse_command, [str(mock_file_system), "--multi"])

        assert result.exit_code == 0
        # Output should contain selected file paths
        # Just check that both filenames appear in output
        assert "file1.mkv" in result.output
        assert "file2.mp4" in result.output

    @patch("sys.stdin.isatty")
    @patch("swirrl.commands.browse.FileBrowserTUI")
    def test_browse_no_selection(self, mock_tui_class, mock_isatty, cli_runner, mock_file_system):
        """Test browse with no selection (cancelled)."""
        mock_isatty.return_value = True
        mock_tui = MagicMock()
        mock_tui.run.side_effect = KeyboardInterrupt()
        mock_tui_class.return_value = mock_tui

        result = cli_runner.invoke(browse_command, [str(mock_file_system)])

        # Should handle cancellation gracefully
        assert result.exit_code == 0

    @patch("sys.stdin.isatty")
    @patch("swirrl.commands.browse.FileBrowserTUI")
    def test_browse_directories_only(
        self, mock_tui_class, mock_isatty, cli_runner, mock_file_system
    ):
        """Test browse with directories-only filter."""
        mock_isatty.return_value = True
        mock_tui = MagicMock()
        mock_tui.run.return_value = [mock_file_system / "dir1"]
        mock_tui_class.return_value = mock_tui

        result = cli_runner.invoke(browse_command, [str(mock_file_system), "--directories-only"])

        assert result.exit_code == 0
        # TUI should be created with directories-only filter
        mock_tui_class.assert_called_once()
        # Check the config passed to TUI constructor
        call_args = mock_tui_class.call_args[0]
        config = call_args[0]
        assert config.directories_only is True

    def test_invalid_directory(self, cli_runner):
        """Test browse with invalid directory."""
        result = cli_runner.invoke(browse_command, ["/nonexistent/directory/that/does/not/exist"])

        # Click catches exceptions, so check output for error message
        assert (
            "invalid" in result.output.lower()
            or "error" in result.output.lower()
            or "not" in result.output.lower()
        )

    @patch("sys.stdin.isatty")
    @patch("swirrl.commands.browse.FileBrowserTUI")
    def test_browse_default_directory(self, mock_tui_class, mock_isatty, cli_runner):
        """Test browse uses current directory by default."""
        mock_isatty.return_value = True
        mock_tui = MagicMock()
        mock_tui.run.return_value = []
        mock_tui_class.return_value = mock_tui

        result = cli_runner.invoke(browse_command, [])

        # Should use current directory
        mock_tui_class.assert_called_once()
        # Check the config passed to TUI constructor
        call_args = mock_tui_class.call_args[0]
        config = call_args[0]
        # start_directory should be set (either cwd or specified)
        assert config.start_directory is not None

    @patch("sys.stdin.isatty")
    @patch("swirrl.commands.browse.FileBrowserTUI")
    def test_browse_multiple_filters(
        self, mock_tui_class, mock_isatty, cli_runner, mock_file_system
    ):
        """Test browse with multiple file extensions."""
        mock_isatty.return_value = True
        mock_tui = MagicMock()
        mock_tui.run.return_value = []
        mock_tui_class.return_value = mock_tui

        result = cli_runner.invoke(browse_command, [str(mock_file_system), "--filter", ".mkv,.mp4"])

        assert result.exit_code == 0
        # TUI should be created with multiple filters
        mock_tui_class.assert_called_once()
        # Check the config passed to TUI constructor
        call_args = mock_tui_class.call_args[0]
        config = call_args[0]
        assert ".mkv" in config.filter_extensions
        assert ".mp4" in config.filter_extensions
