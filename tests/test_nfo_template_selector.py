"""Tests for NFO template selector - interactive template selection."""

from ouro.modules.nfo.template_selector import (
    TemplateOption,
    TemplateSelector,
    build_template_options,
    choose_import_location,
    choose_template,
    choose_template_scope,
    find_template_option,
)


def test_build_template_options():
    """Test building template options from records."""

    class DummyRecord:
        def __init__(self, display_name, template_name, source, scope):
            self.display_name = display_name
            self.template_name = template_name
            self.source = source
            self.scope = scope

    records = [
        DummyRecord("Default", "default", "builtin", "universal"),
        DummyRecord("Detailed", "detailed", "builtin", "universal"),
        DummyRecord("My Movie Layout", "my_movie_layout", "user", "movie"),
    ]

    options = build_template_options(records)

    assert len(options) == 3
    assert options[0].display_name == "Default"
    assert options[0].template_name == "default"
    assert options[2].display_name == "My Movie Layout"
    assert options[2].scope == "movie"


def test_find_template_option():
    """Test finding a template option by name."""
    options = [
        TemplateOption(
            display_name="Default", template_name="default", source="builtin", scope="universal"
        ),
        TemplateOption(
            display_name="Custom Movie", template_name="custom_movie", source="user", scope="movie"
        ),
    ]

    found = find_template_option(options, "custom_movie")
    missing = find_template_option(options, "unknown_template")

    assert found is not None
    assert found.display_name == "Custom Movie"
    assert found.source == "user"
    assert missing is None


def test_template_selector_run_returns_selected(monkeypatch):
    """Test that template selector returns the selected option."""
    options = [
        TemplateOption(
            display_name="Default", template_name="default", source="builtin", scope="universal"
        ),
        TemplateOption(
            display_name="Detailed", template_name="detailed", source="builtin", scope="universal"
        ),
    ]

    def fake_select_one(*, title, entries, page_size):
        assert title == "NFO Template Selector"
        assert page_size == 8
        assert len(entries) == 2
        # ``preferred_name="detailed"`` must preselect that entry so the
        # cursor lands on it. The fix for the "selected detailed → got
        # default" bug relies on this contract; see
        # ``tests/test_nfo_template_selector_preferred.py``.
        assert entries[0].selected is False
        assert entries[1].selected is True
        return options[1]

    monkeypatch.setattr("ouro.modules.nfo.template_selector.select_one", fake_select_one)

    result = TemplateSelector(options, preferred_name="detailed").run()

    assert result is options[1]


def test_template_selector_returns_none_on_keyboard_interrupt(monkeypatch):
    """Test that template selector handles keyboard interrupt gracefully."""
    options = [
        TemplateOption(
            display_name="Default", template_name="default", source="builtin", scope="universal"
        ),
    ]

    def fake_select_one(**kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr("ouro.modules.nfo.template_selector.select_one", fake_select_one)

    result = TemplateSelector(options).run()

    assert result is None


def test_choose_template_scope(monkeypatch):
    """Test choosing a template scope."""

    def fake_run(self):
        return TemplateOption("Movie", "movie", "scope", "movie")

    monkeypatch.setattr("ouro.modules.nfo.template_selector.TemplateSelector.run", fake_run)

    assert choose_template_scope() == "movie"


def test_choose_import_location(monkeypatch):
    """Test choosing an import location."""

    def fake_run(self):
        return TemplateOption("Project Folder", "project", "location", "project")

    monkeypatch.setattr("ouro.modules.nfo.template_selector.TemplateSelector.run", fake_run)

    assert choose_import_location() == "project"


def test_choose_template(monkeypatch):
    """Test choosing a template from options."""
    options = [
        TemplateOption(
            display_name="Default", template_name="default", source="builtin", scope="universal"
        ),
        TemplateOption(
            display_name="Detailed", template_name="detailed", source="builtin", scope="universal"
        ),
    ]

    def fake_run(self):
        return options[0]

    monkeypatch.setattr("ouro.modules.nfo.template_selector.TemplateSelector.run", fake_run)

    result = choose_template(options, preferred_name="default")

    assert result is options[0]
