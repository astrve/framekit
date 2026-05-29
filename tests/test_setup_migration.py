"""Tests for setup configuration migration and compatibility.

This module tests migration of settings from old formats to new formats,
ensuring backward compatibility and proper upgrade paths.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from ouro.commands.setup import (
    _deep_merge_defaults,
    _ensure_setup_shape,
    _load_settings_with_defaults,
)
from ouro.core.settings import DEFAULT_SETTINGS


class TestLegacyConfigMigration:
    """Test migration from legacy configuration formats."""

    def test_migrate_missing_setup_section(self):
        """Test migrating config without setup section."""
        legacy_config = {
            "general": {"locale": "en"},
            "metadata": {"provider": "tmdb"},
        }

        result = _ensure_setup_shape(legacy_config)

        assert "setup" in result
        assert result["setup"]["completed"] is False
        assert result["setup"]["prompt_on_start"] is True

    def test_migrate_missing_modules_section(self):
        """Test migrating config without modules section."""
        legacy_config = {
            "general": {"locale": "en"},
            "metadata": {"provider": "tmdb"},
        }

        result = _ensure_setup_shape(legacy_config)

        assert "modules" in result
        assert "renamer" in result["modules"]
        assert "cleanmkv" in result["modules"]
        assert "nfo" in result["modules"]

    def test_migrate_partial_modules(self):
        """Test migrating config with partial modules."""
        legacy_config = {
            "modules": {
                "nfo": {"active_template": "custom"},
            }
        }

        result = _ensure_setup_shape(legacy_config)

        # Existing module preserved
        assert result["modules"]["nfo"]["active_template"] == "custom"
        # Missing modules added
        assert "renamer" in result["modules"]
        assert "cleanmkv" in result["modules"]
        assert "prez" in result["modules"]
        assert "torrent" in result["modules"]

    def test_ensure_setup_shape_does_not_inject_tmdb_api_key(self):
        """The setup wizard never reintroduces the legacy ``tmdb_api_key``.

        Schema v12 dropped ``tmdb_api_key`` entirely. ``_ensure_setup_shape``
        only fills missing defaults — it must not add the removed key back.
        Stripping of legacy values from a v11 payload is the job of
        ``ouro.core.settings._migrate_legacy_settings`` and is exercised
        in ``tests/test_settings_migration.py``.
        """
        result = _ensure_setup_shape({"metadata": {"provider": "tmdb"}})

        assert "tmdb_api_key" not in result["metadata"]
        assert "tmdb_read_access_token" in result["metadata"]
        assert "interactive_confirmation" in result["metadata"]

    def test_migrate_preserves_all_existing_data(self):
        """Test that migration preserves all existing configuration."""
        legacy_config = {
            "general": {"locale": "fr", "custom_key": "custom_value"},
            "metadata": {"provider": "tmdb", "language": "fr-FR"},
            "modules": {"nfo": {"active_template": "detailed", "custom_setting": "value"}},
        }

        result = _ensure_setup_shape(legacy_config)

        # All existing data preserved
        assert result["general"]["locale"] == "fr"
        assert result["general"]["custom_key"] == "custom_value"
        assert result["metadata"]["language"] == "fr-FR"
        assert result["modules"]["nfo"]["active_template"] == "detailed"
        assert result["modules"]["nfo"]["custom_setting"] == "value"


class TestVersionCompatibility:
    """Test compatibility across different configuration versions."""

    def test_v1_to_current_migration(self):
        """Test migrating from v1 configuration format."""
        v1_config = {
            "schema_version": 1,
            "general": {"ui_locale": "en"},
            "metadata": {"provider": "tmdb"},
        }

        result = _ensure_setup_shape(v1_config)

        # Schema version preserved
        assert result.get("schema_version") == 1
        # New sections added
        assert "setup" in result
        assert "modules" in result

    def test_no_version_to_current_migration(self):
        """Test migrating config without version number."""
        unversioned_config = {
            "general": {"locale": "en"},
            "metadata": {"provider": "tmdb"},
        }

        result = _ensure_setup_shape(unversioned_config)

        # Should still work and add missing sections
        assert "setup" in result
        assert "modules" in result

    def test_future_version_compatibility(self):
        """Test handling config with future version number."""
        future_config = {
            "schema_version": 999,
            "general": {"locale": "en"},
            "metadata": {"provider": "tmdb"},
            "future_section": {"new_feature": "value"},
        }

        result = _ensure_setup_shape(future_config)

        # Future sections preserved
        assert result.get("future_section") == {"new_feature": "value"}
        # Required sections still added
        assert "setup" in result
        assert "modules" in result


class TestDefaultsMerging:
    """Test merging with defaults during migration."""

    def test_merge_adds_missing_top_level_keys(self):
        """Test that merging adds missing top-level keys."""
        current = {"general": {"locale": "en"}}

        result = _deep_merge_defaults(current, DEFAULT_SETTINGS)

        # Should have all top-level keys from defaults
        for key in DEFAULT_SETTINGS:
            assert key in result

    def test_merge_preserves_custom_nested_values(self):
        """Test that custom nested values are preserved."""
        current = {
            "modules": {
                "nfo": {
                    "active_template": "custom",
                    "custom_key": "custom_value",
                }
            }
        }
        defaults = {
            "modules": {
                "nfo": {
                    "active_template": "default",
                    "logo_path": "",
                }
            }
        }

        result = _deep_merge_defaults(current, defaults)

        assert result["modules"]["nfo"]["active_template"] == "custom"
        assert result["modules"]["nfo"]["custom_key"] == "custom_value"
        assert result["modules"]["nfo"]["logo_path"] == ""

    def test_merge_handles_type_conflicts(self):
        """Test handling when current value type differs from default."""
        current = {"key": "string_value"}
        defaults = {"key": {"nested": "dict"}}

        result = _deep_merge_defaults(current, defaults)

        # Current value should win
        assert result["key"] == "string_value"

    def test_merge_deep_nesting(self):
        """Test merging with deeply nested structures."""
        current = {"level1": {"level2": {"level3": {"custom": "value"}}}}
        defaults = {
            "level1": {
                "level2": {"level3": {"custom": "default", "other": "data"}, "sibling": "value"}
            }
        }

        result = _deep_merge_defaults(current, defaults)

        assert result["level1"]["level2"]["level3"]["custom"] == "value"
        assert result["level1"]["level2"]["level3"]["other"] == "data"
        assert result["level1"]["level2"]["sibling"] == "value"


class TestModuleDefaults:
    """Test module-specific default migrations."""

    def test_renamer_module_defaults(self):
        """Test renamer module gets proper defaults."""
        config = {}

        result = _ensure_setup_shape(config)

        assert "renamer" in result["modules"]
        assert "default_folder" in result["modules"]["renamer"]
        assert result["modules"]["renamer"]["default_folder"] == ""

    def test_cleanmkv_module_defaults(self):
        """Test cleanmkv module gets proper defaults."""
        config = {}

        result = _ensure_setup_shape(config)

        assert "cleanmkv" in result["modules"]
        assert "default_folder" in result["modules"]["cleanmkv"]
        assert result["modules"]["cleanmkv"]["default_folder"] == ""

    def test_nfo_module_defaults(self):
        """Test NFO module gets proper defaults."""
        config = {}

        result = _ensure_setup_shape(config)

        nfo = result["modules"]["nfo"]
        assert "default_folder" in nfo
        assert "active_template" in nfo
        assert "logo_path" in nfo
        assert "active_logo" in nfo
        assert "with_metadata" in nfo
        assert nfo["active_template"] == "default"
        assert nfo["with_metadata"] is True

    def test_prez_module_defaults(self):
        """Test Prez module gets proper defaults."""
        config = {}

        result = _ensure_setup_shape(config)

        prez = result["modules"]["prez"]
        assert "preset" in prez
        assert "html_template" in prez
        assert "bbcode_template" in prez
        assert "with_metadata" in prez
        assert prez["preset"] == "default"
        assert prez["html_template"] == "aurora"
        assert prez["bbcode_template"] == "classic"

    def test_torrent_module_defaults(self):
        """Test torrent module gets proper defaults."""
        config = {}

        result = _ensure_setup_shape(config)

        torrent = result["modules"]["torrent"]
        assert "announce" in torrent
        assert "announce_urls" in torrent
        assert "selected_announce" in torrent
        assert torrent["announce"] == ""
        assert torrent["announce_urls"] == []
        assert torrent["selected_announce"] == ""


class TestSettingsStoreIntegration:
    """Test integration with SettingsStore."""

    @patch("ouro.commands.setup.SettingsStore")
    def test_load_with_defaults_empty_store(self, mock_store_class: Mock):
        """Test loading from empty settings store."""
        mock_store = Mock()
        mock_store.load.return_value = {}

        result = _load_settings_with_defaults(mock_store)

        # Should have all required sections
        assert "general" in result
        assert "metadata" in result
        assert "setup" in result
        assert "modules" in result

    @patch("ouro.commands.setup.SettingsStore")
    def test_load_with_defaults_partial_store(self, mock_store_class: Mock):
        """Test loading from partially populated store."""
        mock_store = Mock()
        mock_store.load.return_value = {
            "general": {"locale": "fr"},
            "metadata": {"language": "fr-FR"},
        }

        result = _load_settings_with_defaults(mock_store)

        # Custom values preserved
        assert result["general"]["locale"] == "fr"
        assert result["metadata"]["language"] == "fr-FR"
        # Missing sections added
        assert "setup" in result
        assert "modules" in result

    @patch("ouro.commands.setup.SettingsStore")
    def test_load_with_defaults_complete_store(self, mock_store_class: Mock):
        """Test loading from complete settings store."""
        complete_config = {
            "general": {"locale": "en"},
            "metadata": {
                "provider": "tmdb",
                "language": "en-US",
                "interactive_confirmation": True,
            },
            "setup": {"completed": True, "prompt_on_start": False},
            "modules": {
                "nfo": {"active_template": "detailed"},
                "prez": {"preset": "custom"},
            },
        }
        mock_store = Mock()
        mock_store.load.return_value = complete_config

        result = _load_settings_with_defaults(mock_store)

        # All values preserved
        assert result["general"]["locale"] == "en"
        assert result["metadata"]["language"] == "en-US"
        assert result["setup"]["completed"] is True
        assert result["modules"]["nfo"]["active_template"] == "detailed"


@pytest.mark.unit
class TestMigrationEdgeCases:
    """Test edge cases in configuration migration."""

    def test_empty_nested_dicts(self):
        """Test handling empty nested dictionaries."""
        config = {"modules": {}}

        result = _ensure_setup_shape(config)

        # Should populate empty modules section
        assert "renamer" in result["modules"]
        assert "nfo" in result["modules"]

    def test_none_values_in_config(self):
        """Test handling None values in configuration."""
        config = {
            "general": {"locale": None},
            "metadata": {"language": None},
        }

        result = _ensure_setup_shape(config)

        # None values should be preserved
        assert result["general"]["locale"] is None
        assert result["metadata"]["language"] is None

    def test_list_values_preserved(self):
        """Test that list values are preserved during migration."""
        config = {
            "modules": {
                "torrent": {"announce_urls": ["http://tracker1.com", "http://tracker2.com"]}
            }
        }

        result = _ensure_setup_shape(config)

        assert len(result["modules"]["torrent"]["announce_urls"]) == 2
        assert "http://tracker1.com" in result["modules"]["torrent"]["announce_urls"]

    def test_boolean_values_preserved(self):
        """Test that boolean values are preserved correctly."""
        config = {
            "metadata": {"interactive_confirmation": False},
            "modules": {"nfo": {"with_metadata": False}},
        }

        result = _ensure_setup_shape(config)

        assert result["metadata"]["interactive_confirmation"] is False
        assert result["modules"]["nfo"]["with_metadata"] is False

    def test_numeric_values_preserved(self):
        """Test that numeric values are preserved."""
        config = {
            "metadata": {"cache_ttl_hours": 72},
        }

        result = _ensure_setup_shape(config)

        assert result["metadata"]["cache_ttl_hours"] == 72
