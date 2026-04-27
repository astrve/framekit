from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from framekit.core.diagnostics import reset_diagnostics
from framekit.core.i18n import set_locale
from framekit.core.settings import SettingsStore


@pytest.fixture(autouse=True)
def reset_locale_between_tests() -> Iterator[None]:
    set_locale("en")
    reset_diagnostics()
    yield
    set_locale("en")
    reset_diagnostics()


@pytest.fixture
def temp_settings_store(tmp_path: Path) -> SettingsStore:
    return SettingsStore(tmp_path / "settings.json")


@pytest.fixture
def isolated_settings_store(temp_settings_store: SettingsStore) -> SettingsStore:
    return temp_settings_store
