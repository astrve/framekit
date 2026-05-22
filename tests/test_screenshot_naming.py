"""Tests for screenshot naming utilities."""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from framekit.modules.screenshot.naming import (  # noqa: E402
    generate_screenshot_filename,
    sanitize_release_name,
)


class TestSanitizeReleaseName:
    """Test release name sanitization."""

    def test_basic_name(self):
        """Test sanitizing a basic release name."""
        result = sanitize_release_name("Movie.2024.1080p.BluRay")
        assert result == "Movie.2024.1080p.BluRay"

    def test_remove_special_characters(self):
        """Test removing special characters."""
        result = sanitize_release_name("Movie:2024/Test\\File*Name?")
        # Should remove : / \ * ?
        assert ":" not in result
        assert "/" not in result
        assert "\\" not in result
        assert "*" not in result
        assert "?" not in result

    def test_remove_quotes(self):
        """Test removing quotes."""
        result = sanitize_release_name("Movie\"2024'Test")
        assert '"' not in result
        assert "'" not in result

    def test_remove_angle_brackets(self):
        """Test removing angle brackets."""
        result = sanitize_release_name("Movie<2024>Test")
        assert "<" not in result
        assert ">" not in result

    def test_remove_pipe(self):
        """Test removing pipe character."""
        result = sanitize_release_name("Movie|2024")
        assert "|" not in result

    def test_trim_whitespace(self):
        """Test trimming leading/trailing whitespace."""
        result = sanitize_release_name("  Movie.2024  ")
        assert result == "Movie.2024"

    def test_collapse_multiple_spaces(self):
        """Test collapsing multiple spaces."""
        result = sanitize_release_name("Movie    2024")
        assert "    " not in result

    def test_empty_string(self):
        """Test handling empty string."""
        result = sanitize_release_name("")
        assert result == "untitled"

    def test_only_special_characters(self):
        """Test handling string with only special characters."""
        result = sanitize_release_name("***///???")
        assert result == "untitled"

    def test_preserve_dots_and_dashes(self):
        """Test that dots and dashes are preserved."""
        result = sanitize_release_name("Movie.2024-BluRay")
        assert "." in result
        assert "-" in result


class TestGenerateScreenshotFilename:
    """Test screenshot filename generation."""

    def test_basic_filename(self):
        """Test generating basic filename."""
        result = generate_screenshot_filename("Movie.2024", 1, "png")
        assert result == "Movie.2024_screenshot_001.png"

    def test_different_index(self):
        """Test generating filename with different index."""
        result = generate_screenshot_filename("Movie.2024", 5, "png")
        assert result == "Movie.2024_screenshot_005.png"

    def test_jpg_format(self):
        """Test generating filename with jpg format."""
        result = generate_screenshot_filename("Movie.2024", 1, "jpg")
        assert result == "Movie.2024_screenshot_001.jpg"

    def test_large_index(self):
        """Test generating filename with large index."""
        result = generate_screenshot_filename("Movie.2024", 42, "png")
        assert result == "Movie.2024_screenshot_042.png"

    def test_sanitizes_release_name(self):
        """Test that release name is sanitized."""
        result = generate_screenshot_filename("Movie:2024/Test", 1, "png")
        # Should not contain : or /
        assert ":" not in result
        assert "/" not in result
        assert "_screenshot_001.png" in result

    def test_zero_padding(self):
        """Test that index is zero-padded to 3 digits."""
        result1 = generate_screenshot_filename("Movie", 1, "png")
        result2 = generate_screenshot_filename("Movie", 10, "png")
        result3 = generate_screenshot_filename("Movie", 100, "png")

        assert "001" in result1
        assert "010" in result2
        assert "100" in result3

    def test_handles_empty_release_name(self):
        """Test handling empty release name."""
        result = generate_screenshot_filename("", 1, "png")
        assert result == "untitled_screenshot_001.png"


class TestCollisionDetection:
    """Test filename collision detection and handling."""

    def test_no_collision(self, tmp_path):
        """Test when no collision exists."""
        from framekit.modules.screenshot.naming import get_unique_filename

        output_dir = tmp_path / "screenshots"
        output_dir.mkdir()

        filename = get_unique_filename(output_dir, "Movie.2024", 1, "png")
        assert filename == output_dir / "Movie.2024_screenshot_001.png"

    def test_collision_increments(self, tmp_path):
        """Test that collision increments the filename."""
        from framekit.modules.screenshot.naming import get_unique_filename

        output_dir = tmp_path / "screenshots"
        output_dir.mkdir()

        # Create existing file
        existing = output_dir / "Movie.2024_screenshot_001.png"
        existing.write_text("fake")

        filename = get_unique_filename(output_dir, "Movie.2024", 1, "png")
        # Should increment to avoid collision
        assert filename != existing
        assert not filename.exists()

    def test_multiple_collisions(self, tmp_path):
        """Test handling multiple collisions."""
        from framekit.modules.screenshot.naming import get_unique_filename

        output_dir = tmp_path / "screenshots"
        output_dir.mkdir()

        # Create multiple existing files
        for i in range(1, 4):
            existing = output_dir / f"Movie.2024_screenshot_00{i}.png"
            existing.write_text("fake")

        filename = get_unique_filename(output_dir, "Movie.2024", 1, "png")
        # Should find next available number
        assert not filename.exists()
        assert "screenshot" in filename.name


class TestPathSanitization:
    """Test path sanitization for security."""

    def test_no_path_traversal(self):
        """Test that path traversal is prevented."""
        result = sanitize_release_name("../../../etc/passwd")
        # Should not contain ..
        assert ".." not in result

    def test_no_absolute_path(self):
        """Test that absolute paths are sanitized."""
        result = sanitize_release_name("/etc/passwd")
        # Should not start with /
        assert not result.startswith("/")

    def test_no_null_bytes(self):
        """Test that null bytes are removed."""
        result = sanitize_release_name("Movie\x00.2024")
        assert "\x00" not in result

    def test_no_newlines(self):
        """Test that newlines are removed."""
        result = sanitize_release_name("Movie\n2024")
        assert "\n" not in result
        assert "\r" not in result

    def test_windows_reserved_names(self):
        """Test handling Windows reserved names."""
        reserved_names = ["CON", "PRN", "AUX", "NUL", "COM1", "LPT1"]
        for name in reserved_names:
            result = sanitize_release_name(name)
            # Should not be exactly a reserved name
            assert result.upper() != name

    def test_max_length(self):
        """Test that filename length is limited."""
        long_name = "A" * 300
        result = sanitize_release_name(long_name)
        # Should be truncated to reasonable length (e.g., 200 chars)
        assert len(result) <= 200


# Made with Bob
