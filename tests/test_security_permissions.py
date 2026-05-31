"""
Comprehensive tests for file permissions security module.

Tests Windows ACL and Unix chmod permissions for sensitive files.
"""

import os
import platform
import subprocess

import pytest

from swirrl.core.security.permissions import (
    PermissionError,
    _grants_other_user_access,
    _iter_windows_acl_entries,
    get_permission_info,
    set_secure_permissions,
    verify_secure_permissions,
)


class TestSetSecurePermissions:
    """Test setting secure file permissions."""

    def test_set_permissions_on_new_file(self, tmp_path):
        """Test setting permissions on a newly created file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("sensitive data")

        set_secure_permissions(test_file, mode="owner_only", strict=True)

        assert test_file.exists()
        assert verify_secure_permissions(test_file)

    def test_set_permissions_nonexistent_file_raises(self, tmp_path):
        """Test that setting permissions on nonexistent file raises error."""
        test_file = tmp_path / "nonexistent.txt"

        with pytest.raises(PermissionError, match="does not exist"):
            set_secure_permissions(test_file, mode="owner_only", strict=True)

    def test_set_permissions_strict_false_logs_warning(self, tmp_path):
        """Test that strict=False logs warning instead of raising."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("data")

        # This should not raise even if permissions fail
        set_secure_permissions(test_file, mode="owner_only", strict=False)

        # File should still exist
        assert test_file.exists()

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
    def test_windows_acl_owner_only(self, tmp_path):
        """Test Windows ACL restricts access to owner only."""
        test_file = tmp_path / "secret.txt"
        test_file.write_text("secret data")

        set_secure_permissions(test_file, mode="owner_only", strict=True)

        # Verify using icacls
        result = subprocess.run(
            ["icacls", str(test_file)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        # Should only show current user with full control
        import getpass

        username = getpass.getuser()
        assert username in result.stdout

    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix-specific test")
    def test_unix_permissions_owner_only(self, tmp_path):
        """Test Unix permissions are set to 0o600 (owner read/write only)."""
        test_file = tmp_path / "secret.txt"
        test_file.write_text("secret data")

        set_secure_permissions(test_file, mode="owner_only", strict=True)

        # Check file mode
        stat_info = test_file.stat()
        mode = stat_info.st_mode & 0o777

        assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"

    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix-specific test")
    def test_unix_permissions_owner_group(self, tmp_path):
        """Test Unix permissions for owner_group mode."""
        test_file = tmp_path / "shared.txt"
        test_file.write_text("shared data")

        set_secure_permissions(test_file, mode="owner_group", strict=True)

        stat_info = test_file.stat()
        mode = stat_info.st_mode & 0o777

        assert mode == 0o660, f"Expected 0o660, got {oct(mode)}"

    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix-specific test")
    def test_unix_permissions_world_readable(self, tmp_path):
        """Test Unix permissions for world_readable mode."""
        test_file = tmp_path / "public.txt"
        test_file.write_text("public data")

        set_secure_permissions(test_file, mode="world_readable", strict=True)

        stat_info = test_file.stat()
        mode = stat_info.st_mode & 0o777

        assert mode == 0o644, f"Expected 0o644, got {oct(mode)}"


class TestVerifySecurePermissions:
    """Test verifying secure file permissions."""

    def test_verify_secure_file(self, tmp_path):
        """Test verifying a properly secured file."""
        test_file = tmp_path / "secure.txt"
        test_file.write_text("secure data")

        set_secure_permissions(test_file, mode="owner_only", strict=True)

        assert verify_secure_permissions(test_file) is True

    def test_verify_nonexistent_file(self, tmp_path):
        """Test verifying nonexistent file returns False."""
        test_file = tmp_path / "nonexistent.txt"

        assert verify_secure_permissions(test_file) is False

    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix-specific test")
    def test_verify_insecure_unix_permissions(self, tmp_path):
        """Test detecting insecure Unix permissions."""
        test_file = tmp_path / "insecure.txt"
        test_file.write_text("data")

        # Set world-writable permissions (insecure)
        os.chmod(test_file, 0o666)

        assert verify_secure_permissions(test_file) is False

    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix-specific test")
    def test_verify_read_only_is_secure(self, tmp_path):
        """Test that read-only (0o400) is considered secure."""
        test_file = tmp_path / "readonly.txt"
        test_file.write_text("data")

        os.chmod(test_file, 0o400)

        assert verify_secure_permissions(test_file) is True

    def test_windows_acl_parser_allows_system_and_administrators(self):
        """Test that Windows structural principals are not flagged as user access."""
        assert not _grants_other_user_access("NT AUTHORITY\\SYSTEM:(F)", "runneradmin")
        assert not _grants_other_user_access("BUILTIN\\Administrators:(F)", "runneradmin")
        assert not _grants_other_user_access("OWNER RIGHTS:(F)", "runneradmin")
        assert not _grants_other_user_access("DESKTOP\\runneradmin:(F)", "runneradmin")
        assert not _grants_other_user_access(
            "C:\\Temp\\secret.txt runneradmin:(F)",
            "runneradmin",
        )
        assert not _grants_other_user_access(
            "C:\\Temp\\secret.txt NT AUTHORITY\\SYSTEM:(F)",
            "runneradmin",
        )

    def test_windows_acl_parser_rejects_broad_principals(self):
        """Test that broad Windows principals with access rights are flagged."""
        assert _grants_other_user_access("BUILTIN\\Users:(RX)", "runneradmin")
        assert _grants_other_user_access("Everyone:(R)", "runneradmin")
        assert _grants_other_user_access(
            "C:\\Temp\\secret.txt BUILTIN\\Users:(RX)",
            "runneradmin",
        )
        assert not _grants_other_user_access("Everyone:(DENY)(W)", "runneradmin")

    def test_windows_acl_parser_reads_first_icacls_entry(self, tmp_path):
        """Test that the first icacls entry on the path line is parsed."""
        test_file = tmp_path / "secure file.txt"
        output = (
            f"{test_file.resolve()} BUILTIN\\Users:(RX)\n"
            "                            NT AUTHORITY\\SYSTEM:(F)\n\n"
            "Successfully processed 1 files; Failed processing 0 files"
        )

        assert list(_iter_windows_acl_entries(output, test_file)) == [
            "BUILTIN\\Users:(RX)",
            "NT AUTHORITY\\SYSTEM:(F)",
        ]


class TestGetPermissionInfo:
    """Test getting permission information."""

    def test_get_info_for_file(self, tmp_path):
        """Test getting permission info for a file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("data")

        info = get_permission_info(test_file)

        assert "platform" in info
        assert "path" in info
        assert info["platform"] == platform.system()
        assert str(test_file) in info["path"]

    def test_get_info_nonexistent_file(self, tmp_path):
        """Test getting info for nonexistent file."""
        test_file = tmp_path / "nonexistent.txt"

        info = get_permission_info(test_file)

        assert "error" in info
        assert "does not exist" in info["error"]

    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix-specific test")
    def test_get_info_unix_includes_mode(self, tmp_path):
        """Test Unix permission info includes mode."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("data")
        os.chmod(test_file, 0o600)

        info = get_permission_info(test_file)

        assert "mode_octal" in info
        assert "mode_symbolic" in info
        assert "0o600" in info["mode_octal"]
        assert info["mode_symbolic"] == "rw-------"

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
    def test_get_info_windows_includes_acl(self, tmp_path):
        """Test Windows permission info includes ACL."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("data")

        info = get_permission_info(test_file)

        # Should have ACL info or error
        assert "acl" in info or "error" in info


class TestPermissionEdgeCases:
    """Test edge cases and error handling."""

    def test_set_permissions_on_directory(self, tmp_path):
        """Test setting permissions on a directory."""
        test_dir = tmp_path / "secure_dir"
        test_dir.mkdir()

        set_secure_permissions(test_dir, mode="owner_only", strict=True)

        assert test_dir.exists()
        assert test_dir.is_dir()

    def test_multiple_permission_changes(self, tmp_path):
        """Test changing permissions multiple times."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("data")

        # Set to owner_only
        set_secure_permissions(test_file, mode="owner_only", strict=True)
        assert verify_secure_permissions(test_file)

        # Change to owner_group (if Unix)
        if platform.system() != "Windows":
            set_secure_permissions(test_file, mode="owner_group", strict=True)
            stat_info = test_file.stat()
            mode = stat_info.st_mode & 0o777
            assert mode == 0o660

    def test_permission_on_symlink(self, tmp_path):
        """Test setting permissions on a symlink."""
        if platform.system() == "Windows":
            pytest.skip("Symlink test not reliable on Windows")

        test_file = tmp_path / "original.txt"
        test_file.write_text("data")

        symlink = tmp_path / "link.txt"
        symlink.symlink_to(test_file)

        # Should work on symlink
        set_secure_permissions(symlink, mode="owner_only", strict=True)

        # Verify the target file has secure permissions
        assert verify_secure_permissions(test_file)


class TestCrossPlatformCompatibility:
    """Test cross-platform compatibility."""

    def test_permissions_work_on_current_platform(self, tmp_path):
        """Test that permissions work on the current platform."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("sensitive data")

        # Should not raise
        set_secure_permissions(test_file, mode="owner_only", strict=True)

        # Should verify as secure
        assert verify_secure_permissions(test_file)

    def test_permission_info_includes_platform(self, tmp_path):
        """Test that permission info includes platform information."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("data")

        info = get_permission_info(test_file)

        assert info["platform"] in ["Windows", "Linux", "Darwin"]
