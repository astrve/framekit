from framekit.modules.nfo.logo_tools import _slugify_logo_name


def test_slugify_logo_name():
    assert _slugify_logo_name("My Logo") == "my_logo"
    assert _slugify_logo_name("  Cool-ASCII Logo  ") == "cool_ascii_logo"
