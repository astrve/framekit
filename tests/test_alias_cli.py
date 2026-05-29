"""Tests for alias CLI commands."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from ouro.commands.alias import alias_command
from ouro.commands.main import cli
from ouro.core.settings import SettingsStore


@pytest.fixture
def cli_runner():
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def settings_with_aliases(tmp_path):
    """Create settings with some test aliases."""
    settings_file = tmp_path / "ouro.yaml"
    store = SettingsStore(settings_file)
    settings = store.load()

    # Add a test user alias
    settings["aliases"]["user"]["test-alias"] = {
        "command": "renamer",
        "description": "Test alias",
        "enabled": True,
    }

    store.save(settings)
    return settings_file


class TestAliasListCommand:
    """Test 'ouro alias list' command."""

    def test_list_all_aliases(self, cli_runner, tmp_path, monkeypatch):
        """Test listing all aliases."""
        settings_file = tmp_path / "ouro.yaml"
        monkeypatch.setenv("OURO_CONFIG", str(settings_file))

        result = cli_runner.invoke(alias_command, ["list"])

        assert result.exit_code == 0
        # Should show builtin aliases
        assert "ren" in result.output or "cmk" in result.output

    def test_list_user_aliases_only(self, cli_runner, settings_with_aliases, monkeypatch):
        """Test listing only user aliases."""
        monkeypatch.setenv("OURO_CONFIG", str(settings_with_aliases))

        result = cli_runner.invoke(alias_command, ["list", "--user"])

        assert result.exit_code == 0
        assert "test-alias" in result.output

    def test_list_builtin_aliases_only(self, cli_runner, tmp_path, monkeypatch):
        """Test listing only builtin aliases."""
        settings_file = tmp_path / "ouro.yaml"
        monkeypatch.setenv("OURO_CONFIG", str(settings_file))

        result = cli_runner.invoke(alias_command, ["list", "--builtin"])

        assert result.exit_code == 0
        assert "ren" in result.output or "cmk" in result.output

    def test_list_aliases_json_format(self, cli_runner, tmp_path, monkeypatch):
        """Test listing aliases in JSON format."""
        settings_file = tmp_path / "ouro.yaml"
        monkeypatch.setenv("OURO_CONFIG", str(settings_file))

        result = cli_runner.invoke(alias_command, ["list", "--json"])

        assert result.exit_code == 0
        # Should be valid JSON
        data = json.loads(result.output)
        assert isinstance(data, dict)


class TestAliasShowCommand:
    """Test 'ouro alias show' command."""

    def test_show_existing_alias(self, cli_runner, settings_with_aliases, monkeypatch):
        """Test showing an existing alias."""
        monkeypatch.setenv("OURO_CONFIG", str(settings_with_aliases))

        result = cli_runner.invoke(alias_command, ["show", "test-alias"])

        assert result.exit_code == 0
        assert "test-alias" in result.output
        assert "renamer" in result.output

    def test_show_nonexistent_alias(self, cli_runner, tmp_path, monkeypatch):
        """Test showing a nonexistent alias."""
        settings_file = tmp_path / "ouro.yaml"
        monkeypatch.setenv("OURO_CONFIG", str(settings_file))

        result = cli_runner.invoke(alias_command, ["show", "nonexistent"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_show_builtin_alias(self, cli_runner, tmp_path, monkeypatch):
        """Test showing a builtin alias."""
        settings_file = tmp_path / "ouro.yaml"
        monkeypatch.setenv("OURO_CONFIG", str(settings_file))

        result = cli_runner.invoke(alias_command, ["show", "ren"])

        assert result.exit_code == 0
        assert "ren" in result.output
        assert "renamer" in result.output


class TestAliasAddCommand:
    """Test 'ouro alias add' command."""

    def test_add_simple_alias(self, cli_runner, tmp_path, monkeypatch):
        """Test adding a simple alias."""
        settings_file = tmp_path / "ouro.yaml"
        monkeypatch.setenv("OURO_CONFIG", str(settings_file))

        result = cli_runner.invoke(alias_command, ["add", "my-alias", "pipeline run"])

        assert result.exit_code == 0
        assert "added" in result.output.lower() or "created" in result.output.lower()

    def test_add_alias_with_description(self, cli_runner, tmp_path, monkeypatch):
        """Test adding an alias with description."""
        settings_file = tmp_path / "ouro.yaml"
        monkeypatch.setenv("OURO_CONFIG", str(settings_file))

        result = cli_runner.invoke(
            alias_command, ["add", "my-alias", "pipeline run", "--description", "My custom alias"]
        )

        assert result.exit_code == 0

    def test_add_alias_with_invalid_name(self, cli_runner, tmp_path, monkeypatch):
        """Test adding an alias with invalid name."""
        settings_file = tmp_path / "ouro.yaml"
        monkeypatch.setenv("OURO_CONFIG", str(settings_file))

        result = cli_runner.invoke(alias_command, ["add", "invalid name", "cmd"])

        assert result.exit_code != 0
        assert "invalid" in result.output.lower()

    def test_add_alias_conflicts_with_builtin(self, cli_runner, tmp_path, monkeypatch):
        """Test adding an alias that conflicts with builtin command."""
        settings_file = tmp_path / "ouro.yaml"
        monkeypatch.setenv("OURO_CONFIG", str(settings_file))

        result = cli_runner.invoke(alias_command, ["add", "pipeline", "custom_pipeline"])

        assert result.exit_code != 0
        assert "conflict" in result.output.lower()

    def test_user_alias_routes_from_top_level_cli(self, cli_runner, tmp_path, monkeypatch):
        """User aliases must dispatch from the root CLI, not only appear in alias list."""
        settings_file = tmp_path / "ouro.yaml"
        monkeypatch.setenv("OURO_CONFIG", str(settings_file))

        add_result = cli_runner.invoke(alias_command, ["add", "box", "seedbox"])
        assert add_result.exit_code == 0

        result = cli_runner.invoke(cli, ["box", "--help"])

        assert result.exit_code == 0
        assert "push" in result.output
        assert "pull" in result.output


class TestAliasRemoveCommand:
    """Test 'ouro alias remove' command."""

    def test_remove_user_alias(self, cli_runner, settings_with_aliases, monkeypatch):
        """Test removing a user alias."""
        monkeypatch.setenv("OURO_CONFIG", str(settings_with_aliases))

        result = cli_runner.invoke(alias_command, ["remove", "test-alias", "--force"])

        assert result.exit_code == 0
        assert "removed" in result.output.lower()

    def test_remove_builtin_alias_hides_from_list_and_dispatch(
        self, cli_runner, tmp_path, monkeypatch
    ):
        """Test removing a builtin alias hides it from list and root dispatch."""
        settings_file = tmp_path / "ouro.yaml"
        monkeypatch.setenv("OURO_CONFIG", str(settings_file))

        result = cli_runner.invoke(alias_command, ["remove", "ren", "--force"])

        assert result.exit_code == 0

        list_result = cli_runner.invoke(alias_command, ["list", "--json"])
        assert list_result.exit_code == 0
        assert "ren" not in json.loads(list_result.output)

        dispatch_result = cli_runner.invoke(cli, ["ren", "--help"])
        assert dispatch_result.exit_code != 0
        assert "no such command" in dispatch_result.output.lower()

    def test_pull_builtin_alias_routes_to_seedbox_pull(self, cli_runner, tmp_path, monkeypatch):
        """Test the built-in pull alias routes to seedbox pull."""
        settings_file = tmp_path / "ouro.yaml"
        monkeypatch.setenv("OURO_CONFIG", str(settings_file))

        result = cli_runner.invoke(cli, ["pull", "--help"])

        assert result.exit_code == 0
        assert "Download files from the seedbox" in result.output

    def test_remove_nonexistent_alias(self, cli_runner, tmp_path, monkeypatch):
        """Test removing a nonexistent alias."""
        settings_file = tmp_path / "ouro.yaml"
        monkeypatch.setenv("OURO_CONFIG", str(settings_file))

        result = cli_runner.invoke(alias_command, ["remove", "nonexistent", "--force"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_remove_with_confirmation(self, cli_runner, settings_with_aliases, monkeypatch):
        """Test removing with confirmation (uses --force to bypass interactive selector)."""
        monkeypatch.setenv("OURO_CONFIG", str(settings_with_aliases))

        result = cli_runner.invoke(
            alias_command,
            ["remove", "test-alias", "--force"],
        )

        assert result.exit_code == 0


class TestAliasEnableCommand:
    """Test 'ouro alias enable' command."""

    def test_enable_disabled_alias(self, cli_runner, tmp_path, monkeypatch):
        """Test enabling a disabled alias."""
        settings_file = tmp_path / "ouro.yaml"
        monkeypatch.setenv("OURO_CONFIG", str(settings_file))

        # First add and disable an alias
        cli_runner.invoke(alias_command, ["add", "test-alias", "cmd"])
        cli_runner.invoke(alias_command, ["disable", "test-alias"])

        # Now enable it
        result = cli_runner.invoke(alias_command, ["enable", "test-alias"])

        assert result.exit_code == 0
        assert "enabled" in result.output.lower()

    def test_enable_nonexistent_alias(self, cli_runner, tmp_path, monkeypatch):
        """Test enabling a nonexistent alias."""
        settings_file = tmp_path / "ouro.yaml"
        monkeypatch.setenv("OURO_CONFIG", str(settings_file))

        result = cli_runner.invoke(alias_command, ["enable", "nonexistent"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()


class TestAliasDisableCommand:
    """Test 'ouro alias disable' command."""

    def test_disable_alias(self, cli_runner, settings_with_aliases, monkeypatch):
        """Test disabling an alias."""
        monkeypatch.setenv("OURO_CONFIG", str(settings_with_aliases))

        result = cli_runner.invoke(alias_command, ["disable", "test-alias"])

        assert result.exit_code == 0
        assert "disabled" in result.output.lower()

    def test_disable_nonexistent_alias(self, cli_runner, tmp_path, monkeypatch):
        """Test disabling a nonexistent alias."""
        settings_file = tmp_path / "ouro.yaml"
        monkeypatch.setenv("OURO_CONFIG", str(settings_file))

        result = cli_runner.invoke(alias_command, ["disable", "nonexistent"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()


class TestAliasCommandHelp:
    """Test alias command help text."""

    def test_alias_command_help(self, cli_runner):
        """Test alias command help."""
        result = cli_runner.invoke(alias_command, ["--help"])

        assert result.exit_code == 0
        assert "alias" in result.output.lower()
        assert "list" in result.output.lower()
        assert "add" in result.output.lower()
        assert "remove" in result.output.lower()

    def test_alias_list_help(self, cli_runner):
        """Test alias list help."""
        result = cli_runner.invoke(alias_command, ["list", "--help"])

        assert result.exit_code == 0
        assert "list" in result.output.lower()

    def test_alias_add_help(self, cli_runner):
        """Test alias add help."""
        result = cli_runner.invoke(alias_command, ["add", "--help"])

        assert result.exit_code == 0
        assert "add" in result.output.lower()
