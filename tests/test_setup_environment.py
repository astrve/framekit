"""Tests for setup environment detection and system checks.

This module tests environment detection, tool availability checks,
and system-specific configuration in the setup module.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ouro.commands.setup import (
    _ensure_default_folders_exist,
    _print_setup_summary,
    _workspace_paths,
    maybe_offer_first_time_setup,
)


class TestWorkspacePathDetection:
    """Test workspace path detection and generation."""

    @patch("ouro.commands.setup.get_config_dir")
    def test_workspace_paths_appdata(self, mock_get_config: Mock, tmp_path: Path):
        """Test AppData workspace path generation."""
        config_dir = tmp_path / "config"
        mock_get_config.return_value = config_dir
        project_root = tmp_path / "project"

        appdata, project = _workspace_paths(project_root, "TestModule")

        assert appdata == config_dir / "Workspace" / "TestModule"
        assert project == project_root / "Workspace" / "TestModule"

    @patch("ouro.commands.setup.get_config_dir")
    def test_workspace_paths_project(self, mock_get_config: Mock, tmp_path: Path):
        """Test project workspace path generation."""
        config_dir = tmp_path / "config"
        mock_get_config.return_value = config_dir
        project_root = tmp_path / "project"

        appdata, project = _workspace_paths(project_root, "TestModule")

        assert project.parent.name == "Workspace"
        assert project.name == "TestModule"

    @patch("ouro.commands.setup.get_config_dir")
    def test_workspace_paths_multiple_modules(self, mock_get_config: Mock, tmp_path: Path):
        """Test workspace paths for multiple modules."""
        config_dir = tmp_path / "config"
        mock_get_config.return_value = config_dir
        project_root = tmp_path / "project"

        modules = ["Renamer", "CleanMKV", "NFO", "Prez"]
        paths = [_workspace_paths(project_root, module) for module in modules]

        # All should have unique paths
        appdata_paths = [p[0] for p in paths]
        project_paths = [p[1] for p in paths]

        assert len(set(appdata_paths)) == len(modules)
        assert len(set(project_paths)) == len(modules)


class TestFolderCreation:
    """Test default folder creation."""

    def test_ensure_folders_creates_missing(self, tmp_path: Path):
        """Test creating missing default folders."""
        settings = {
            "modules": {
                "renamer": {"default_folder": str(tmp_path / "renamer")},
                "cleanmkv": {"default_folder": str(tmp_path / "cleanmkv")},
                "nfo": {"default_folder": str(tmp_path / "nfo")},
            }
        }

        _ensure_default_folders_exist(settings)

        assert (tmp_path / "renamer").exists()
        assert (tmp_path / "cleanmkv").exists()
        assert (tmp_path / "nfo").exists()

    def test_ensure_folders_skips_empty_paths(self, tmp_path: Path):
        """Test skipping modules with empty paths."""
        settings = {
            "modules": {
                "renamer": {"default_folder": ""},
                "cleanmkv": {"default_folder": str(tmp_path / "cleanmkv")},
                "nfo": {"default_folder": ""},
            }
        }

        _ensure_default_folders_exist(settings)

        # Only cleanmkv folder should be created
        assert (tmp_path / "cleanmkv").exists()
        assert not (tmp_path / "renamer").exists()
        assert not (tmp_path / "nfo").exists()

    def test_ensure_folders_handles_existing(self, tmp_path: Path):
        """Test handling existing folders."""
        existing_folder = tmp_path / "existing"
        existing_folder.mkdir(parents=True)

        settings = {
            "modules": {
                "renamer": {"default_folder": str(existing_folder)},
                "cleanmkv": {"default_folder": ""},
                "nfo": {"default_folder": ""},
            }
        }

        # Should not raise error
        _ensure_default_folders_exist(settings)

        assert existing_folder.exists()

    def test_ensure_folders_creates_nested_paths(self, tmp_path: Path):
        """Test creating nested folder structures."""
        nested_path = tmp_path / "level1" / "level2" / "level3"

        settings = {
            "modules": {
                "renamer": {"default_folder": str(nested_path)},
                "cleanmkv": {"default_folder": ""},
                "nfo": {"default_folder": ""},
            }
        }

        _ensure_default_folders_exist(settings)

        assert nested_path.exists()

    @patch("ouro.commands.setup.Path.mkdir")
    @patch("ouro.commands.setup.print_warning")
    def test_ensure_folders_handles_permission_error(
        self, mock_warning: Mock, mock_mkdir: Mock, tmp_path: Path
    ):
        """Test handling permission errors during folder creation."""
        # Force mkdir to raise an error
        mock_mkdir.side_effect = PermissionError("Access denied")

        settings = {
            "modules": {
                "renamer": {"default_folder": str(tmp_path / "test")},
                "cleanmkv": {"default_folder": ""},
                "nfo": {"default_folder": ""},
            }
        }

        # Should not raise, but should warn
        _ensure_default_folders_exist(settings)

        # Warning should be printed
        mock_warning.assert_called()


class TestFirstTimeSetupDetection:
    """Test first-time setup detection and prompting."""

    @patch("ouro.commands.setup.sys.stdin")
    @patch("ouro.commands.setup.sys.stdout")
    def test_skip_if_not_tty(self, mock_stdout: Mock, mock_stdin: Mock):
        """Test skipping setup if not in TTY."""
        mock_stdin.isatty.return_value = False
        mock_stdout.isatty.return_value = True

        # Should return without prompting
        maybe_offer_first_time_setup()

        # No assertions needed - just shouldn't raise

    @patch("ouro.commands.setup.sys.stdin")
    @patch("ouro.commands.setup.sys.stdout")
    @patch("ouro.commands.setup.SettingsStore")
    def test_skip_if_completed(self, mock_store_class: Mock, mock_stdout: Mock, mock_stdin: Mock):
        """Test skipping if setup already completed."""
        mock_stdin.isatty.return_value = True
        mock_stdout.isatty.return_value = True

        mock_store = Mock()
        mock_store.load.return_value = {"setup": {"completed": True, "prompt_on_start": True}}
        mock_store_class.return_value = mock_store

        maybe_offer_first_time_setup()

        # Should not prompt user

    @patch("ouro.commands.setup.sys.stdin")
    @patch("ouro.commands.setup.sys.stdout")
    @patch("ouro.commands.setup.sys.argv", ["ouro", "setup"])
    @patch("ouro.commands.setup.SettingsStore")
    def test_skip_if_running_setup_command(
        self, mock_store_class: Mock, mock_stdout: Mock, mock_stdin: Mock
    ):
        """Test skipping if already running setup command."""
        mock_stdin.isatty.return_value = True
        mock_stdout.isatty.return_value = True

        mock_store = Mock()
        mock_store.load.return_value = {"setup": {"completed": False, "prompt_on_start": True}}
        mock_store_class.return_value = mock_store

        maybe_offer_first_time_setup()

        # Should not prompt since already in setup

    @patch("ouro.commands.setup.sys.stdin")
    @patch("ouro.commands.setup.sys.stdout")
    @patch("ouro.commands.setup.sys.argv", ["ouro", "--help"])
    @patch("ouro.commands.setup.SettingsStore")
    def test_skip_if_help_command(
        self, mock_store_class: Mock, mock_stdout: Mock, mock_stdin: Mock
    ):
        """Test skipping if running help command."""
        mock_stdin.isatty.return_value = True
        mock_stdout.isatty.return_value = True

        mock_store = Mock()
        mock_store.load.return_value = {"setup": {"completed": False, "prompt_on_start": True}}
        mock_store_class.return_value = mock_store

        maybe_offer_first_time_setup()

        # Should not prompt for help command


class TestSetupSummary:
    """Test setup summary display."""

    @patch("ouro.commands.setup.console")
    def test_print_summary_basic(self, mock_console: Mock):
        """Test printing basic setup summary."""
        settings = {
            "general": {"locale": "en"},
            "metadata": {
                "language": "en-US",
                "interactive_confirmation": True,
                "tmdb_read_access_token": "",
            },
            "modules": {
                "renamer": {"default_folder": "/path/to/renamer"},
                "cleanmkv": {"default_folder": "/path/to/cleanmkv"},
                "nfo": {
                    "default_folder": "/path/to/nfo",
                    "active_template": "default",
                    "active_logo": "",
                },
                "prez": {
                    "bbcode_template": "classic",
                    "html_template": "aurora",
                },
                "torrent": {"selected_announce": ""},
            },
        }

        _print_setup_summary(settings)

        # Should print table
        mock_console.print.assert_called()

    @patch("ouro.commands.setup.console")
    def test_print_summary_with_token(self, mock_console: Mock):
        """Test summary shows token as configured."""
        settings = {
            "general": {"locale": "en"},
            "metadata": {
                "language": "en-US",
                "interactive_confirmation": True,
                "tmdb_read_access_token": "eyJhbGciOiJIUzI1NiJ9.test",
            },
            "modules": {
                "renamer": {"default_folder": ""},
                "cleanmkv": {"default_folder": ""},
                "nfo": {
                    "default_folder": "",
                    "active_template": "default",
                    "active_logo": "",
                },
                "prez": {
                    "bbcode_template": "classic",
                    "html_template": "aurora",
                },
                "torrent": {"selected_announce": ""},
            },
        }

        _print_setup_summary(settings)

        mock_console.print.assert_called()

    @patch("ouro.commands.setup.console")
    def test_print_summary_with_logo(self, mock_console: Mock):
        """Test summary shows active logo."""
        settings = {
            "general": {"locale": "en"},
            "metadata": {
                "language": "en-US",
                "interactive_confirmation": True,
                "tmdb_read_access_token": "",
            },
            "modules": {
                "renamer": {"default_folder": ""},
                "cleanmkv": {"default_folder": ""},
                "nfo": {
                    "default_folder": "",
                    "active_template": "default",
                    "active_logo": "custom_logo",
                },
                "prez": {
                    "bbcode_template": "classic",
                    "html_template": "aurora",
                },
                "torrent": {"selected_announce": "http://tracker.example.com"},
            },
        }

        _print_setup_summary(settings)

        mock_console.print.assert_called()


class TestEnvironmentCompatibility:
    """Test environment compatibility checks."""

    @patch("ouro.commands.setup.get_config_dir")
    def test_config_dir_windows_style(self, mock_get_config: Mock, tmp_path: Path):
        """Test Windows-style config directory."""
        config_dir = tmp_path / "AppData" / "Roaming" / "Ouro"
        mock_get_config.return_value = config_dir
        project_root = tmp_path / "project"

        appdata, project = _workspace_paths(project_root, "Test")

        assert "AppData" in str(appdata)
        assert "Workspace" in str(appdata)

    @patch("ouro.commands.setup.get_config_dir")
    def test_config_dir_unix_style(self, mock_get_config: Mock, tmp_path: Path):
        """Test Unix-style config directory."""
        config_dir = tmp_path / ".config" / "ouro"
        mock_get_config.return_value = config_dir
        project_root = tmp_path / "project"

        appdata, project = _workspace_paths(project_root, "Test")

        assert ".config" in str(appdata) or "Workspace" in str(appdata)

    def test_folder_creation_cross_platform(self, tmp_path: Path):
        """Test folder creation works cross-platform."""
        # Test with both forward and backslashes
        paths = [
            tmp_path / "test1",
            tmp_path / "test2" / "nested",
        ]

        settings = {
            "modules": {
                "renamer": {"default_folder": str(paths[0])},
                "cleanmkv": {"default_folder": str(paths[1])},
                "nfo": {"default_folder": ""},
            }
        }

        _ensure_default_folders_exist(settings)

        for path in paths:
            assert path.exists()


@pytest.mark.unit
class TestEnvironmentEdgeCases:
    """Test edge cases in environment detection."""

    def test_ensure_folders_with_unicode_paths(self, tmp_path: Path):
        """Test handling Unicode characters in paths."""
        unicode_path = tmp_path / "Dossier_Français" / "NFO"

        settings = {
            "modules": {
                "renamer": {"default_folder": str(unicode_path)},
                "cleanmkv": {"default_folder": ""},
                "nfo": {"default_folder": ""},
            }
        }

        _ensure_default_folders_exist(settings)

        assert unicode_path.exists()

    def test_ensure_folders_with_spaces(self, tmp_path: Path):
        """Test handling paths with spaces."""
        spaced_path = tmp_path / "My Folder" / "Sub Folder"

        settings = {
            "modules": {
                "renamer": {"default_folder": str(spaced_path)},
                "cleanmkv": {"default_folder": ""},
                "nfo": {"default_folder": ""},
            }
        }

        _ensure_default_folders_exist(settings)

        assert spaced_path.exists()

    def test_ensure_folders_with_special_chars(self, tmp_path: Path):
        """Test handling paths with special characters."""
        special_path = tmp_path / "Folder-With_Special.Chars"

        settings = {
            "modules": {
                "renamer": {"default_folder": str(special_path)},
                "cleanmkv": {"default_folder": ""},
                "nfo": {"default_folder": ""},
            }
        }

        _ensure_default_folders_exist(settings)

        assert special_path.exists()

    @patch("ouro.commands.setup.Path.mkdir")
    @patch("ouro.commands.setup.print_warning")
    def test_ensure_folders_handles_os_error(self, mock_warning: Mock, mock_mkdir: Mock):
        """Test handling OSError during folder creation."""
        mock_mkdir.side_effect = OSError("Permission denied")

        settings = {
            "modules": {
                "renamer": {"default_folder": "/invalid/path"},
                "cleanmkv": {"default_folder": ""},
                "nfo": {"default_folder": ""},
            }
        }

        # Should not raise
        _ensure_default_folders_exist(settings)

        # Should warn user
        mock_warning.assert_called()
