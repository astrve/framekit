"""Tests for the command aliases system."""

from __future__ import annotations

import pytest

from framekit.core.aliases import (
    AliasDefinition,
    AliasError,
    AliasManager,
    CircularReferenceError,
    InvalidAliasNameError,
)
from framekit.core.settings import SettingsStore


class TestAliasDefinition:
    """Test AliasDefinition model."""

    def test_create_simple_alias(self):
        """Test creating a simple alias."""
        alias = AliasDefinition(
            name="ren",
            command="renamer",
            description="Shortcut for renamer",
            enabled=True,
        )
        assert alias.name == "ren"
        assert alias.command == "renamer"
        assert alias.description == "Shortcut for renamer"
        assert alias.enabled is True

    def test_create_alias_with_parameters(self):
        """Test creating an alias with parameter substitution."""
        alias = AliasDefinition(
            name="quick-encode",
            command="pipeline run --preset multi_en {0}",
            description="Quick encode",
            enabled=True,
        )
        assert "{0}" in alias.command

    def test_alias_equality(self):
        """Test alias equality comparison."""
        alias1 = AliasDefinition(name="test", command="cmd", description="", enabled=True)
        alias2 = AliasDefinition(name="test", command="cmd", description="", enabled=True)
        alias3 = AliasDefinition(name="other", command="cmd", description="", enabled=True)

        assert alias1 == alias2
        assert alias1 != alias3


