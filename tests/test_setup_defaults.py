from framekit.core.settings import DEFAULT_SETTINGS


def test_setup_defaults_exist():
    assert "setup" in DEFAULT_SETTINGS
    assert DEFAULT_SETTINGS["setup"]["completed"] is False
    assert DEFAULT_SETTINGS["setup"]["prompt_on_start"] is True
