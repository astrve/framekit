from __future__ import annotations

from framekit.commands import settings as settings_command_module
from framekit.core.settings import SettingsStore


class _StoreFactory:
    def __init__(self, store: SettingsStore) -> None:
        self.store = store

    def __call__(self) -> SettingsStore:
        return self.store


def test_settings_set_parses_bool_and_saves(monkeypatch, temp_settings_store):
    monkeypatch.setattr(
        settings_command_module, "SettingsStore", _StoreFactory(temp_settings_store)
    )

    assert (
        settings_command_module.run_settings_set("modules.cleanmkv.copy_unchanged_files", "false")
        == 0
    )

    assert temp_settings_store.get("modules.cleanmkv.copy_unchanged_files") is False


def test_settings_reset_restores_default(monkeypatch, temp_settings_store):
    monkeypatch.setattr(
        settings_command_module, "SettingsStore", _StoreFactory(temp_settings_store)
    )
    temp_settings_store.set("general.locale", "es")

    assert settings_command_module.run_settings_reset("general.locale") == 0

    # The default UI locale for a fresh settings reset is English.
    assert temp_settings_store.get("general.locale") == "en"


def test_settings_set_nfo_locale(monkeypatch, temp_settings_store):
    monkeypatch.setattr(
        settings_command_module, "SettingsStore", _StoreFactory(temp_settings_store)
    )

    assert settings_command_module.run_settings_set("modules.nfo.locale", "es") == 0

    assert temp_settings_store.get("modules.nfo.locale") == "es"
