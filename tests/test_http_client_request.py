from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from email.message import Message

import pytest

from framekit.core.http import (
    HttpClient,
    HttpClientConfig,
    HttpDecodeError,
    HttpRateLimitError,
    HttpRetryPolicy,
    HttpTimeoutError,
)


def _message_headers(values: dict[str, str] | None = None) -> Message:
    headers = Message()
    for key, value in (values or {}).items():
        headers[key] = value
    return headers


class _Response:
    def __init__(self, *, status: int = 200, body: bytes = b"{}", headers=None) -> None:
        self.status = status
        self._body = body
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def getcode(self) -> int:
        return self.status

    def read(self) -> bytes:
        return self._body


def test_request_json_posts_body_and_merges_headers(monkeypatch):
    captured = {}

    def fake_urlopen(request, *, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["data"] = request.data
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        return _Response(body=b'{"ok": true}', headers={"Content-Type": "application/json"})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    client = HttpClient(
        base_url="https://api.example.test",
        default_headers={"X-Default": "yes"},
        config=HttpClientConfig(timeout_seconds=3.5),
    )

    result = client.request_json(
        "POST",
        "/search",
        params={"query": "Movie"},
        headers={"X-Request": "one"},
        json_body={"page": 1},
    )

    assert result == {"ok": True}
    assert captured["url"] == "https://api.example.test/search?query=Movie"
    assert captured["method"] == "POST"
    assert json.loads(captured["data"].decode("utf-8")) == {"page": 1}
    assert captured["headers"]["X-default"] == "yes"
    assert captured["headers"]["X-request"] == "one"
    assert captured["timeout"] == 3.5


def test_request_retries_http_error_then_succeeds(monkeypatch):
    calls = []
    sleeps = []

    def fake_urlopen(request, *, timeout):
        calls.append(request.full_url)
        if len(calls) == 1:
            raise urllib.error.HTTPError(
                request.full_url,
                429,
                "Too Many Requests",
                _message_headers({"Retry-After": "1"}),
                io.BytesIO(b"rate limited"),
            )
        return _Response(body=b"done")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    client = HttpClient(
        config=HttpClientConfig(retry_policy=HttpRetryPolicy(max_attempts=2)),
        sleep=sleeps.append,
    )

    response = client.get("https://example.test/resource")

    assert response.body == b"done"
    assert len(calls) == 2
    assert sleeps == [1.0]


def test_request_raises_rate_limit_after_retries(monkeypatch):
    def fake_urlopen(request, *, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            429,
            "Too Many Requests",
            _message_headers(),
            io.BytesIO(b"rate limited"),
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    client = HttpClient(config=HttpClientConfig(retry_policy=HttpRetryPolicy(max_attempts=1)))

    with pytest.raises(HttpRateLimitError) as excinfo:
        client.get("https://example.test/resource?api_key=secret")

    assert excinfo.value.status_code == 429
    assert excinfo.value.response_body == "rate limited"
    assert "secret" not in str(excinfo.value)


def test_request_converts_socket_timeout_to_timeout_error(monkeypatch):
    def fake_urlopen(request, *, timeout):
        raise urllib.error.URLError(TimeoutError("slow"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    client = HttpClient(config=HttpClientConfig(retry_policy=HttpRetryPolicy(max_attempts=1)))

    with pytest.raises(HttpTimeoutError):
        client.get("https://example.test/slow")


def test_response_json_raises_decode_error():
    from framekit.core.http import HttpResponse

    http_response = HttpResponse(
        url="https://example.test",
        status_code=200,
        headers={},
        body=b"not-json",
    )

    with pytest.raises(HttpDecodeError):
        http_response.json()
