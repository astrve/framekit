"""Regression tests for ``HttpClient`` connect-error classification.

Historically, ``httpx.ConnectError`` was unconditionally re-raised as
``HttpCertificateError("SSL certificate validation failed ...")``. That covered
the SSL handshake case but mislabelled DNS, refused-connection, and unreachable
errors. These tests pin the new behaviour: only SSL-shaped failures map to
``HttpCertificateError``; everything else maps to ``HttpNetworkError``.
"""

from __future__ import annotations

import ssl
from unittest.mock import Mock

import httpx
import pytest

from swirrl.core.http import (
    HttpCertificateError,
    HttpClient,
    HttpClientConfig,
    HttpNetworkError,
    HttpRetryPolicy,
    _classify_connect_error,
    _is_ssl_error,
    redact_url,
)


def test_ssl_error_chain_is_detected() -> None:
    exc = httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] bad cert")
    exc.__cause__ = ssl.SSLError("bad cert")
    assert _is_ssl_error(exc) is True


def test_message_with_certificate_keyword_is_detected() -> None:
    exc = httpx.ConnectError("self-signed certificate in chain")
    assert _is_ssl_error(exc) is True


def test_dns_failure_is_not_classified_as_ssl() -> None:
    exc = httpx.ConnectError("getaddrinfo failed for unknown.invalid")
    assert _is_ssl_error(exc) is False


def test_classify_returns_certificate_error_for_ssl_failure() -> None:
    raw = httpx.ConnectError("[SSL] handshake failed")
    raw.__cause__ = ssl.SSLError("handshake failed")
    result = _classify_connect_error(raw, "https://api.example/test?api_key=abc")
    assert isinstance(result, HttpCertificateError)
    # Redaction must hide the secret. urlencode percent-encodes ``*`` to
    # ``%2A`` so the literal placeholder may appear in either form, but the
    # original value must never leak.
    rendered = str(result)
    assert "api_key=abc" not in rendered
    assert "abc" not in rendered.split("api_key=", 1)[1].split("&")[0].split(":")[0]


def test_classify_returns_network_error_for_dns_failure() -> None:
    raw = httpx.ConnectError("[Errno -2] Name or service not known")
    result = _classify_connect_error(raw, "https://unknown.invalid")
    assert isinstance(result, HttpNetworkError)
    assert not isinstance(result, HttpCertificateError)


def test_request_propagates_classified_error(monkeypatch: pytest.MonkeyPatch) -> None:
    config = HttpClientConfig(retry_policy=HttpRetryPolicy(max_attempts=1))
    client = HttpClient(config=config, sleep=lambda _s: None)

    mock_client = Mock()
    mock_client.request.side_effect = httpx.ConnectError("getaddrinfo failed")
    monkeypatch.setattr(client, "_get_sync_client", lambda: mock_client)

    with pytest.raises(HttpNetworkError) as info:
        client.request("GET", "https://nope.invalid/")
    assert not isinstance(info.value, HttpCertificateError)


def test_request_raises_certificate_error_for_ssl_handshake(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = HttpClientConfig(retry_policy=HttpRetryPolicy(max_attempts=1))
    client = HttpClient(config=config, sleep=lambda _s: None)

    ssl_exc = httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED]")
    ssl_exc.__cause__ = ssl.SSLError("verify failed")

    mock_client = Mock()
    mock_client.request.side_effect = ssl_exc
    monkeypatch.setattr(client, "_get_sync_client", lambda: mock_client)

    with pytest.raises(HttpCertificateError):
        client.request("GET", "https://expired.badssl.com/")


def test_redact_url_masks_known_sensitive_query_keys() -> None:
    redacted = redact_url("https://example.test/path?api_key=xyz&page=2")
    # urlencode percent-encodes ``*`` to ``%2A`` — both forms are acceptable
    # as long as the original ``xyz`` value does not survive.
    assert "xyz" not in redacted
    assert "api_key=" in redacted
    assert "page=2" in redacted


def test_redact_url_passes_through_when_no_secrets() -> None:
    url = "https://example.test/path?page=2&size=10"
    assert redact_url(url) == url
