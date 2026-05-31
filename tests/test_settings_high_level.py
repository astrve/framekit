from __future__ import annotations

from copy import deepcopy
from typing import Any

from swirrl.core.settings.high_level import Settings


class _FakeStore:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = deepcopy(data)

    def load(self) -> dict[str, Any]:
        return deepcopy(self._data)

    def save(self, data: dict[str, Any]) -> None:
        self._data = deepcopy(data)

    def get(self, path: str) -> Any:  # pragma: no cover
        raise NotImplementedError

    def set(self, path: str, value: Any) -> dict[str, Any]:  # pragma: no cover
        raise NotImplementedError

    @property
    def data(self) -> dict[str, Any]:
        return deepcopy(self._data)


class _FakeVault:
    def __init__(self) -> None:
        self.values: dict[str, Any] = {}

    def store(self, key: str, value: Any) -> None:
        self.values[key] = value

    def retrieve(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)


def test_set_torrent_announces_plaintext_when_security_disabled() -> None:
    store = _FakeStore({"security": {"enabled": False}, "modules": {"torrent": {}}})
    settings = Settings(store=store)
    settings.set_torrent_announces([" https://tracker/announce ", ""])

    torrent = store.data["modules"]["torrent"]
    assert torrent["announce_urls"] == ["https://tracker/announce"]
    assert torrent["selected_announce"] == "https://tracker/announce"
    assert torrent["announce"] == "https://tracker/announce"


def test_set_torrent_announces_secure_when_vault_available() -> None:
    store = _FakeStore({"security": {"enabled": True}, "modules": {"torrent": {}}})
    settings = Settings(store=store)
    vault = _FakeVault()
    settings._get_vault = lambda: vault  # type: ignore[method-assign]

    settings.set_torrent_announces(["https://a/announce", "https://b/announce"])

    torrent = store.data["modules"]["torrent"]
    assert torrent["announce_urls"] == [Settings.ENCRYPTED_PLACEHOLDER]
    assert torrent["selected_announce"] == Settings.ENCRYPTED_PLACEHOLDER
    assert torrent["announce"] == Settings.ENCRYPTED_PLACEHOLDER
    assert vault.values["torrent_announces"] == ["https://a/announce", "https://b/announce"]
    assert vault.values["torrent_selected_announce_index"] == 0


def test_set_selected_announce_secure_stores_index() -> None:
    store = _FakeStore(
        {
            "security": {"enabled": True},
            "modules": {
                "torrent": {
                    "announce_urls": ["https://a/announce", "https://b/announce"],
                    "selected_announce": "",
                    "announce": "",
                }
            },
        }
    )
    settings = Settings(store=store)
    vault = _FakeVault()
    settings._get_vault = lambda: vault  # type: ignore[method-assign]

    settings.set_selected_announce("https://b/announce")

    torrent = store.data["modules"]["torrent"]
    assert torrent["selected_announce"] == Settings.ENCRYPTED_PLACEHOLDER
    assert torrent["announce"] == Settings.ENCRYPTED_PLACEHOLDER
    assert vault.values["torrent_selected_announce_index"] == 1


def test_migrate_to_vault_migrates_token_and_announces() -> None:
    store = _FakeStore(
        {
            "security": {"enabled": True},
            "metadata": {"tmdb_read_access_token": "token-value"},
            "modules": {"torrent": {"announce_urls": ["https://a/announce"]}},
        }
    )
    settings = Settings(store=store)
    vault = _FakeVault()
    settings._get_vault = lambda: vault  # type: ignore[method-assign]

    result = settings.migrate_to_vault()

    assert "tmdb_api_token" in result["success"]
    assert "torrent_announces" in result["success"]
    assert vault.values["tmdb_api_token"] == "token-value"
    assert vault.values["torrent_announces"] == ["https://a/announce"]
