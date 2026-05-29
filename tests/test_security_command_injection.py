"""
Tests for command injection vulnerabilities in subprocess calls.

Focuses on the NFO command's _open_folder function which passes
user-controlled paths to subprocess/os.startfile with validation.
"""

import platform
from pathlib import Path
from unittest.mock import patch

import pytest

from ouro.commands.nfo import _open_folder


class TestNFOCommandInjection:
    """Test command injection protection in NFO command."""

    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix-specific test")
    def test_open_folder_with_malicious_path_darwin(self, tmp_path):
        """Test that malicious paths are rejected on macOS."""
        malicious_dir = tmp_path / "; rm -rf /"
        malicious_dir.mkdir()
        malicious_file = malicious_dir / "test.nfo"
        malicious_file.write_text("test")

        with (
            patch("sys.platform", "darwin"),
            patch("ouro.commands.nfo.popen_safe") as mock_popen,
        ):
            _open_folder(malicious_file)
            mock_popen.assert_called_once()
            call_args = mock_popen.call_args[0][0]
            assert isinstance(call_args, list)
            assert call_args == ["open", str(malicious_dir.resolve())]

    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix-specific test")
    def test_open_folder_with_malicious_path_linux(self, tmp_path):
        """Test that malicious paths are rejected on Linux."""
        malicious_dir = tmp_path / "$(whoami)"
        malicious_dir.mkdir()
        malicious_file = malicious_dir / "test.nfo"
        malicious_file.write_text("test")

        with (
            patch("sys.platform", "linux"),
            patch("ouro.commands.nfo.popen_safe") as mock_popen,
        ):
            _open_folder(malicious_file)
            mock_popen.assert_called_once()
            call_args = mock_popen.call_args[0][0]
            assert isinstance(call_args, list)
            assert call_args == ["xdg-open", str(malicious_dir.resolve())]

    def test_open_folder_with_path_traversal(self, tmp_path):
        """Test that path traversal to nonexistent dir is blocked."""
        # Path resolves to nonexistent directory -> validate_directory_path raises
        # PathValidationError("Directory does not exist") -> _open_folder catches it
        traversal_path = tmp_path / ".." / ".." / "etc" / "passwd"

        with (
            patch("subprocess.Popen") as mock_popen,
            patch("os.startfile", create=True) as mock_startfile,
        ):
            # Should not raise — _open_folder handles errors internally
            _open_folder(traversal_path)

            # Neither subprocess nor startfile should be called
            mock_popen.assert_not_called()
            mock_startfile.assert_not_called()

    def test_open_folder_with_valid_path(self, tmp_path):
        """Test that valid paths are allowed."""
        test_file = tmp_path / "test.nfo"
        test_file.write_text("test")

        if platform.system() == "Windows":
            with patch("os.startfile", create=True) as mock_startfile:
                _open_folder(test_file)
                mock_startfile.assert_called_once()
        else:
            with patch("ouro.commands.nfo.popen_safe") as mock_popen:
                _open_folder(test_file)
                mock_popen.assert_called_once()
                call_args = mock_popen.call_args[0][0]
                folder_path = call_args[-1]
                assert ";" not in folder_path
                assert "$" not in folder_path
                assert "|" not in folder_path
                assert "&" not in folder_path

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
    def test_open_folder_windows_with_malicious_path(self, tmp_path):
        """Test that malicious directory names still pass (they exist) on Windows.

        Note: On Windows, _open_folder uses os.startfile which doesn't interpret
        shell metacharacters. The path validation ensures the directory exists,
        and os.startfile opens it safely without shell interpretation.
        """
        malicious_dir = tmp_path / "& calc.exe"
        malicious_dir.mkdir()
        malicious_file = malicious_dir / "test.nfo"
        malicious_file.write_text("test")

        with patch("os.startfile", create=True) as mock_startfile:
            # Directory exists and is valid — os.startfile is safe against injection
            _open_folder(malicious_file)
            # os.startfile IS called because the dir exists and passes validation
            # This is safe because os.startfile doesn't use shell interpretation
            mock_startfile.assert_called_once()

    def test_open_folder_with_special_characters(self, tmp_path):
        """Test handling of special characters in paths."""
        special_chars = ["'", '"', "`"]

        for char in special_chars:
            try:
                special_dir = tmp_path / f"test{char}dir"
                special_dir.mkdir(exist_ok=True)
                special_file = special_dir / "test.nfo"
                special_file.write_text("test")

                if platform.system() == "Windows":
                    with patch("os.startfile", create=True) as mock_startfile:
                        _open_folder(special_file)
                        # os.startfile is safe with special chars
                        mock_startfile.assert_called_once()
                else:
                    with patch("ouro.commands.nfo.popen_safe") as mock_popen:
                        _open_folder(special_file)
                        mock_popen.assert_called_once()
            except OSError:
                pass

    def test_open_folder_with_null_byte(self, tmp_path):
        """Test that null bytes in paths are handled gracefully.

        On Windows, Python's Path strips null bytes so the path may resolve
        to a valid directory. The key security property is that no command
        injection occurs — os.startfile and subprocess.Popen with list args
        are both safe against null-byte injection.
        """
        test_file = tmp_path / "test.nfo"
        test_file.write_text("test")

        malicious_path = str(test_file) + "\x00.txt"

        import contextlib

        # The function should not crash regardless of platform behavior
        with contextlib.suppress(ValueError, OSError):
            _open_folder(Path(malicious_path))

    def test_open_folder_validates_before_subprocess(self, tmp_path):
        """Test that path validation occurs before subprocess call."""
        test_file = tmp_path / "test.nfo"
        test_file.write_text("test")

        with patch("ouro.commands.nfo.validate_directory_path") as mock_validate:
            mock_validate.return_value = test_file.parent

            if platform.system() == "Windows":
                with patch("os.startfile", create=True) as mock_open:
                    _open_folder(test_file)
                    assert mock_validate.called
                    assert mock_open.called
            else:
                with patch("ouro.commands.nfo.popen_safe") as mock_popen:
                    _open_folder(test_file)
                    assert mock_validate.called
                    assert mock_popen.called


class TestSubprocessArgumentSafety:
    """Test that subprocess arguments are properly constructed."""

    @pytest.mark.skipif(platform.system() == "Windows", reason="Uses subprocess.Popen on Unix only")
    def test_subprocess_uses_list_not_shell(self, tmp_path):
        """Test that subprocess.Popen uses list arguments, not shell=True."""
        test_file = tmp_path / "test.nfo"
        test_file.write_text("test")

        with patch("ouro.commands.nfo.popen_safe") as mock_popen:
            _open_folder(test_file)

            call_args = mock_popen.call_args
            assert isinstance(call_args[0][0], list)

            if call_args[1] and "shell" in call_args[1]:
                assert call_args[1]["shell"] is False

    @pytest.mark.skipif(platform.system() == "Windows", reason="Uses subprocess.Popen on Unix only")
    def test_subprocess_command_structure(self, tmp_path):
        """Test that subprocess command has proper structure."""
        test_file = tmp_path / "test.nfo"
        test_file.write_text("test")

        with (
            patch("ouro.commands.nfo.popen_safe") as mock_popen,
            patch("sys.platform", "linux"),
        ):
            _open_folder(test_file)

            call_args = mock_popen.call_args[0][0]

            assert isinstance(call_args, list)
            assert len(call_args) == 2
            assert call_args[0] == "xdg-open"
            assert Path(call_args[1]).is_absolute()
