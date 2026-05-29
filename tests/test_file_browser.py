"""Tests for file browser engine."""

from pathlib import Path

import pytest

from ouro.core.file_browser import (
    BrowserConfig,
    FileBrowserEngine,
    FileBrowserState,
    FileEntry,
)


@pytest.fixture
def mock_file_system(tmp_path):
    """Create mock file system for browser tests."""
    # Create directory structure
    (tmp_path / "dir1").mkdir()
    (tmp_path / "dir2").mkdir()
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "nested").mkdir()

    # Create files with various extensions
    (tmp_path / "file1.mkv").write_text("test")
    (tmp_path / "file2.mp4").write_text("test")
    (tmp_path / "file3.txt").write_text("test")
    (tmp_path / "dir1" / "video.mkv").write_text("test")
    (tmp_path / "subdir" / "nested" / "deep.mkv").write_text("test")

    return tmp_path


class TestFileEntry:
    """Test FileEntry dataclass."""

    def test_file_entry_creation(self, tmp_path):
        """Test FileEntry creation."""
        test_file = tmp_path / "test.mkv"
        test_file.write_text("test")

        entry = FileEntry(
            path=test_file, name="test.mkv", is_directory=False, size=4, extension=".mkv"
        )

        assert entry.path == test_file
        assert entry.name == "test.mkv"
        assert not entry.is_directory
        assert entry.size == 4
        assert entry.extension == ".mkv"

    def test_directory_entry_creation(self, tmp_path):
        """Test directory FileEntry creation."""
        test_dir = tmp_path / "testdir"
        test_dir.mkdir()

        entry = FileEntry(path=test_dir, name="testdir", is_directory=True, size=0, extension="")

        assert entry.is_directory
        assert entry.extension == ""


class TestBrowserConfig:
    """Test BrowserConfig dataclass."""

    def test_default_config(self):
        """Test default configuration."""
        config = BrowserConfig()

        assert config.start_directory == Path.cwd()
        assert config.filter_extensions is None
        assert config.filter_pattern is None
        assert config.multi_select is False
        assert config.show_hidden is False
        assert config.directories_only is False

    def test_custom_config(self, tmp_path):
        """Test custom configuration."""
        config = BrowserConfig(
            start_directory=tmp_path,
            filter_extensions=[".mkv", ".mp4"],
            multi_select=True,
            show_hidden=True,
        )

        assert config.start_directory == tmp_path
        assert config.filter_extensions == [".mkv", ".mp4"]
        assert config.multi_select is True
        assert config.show_hidden is True


class TestFileBrowserState:
    """Test FileBrowserState dataclass."""

    def test_state_initialization(self, tmp_path):
        """Test state initialization."""
        state = FileBrowserState(
            current_dir=tmp_path, entries=[], cursor_index=0, selected_indices=set()
        )

        assert state.current_dir == tmp_path
        assert state.entries == []
        assert state.cursor_index == 0
        assert state.selected_indices == set()


