"""Tests for setup module default configuration handling.

This module tests default settings initialization, merging, and validation
in the setup module.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from swirrl.commands.setup import (
    _deep_merge_defaults,
    _ensure_setup_shape,
    _load_settings_with_defaults,
    _strip_wrapping_quotes,
    _workspace_paths,
)
from swirrl.core.settings import DEFAULT_SETTINGS


class TestDefaultMerging:
    """Test default settings merging logic."""

    def test_deep_merge_empty_current(self):
        """Test merging when current settings are empty."""
        current = {}
        defaults = {"key": "value", "nested": {"inner": "data"}}

        result = _deep_merge_defaults(current, defaults)

        assert result == defaults
        assert result is not defaults  # Should be a copy

    def test_deep_merge_preserves_current_values(self):
        """Test that current values override defaults."""
        current = {"key": "custom_value"}
        defaults = {"key": "default_value", "other": "data"}

        result = _deep_merge_defaults(current, defaults)

        assert result["key"] == "custom_value"
        assert result["other"] == "data"

    def test_deep_merge_nested_dicts(self):
        """Test merging nested dictionaries."""
        current = {"nested": {"custom": "value"}}
        defaults = {"nested": {"custom": "default", "other": "data"}}

        result = _deep_merge_defaults(current, defaults)

        assert result["nested"]["custom"] == "value"
        assert result["nested"]["other"] == "data"

    def test_deep_merge_does_not_modify_inputs(self):
        """Test that merging doesn't modify input dictionaries."""
        current = {"key": "value"}
        defaults = {"key": "default", "other": "data"}
        current_copy = current.copy()
        defaults_copy = defaults.copy()

        _deep_merge_defaults(current, defaults)

        assert current == current_copy
        assert defaults == defaults_copy

    def test_deep_merge_complex_structure(self):
        """Test merging complex nested structures."""
        current = {
            "general": {"locale": "fr"},
            "modules": {"nfo": {"active_template": "custom"}},
        }
        defaults = {
            "general": {"locale": "en", "debug": False},
            "modules": {
                "nfo": {"active_template": "default", "logo_path": ""},
                "prez": {"preset": "default"},
            },
        }

        result = _deep_merge_defaults(current, defaults)

        assert result["general"]["locale"] == "fr"
        assert result["general"]["debug"] is False
        assert result["modules"]["nfo"]["active_template"] == "custom"
        assert result["modules"]["nfo"]["logo_path"] == ""
        assert result["modules"]["prez"]["preset"] == "default"


class TestSetupShapeEnsuring:
    """Test ensuring proper settings structure."""

    def test_ensure_setup_shape_empty_dict(self):
        """Test ensuring shape on empty dictionary."""
        settings = {}

        result = _ensure_setup_shape(settings)

        assert "general" in result
        assert "metadata" in result
        assert "setup" in result
        assert "modules" in result

    def test_ensure_setup_shape_general_section(self):
        """Test general section is properly shaped."""
        settings = {}

        result = _ensure_setup_shape(settings)

        assert "locale" in result["general"]
        assert result["general"]["locale"] == DEFAULT_SETTINGS["general"]["locale"]

    def test_ensure_setup_shape_metadata_section(self):
        """Test metadata section is properly shaped."""
        settings = {}

        result = _ensure_setup_shape(settings)

        assert result["metadata"]["provider"] == "tmdb"
        assert result["metadata"]["interactive_confirmation"] is True
        assert result["metadata"]["cache_ttl_hours"] == 168
        assert result["metadata"]["language"] == "en-US"
        assert "tmdb_api_key" not in result["metadata"]
        assert result["metadata"]["tmdb_read_access_token"] == ""
        assert result["metadata"]["enabled_by_default"] is True

    def test_ensure_setup_shape_setup_section(self):
        """Test setup section is properly shaped."""
        settings = {}

        result = _ensure_setup_shape(settings)

        assert result["setup"]["completed"] is False
        assert result["setup"]["prompt_on_start"] is True

    def test_ensure_setup_shape_modules_section(self):
        """Test modules section is properly shaped."""
        settings = {}

        result = _ensure_setup_shape(settings)

        assert "renamer" in result["modules"]
        assert "cleanmkv" in result["modules"]
        assert "nfo" in result["modules"]
        assert "prez" in result["modules"]
        assert "torrent" in result["modules"]

    def test_ensure_setup_shape_renamer_defaults(self):
        """Test renamer module defaults."""
        settings = {}

        result = _ensure_setup_shape(settings)

        assert result["modules"]["renamer"]["default_folder"] == ""

    def test_ensure_setup_shape_cleanmkv_defaults(self):
        """Test cleanmkv module defaults."""
        settings = {}

        result = _ensure_setup_shape(settings)

        assert result["modules"]["cleanmkv"]["default_folder"] == ""

    def test_ensure_setup_shape_nfo_defaults(self):
        """Test NFO module defaults."""
        settings = {}

        result = _ensure_setup_shape(settings)

        nfo = result["modules"]["nfo"]
        assert nfo["default_folder"] == ""
        assert nfo["active_template"] == "default"
        assert nfo["logo_path"] == ""
        assert nfo["active_logo"] == ""
        assert nfo["with_metadata"] is True

    def test_ensure_setup_shape_prez_defaults(self):
        """Test Prez module defaults."""
        settings = {}

        result = _ensure_setup_shape(settings)

        prez = result["modules"]["prez"]
        assert prez["preset"] == "default"
        assert prez["html_template"] == "aurora"
        assert prez["bbcode_template"] == "classic"
        assert prez["with_metadata"] is True

    def test_ensure_setup_shape_torrent_defaults(self):
        """Test torrent module defaults."""
        settings = {}

        result = _ensure_setup_shape(settings)

        torrent = result["modules"]["torrent"]
        assert torrent["announce"] == ""
        assert torrent["announce_urls"] == []
        assert torrent["selected_announce"] == ""

    def test_ensure_setup_shape_preserves_existing(self):
        """Test that existing values are preserved."""
        settings = {
            "general": {"locale": "fr"},
            "metadata": {"language": "fr-FR"},
            "modules": {"nfo": {"active_template": "detailed"}},
        }

        result = _ensure_setup_shape(settings)

        assert result["general"]["locale"] == "fr"
        assert result["metadata"]["language"] == "fr-FR"
        assert result["modules"]["nfo"]["active_template"] == "detailed"