class TestAliasManager:
    """Test AliasManager functionality."""

    def test_manager_initialization(self, tmp_path):
        """Test manager initialization with settings."""
        settings_file = tmp_path / "framekit.yaml"
        store = SettingsStore(settings_file)
        manager = AliasManager(store)

        assert manager is not None
        assert manager.settings_store == store

    def test_list_all_aliases(self, tmp_path):
        """Test listing all aliases."""
        settings_file = tmp_path / "framekit.yaml"
        store = SettingsStore(settings_file)
        manager = AliasManager(store)

        aliases = manager.list_aliases()
        assert isinstance(aliases, dict)
        # Should have builtin aliases
        assert "ren" in aliases or "cmk" in aliases

    def test_list_user_aliases_only(self, tmp_path):
        """Test listing only user-defined aliases."""
        settings_file = tmp_path / "framekit.yaml"
        store = SettingsStore(settings_file)
        manager = AliasManager(store)

        # Add a user alias
        manager.add_alias("test-alias", "renamer", "Test alias")

        user_aliases = manager.list_aliases(user_only=True)
        assert "test-alias" in user_aliases
        assert "ren" not in user_aliases  # builtin should not be included

    def test_list_builtin_aliases_only(self, tmp_path):
        """Test listing only builtin aliases."""
        settings_file = tmp_path / "framekit.yaml"
        store = SettingsStore(settings_file)
        manager = AliasManager(store)

        builtin_aliases = manager.list_aliases(builtin_only=True)
        assert "ren" in builtin_aliases or "cmk" in builtin_aliases

    def test_get_alias(self, tmp_path):
        """Test getting a specific alias."""
        settings_file = tmp_path / "framekit.yaml"
        store = SettingsStore(settings_file)
        manager = AliasManager(store)

        # Get builtin alias
        alias = manager.get_alias("ren")
        assert alias is not None
        assert alias.name == "ren"
        assert alias.command == "renamer"

    def test_get_nonexistent_alias(self, tmp_path):
        """Test getting a nonexistent alias returns None."""
        settings_file = tmp_path / "framekit.yaml"
        store = SettingsStore(settings_file)
        manager = AliasManager(store)

        alias = manager.get_alias("nonexistent")
        assert alias is None

    def test_add_user_alias(self, tmp_path):
        """Test adding a user alias."""
        settings_file = tmp_path / "framekit.yaml"
        store = SettingsStore(settings_file)
        manager = AliasManager(store)

        manager.add_alias("my-alias", "pipeline run", "My custom alias")

        alias = manager.get_alias("my-alias")
        assert alias is not None
        assert alias.name == "my-alias"
        assert alias.command == "pipeline run"
        assert alias.description == "My custom alias"
        assert alias.enabled is True

    def test_add_alias_with_invalid_name(self, tmp_path):
        """Test adding an alias with invalid name raises error."""
        settings_file = tmp_path / "framekit.yaml"
        store = SettingsStore(settings_file)
        manager = AliasManager(store)

        with pytest.raises(InvalidAliasNameError):
            manager.add_alias("invalid name", "cmd", "")

        with pytest.raises(InvalidAliasNameError):
            manager.add_alias("invalid@name", "cmd", "")

    def test_add_alias_conflicts_with_builtin_command(self, tmp_path):
        """Test adding an alias that conflicts with builtin command."""
        settings_file = tmp_path / "framekit.yaml"
        store = SettingsStore(settings_file)
        manager = AliasManager(store)

        # Should raise error when trying to shadow a builtin command
        with pytest.raises(AliasError, match="conflicts with built-in command"):
            manager.add_alias("pipeline", "custom_pipeline", "")

    def test_remove_user_alias(self, tmp_path):
        """Test removing a user alias."""
        settings_file = tmp_path / "framekit.yaml"
        store = SettingsStore(settings_file)
        manager = AliasManager(store)

        manager.add_alias("temp-alias", "cmd", "Temporary")
        assert manager.get_alias("temp-alias") is not None

        manager.remove_alias("temp-alias")
        assert manager.get_alias("temp-alias") is None

    def test_remove_builtin_alias_raises_error(self, tmp_path):
        """Test removing a builtin alias raises error."""
        settings_file = tmp_path / "framekit.yaml"
        store = SettingsStore(settings_file)
        manager = AliasManager(store)

        with pytest.raises(AliasError, match="Cannot remove built-in alias"):
            manager.remove_alias("ren")

    def test_enable_alias(self, tmp_path):
        """Test enabling a disabled alias."""
        settings_file = tmp_path / "framekit.yaml"
        store = SettingsStore(settings_file)
        manager = AliasManager(store)

        manager.add_alias("test-alias", "cmd", "Test")
        manager.disable_alias("test-alias")

        alias = manager.get_alias("test-alias")
        assert alias.enabled is False

        manager.enable_alias("test-alias")
        alias = manager.get_alias("test-alias")
        assert alias.enabled is True

    def test_disable_alias(self, tmp_path):
        """Test disabling an alias."""
        settings_file = tmp_path / "framekit.yaml"
        store = SettingsStore(settings_file)
        manager = AliasManager(store)

        manager.add_alias("test-alias", "cmd", "Test")
        manager.disable_alias("test-alias")

        alias = manager.get_alias("test-alias")
        assert alias.enabled is False

    def test_resolve_simple_alias(self, tmp_path):
        """Test resolving a simple alias without parameters."""
        settings_file = tmp_path / "framekit.yaml"
        store = SettingsStore(settings_file)
        manager = AliasManager(store)

        result = manager.resolve("ren", ["input.mkv"])
        assert result.command == "renamer"
        assert result.args == ["input.mkv"]

    def test_resolve_alias_with_positional_params(self, tmp_path):
        """Test resolving alias with positional parameter substitution."""
        settings_file = tmp_path / "framekit.yaml"
        store = SettingsStore(settings_file)
        manager = AliasManager(store)

        manager.add_alias("quick-encode", "pipeline run --preset multi_en {0}", "Quick encode")

        result = manager.resolve("quick-encode", ["input.mkv"])
        assert result.command == "pipeline"
        assert "run" in result.args
        assert "--preset" in result.args
        assert "multi_en" in result.args
        assert "input.mkv" in result.args

    def test_resolve_alias_with_multiple_params(self, tmp_path):
        """Test resolving alias with multiple parameters."""
        settings_file = tmp_path / "framekit.yaml"
        store = SettingsStore(settings_file)
        manager = AliasManager(store)

        manager.add_alias(
            "extract-sub", "extract subtitle --language {0} --format {1} {2}", "Extract"
        )

        result = manager.resolve("extract-sub", ["eng", "srt", "input.mkv"])
        assert "eng" in result.args
        assert "srt" in result.args
        assert "input.mkv" in result.args

    def test_resolve_disabled_alias_raises_error(self, tmp_path):
        """Test resolving a disabled alias raises error."""
        settings_file = tmp_path / "framekit.yaml"
        store = SettingsStore(settings_file)
        manager = AliasManager(store)

        manager.add_alias("test-alias", "cmd", "Test")
        manager.disable_alias("test-alias")

        with pytest.raises(AliasError, match="disabled"):
            manager.resolve("test-alias", [])

    def test_resolve_nonexistent_alias_raises_error(self, tmp_path):
        """Test resolving nonexistent alias raises error."""
        settings_file = tmp_path / "framekit.yaml"
        store = SettingsStore(settings_file)
        manager = AliasManager(store)

        with pytest.raises(AliasError, match="not found"):
            manager.resolve("nonexistent", [])

    def test_circular_reference_detection(self, tmp_path):
        """Test circular reference detection."""
        settings_file = tmp_path / "framekit.yaml"
        store = SettingsStore(settings_file)
        manager = AliasManager(store)

        # Create circular reference: a -> b -> a
        manager.add_alias("alias-a", "alias-b", "A")
        manager.add_alias("alias-b", "alias-a", "B")

        with pytest.raises(CircularReferenceError):
            manager.resolve("alias-a", [])

    def test_max_chain_depth_detection(self, tmp_path):
        """Test max chain depth detection."""
        settings_file = tmp_path / "framekit.yaml"
        store = SettingsStore(settings_file)
        manager = AliasManager(store)

        # Create a chain within max depth (5 aliases)
        manager.add_alias("alias-1", "alias-2", "1")
        manager.add_alias("alias-2", "alias-3", "2")
        manager.add_alias("alias-3", "alias-4", "3")
        manager.add_alias("alias-4", "alias-5", "4")
        manager.add_alias("alias-5", "renamer", "5")

        # Should work within max depth (default 5)
        result = manager.resolve("alias-1", [])
        assert result.command == "renamer"

        # Now test exceeding max depth
        manager.add_alias("alias-6", "alias-1", "6")
        manager.add_alias("alias-7", "alias-6", "7")

        # This should fail due to exceeding max depth
        with pytest.raises(CircularReferenceError):
            manager.resolve("alias-7", [])

    def test_alias_chaining(self, tmp_path):
        """Test alias chaining (alias pointing to another alias)."""
        settings_file = tmp_path / "framekit.yaml"
        store = SettingsStore(settings_file)
        manager = AliasManager(store)

        manager.add_alias("alias-a", "alias-b", "A")
        manager.add_alias("alias-b", "renamer", "B")

        result = manager.resolve("alias-a", ["input.mkv"])
        assert result.command == "renamer"
        assert result.args == ["input.mkv"]

    def test_parameter_substitution_with_missing_params(self, tmp_path):
        """Test parameter substitution with missing parameters."""
        settings_file = tmp_path / "framekit.yaml"
        store = SettingsStore(settings_file)
        manager = AliasManager(store)

        manager.add_alias("needs-params", "cmd {0} {1}", "Needs params")

        # Should raise error when not enough parameters provided
        with pytest.raises(AliasError, match="parameter"):
            manager.resolve("needs-params", ["only-one"])

    def test_validate_alias_name(self, tmp_path):
        """Test alias name validation."""
        settings_file = tmp_path / "framekit.yaml"
        store = SettingsStore(settings_file)
        manager = AliasManager(store)

        # Valid names
        assert manager._is_valid_alias_name("valid-name")
        assert manager._is_valid_alias_name("valid_name")
        assert manager._is_valid_alias_name("valid123")

        # Invalid names
        assert not manager._is_valid_alias_name("invalid name")
        assert not manager._is_valid_alias_name("invalid@name")
        assert not manager._is_valid_alias_name("invalid.name")
        assert not manager._is_valid_alias_name("")

    def test_conflict_detection_with_builtin_commands(self, tmp_path):
        """Test conflict detection with built-in commands."""
        settings_file = tmp_path / "framekit.yaml"
        store = SettingsStore(settings_file)
        manager = AliasManager(store)

        # These should conflict with built-in commands
        builtin_commands = ["pipeline", "renamer", "cleanmkv", "nfo", "metadata", "torrent"]

        for cmd in builtin_commands:
            with pytest.raises(AliasError, match="conflicts with built-in command"):
                manager.add_alias(cmd, "custom_command", "")

    def test_settings_persistence(self, tmp_path):
        """Test that aliases are persisted to settings."""
        settings_file = tmp_path / "framekit.yaml"
        store = SettingsStore(settings_file)
        manager = AliasManager(store)

        manager.add_alias("persistent-alias", "cmd", "Persistent")

        # Create new manager instance
        new_store = SettingsStore(settings_file)
        new_manager = AliasManager(new_store)

        alias = new_manager.get_alias("persistent-alias")
        assert alias is not None
        assert alias.name == "persistent-alias"
        assert alias.command == "cmd"


class TestAliasResolutionResult:
    """Test alias resolution result."""

    def test_resolution_result_structure(self, tmp_path):
        """Test resolution result structure."""
        settings_file = tmp_path / "framekit.yaml"
        store = SettingsStore(settings_file)
        manager = AliasManager(store)

        result = manager.resolve("ren", ["input.mkv"])

        assert hasattr(result, "command")
        assert hasattr(result, "args")
        assert hasattr(result, "chain")
        assert result.command == "renamer"
        assert result.args == ["input.mkv"]
        assert "ren" in result.chain

    def test_resolution_chain_tracking(self, tmp_path):
        """Test that resolution tracks the alias chain."""
        settings_file = tmp_path / "framekit.yaml"
        store = SettingsStore(settings_file)
        manager = AliasManager(store)

        manager.add_alias("alias-a", "alias-b", "A")
        manager.add_alias("alias-b", "alias-c", "B")
        manager.add_alias("alias-c", "renamer", "C")

        result = manager.resolve("alias-a", [])

        assert "alias-a" in result.chain
        assert "alias-b" in result.chain
        assert "alias-c" in result.chain
        assert len(result.chain) == 3


# Made with Bob
