"""Tests for httpx-based HTTP client with HTTP/2 support."""

from __future__ import annotations

import asyncio
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from ouro.core.http import (
    HttpAuthError,
    HttpClient,
    HttpClientConfig,
    HttpDecodeError,
    HttpNetworkError,
    HttpRateLimitError,
    HttpResponse,
    HttpRetryPolicy,
    HttpServerError,
    HttpTimeoutError,
    redact_headers,
    redact_url,
)

# ===== Utility Functions Tests =====


def test_redact_url_masks_sensitive_query_values():
    """Test that sensitive query parameters are redacted."""
    url = "https://example.test/path?api_key=secret&page=1&access_token=tok"

    redacted = redact_url(url)
    query = parse_qs(urlparse(redacted).query)

    assert query["api_key"] == ["********"]
    assert query["access_token"] == ["********"]
    assert query["page"] == ["1"]


def test_redact_headers_masks_authorization():
    """Test that sensitive headers are redacted."""
    headers = redact_headers({"Authorization": "Bearer secret", "Accept": "application/json"})

    assert headers["Authorization"] == "********"
    assert headers["Accept"] == "application/json"


def test_http_client_build_url_skips_empty_params_and_encodes_bool():
    """Test URL building with parameter encoding."""
    client = HttpClient(base_url="https://example.test/api")

    url = client.build_url("/search", {"query": "Moonlight", "include_adult": False, "empty": ""})

    assert url == "https://example.test/api/search?query=Moonlight&include_adult=false"


def test_retry_policy_uses_retry_after_header():
    """Test retry policy respects Retry-After header."""
    policy = HttpRetryPolicy(backoff_max_seconds=10)

    assert policy.delay_for_attempt(1, "2") == 2


# ===== HttpResponse Tests =====


def test_http_response_text_property():
    """Test HttpResponse text property decodes body."""
    response = HttpResponse(
        url="https://example.test",
        status_code=200,
        headers={},
        body=b"Hello World",
    )

    assert response.text == "Hello World"


def test_http_response_json_parses_valid_json():
    """Test HttpResponse json() method parses valid JSON."""
    response = HttpResponse(
        url="https://example.test",
        status_code=200,
        headers={},
        body=b'{"key": "value"}',
    )

    assert response.json() == {"key": "value"}


def test_http_response_json_raises_decode_error():
    """Test HttpResponse json() raises HttpDecodeError for invalid JSON."""
    response = HttpResponse(
        url="https://example.test",
        status_code=200,
        headers={},
        body=b"not-json",
    )

    with pytest.raises(HttpDecodeError) as excinfo:
        response.json()

    assert excinfo.value.status_code == 200
    assert excinfo.value.url == "https://example.test"


# ===== HttpClient Sync Tests =====


def test_http_client_get_request(respx_mock):
    """Test synchronous GET request."""
    respx_mock.get("https://api.example.test/users").mock(
        return_value=httpx.Response(200, json={"users": []})
    )

    client = HttpClient(base_url="https://api.example.test")
    response = client.get("/users")

    assert response.status_code == 200
    assert response.json() == {"users": []}


def test_http_client_post_with_json_body(respx_mock):
    """Test synchronous POST request with JSON body."""
    respx_mock.post("https://api.example.test/users").mock(
        return_value=httpx.Response(201, json={"id": 1, "name": "Alice"})
    )

    client = HttpClient(base_url="https://api.example.test")
    response = client.post("/users", json_body={"name": "Alice"})

    assert response.status_code == 201
    assert response.json() == {"id": 1, "name": "Alice"}


def test_http_client_request_with_params(respx_mock):
    """Test request with query parameters."""
    respx_mock.get("https://api.example.test/search").mock(
        return_value=httpx.Response(200, json={"results": []})
    )

    client = HttpClient(base_url="https://api.example.test")
    response = client.get("/search", params={"q": "test", "page": 1})

    assert response.status_code == 200


