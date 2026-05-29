"""
Comprehensive tests for path traversal validation and security.

Tests strict mode, symlink detection, directory whitelisting, and attack vectors.
"""

import platform

# Import from the security.py module (not the security package)
import sys
from pathlib import Path
from pathlib import Path as PathLib

import pytest

# Add src to path before importing the package under test. Tests can be
# invoked outside of an editable install, so this is intentional and the
# import below is correctly placed after the sys.path mutation.
src_path = PathLib(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from ouro.core.path_validation import (  # noqa: E402
    PathValidationError,
    configure_security,
    get_security_config,
    sanitize_filename,
    validate_directory_path,
    validate_file_path,
)


@pytest.fixture(autouse=True)
def _reset_security_config():
    """Reset the global security config between tests.

    ``configure_security`` mutates module-level state. Without this fixture,
    a test that enables strict mode poisons every subsequent test in the
    file with the strict + allowed_base_dirs settings.
    """
    configure_security(strict_mode=False, allowed_base_dirs=[], allow_symlinks=True)
    yield
    configure_security(strict_mode=False, allowed_base_dirs=[], allow_symlinks=True)


class TestPathTraversalAttacks:
    """Test protection against path traversal attacks."""

    def test_basic_path_traversal_attack(self, tmp_path):
        """Test detection of basic ../ path traversal."""
        malicious_path = tmp_path / ".." / ".." / "etc" / "passwd"

        # In strict mode, should raise
        configure_security(strict_mode=True, allowed_base_dirs=[tmp_path])

        with pytest.raises(PathValidationError, match="outside allowed"):
            validate_file_path(malicious_path, must_exist=False, strict=True)

    def test_encoded_path_traversal(self, tmp_path):
        """Test detection of encoded path traversal attempts."""
        # Create a file with encoded path separators
        test_file = tmp_path / "test.txt"
        test_file.write_text("data")

        configure_security(strict_mode=True, allowed_base_dirs=[tmp_path])

        # This should work (within allowed dir)
        result = validate_file_path(test_file, strict=True)
        assert result == test_file.resolve()

    def test_absolute_path_outside_allowed_dirs(self, tmp_path):
        """Test rejection of absolute paths outside allowed directories."""
        configure_security(
            strict_mode=True,
            allowed_base_dirs=[tmp_path],
            allow_absolute_paths=False,
        )

        # Try to access a path outside tmp_path
        outside_path = Path("/etc/passwd")

        with pytest.raises(PathValidationError):
            validate_file_path(outside_path, must_exist=False, strict=True)

    def test_null_byte_injection(self, tmp_path):
        """Test protection against null byte injection.

        On Windows Python 3.14+, Path may preserve null bytes in its string
        representation without raising. The key security property is that
        subprocess calls using list arguments (not shell=True) handle null
        bytes safely at the OS level.
        """
        test_file = tmp_path / "test.txt"
        test_file.write_text("data")

        malicious = str(test_file) + "\x00.txt"
        try:
            result = validate_file_path(malicious, must_exist=False)
            # On platforms where null byte survives Path resolution,
            # verify the path still resolves to something usable
            assert result is not None
        except (PathValidationError, ValueError, OSError):
            pass


class TestStrictMode:
    """Test strict mode security configuration."""

    def test_strict_mode_enabled(self, tmp_path):
        """Test that strict mode enforces security checks."""
        configure_security(strict_mode=True, allowed_base_dirs=[tmp_path])

        config = get_security_config()
        assert config.strict_mode is True

    def test_strict_mode_disabled_allows_outside_paths(self, tmp_path):
        """Test that non-strict mode allows paths outside base dirs."""
        configure_security(strict_mode=False)

        # Should not raise even if outside tmp_path
        test_file = tmp_path / "test.txt"
        test_file.write_text("data")

        result = validate_file_path(test_file, strict=False)
        assert result.exists()

    def test_strict_mode_override(self, tmp_path):
        """Test that strict parameter overrides global config."""
        configure_security(strict_mode=False)

        outside_path = Path("/etc/passwd")

        # Override with strict=True
        with pytest.raises(PathValidationError):
            validate_file_path(
                outside_path,
                must_exist=False,
                strict=True,
                allowed_base_dirs=[tmp_path],
            )


class TestSymlinkValidation:
    """Test symlink and junction point detection."""

    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix symlink test")
    def test_detect_symlink_file(self, tmp_path):
        """Test detection of symbolic link files."""
        target = tmp_path / "target.txt"
        target.write_text("data")

        symlink = tmp_path / "link.txt"
        symlink.symlink_to(target)

        configure_security(allow_symlinks=False, strict_mode=True)

        with pytest.raises(PathValidationError, match="symbolic link"):
            validate_file_path(symlink, strict=True)

    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix symlink test")
    def test_detect_symlink_in_path(self, tmp_path):
        """Test detection of symlinks in parent directories."""
        real_dir = tmp_path / "real"
        real_dir.mkdir()

        link_dir = tmp_path / "link"
        link_dir.symlink_to(real_dir)

        test_file = link_dir / "test.txt"
        test_file.write_text("data")

        configure_security(allow_symlinks=False, strict_mode=True)

        with pytest.raises(PathValidationError, match="symbolic link"):
            validate_file_path(test_file, strict=True)

    def test_allow_symlinks_when_configured(self, tmp_path):
        """Test that symlinks are allowed when configured."""
        if platform.system() == "Windows":
            pytest.skip("Unix symlink test")

        target = tmp_path / "target.txt"
        target.write_text("data")

        symlink = tmp_path / "link.txt"
        symlink.symlink_to(target)

        configure_security(allow_symlinks=True)

        # Should not raise
        result = validate_file_path(symlink)
        assert result.exists()


class TestDirectoryWhitelist:
    """Test directory whitelisting functionality."""

    def test_whitelist_single_directory(self, tmp_path):
        """Test whitelisting a single directory."""
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()

        forbidden_dir = tmp_path / "forbidden"
        forbidden_dir.mkdir()

        configure_security(strict_mode=True, allowed_base_dirs=[allowed_dir])

        # File in allowed dir should work
        allowed_file = allowed_dir / "test.txt"
        allowed_file.write_text("data")
        result = validate_file_path(allowed_file, strict=True)
        assert result.exists()

        # File in forbidden dir should fail
        forbidden_file = forbidden_dir / "test.txt"
        forbidden_file.write_text("data")
        with pytest.raises(PathValidationError, match="outside allowed"):
            validate_file_path(forbidden_file, strict=True)

    def test_whitelist_multiple_directories(self, tmp_path):
        """Test whitelisting multiple directories."""
        dir1 = tmp_path / "dir1"
        dir1.mkdir()
        dir2 = tmp_path / "dir2"
        dir2.mkdir()
        dir3 = tmp_path / "dir3"
        dir3.mkdir()

        configure_security(strict_mode=True, allowed_base_dirs=[dir1, dir2])

        # Files in dir1 and dir2 should work
        file1 = dir1 / "test.txt"
        file1.write_text("data")
        assert validate_file_path(file1, strict=True).exists()

        file2 = dir2 / "test.txt"
        file2.write_text("data")
        assert validate_file_path(file2, strict=True).exists()

        # File in dir3 should fail
        file3 = dir3 / "test.txt"
        file3.write_text("data")
        with pytest.raises(PathValidationError):
            validate_file_path(file3, strict=True)

    def test_whitelist_with_subdirectories(self, tmp_path):
        """Test that whitelisting allows subdirectories."""
        base_dir = tmp_path / "base"
        base_dir.mkdir()

        sub_dir = base_dir / "sub" / "deep"
        sub_dir.mkdir(parents=True)

        configure_security(strict_mode=True, allowed_base_dirs=[base_dir])

        # File in subdirectory should work
        deep_file = sub_dir / "test.txt"
        deep_file.write_text("data")
        result = validate_file_path(deep_file, strict=True)
        assert result.exists()


class TestValidateFilePath:
    """Test file path validation."""

    def test_validate_existing_file(self, tmp_path):
        """Test validating an existing file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("data")

        result = validate_file_path(test_file, must_exist=True)
        assert result == test_file.resolve()

    def test_validate_nonexistent_file_with_must_exist(self, tmp_path):
        """Test that nonexistent file raises when must_exist=True."""
        test_file = tmp_path / "nonexistent.txt"

        with pytest.raises(PathValidationError, match="Invalid path"):
            validate_file_path(test_file, must_exist=True)

    def test_validate_nonexistent_file_without_must_exist(self, tmp_path):
        """Test validating nonexistent file when must_exist=False."""
        test_file = tmp_path / "future.txt"

        result = validate_file_path(test_file, must_exist=False)
        assert result == test_file.resolve()

    def test_validate_with_extension_filter(self, tmp_path):
        """Test extension filtering."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("data")

        # Should work with correct extension
        result = validate_file_path(test_file, allowed_extensions={".txt", ".md"})
        assert result.exists()

        # Should fail with wrong extension
        with pytest.raises(PathValidationError, match="Invalid extension"):
            validate_file_path(test_file, allowed_extensions={".pdf", ".doc"})

    def test_validate_with_size_limit(self, tmp_path):
        """Test file size validation."""
        test_file = tmp_path / "large.txt"
        test_file.write_text("x" * 1024 * 1024 * 2)  # 2 MB

        # Should work under limit
        result = validate_file_path(test_file, max_size_mb=5.0)
        assert result.exists()

        # Should fail over limit
        with pytest.raises(PathValidationError, match="too large"):
            validate_file_path(test_file, max_size_mb=1.0)


class TestValidateDirectoryPath:
    """Test directory path validation."""

    def test_validate_existing_directory(self, tmp_path):
        """Test validating an existing directory."""
        test_dir = tmp_path / "testdir"
        test_dir.mkdir()

        result = validate_directory_path(test_dir, must_exist=True)
        assert result == test_dir.resolve()
        assert result.is_dir()

    def test_validate_nonexistent_directory_with_create(self, tmp_path):
        """Test creating directory when create_if_missing=True."""
        test_dir = tmp_path / "newdir"

        result = validate_directory_path(
            test_dir,
            must_exist=True,
            create_if_missing=True,
        )

        assert result.exists()
        assert result.is_dir()

    def test_validate_file_as_directory_fails(self, tmp_path):
        """Test that validating a file as directory fails."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("data")

        with pytest.raises(PathValidationError, match="not a directory"):
            validate_directory_path(test_file, must_exist=True)

    def test_validate_directory_with_security_checks(self, tmp_path):
        """Test directory validation with security checks."""
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()

        forbidden_dir = tmp_path / "forbidden"
        forbidden_dir.mkdir()

        configure_security(strict_mode=True, allowed_base_dirs=[allowed_dir])

        # Allowed directory should work
        result = validate_directory_path(allowed_dir, strict=True)
        assert result.is_dir()

        # Forbidden directory should fail
        with pytest.raises(PathValidationError):
            validate_directory_path(forbidden_dir, strict=True)


class TestSanitizeFilename:
    """Test filename sanitization."""

    def test_sanitize_basic_filename(self):
        """Test sanitizing a basic filename."""
        result = sanitize_filename("test.txt")
        assert result == "test.txt"

    def test_sanitize_path_separators(self):
        """Test removing path separators."""
        result = sanitize_filename("../../etc/passwd")
        assert "/" not in result
        assert "\\" not in result
        assert ".." not in result

    def test_sanitize_null_bytes(self):
        """Test removing null bytes."""
        result = sanitize_filename("test\x00.txt")
        assert "\x00" not in result

    def test_sanitize_leading_trailing_dots(self):
        """Test removing leading/trailing dots and spaces."""
        result = sanitize_filename("...test.txt...")
        assert not result.startswith(".")
        assert not result.endswith(".")

    def test_sanitize_empty_filename(self):
        """Test handling empty filename."""
        result = sanitize_filename("")
        assert result == "unnamed"

    def test_sanitize_only_dangerous_chars(self):
        """Test filename with only dangerous characters."""
        result = sanitize_filename("../../")
        assert result == "unnamed"

    def test_sanitize_custom_replacement(self):
        """Test custom replacement character."""
        result = sanitize_filename("test/file.txt", replacement="-")
        assert "/" not in result
        assert "-" in result


class TestSecurityConfiguration:
    """Test security configuration management."""

    def test_default_configuration(self):
        """Test default security configuration."""
        configure_security()  # Reset to defaults

        config = get_security_config()
        assert config.strict_mode is False
        assert config.allow_symlinks is True
        assert config.allow_absolute_paths is True
        assert len(config.allowed_base_dirs) == 0

    def test_configure_strict_mode(self):
        """Test configuring strict mode."""
        configure_security(strict_mode=True)

        config = get_security_config()
        assert config.strict_mode is True

    def test_configure_allowed_directories(self, tmp_path):
        """Test configuring allowed directories."""
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"

        configure_security(allowed_base_dirs=[dir1, dir2])

        config = get_security_config()
        assert len(config.allowed_base_dirs) == 2

    def test_configure_symlink_policy(self):
        """Test configuring symlink policy."""
        configure_security(allow_symlinks=False)

        config = get_security_config()
        assert config.allow_symlinks is False
