from __future__ import annotations

from framekit.commands import language as language_command_module
from framekit.core.settings import SettingsStore


class _StoreFactory:
    def __init__(self, store: SettingsStore) -> None:
        self.store = store

    def __call__(self) -> SettingsStore:
        return self.store


def test_language_set_updates_general_locale(monkeypatch, temp_settings_store):
    monkeypatch.setattr(
        language_command_module, "SettingsStore", _StoreFactory(temp_settings_store)
    )

    assert language_command_module.run_language_set("es") == 0

    assert temp_settings_store.get("general.locale") == "es"


def test_language_set_rejects_unknown_locale(monkeypatch, temp_settings_store):
    monkeypatch.setattr(
        language_command_module, "SettingsStore", _StoreFactory(temp_settings_store)
    )

    assert language_command_module.run_language_set("de") == 1

    assert temp_settings_store.get("general.locale") != "de"