def test_http_client_request_with_custom_headers(respx_mock):
    """Test request with custom headers."""

    def check_headers(request):
        assert request.headers["X-Custom"] == "value"
        return httpx.Response(200, json={})

    respx_mock.get("https://api.example.test/data").mock(side_effect=check_headers)

    client = HttpClient(base_url="https://api.example.test")
    response = client.get("/data", headers={"X-Custom": "value"})

    assert response.status_code == 200


def test_http_client_default_headers(respx_mock):
    """Test that default headers are included in requests."""

    def check_headers(request):
        assert request.headers["X-Default"] == "yes"
        return httpx.Response(200, json={})

    respx_mock.get("https://api.example.test/data").mock(side_effect=check_headers)

    client = HttpClient(base_url="https://api.example.test", default_headers={"X-Default": "yes"})
    response = client.get("/data")

    assert response.status_code == 200


def test_http_client_get_json_convenience_method(respx_mock):
    """Test get_json() convenience method."""
    respx_mock.get("https://api.example.test/data").mock(
        return_value=httpx.Response(200, json={"key": "value"})
    )

    client = HttpClient(base_url="https://api.example.test")
    data = client.get_json("/data")

    assert data == {"key": "value"}


def test_http_client_download_bytes(respx_mock):
    """Test download_bytes() method."""
    respx_mock.get("https://api.example.test/file").mock(
        return_value=httpx.Response(200, content=b"binary data")
    )

    client = HttpClient(base_url="https://api.example.test")
    data = client.download_bytes("/file")

    assert data == b"binary data"


# ===== Error Handling Tests =====


def test_http_client_raises_auth_error_on_401(respx_mock):
    """Test that 401 status raises HttpAuthError."""
    respx_mock.get("https://api.example.test/protected").mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )

    client = HttpClient(base_url="https://api.example.test")

    with pytest.raises(HttpAuthError) as excinfo:
        client.get("/protected")

    assert excinfo.value.status_code == 401


def test_http_client_raises_rate_limit_error_on_429(respx_mock):
    """Test that 429 status raises HttpRateLimitError."""
    respx_mock.get("https://api.example.test/data").mock(
        return_value=httpx.Response(429, text="Too Many Requests")
    )

    client = HttpClient(
        base_url="https://api.example.test",
        config=HttpClientConfig(retry_policy=HttpRetryPolicy(max_attempts=1)),
    )

    with pytest.raises(HttpRateLimitError) as excinfo:
        client.get("/data")

    assert excinfo.value.status_code == 429


def test_http_client_raises_server_error_on_500(respx_mock):
    """Test that 500 status raises HttpServerError."""
    respx_mock.get("https://api.example.test/data").mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )

    client = HttpClient(
        base_url="https://api.example.test",
        config=HttpClientConfig(retry_policy=HttpRetryPolicy(max_attempts=1)),
    )

    with pytest.raises(HttpServerError) as excinfo:
        client.get("/data")

    assert excinfo.value.status_code == 500


def test_http_client_raises_timeout_error(respx_mock):
    """Test that timeout raises HttpTimeoutError."""
    respx_mock.get("https://api.example.test/slow").mock(
        side_effect=httpx.TimeoutException("Request timed out")
    )

    client = HttpClient(
        base_url="https://api.example.test",
        config=HttpClientConfig(timeout_seconds=1.0, retry_policy=HttpRetryPolicy(max_attempts=1)),
    )

    with pytest.raises(HttpTimeoutError):
        client.get("/slow")


def test_http_client_raises_network_error(respx_mock):
    """Test that network errors raise HttpNetworkError."""
    respx_mock.get("https://api.example.test/data").mock(
        side_effect=httpx.NetworkError("Connection failed")
    )

    client = HttpClient(
        base_url="https://api.example.test",
        config=HttpClientConfig(retry_policy=HttpRetryPolicy(max_attempts=1)),
    )

    with pytest.raises(HttpNetworkError):
        client.get("/data")