class TestSettingsLoading:
    """Test settings loading with defaults."""

    @patch("swirrl.commands.setup.SettingsStore")
    def test_load_settings_with_defaults_empty(self, mock_store_class: Mock):
        """Test loading when no settings exist."""
        mock_store = Mock()
        mock_store.load.return_value = {}
        mock_store_class.return_value = mock_store

        result = _load_settings_with_defaults(mock_store)

        assert "general" in result
        assert "metadata" in result
        assert "setup" in result
        assert "modules" in result

    @patch("swirrl.commands.setup.SettingsStore")
    def test_load_settings_with_defaults_existing(self, mock_store_class: Mock):
        """Test loading with existing settings."""
        mock_store = Mock()
        mock_store.load.return_value = {
            "general": {"locale": "es"},
            "metadata": {"language": "es-ES"},
        }
        mock_store_class.return_value = mock_store

        result = _load_settings_with_defaults(mock_store)

        assert result["general"]["locale"] == "es"
        assert result["metadata"]["language"] == "es-ES"
        # Should still have all required sections
        assert "setup" in result
        assert "modules" in result


class TestStringUtilities:
    """Test string utility functions."""

    def test_strip_wrapping_quotes_double(self):
        """Test stripping double quotes."""
        assert _strip_wrapping_quotes('"value"') == "value"

    def test_strip_wrapping_quotes_single(self):
        """Test stripping single quotes."""
        assert _strip_wrapping_quotes("'value'") == "value"

    def test_strip_wrapping_quotes_no_quotes(self):
        """Test string without quotes."""
        assert _strip_wrapping_quotes("value") == "value"

    def test_strip_wrapping_quotes_whitespace(self):
        """Test stripping with whitespace."""
        assert _strip_wrapping_quotes('  "value"  ') == "value"

    def test_strip_wrapping_quotes_mismatched(self):
        """Test mismatched quotes are not stripped."""
        assert _strip_wrapping_quotes("\"value'") == "\"value'"

    def test_strip_wrapping_quotes_empty(self):
        """Test empty string."""
        assert _strip_wrapping_quotes("") == ""

    def test_strip_wrapping_quotes_only_quotes(self):
        """Test string with only quotes."""
        assert _strip_wrapping_quotes('""') == ""

    def test_strip_wrapping_quotes_path_with_spaces(self):
        """Test path with spaces in quotes."""
        assert _strip_wrapping_quotes(r'"E:\My Folder\NFO"') == r"E:\My Folder\NFO"


class TestWorkspacePaths:
    """Test workspace path generation."""

    @patch("swirrl.commands.setup.get_config_dir")
    def test_workspace_paths_generation(self, mock_get_config: Mock, tmp_path: Path):
        """Test generating workspace paths."""
        mock_get_config.return_value = tmp_path / "config"
        project_root = tmp_path / "project"

        appdata, project = _workspace_paths(project_root, "TestFolder")

        assert appdata == tmp_path / "config" / "Workspace" / "TestFolder"
        assert project == project_root / "Workspace" / "TestFolder"

    @patch("swirrl.commands.setup.get_config_dir")
    def test_workspace_paths_different_folders(self, mock_get_config: Mock, tmp_path: Path):
        """Test generating paths for different folder names."""
        mock_get_config.return_value = tmp_path / "config"
        project_root = tmp_path / "project"

        renamer_appdata, renamer_project = _workspace_paths(project_root, "Renamer")
        nfo_appdata, nfo_project = _workspace_paths(project_root, "NFO")

        assert renamer_appdata.name == "Renamer"
        assert nfo_appdata.name == "NFO"
        assert renamer_project.name == "Renamer"
        assert nfo_project.name == "NFO"


@pytest.mark.unit
class TestDefaultsIntegration:
    """Integration tests for defaults handling."""

    def test_full_defaults_pipeline(self):
        """Test complete defaults initialization pipeline."""
        settings = {}

        # Apply shape
        settings = _ensure_setup_shape(settings)

        # Merge with defaults
        settings = _deep_merge_defaults(settings, DEFAULT_SETTINGS)

        # Verify all required sections exist
        assert "general" in settings
        assert "metadata" in settings
        assert "setup" in settings
        assert "modules" in settings

        # Verify critical defaults
        assert settings["metadata"]["provider"] == "tmdb"
        assert settings["setup"]["completed"] is False

    def test_defaults_with_partial_config(self):
        """Test defaults with partial existing configuration."""
        settings = {
            "general": {"locale": "fr"},
            "modules": {"nfo": {"active_template": "custom"}},
        }

        settings = _ensure_setup_shape(settings)
        settings = _deep_merge_defaults(settings, DEFAULT_SETTINGS)

        # Custom values preserved
        assert settings["general"]["locale"] == "fr"
        assert settings["modules"]["nfo"]["active_template"] == "custom"

        # Defaults filled in
        assert "metadata" in settings
        assert "setup" in settings
        assert settings["metadata"]["provider"] == "tmdb"