class TestFileBrowserEngine:
    """Test FileBrowserEngine."""

    def test_engine_initialization(self, mock_file_system):
        """Test browser engine initialization."""
        config = BrowserConfig(start_directory=mock_file_system)
        engine = FileBrowserEngine(config)

        assert engine.state.current_dir == mock_file_system
        assert len(engine.state.entries) > 0

    def test_load_directory_entries(self, mock_file_system):
        """Test loading directory entries."""
        config = BrowserConfig(start_directory=mock_file_system)
        engine = FileBrowserEngine(config)

        # Should have directories and files
        entries = engine.state.entries
        assert len(entries) > 0

        # Check for expected entries
        names = [e.name for e in entries]
        assert "dir1" in names
        assert "dir2" in names
        assert "file1.mkv" in names

    def test_filter_by_extension(self, mock_file_system):
        """Test file filtering by extension."""
        config = BrowserConfig(start_directory=mock_file_system, filter_extensions=[".mkv"])
        engine = FileBrowserEngine(config)

        # All file entries should be .mkv
        file_entries = [e for e in engine.state.entries if not e.is_directory]
        for entry in file_entries:
            assert entry.extension == ".mkv"

    def test_filter_multiple_extensions(self, mock_file_system):
        """Test filtering with multiple extensions."""
        config = BrowserConfig(start_directory=mock_file_system, filter_extensions=[".mkv", ".mp4"])
        engine = FileBrowserEngine(config)

        file_entries = [e for e in engine.state.entries if not e.is_directory]
        for entry in file_entries:
            assert entry.extension in [".mkv", ".mp4"]

    def test_directories_only_filter(self, mock_file_system):
        """Test directories-only filter."""
        config = BrowserConfig(start_directory=mock_file_system, directories_only=True)
        engine = FileBrowserEngine(config)

        # All entries should be directories
        for entry in engine.state.entries:
            assert entry.is_directory

    def test_hidden_files_filtering(self, mock_file_system):
        """Test hidden files are filtered by default."""
        # Create hidden file
        hidden_file = mock_file_system / ".hidden"
        hidden_file.write_text("test")

        config = BrowserConfig(start_directory=mock_file_system, show_hidden=False)
        engine = FileBrowserEngine(config)

        names = [e.name for e in engine.state.entries]
        assert ".hidden" not in names

    def test_show_hidden_files(self, mock_file_system):
        """Test showing hidden files."""
        # Create hidden file
        hidden_file = mock_file_system / ".hidden"
        hidden_file.write_text("test")

        config = BrowserConfig(start_directory=mock_file_system, show_hidden=True)
        engine = FileBrowserEngine(config)

        names = [e.name for e in engine.state.entries]
        assert ".hidden" in names

    def test_navigate_into_directory(self, mock_file_system):
        """Test navigating into a directory."""
        config = BrowserConfig(start_directory=mock_file_system)
        engine = FileBrowserEngine(config)

        # Find a directory entry
        dir_entry = next((e for e in engine.state.entries if e.is_directory), None)
        assert dir_entry is not None

        # Set cursor to directory
        engine.state.cursor_index = engine.state.entries.index(dir_entry)

        # Navigate into it
        initial_dir = engine.state.current_dir
        engine.navigate_into()

        assert engine.state.current_dir != initial_dir
        assert engine.state.current_dir == dir_entry.path

    def test_navigate_up(self, mock_file_system):
        """Test navigating up to parent directory."""
        subdir = mock_file_system / "subdir"
        config = BrowserConfig(start_directory=subdir)
        engine = FileBrowserEngine(config)

        assert engine.state.current_dir == subdir

        # Navigate up
        engine.navigate_up()

        assert engine.state.current_dir == mock_file_system

    def test_navigate_up_at_root(self, mock_file_system):
        """Test navigating up at filesystem boundary."""
        config = BrowserConfig(start_directory=mock_file_system)
        engine = FileBrowserEngine(config)

        initial_dir = engine.state.current_dir

        # Navigate up multiple times until we can't go further
        prev_dir = initial_dir
        for _ in range(10):  # Arbitrary limit to prevent infinite loop
            engine.navigate_up()
            if engine.state.current_dir == prev_dir:
                # We've reached a boundary where we can't go up anymore
                break
            prev_dir = engine.state.current_dir

        # Try to navigate up one more time - should stay at same directory
        boundary_dir = engine.state.current_dir
        engine.navigate_up()
        assert engine.state.current_dir == boundary_dir

    def test_toggle_selection_single_mode(self, mock_file_system):
        """Test selection toggle in single-select mode."""
        config = BrowserConfig(start_directory=mock_file_system, multi_select=False)
        engine = FileBrowserEngine(config)

        # Toggle selection
        engine.toggle_selection()

        # Should have exactly one selected
        assert len(engine.state.selected_indices) == 1
        assert 0 in engine.state.selected_indices

    def test_toggle_selection_multi_mode(self, mock_file_system):
        """Test selection toggle in multi-select mode."""
        config = BrowserConfig(start_directory=mock_file_system, multi_select=True)
        engine = FileBrowserEngine(config)

        # Toggle first item
        engine.state.cursor_index = 0
        engine.toggle_selection()
        assert 0 in engine.state.selected_indices

        # Toggle second item
        engine.state.cursor_index = 1
        engine.toggle_selection()
        assert 0 in engine.state.selected_indices
        assert 1 in engine.state.selected_indices

        # Toggle first item again (deselect)
        engine.state.cursor_index = 0
        engine.toggle_selection()
        assert 0 not in engine.state.selected_indices
        assert 1 in engine.state.selected_indices

    def test_get_selected_paths(self, mock_file_system):
        """Test getting selected file paths."""
        config = BrowserConfig(start_directory=mock_file_system, multi_select=True)
        engine = FileBrowserEngine(config)

        # Select multiple items
        engine.state.cursor_index = 0
        engine.toggle_selection()
        engine.state.cursor_index = 1
        engine.toggle_selection()

        selected = engine.get_selected_paths()
        assert len(selected) == 2
        assert all(isinstance(p, Path) for p in selected)

    def test_move_cursor_down(self, mock_file_system):
        """Test moving cursor down."""
        config = BrowserConfig(start_directory=mock_file_system)
        engine = FileBrowserEngine(config)

        initial_cursor = engine.state.cursor_index
        engine.move_cursor(1)

        assert engine.state.cursor_index == initial_cursor + 1

    def test_move_cursor_up(self, mock_file_system):
        """Test moving cursor up."""
        config = BrowserConfig(start_directory=mock_file_system)
        engine = FileBrowserEngine(config)

        # Move to second item first
        engine.state.cursor_index = 1
        engine.move_cursor(-1)

        assert engine.state.cursor_index == 0

    def test_move_cursor_wraps(self, mock_file_system):
        """Test cursor wraps at boundaries."""
        config = BrowserConfig(start_directory=mock_file_system)
        engine = FileBrowserEngine(config)

        # Move up from first item (should wrap to last)
        engine.state.cursor_index = 0
        engine.move_cursor(-1)

        assert engine.state.cursor_index == len(engine.state.entries) - 1

    def test_refresh_directory(self, mock_file_system):
        """Test refreshing directory contents."""
        config = BrowserConfig(start_directory=mock_file_system)
        engine = FileBrowserEngine(config)

        initial_count = len(engine.state.entries)

        # Add a new file
        (mock_file_system / "newfile.mkv").write_text("test")

        # Refresh
        engine.refresh()

        # Should have one more entry
        assert len(engine.state.entries) == initial_count + 1

    def test_path_validation_on_navigation(self, mock_file_system):
        """Test path validation during navigation."""
        config = BrowserConfig(start_directory=mock_file_system)
        engine = FileBrowserEngine(config)

        # All loaded paths should be valid
        for entry in engine.state.entries:
            assert entry.path.exists()

    def test_empty_directory(self, tmp_path):
        """Test handling empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        config = BrowserConfig(start_directory=empty_dir)
        engine = FileBrowserEngine(config)

        # Should have no entries
        assert len(engine.state.entries) == 0

    def test_navigate_into_file_does_nothing(self, mock_file_system):
        """Test navigating into a file does nothing."""
        config = BrowserConfig(start_directory=mock_file_system)
        engine = FileBrowserEngine(config)

        # Find a file entry
        file_entry = next((e for e in engine.state.entries if not e.is_directory), None)
        assert file_entry is not None

        # Set cursor to file
        engine.state.cursor_index = engine.state.entries.index(file_entry)

        # Try to navigate into it
        initial_dir = engine.state.current_dir
        engine.navigate_into()

        # Should stay in same directory
        assert engine.state.current_dir == initial_dir

    def test_sorting_directories_first(self, mock_file_system):
        """Test that directories are sorted before files."""
        config = BrowserConfig(start_directory=mock_file_system)
        engine = FileBrowserEngine(config)

        # Find first file entry
        first_file_idx = next(
            (i for i, e in enumerate(engine.state.entries) if not e.is_directory), None
        )

        if first_file_idx is not None:
            # All entries before first file should be directories
            for i in range(first_file_idx):
                assert engine.state.entries[i].is_directory