# ===== Retry Logic Tests =====


def test_http_client_retries_on_429_then_succeeds(respx_mock):
    """Test that client retries on 429 and succeeds on retry."""
    call_count = 0

    def mock_response(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(429, headers={"Retry-After": "0.1"})
        return httpx.Response(200, json={"success": True})

    respx_mock.get("https://api.example.test/data").mock(side_effect=mock_response)

    client = HttpClient(
        base_url="https://api.example.test",
        config=HttpClientConfig(retry_policy=HttpRetryPolicy(max_attempts=2)),
        sleep=lambda x: None,  # Skip sleep for testing
    )

    response = client.get("/data")

    assert response.status_code == 200
    assert call_count == 2


def test_http_client_retries_on_500_then_succeeds(respx_mock):
    """Test that client retries on 500 and succeeds on retry."""
    call_count = 0

    def mock_response(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(500)
        return httpx.Response(200, json={"success": True})

    respx_mock.get("https://api.example.test/data").mock(side_effect=mock_response)

    client = HttpClient(
        base_url="https://api.example.test",
        config=HttpClientConfig(retry_policy=HttpRetryPolicy(max_attempts=2)),
        sleep=lambda x: None,
    )

    response = client.get("/data")

    assert response.status_code == 200
    assert call_count == 2


def test_http_client_retries_on_network_error_then_succeeds(respx_mock):
    """Test that client retries on network error and succeeds on retry."""
    call_count = 0

    def mock_response(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.NetworkError("Connection failed")
        return httpx.Response(200, json={"success": True})

    respx_mock.get("https://api.example.test/data").mock(side_effect=mock_response)

    client = HttpClient(
        base_url="https://api.example.test",
        config=HttpClientConfig(retry_policy=HttpRetryPolicy(max_attempts=2)),
        sleep=lambda x: None,
    )

    response = client.get("/data")

    assert response.status_code == 200
    assert call_count == 2


def test_http_client_exhausts_retries_and_fails(respx_mock):
    """Test that client fails after exhausting retries."""
    respx_mock.get("https://api.example.test/data").mock(return_value=httpx.Response(500))

    client = HttpClient(
        base_url="https://api.example.test",
        config=HttpClientConfig(retry_policy=HttpRetryPolicy(max_attempts=2)),
        sleep=lambda x: None,
    )

    with pytest.raises(HttpServerError):
        client.get("/data")


# ===== Async Tests =====


@pytest.mark.asyncio
async def test_http_client_async_get_request(respx_mock):
    """Test asynchronous GET request."""
    respx_mock.get("https://api.example.test/users").mock(
        return_value=httpx.Response(200, json={"users": []})
    )

    client = HttpClient(base_url="https://api.example.test")
    response = await client.async_get("/users")

    assert response.status_code == 200
    assert response.json() == {"users": []}


@pytest.mark.asyncio
async def test_http_client_async_post_with_json_body(respx_mock):
    """Test asynchronous POST request with JSON body via async_request."""
    respx_mock.post("https://api.example.test/users").mock(
        return_value=httpx.Response(201, json={"id": 1, "name": "Alice"})
    )

    client = HttpClient(base_url="https://api.example.test")
    response = await client.async_request("POST", "/users", json_body={"name": "Alice"})

    assert response.status_code == 201
    assert response.json() == {"id": 1, "name": "Alice"}


@pytest.mark.asyncio
async def test_http_client_async_request_json(respx_mock):
    """Test async_request_json() convenience method."""
    respx_mock.get("https://api.example.test/data").mock(
        return_value=httpx.Response(200, json={"key": "value"})
    )

    client = HttpClient(base_url="https://api.example.test")
    data = await client.async_request_json("GET", "/data")

    assert data == {"key": "value"}


@pytest.mark.asyncio
async def test_http_client_async_retries_on_429(respx_mock):
    """Test that async client retries on 429."""
    call_count = 0

    def mock_response(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(429, headers={"Retry-After": "0.1"})
        return httpx.Response(200, json={"success": True})

    respx_mock.get("https://api.example.test/data").mock(side_effect=mock_response)

    client = HttpClient(
        base_url="https://api.example.test",
        config=HttpClientConfig(retry_policy=HttpRetryPolicy(max_attempts=2)),
    )

    # Patch asyncio.sleep to avoid delays
    original_sleep = asyncio.sleep
    asyncio.sleep = lambda x: original_sleep(0)

    try:
        response = await client.async_get("/data")
        assert response.status_code == 200
        assert call_count == 2
    finally:
        asyncio.sleep = original_sleep


@pytest.mark.asyncio
async def test_http_client_async_raises_timeout_error(respx_mock):
    """Test that async client raises HttpTimeoutError on timeout."""
    respx_mock.get("https://api.example.test/slow").mock(
        side_effect=httpx.TimeoutException("Request timed out")
    )

    client = HttpClient(
        base_url="https://api.example.test",
        config=HttpClientConfig(timeout_seconds=1.0, retry_policy=HttpRetryPolicy(max_attempts=1)),
    )

    with pytest.raises(HttpTimeoutError):
        await client.async_get("/slow")


# ===== Context Manager Tests =====


def test_http_client_sync_context_manager(respx_mock):
    """Test HttpClient as synchronous context manager."""
    respx_mock.get("https://api.example.test/data").mock(
        return_value=httpx.Response(200, json={"key": "value"})
    )

    with HttpClient(base_url="https://api.example.test") as client:
        response = client.get("/data")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_http_client_async_context_manager(respx_mock):
    """Test HttpClient as asynchronous context manager."""
    respx_mock.get("https://api.example.test/data").mock(
        return_value=httpx.Response(200, json={"key": "value"})
    )

    async with HttpClient(base_url="https://api.example.test") as client:
        response = await client.async_get("/data")
        assert response.status_code == 200


# ===== HTTP/2 and Connection Pooling Tests =====


def test_http_client_enables_http2_by_default():
    """Test that HTTP/2 is enabled by default."""
    client = HttpClient()
    assert client.config.http2 is True


def test_http_client_connection_pool_limits():
    """Test that connection pool limits are configurable."""
    config = HttpClientConfig(max_connections=50, max_keepalive_connections=10)
    client = HttpClient(config=config)

    assert client.config.max_connections == 50
    assert client.config.max_keepalive_connections == 10


def test_http_client_can_disable_http2():
    """Test that HTTP/2 can be disabled."""
    config = HttpClientConfig(http2=False)
    client = HttpClient(config=config)

    assert client.config.http2 is False


# ===== Backward Compatibility Tests =====


def test_http_client_maintains_backward_compatible_api(respx_mock):
    """Test that the API is backward compatible with urllib-based version."""
    respx_mock.get("https://api.example.test/search").mock(
        return_value=httpx.Response(200, json={"results": []})
    )

    # This should work exactly like the old urllib-based client
    client = HttpClient(
        base_url="https://api.example.test",
        default_headers={"X-Default": "yes"},
        config=HttpClientConfig(timeout_seconds=3.5),
    )

    result = client.request_json(
        "GET",
        "/search",
        params={"query": "Movie"},
        headers={"X-Request": "one"},
    )

    assert result == {"results": []}


def test_http_client_request_method_signature_compatible(respx_mock):
    """Test that request() method signature is backward compatible."""
    respx_mock.post("https://api.example.test/data").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )

    client = HttpClient(base_url="https://api.example.test")

    # Old signature should still work
    response = client.request(
        "POST",
        "/data",
        params={"key": "value"},
        headers={"X-Custom": "header"},
        json_body={"data": "test"},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
