from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from framekit.commands import prez as prez_command_module
from framekit.commands import torrent as torrent_command_module
from framekit.core.settings import SettingsStore


class _StoreFactory:
    def __init__(self, store: SettingsStore) -> None:
        self.store = store

    def __call__(self) -> SettingsStore:
        return self.store


def test_torrent_parse_piece_length_units():
    assert torrent_command_module._parse_piece_length(None) is None
    assert torrent_command_module._parse_piece_length("auto") is None
    assert torrent_command_module._parse_piece_length("512K") == 512 * 1024
    assert torrent_command_module._parse_piece_length("2M") == 2 * 1024 * 1024
    assert torrent_command_module._parse_piece_length("1024") == 1024


def test_torrent_command_builds_with_settings_and_saves_last_folder(
    monkeypatch, tmp_path, temp_settings_store
):
    target = tmp_path / "Release"
    target.mkdir()
    (target / "Movie.2024.1080p.mkv").write_bytes(b"movie")
    temp_settings_store.set("modules.torrent.announce", "https://tracker.example/announce")
    temp_settings_store.set("modules.torrent.piece_length", "512K")
    monkeypatch.setattr(torrent_command_module, "SettingsStore", _StoreFactory(temp_settings_store))

    captured = {}

    class _Service:
        def build(self, target_path: Path, *, options, write: bool):
            captured["target"] = target_path
            captured["options"] = options
            captured["write"] = write
            return (
                SimpleNamespace(modified=1),
                SimpleNamespace(
                    files_count=2,
                    piece_length=options.piece_length,
                    pieces_count=4,
                    output_path=tmp_path / "Release.torrent",
                ),
            )

    monkeypatch.setattr(torrent_command_module, "TorrentService", _Service)

    assert (
        torrent_command_module.run_torrent_command(
            path=str(target),
            output=None,
            announce=None,
            private=None,
            piece_length=None,
            dry_run=False,
        )
        == 0
    )

    assert captured["target"] == target
    assert captured["write"] is True
    assert captured["options"].announce == "https://tracker.example/announce"
    assert captured["options"].piece_length == 512 * 1024
    assert temp_settings_store.get("modules.torrent.last_folder") == str(target)


def test_torrent_command_missing_path_returns_error(monkeypatch, tmp_path, temp_settings_store):
    monkeypatch.setattr(torrent_command_module, "SettingsStore", _StoreFactory(temp_settings_store))

    assert (
        torrent_command_module.run_torrent_command(
            path=str(tmp_path / "missing"),
            output=None,
            announce=None,
            private=None,
            piece_length=None,
            dry_run=True,
        )
        == 1
    )


def test_prez_formats_from_option():
    assert prez_command_module._formats_from_option("both") == ("html", "bbcode")
    assert prez_command_module._formats_from_option("html") == ("html",)


def test_prez_template_selector_uses_shared_checkbox_selector(monkeypatch):
    captured = {}

    def fake_select_one(*, title, entries, page_size, **kwargs):
        captured["title"] = title
        captured["entries"] = entries
        captured["page_size"] = page_size
        return "timeline"

    monkeypatch.setattr(prez_command_module, "select_one", fake_select_one)

    assert (
        prez_command_module._select_template("HTML", ("aurora", "timeline"), "aurora") == "timeline"
    )
    assert captured["page_size"] == 8

    selectable_entries = [entry for entry in captured["entries"] if hasattr(entry, "selected")]

    assert selectable_entries
    assert all(entry.selected is False for entry in selectable_entries)


def test_prez_command_uses_locale_and_saves_last_folder(monkeypatch, tmp_path, temp_settings_store):
    folder = tmp_path / "Release"
    folder.mkdir()
    monkeypatch.setattr(prez_command_module, "SettingsStore", _StoreFactory(temp_settings_store))

    captured = {}

    class _Service:
        def build(self, folder_path: Path, *, options, write: bool):
            captured["folder"] = folder_path
            captured["options"] = options
            captured["write"] = write
            return (
                SimpleNamespace(),
                SimpleNamespace(outputs=[tmp_path / "Release.html", tmp_path / "Release.bbcode"]),
            )

    monkeypatch.setattr(prez_command_module, "PrezService", _Service)

    assert (
        prez_command_module.run_prez_command(
            path=str(folder),
            output_dir=None,
            output_format="both",
            with_metadata=False,
            locale="es",
            dry_run=True,
        )
        == 0
    )

    assert captured["folder"] == folder
    assert captured["write"] is False
    assert captured["options"].formats == ("html", "bbcode")
    assert captured["options"].locale == "es"
    assert temp_settings_store.get("modules.prez.last_folder") == str(folder)


def test_prez_command_missing_folder_returns_error(monkeypatch, tmp_path, temp_settings_store):
    monkeypatch.setattr(prez_command_module, "SettingsStore", _StoreFactory(temp_settings_store))

    assert (
        prez_command_module.run_prez_command(
            path=str(tmp_path / "missing"),
            output_dir=None,
            output_format="html",
            with_metadata=False,
            locale=None,
            dry_run=True,
        )
        == 1
    )


def test_prez_select_template_bbcode_has_no_divider(monkeypatch):
    captured = {}

    def fake_select_one(*, title, entries, page_size, **kwargs):
        captured["entries"] = entries
        return "compact"

    monkeypatch.setattr(prez_command_module, "select_one", fake_select_one)

    assert (
        prez_command_module._select_template(
            "BBCode", ("classic", "compact"), "classic", grouped=False
        )
        == "compact"
    )
    assert captured["entries"][0].label == "classic"
    assert hasattr(captured["entries"][0], "selected")
