"""Tests for custom_json_api_v1 adapter upload error handling."""

from __future__ import annotations

from ouro.core.http import HttpResponse
from ouro.modules.upload.adapters.custom_json_api_v1 import CustomJsonApiAdapter
from ouro.modules.upload.models import TorrentFile, TorrentMetadata, TrackerConfig


def _make_config() -> TrackerConfig:
    return TrackerConfig(
        name="Custom JSON API",
        type="custom_json_api_v1",
        url="https://tracker.example",
        api_key="token",
        defaults={},
    )


def _make_metadata() -> TorrentMetadata:
    return TorrentMetadata(
        name="Gone Baby Gone",
        description="[b]Long enough description for tracker validation[/b]",
        category="Films & Videos",
        type="custom_json_api_v1",
        resolution="custom_json_api_v1",
        custom_api_category_id=1,
        custom_api_subcategory_id=6,
    )


def test_custom_json_api_upload_parses_403_json_errors(monkeypatch, tmp_path):
    torrent_path = tmp_path / "sample.torrent"
    torrent_path.write_bytes(
        b"d8:announce13:https://x/4:infod6:lengthi1e4:name1:a12:piece lengthi16e6:pieces20:aaaaaaaaaaaaaaaaaaaaee"
    )
    nfo_path = tmp_path / "sample.nfo"
    nfo_path.write_text("nfo", encoding="utf-8")

    torrent_file = TorrentFile(path=torrent_path, name=torrent_path.name, size=0)
    monkeypatch.setattr(torrent_file, "validate", lambda: True)

    adapter = CustomJsonApiAdapter(_make_config())
    monkeypatch.setattr(adapter, "validate_credentials", lambda: True)
    monkeypatch.setattr(adapter, "_resolve_nfo_path", lambda *_a, **_k: nfo_path)

    def _fake_request(*_args, **_kwargs):
        return HttpResponse(
            url="https://tracker.example/api/torrents",
            status_code=403,
            headers={},
            body=b'{"errors":{"descriptionFormat":["HTML mode not permitted"]}}',
        )

    monkeypatch.setattr(adapter.client, "request", _fake_request)

    result = adapter.upload_torrent(torrent_file, _make_metadata())

    assert not result.success
    assert any("descriptionFormat: HTML mode not permitted" in err for err in result.errors)
    assert any("Forbidden by tracker" in err for err in result.errors)


def test_custom_json_api_upload_parses_422_json_errors(monkeypatch, tmp_path):
    torrent_path = tmp_path / "sample.torrent"
    torrent_path.write_bytes(
        b"d8:announce13:https://x/4:infod6:lengthi1e4:name1:a12:piece lengthi16e6:pieces20:aaaaaaaaaaaaaaaaaaaaee"
    )
    nfo_path = tmp_path / "sample.nfo"
    nfo_path.write_text("nfo", encoding="utf-8")

    torrent_file = TorrentFile(path=torrent_path, name=torrent_path.name, size=0)
    monkeypatch.setattr(torrent_file, "validate", lambda: True)

    adapter = CustomJsonApiAdapter(_make_config())
    monkeypatch.setattr(adapter, "validate_credentials", lambda: True)
    monkeypatch.setattr(adapter, "_resolve_nfo_path", lambda *_a, **_k: nfo_path)

    def _fake_request(*_args, **_kwargs):
        return HttpResponse(
            url="https://tracker.example/api/torrents",
            status_code=422,
            headers={},
            body=b'{"errors":{"title":["Title already exists"]}}',
        )

    monkeypatch.setattr(adapter.client, "request", _fake_request)

    result = adapter.upload_torrent(torrent_file, _make_metadata())

    assert not result.success
    assert any("title: Title already exists" in err for err in result.errors)


def test_custom_json_api_validate_credentials_detects_missing_upload_scope(monkeypatch):
    adapter = CustomJsonApiAdapter(_make_config())

    def _fake_get(*_args, **_kwargs):
        return HttpResponse(
            url="https://tracker.example/api/categories",
            status_code=200,
            headers={},
            body=b'{"data":[]}',
        )

    def _fake_request(*_args, **_kwargs):
        return HttpResponse(
            url="https://tracker.example/api/torrents",
            status_code=403,
            headers={},
            body=b'{"message":"Cette cl\\u00e9 API n\\u0027a pas le scope requis : upload:write."}',
        )

    monkeypatch.setattr(adapter.client, "get", _fake_get)
    monkeypatch.setattr(adapter.client, "request", _fake_request)

    try:
        adapter.validate_credentials()
    except Exception as exc:
        assert "upload:write" in str(exc)
    else:
        raise AssertionError("validate_credentials() should fail when upload scope is missing")


def test_custom_json_api_validate_credentials_accepts_payload_validation_errors(monkeypatch):
    adapter = CustomJsonApiAdapter(_make_config())

    def _fake_get(*_args, **_kwargs):
        return HttpResponse(
            url="https://tracker.example/api/categories",
            status_code=200,
            headers={},
            body=b'{"data":[]}',
        )

    def _fake_request(*_args, **_kwargs):
        return HttpResponse(
            url="https://tracker.example/api/torrents",
            status_code=422,
            headers={},
            body=b'{"errors":{"torrent":["The torrent field is required."]}}',
        )

    monkeypatch.setattr(adapter.client, "get", _fake_get)
    monkeypatch.setattr(adapter.client, "request", _fake_request)

    assert adapter.validate_credentials() is True
