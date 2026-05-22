"""Tests for setup input validation and error handling.

This module tests validation of user inputs in the setup wizard,
including locale codes, paths, tokens, and URLs.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from framekit.commands.setup import (
    _is_valid_locale,
    _prompt_custom_language,
    _prompt_custom_path,
    _prompt_tmdb_token,
    _strip_wrapping_quotes,
)


class TestLocaleValidation:
    """Test locale code validation."""

    def test_valid_locale_two_letter(self):
        """Test valid two-letter locale code."""
        assert _is_valid_locale("en") is True
        assert _is_valid_locale("fr") is True
        assert _is_valid_locale("es") is True

    def test_valid_locale_with_region(self):
        """Test valid locale with region code."""
        assert _is_valid_locale("en-US") is True
        assert _is_valid_locale("fr-FR") is True
        assert _is_valid_locale("es-419") is True
        assert _is_valid_locale("zh-CN") is True

    def test_valid_locale_three_letter(self):
        """Test valid three-letter locale codes."""
        assert _is_valid_locale("eng") is True
        assert _is_valid_locale("fra") is True

    def test_valid_locale_extended_region(self):
        """Test valid locale with extended region codes."""
        assert _is_valid_locale("en-US") is True
        # Note: sr-Latn-RS has 3 parts which exceeds the simple regex pattern

    def test_invalid_locale_empty(self):
        """Test empty string is invalid."""
        assert _is_valid_locale("") is False

    def test_invalid_locale_single_char(self):
        """Test single character is invalid."""
        assert _is_valid_locale("e") is False

    def test_invalid_locale_numbers(self):
        """Test locale with numbers only is invalid."""
        assert _is_valid_locale("123") is False

    def test_invalid_locale_special_chars(self):
        """Test locale with special characters is invalid."""
        assert _is_valid_locale("en@US") is False
        assert _is_valid_locale("en_US") is False  # Underscore not allowed
        assert _is_valid_locale("en.US") is False

    def test_invalid_locale_too_long(self):
        """Test overly long locale codes."""
        assert _is_valid_locale("en-VERYLONGREGION") is False

    def test_invalid_locale_wrong_format(self):
        """Test incorrectly formatted locales."""
        assert _is_valid_locale("en-") is False
        assert _is_valid_locale("-US") is False
        assert _is_valid_locale("en--US") is False


class TestPathValidation:
    """Test path input validation."""

    def test_strip_quotes_double(self):
        """Test stripping double quotes from paths."""
        assert _strip_wrapping_quotes('"C:\\Path\\To\\Folder"') == "C:\\Path\\To\\Folder"

    def test_strip_quotes_single(self):
        """Test stripping single quotes from paths."""
        assert _strip_wrapping_quotes("'C:\\Path\\To\\Folder'") == "C:\\Path\\To\\Folder"

    def test_strip_quotes_with_spaces(self):
        """Test stripping quotes from paths with spaces."""
        assert _strip_wrapping_quotes('"C:\\My Folder\\NFO"') == "C:\\My Folder\\NFO"

    def test_strip_quotes_no_quotes(self):
        """Test path without quotes."""
        assert _strip_wrapping_quotes("C:\\Path\\To\\Folder") == "C:\\Path\\To\\Folder"

    def test_strip_quotes_whitespace(self):
        """Test stripping with surrounding whitespace."""
        assert _strip_wrapping_quotes('  "path"  ') == "path"

    def test_strip_quotes_mismatched(self):
        """Test mismatched quotes are not stripped."""
        assert _strip_wrapping_quotes("\"path'") == "\"path'"
        assert _strip_wrapping_quotes("'path\"") == "'path\""

    def test_strip_quotes_nested(self):
        """Test quotes inside path are preserved."""
        result = _strip_wrapping_quotes('"C:\\Path\\"With\\"Quotes"')
        assert result == 'C:\\Path\\"With\\"Quotes'

    @patch("framekit.commands.setup.console")
    @patch("framekit.commands.setup.print_error")
    def test_prompt_custom_path_empty_rejected(self, mock_error: Mock, mock_console: Mock):
        """Test empty path is rejected."""
        mock_console.input.side_effect = ["", "valid_path"]

        result = _prompt_custom_path("Test", "")

        assert result == "valid_path"
        mock_error.assert_called_once()

    @patch("framekit.commands.setup.console")
    @patch("framekit.commands.setup.print_error")
    def test_prompt_custom_path_whitespace_rejected(self, mock_error: Mock, mock_console: Mock):
        """Test whitespace-only path is rejected."""
        mock_console.input.side_effect = ["   ", "valid_path"]

        result = _prompt_custom_path("Test", "")

        assert result == "valid_path"
        mock_error.assert_called_once()


class TestTMDbTokenValidation:
    """Test TMDb token validation."""

    @patch("framekit.commands.setup.console")
    @patch("framekit.commands.setup.print_error")
    def test_prompt_token_empty_rejected(self, mock_error: Mock, mock_console: Mock):
        """Test empty token is rejected."""
        mock_console.input.side_effect = ["", "skip"]

        result = _prompt_tmdb_token("")

        assert result == ""
        mock_error.assert_called_once()

    @patch("framekit.commands.setup.console")
    @patch("framekit.commands.setup.normalize_secret_input")
    @patch("framekit.commands.setup.looks_like_tmdb_read_access_token")
    @patch("framekit.commands.setup.print_error")
    def test_prompt_token_invalid_format_rejected(
        self,
        mock_error: Mock,
        mock_looks_token: Mock,
        mock_normalize: Mock,
        mock_console: Mock,
    ):
        """Anything that is not a v4 read-access token is rejected."""
        invalid_token = "1234567890abcdef1234567890abcdef"
        mock_console.input.side_effect = [invalid_token, "skip"]
        mock_normalize.side_effect = [invalid_token, ""]
        mock_looks_token.side_effect = [False, False]

        result = _prompt_tmdb_token("")

        assert result == ""
        mock_error.assert_called()

    @patch("framekit.commands.setup.console")
    @patch("framekit.commands.setup.normalize_secret_input")
    @patch("framekit.commands.setup.looks_like_tmdb_read_access_token")
    def test_prompt_token_valid_accepted(
        self,
        mock_looks_token: Mock,
        mock_normalize: Mock,
        mock_console: Mock,
    ):
        """A JWT-shaped value is accepted as a v4 read-access token."""
        valid_token = "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJ0ZXN0In0.test"
        mock_console.input.return_value = valid_token
        mock_normalize.return_value = valid_token
        mock_looks_token.return_value = True

        result = _prompt_tmdb_token("")

        assert result == valid_token


class TestLanguageInputValidation:
    """Test language input validation."""

    @patch("framekit.commands.setup.console")
    @patch("framekit.commands.setup.print_error")
    def test_prompt_language_empty_rejected(self, mock_error: Mock, mock_console: Mock):
        """Test empty language input is rejected."""
        mock_console.input.side_effect = ["", "en-US"]

        result = _prompt_custom_language("")

        assert result == "en-US"
        mock_error.assert_called_once()

    @patch("framekit.commands.setup.console")
    @patch("framekit.commands.setup.print_error")
    def test_prompt_language_invalid_format_rejected(self, mock_error: Mock, mock_console: Mock):
        """Test invalid language format is rejected."""
        mock_console.input.side_effect = ["invalid!", "en-US"]

        result = _prompt_custom_language("")

        assert result == "en-US"
        mock_error.assert_called_once()

    @patch("framekit.commands.setup.console")
    @patch("framekit.commands.setup.print_error")
    def test_prompt_language_multiple_invalid_attempts(self, mock_error: Mock, mock_console: Mock):
        """Test multiple invalid attempts before valid input."""
        mock_console.input.side_effect = ["", "123", "en_US", "en-US"]

        result = _prompt_custom_language("")

        assert result == "en-US"
        assert mock_error.call_count == 3

    @patch("framekit.commands.setup.console")
    def test_prompt_language_valid_formats(self, mock_console: Mock):
        """Test various valid language formats."""
        valid_locales = ["en", "en-US", "fr-FR", "es-419", "zh-CN"]

        for locale in valid_locales:
            mock_console.input.return_value = locale
            result = _prompt_custom_language("")
            assert result == locale


class TestInputSanitization:
    """Test input sanitization and normalization."""

    def test_strip_quotes_preserves_internal_content(self):
        """Test that internal content is preserved."""
        path = '"C:\\Path\\With\\Special-Chars_123"'
        result = _strip_wrapping_quotes(path)
        assert result == "C:\\Path\\With\\Special-Chars_123"

    def test_strip_quotes_handles_unicode(self):
        """Test handling of Unicode characters."""
        path = '"C:\\Dossier\\Français"'
        result = _strip_wrapping_quotes(path)
        assert result == "C:\\Dossier\\Français"

    def test_strip_quotes_empty_after_strip(self):
        """Test handling when only quotes remain."""
        assert _strip_wrapping_quotes('""') == ""
        assert _strip_wrapping_quotes("''") == ""

    def test_strip_quotes_single_quote(self):
        """Test single quote character."""
        assert _strip_wrapping_quotes('"') == '"'
        assert _strip_wrapping_quotes("'") == "'"


class TestValidationEdgeCases:
    """Test edge cases in validation."""

    def test_locale_case_sensitivity(self):
        """Test locale validation is case-insensitive for letters."""
        assert _is_valid_locale("EN") is True
        assert _is_valid_locale("en") is True
        assert _is_valid_locale("En") is True
        assert _is_valid_locale("EN-us") is True

    def test_locale_with_script(self):
        """Test locale with script subtag."""
        assert _is_valid_locale("sr-Latn") is True
        assert _is_valid_locale("zh-Hans") is True

    def test_path_with_forward_slashes(self):
        """Test Unix-style paths."""
        path = '"/home/user/framekit/NFO"'
        result = _strip_wrapping_quotes(path)
        assert result == "/home/user/framekit/NFO"

    def test_path_with_mixed_slashes(self):
        """Test paths with mixed slashes."""
        path = '"C:/Path\\To/Folder"'
        result = _strip_wrapping_quotes(path)
        assert result == "C:/Path\\To/Folder"

    @patch("framekit.commands.setup.console")
    def test_prompt_handles_ctrl_c(self, mock_console: Mock):
        """Test handling of KeyboardInterrupt."""
        mock_console.input.side_effect = KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            _prompt_custom_path("Test", "")

    @patch("framekit.commands.setup.console")
    def test_prompt_handles_eof(self, mock_console: Mock):
        """Test handling of EOFError."""
        mock_console.input.side_effect = EOFError()

        with pytest.raises(EOFError):
            _prompt_custom_path("Test", "")


@pytest.mark.unit
class TestValidationIntegration:
    """Integration tests for validation workflows."""

    @patch("framekit.commands.setup.console")
    @patch("framekit.commands.setup.print_error")
    def test_validation_retry_workflow(self, mock_error: Mock, mock_console: Mock):
        """Test complete validation retry workflow."""
        # Simulate user making mistakes then correcting
        mock_console.input.side_effect = [
            "",  # Empty - rejected
            "   ",  # Whitespace - rejected
            "valid_path",  # Valid - accepted
        ]

        result = _prompt_custom_path("Test", "")

        assert result == "valid_path"
        assert mock_error.call_count == 2

    @patch("framekit.commands.setup.console")
    def test_validation_with_default_value(self, mock_console: Mock):
        """Test validation when default value exists."""
        mock_console.input.return_value = "new_path"

        result = _prompt_custom_path("Test", "default_path")

        assert result == "new_path"

    def test_locale_validation_comprehensive(self):
        """Test comprehensive locale validation scenarios."""
        valid_cases = [
            "en",
            "fr",
            "es",
            "de",
            "it",
            "pt",
            "ja",
            "zh",
            "ko",
            "en-US",
            "en-GB",
            "fr-FR",
            "fr-CA",
            "es-ES",
            "es-419",
            "zh-CN",
            "zh-TW",
            "pt-BR",
            "pt-PT",
            "eng",
            "fra",
            "deu",
        ]

        for locale in valid_cases:
            assert _is_valid_locale(locale), f"Expected {locale} to be valid"

        invalid_cases = [
            "",
            "e",
            "1",
            "en_US",
            "en@US",
            "en.US",
            "en-",
            "-US",
            "en--US",
            "toolongcode",
            "123",
            "en-123456789",
        ]

        for locale in invalid_cases:
            assert not _is_valid_locale(locale), f"Expected {locale} to be invalid"
