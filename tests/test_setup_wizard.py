"""Tests for setup wizard interactive flows.

This module tests the interactive wizard functionality in the setup command,
including user input handling, navigation, and state management.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from framekit.commands.setup import (
    SetupCancelled,
    _choose_interface_language,
    _choose_metadata_language,
    _choose_workspace_path,
    _prompt_custom_language,
    _prompt_custom_path,
    _prompt_tmdb_token,
    _run_storage_step,
    run_guided_setup,
)


class TestSetupWizardNavigation:
    """Test wizard navigation and cancellation."""

    def test_setup_cancelled_exception(self):
        """Test that SetupCancelled exception can be raised and caught."""
        with pytest.raises(SetupCancelled):
            raise SetupCancelled()

    @patch("framekit.commands.setup.choose_yes_no")
    @patch("framekit.commands.setup.print_module_banner")
    def test_wizard_cancellation_at_start(
        self, mock_banner: Mock, mock_choose: Mock, temp_settings_store
    ):
        """Test cancelling wizard at the first prompt."""
        mock_choose.return_value = None  # User cancels

        result = run_guided_setup(mark_completed=False)

        assert result == 0  # Should exit gracefully
        mock_banner.assert_called_once_with("Setup")

    @patch("framekit.commands.setup.choose_yes_no")
    @patch("framekit.commands.setup.print_module_banner")
    def test_wizard_skip_all_steps(self, mock_banner: Mock, mock_choose: Mock, temp_settings_store):
        """Skip every optional step and save at the end.

        The wizard fires one yes/no per major step (Storage, Language,
        Security, Folders, Metadata, NFO Template, Prez, Torrent, Logo),
        then the final ``save_choice``.
        """
        mock_choose.side_effect = [False] * 9 + [True]

        result = run_guided_setup(mark_completed=True)

        assert result == 0
        # The skip-all path uses a minimum of ten yes/no prompts; the exact
        # count depends on the logo sub-flow. Pin only the lower bound.
        assert mock_choose.call_count >= 10


class TestInterfaceLanguageSelection:
    """Test interface language selection."""

    @patch("framekit.commands.setup.choose_option")
    @patch("framekit.commands.setup.set_locale")
    def test_choose_interface_language_english(self, mock_set_locale: Mock, mock_choose: Mock):
        """Test selecting English as interface language."""
        mock_choose.return_value = "en"

        result = _choose_interface_language("fr")

        assert result == "en"
        mock_set_locale.assert_called_once_with("en")

    @patch("framekit.commands.setup.choose_option")
    @patch("framekit.commands.setup.set_locale")
    def test_choose_interface_language_french(self, mock_set_locale: Mock, mock_choose: Mock):
        """Test selecting French as interface language."""
        mock_choose.return_value = "fr"

        result = _choose_interface_language("en")

        assert result == "fr"
        mock_set_locale.assert_called_once_with("fr")

    @patch("framekit.commands.setup.choose_option")
    def test_choose_interface_language_cancelled(self, mock_choose: Mock):
        """Test cancelling interface language selection."""
        mock_choose.return_value = None

        with pytest.raises(SetupCancelled):
            _choose_interface_language("en")


class TestMetadataLanguageSelection:
    """Test metadata language selection."""

    @patch("framekit.commands.setup.choose_option")
    def test_choose_metadata_language_standard(self, mock_choose: Mock):
        """Test selecting a standard metadata language."""
        mock_choose.return_value = "en-US"

        result = _choose_metadata_language("fr-FR")

        assert result == "en-US"

    @patch("framekit.commands.setup.choose_option")
    def test_choose_metadata_language_cancelled(self, mock_choose: Mock):
        """Test cancelling metadata language selection."""
        mock_choose.return_value = None

        with pytest.raises(SetupCancelled):
            _choose_metadata_language("en-US")

    @patch("framekit.commands.setup.console")
    @patch("framekit.commands.setup.choose_option")
    def test_choose_metadata_language_custom(self, mock_choose: Mock, mock_console: Mock):
        """Test selecting custom metadata language."""
        mock_choose.side_effect = ["custom", "de-DE"]
        mock_console.input.return_value = "de-DE"

        result = _choose_metadata_language("en-US")

        assert result == "de-DE"

    @patch("framekit.commands.setup.console")
    def test_prompt_custom_language_valid(self, mock_console: Mock):
        """Test prompting for valid custom language."""
        mock_console.input.return_value = "ja-JP"

        result = _prompt_custom_language("en-US")

        assert result == "ja-JP"

    @patch("framekit.commands.setup.console")
    def test_prompt_custom_language_quit(self, mock_console: Mock):
        """Test quitting custom language prompt."""
        mock_console.input.return_value = "quit"

        with pytest.raises(SetupCancelled):
            _prompt_custom_language("en-US")

    @patch("framekit.commands.setup.console")
    def test_prompt_custom_language_back(self, mock_console: Mock):
        """Test going back from custom language prompt."""
        mock_console.input.return_value = "back"

        result = _prompt_custom_language("en-US")

        assert result is None

    @patch("framekit.commands.setup.console")
    @patch("framekit.commands.setup.print_error")
    def test_prompt_custom_language_invalid_format(self, mock_error: Mock, mock_console: Mock):
        """Test invalid locale format handling."""
        mock_console.input.side_effect = ["invalid!", "en-US"]

        result = _prompt_custom_language("")

        assert result == "en-US"
        mock_error.assert_called_once()


class TestWorkspacePathSelection:
    """Test workspace path selection."""

    @patch("framekit.commands.setup.choose_option")
    def test_choose_workspace_path_appdata(self, mock_choose: Mock, tmp_path: Path):
        """Test selecting AppData workspace path."""
        mock_choose.return_value = "appdata"
        appdata_path = tmp_path / "appdata"
        project_path = tmp_path / "project"

        result = _choose_workspace_path("Test", "", appdata_path, project_path)

        assert result == str(appdata_path)

    @patch("framekit.commands.setup.choose_option")
    def test_choose_workspace_path_project(self, mock_choose: Mock, tmp_path: Path):
        """Test selecting project workspace path."""
        mock_choose.return_value = "project"
        appdata_path = tmp_path / "appdata"
        project_path = tmp_path / "project"

        result = _choose_workspace_path("Test", "", appdata_path, project_path)

        assert result == str(project_path)

    @patch("framekit.commands.setup.console")
    @patch("framekit.commands.setup.choose_option")
    def test_choose_workspace_path_custom(
        self, mock_choose: Mock, mock_console: Mock, tmp_path: Path
    ):
        """Test selecting custom workspace path."""
        custom_path = str(tmp_path / "custom")
        mock_choose.return_value = "custom"
        mock_console.input.return_value = custom_path
        appdata_path = tmp_path / "appdata"
        project_path = tmp_path / "project"

        result = _choose_workspace_path("Test", "", appdata_path, project_path)

        assert result == custom_path

    @patch("framekit.commands.setup.console")
    def test_prompt_custom_path_valid(self, mock_console: Mock):
        """Test prompting for valid custom path."""
        mock_console.input.return_value = r"E:\Releases\NFO"

        result = _prompt_custom_path("NFO", "")

        assert result == r"E:\Releases\NFO"

    @patch("framekit.commands.setup.console")
    def test_prompt_custom_path_with_quotes(self, mock_console: Mock):
        """Test custom path with quotes stripped."""
        mock_console.input.return_value = r'"E:\My Folder\NFO"'

        result = _prompt_custom_path("NFO", "")

        assert result == r"E:\My Folder\NFO"

    @patch("framekit.commands.setup.console")
    def test_prompt_custom_path_quit(self, mock_console: Mock):
        """Test quitting custom path prompt."""
        mock_console.input.return_value = "quit"

        with pytest.raises(SetupCancelled):
            _prompt_custom_path("NFO", "")

    @patch("framekit.commands.setup.console")
    def test_prompt_custom_path_back(self, mock_console: Mock):
        """Test going back from custom path prompt."""
        mock_console.input.return_value = "back"

        result = _prompt_custom_path("NFO", "")

        assert result is None


class TestSettingsStorageSelection:
    """Test settings storage path selection."""

    @patch("framekit.commands.setup.console")
    @patch("framekit.commands.setup.choose_option")
    @patch("framekit.commands.setup.choose_yes_no")
    def test_run_storage_step_custom_folder(
        self,
        mock_yes_no: Mock,
        mock_choose: Mock,
        mock_console: Mock,
        tmp_path: Path,
        monkeypatch,
    ):
        """Custom storage folder persists a global settings path."""
        from framekit.core import paths

        workspace = tmp_path / "workspace"
        config_dir = tmp_path / "config"
        cache_dir = tmp_path / "cache"
        custom_dir = tmp_path / "portable-config"
        workspace.mkdir()
        monkeypatch.chdir(workspace)
        monkeypatch.delenv("FRAMEKIT_CONFIG", raising=False)
        monkeypatch.setattr(paths, "user_config_dir", lambda app, author: str(config_dir))
        monkeypatch.setattr(paths, "user_cache_dir", lambda app, author: str(cache_dir))
        mock_yes_no.return_value = True
        mock_choose.return_value = "custom"
        mock_console.input.return_value = str(custom_dir)

        store = _run_storage_step()

        expected = custom_dir / "framekit.yaml"
        assert store.path == expected
        assert (config_dir / "settings-path.txt").read_text(encoding="utf-8") == str(
            expected.resolve()
        )


class TestTMDbTokenPrompt:
    """Test TMDb token prompting."""

    @patch("framekit.commands.setup.console")
    @patch("framekit.commands.setup.normalize_secret_input")
    @patch("framekit.commands.setup.looks_like_tmdb_read_access_token")
    def test_prompt_tmdb_token_valid(
        self, mock_looks_like: Mock, mock_normalize: Mock, mock_console: Mock
    ):
        """Test prompting for valid TMDb token."""
        token = "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJ0ZXN0IiwianRpIjoidGVzdCJ9.test"
        mock_console.input.return_value = token
        mock_normalize.return_value = token
        mock_looks_like.return_value = True

        result = _prompt_tmdb_token("")

        assert result == token

    @patch("framekit.commands.setup.console")
    def test_prompt_tmdb_token_quit(self, mock_console: Mock):
        """Test quitting TMDb token prompt."""
        mock_console.input.return_value = "quit"

        with pytest.raises(SetupCancelled):
            _prompt_tmdb_token("")

    @patch("framekit.commands.setup.console")
    def test_prompt_tmdb_token_back(self, mock_console: Mock):
        """Test going back from TMDb token prompt."""
        mock_console.input.return_value = "back"

        result = _prompt_tmdb_token("")

        assert result is None

    @patch("framekit.commands.setup.console")
    def test_prompt_tmdb_token_skip_with_existing(self, mock_console: Mock):
        """Test skipping token prompt when token exists."""
        existing_token = "existing_token"
        mock_console.input.return_value = "skip"

        result = _prompt_tmdb_token(existing_token)

        assert result == existing_token

    @patch("framekit.commands.setup.console")
    def test_prompt_tmdb_token_skip_without_existing(self, mock_console: Mock):
        """Test skipping token prompt without existing token."""
        mock_console.input.return_value = "skip"

        result = _prompt_tmdb_token("")

        assert result == ""

    @patch("framekit.commands.setup.console")
    def test_prompt_tmdb_token_clear(self, mock_console: Mock):
        """Test clearing existing token."""
        mock_console.input.return_value = "clear"

        result = _prompt_tmdb_token("existing_token")

        assert result == ""

    @patch("framekit.commands.setup.console")
    @patch("framekit.commands.setup.normalize_secret_input")
    @patch("framekit.commands.setup.looks_like_tmdb_read_access_token")
    @patch("framekit.commands.setup.print_error")
    def test_prompt_tmdb_token_non_token_rejected(
        self,
        mock_error: Mock,
        mock_looks_token: Mock,
        mock_normalize: Mock,
        mock_console: Mock,
    ):
        """Anything that does not look like a v4 read-access token is rejected."""
        api_key = "1234567890abcdef1234567890abcdef"

        mock_console.input.side_effect = [api_key, "skip"]
        mock_normalize.return_value = api_key
        mock_looks_token.return_value = False

        result = _prompt_tmdb_token("")

        assert result == ""
        mock_error.assert_called_once()


class TestWizardIntegration:
    """Test full wizard integration scenarios."""

    @patch("framekit.commands.setup.choose_yes_no")
    @patch("framekit.commands.setup.print_module_banner")
    @patch("framekit.commands.setup._ensure_default_folders_exist")
    def test_wizard_minimal_configuration(
        self, mock_ensure: Mock, mock_banner: Mock, mock_choose: Mock, temp_settings_store
    ):
        """Test wizard with minimal configuration."""
        # See ``test_wizard_skip_all_steps`` for the prompt sequence rationale.
        mock_choose.side_effect = [False] * 9 + [True]

        result = run_guided_setup(mark_completed=True)

        assert result == 0
        mock_ensure.assert_called_once()

    @patch("framekit.commands.setup.choose_yes_no")
    @patch("framekit.commands.setup.print_module_banner")
    def test_wizard_decline_save(self, mock_banner: Mock, mock_choose: Mock, temp_settings_store):
        """Test declining to save configuration."""
        mock_choose.side_effect = [False] * 10

        result = run_guided_setup(mark_completed=False)

        assert result == 0


@pytest.mark.unit
class TestWizardHelpers:
    """Test wizard helper functions."""

    def test_setup_cancelled_is_exception(self):
        """Test that SetupCancelled is an Exception."""
        assert issubclass(SetupCancelled, Exception)

    def test_setup_cancelled_can_be_caught(self):
        """Test that SetupCancelled can be caught."""
        try:
            raise SetupCancelled()
        except SetupCancelled:
            pass  # Successfully caught
        except Exception:
            pytest.fail("SetupCancelled should be catchable as SetupCancelled")
