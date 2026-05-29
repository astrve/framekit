"""Tests for NFO logo tools - logo name utilities."""

from ouro.modules.nfo.logo_tools import _slugify_logo_name


def test_slugify_logo_name():
    """Test that logo names are correctly slugified."""
    assert _slugify_logo_name("My Logo") == "my_logo"
    assert _slugify_logo_name("  Cool-ASCII Logo  ") == "cool_ascii_logo"
