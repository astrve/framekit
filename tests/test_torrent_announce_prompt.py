"""Tests for the interactive announce-URL prompt used by ``ouro torrent``.

When no announce is configured (typical first-run state) the torrent
command used to exit 1 with a one-line error. The current behaviour is to
prompt the user on a TTY, validate the URL, persist it, and continue. On a
non-TTY the explicit error path is preserved so CI scripts fail loudly.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ouro.commands import torrent as torrent_module


def test_non_tty_returns_empty_string(monkeypatch: pytest.MonkeyPatch) -> None:
    """On a non-TTY stdin the function must abort without prompting."""

    class _Stdin:
        @staticmethod
        def isatty() -> bool:
            return False

    monkeypatch.setattr(torrent_module.sys, "stdin", _Stdin())
    result = torrent_module._prompt_for_announce_and_save({})
    assert result == ""


def test_tty_with_empty_input_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty answer cancels the prompt and returns ``""``."""

    class _Stdin:
        @staticmethod
        def isatty() -> bool:
            return True

    monkeypatch.setattr(torrent_module.sys, "stdin", _Stdin())
    with patch.object(torrent_module.click, "prompt", return_value=""):
        result = torrent_module._prompt_for_announce_and_save({})
    assert result == ""


def test_tty_with_invalid_url_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """A malformed URL is rejected; the function returns ``""``."""

    class _Stdin:
        @staticmethod
        def isatty() -> bool:
            return True

    monkeypatch.setattr(torrent_module.sys, "stdin", _Stdin())
    with patch.object(torrent_module.click, "prompt", return_value="not a url"):
        result = torrent_module._prompt_for_announce_and_save({})
    assert result == ""


def test_tty_with_valid_url_saves_and_returns(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A valid URL is persisted when the user accepts the save prompt."""

    class _Stdin:
        @staticmethod
        def isatty() -> bool:
            return True

    monkeypatch.setattr(torrent_module.sys, "stdin", _Stdin())
    valid_url = "https://tracker.example/announce/abc"
    settings: dict = {}

    save_mock = MagicMock()
    with (
        patch.object(torrent_module.click, "prompt", return_value=valid_url),
        patch.object(torrent_module, "select_one", return_value="yes"),
        patch.object(torrent_module, "_save_announce_selection", save_mock),
        patch.object(torrent_module, "SettingsStore"),
    ):
        result = torrent_module._prompt_for_announce_and_save(settings)

    assert result == valid_url
    save_mock.assert_called_once()
    saved_args = save_mock.call_args
    assert saved_args.args[2] == valid_url


def test_tty_with_valid_url_can_skip_save(monkeypatch: pytest.MonkeyPatch) -> None:
    """A valid URL can be used only for the current run."""

    class _Stdin:
        @staticmethod
        def isatty() -> bool:
            return True

    monkeypatch.setattr(torrent_module.sys, "stdin", _Stdin())
    valid_url = "https://tracker.example/announce/abc"
    save_mock = MagicMock()

    with (
        patch.object(torrent_module.click, "prompt", return_value=valid_url),
        patch.object(torrent_module, "select_one", return_value="no"),
        patch.object(torrent_module, "_save_announce_selection", save_mock),
        patch.object(torrent_module, "SettingsStore"),
    ):
        result = torrent_module._prompt_for_announce_and_save({})

    assert result == valid_url
    save_mock.assert_not_called()


def test_tty_with_valid_url_can_disable_save_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    """The save reminder can be disabled without saving the announce URL."""

    class _Stdin:
        @staticmethod
        def isatty() -> bool:
            return True

    monkeypatch.setattr(torrent_module.sys, "stdin", _Stdin())
    valid_url = "https://tracker.example/announce/abc"
    settings: dict = {}
    store_mock = MagicMock()

    with (
        patch.object(torrent_module.click, "prompt", return_value=valid_url),
        patch.object(torrent_module, "select_one", return_value="never"),
        patch.object(torrent_module, "_save_announce_selection") as save_mock,
        patch.object(torrent_module, "SettingsStore", return_value=store_mock),
    ):
        result = torrent_module._prompt_for_announce_and_save(settings)

    assert result == valid_url
    assert settings["modules"]["torrent"]["prompt_save_announce"] is False
    store_mock.save.assert_called_once_with(settings)
    save_mock.assert_not_called()


def test_tty_save_failure_still_returns_announce(monkeypatch: pytest.MonkeyPatch) -> None:
    """Persistence errors are reported, but the entered announce remains usable."""

    class _Stdin:
        @staticmethod
        def isatty() -> bool:
            return True

    monkeypatch.setattr(torrent_module.sys, "stdin", _Stdin())
    valid_url = "udp://tracker.example:6969/announce"

    def _boom(*_args, **_kwargs):
        raise OSError("disk full")

    with (
        patch.object(torrent_module.click, "prompt", return_value=valid_url),
        patch.object(torrent_module, "select_one", return_value="yes"),
        patch.object(torrent_module, "_save_announce_selection", _boom),
        patch.object(torrent_module, "SettingsStore"),
    ):
        result = torrent_module._prompt_for_announce_and_save({})

    assert result == valid_url
