from urllib.parse import parse_qs, urlparse

from framekit.core.http import HttpClient, HttpRetryPolicy, redact_headers, redact_url


def test_redact_url_masks_sensitive_query_values():
    url = "https://example.test/path?api_key=secret&page=1&access_token=tok"

    redacted = redact_url(url)
    query = parse_qs(urlparse(redacted).query)

    assert query["api_key"] == ["********"]
    assert query["access_token"] == ["********"]
    assert query["page"] == ["1"]


def test_redact_headers_masks_authorization():
    headers = redact_headers({"Authorization": "Bearer secret", "Accept": "application/json"})

    assert headers["Authorization"] == "********"
    assert headers["Accept"] == "application/json"


def test_http_client_build_url_skips_empty_params_and_encodes_bool():
    client = HttpClient(base_url="https://example.test/api")

    url = client.build_url("/search", {"query": "Moonlight", "include_adult": False, "empty": ""})

    assert url == "https://example.test/api/search?query=Moonlight&include_adult=false"


def test_retry_policy_uses_retry_after_header():
    policy = HttpRetryPolicy(backoff_max_seconds=10)

    assert policy.delay_for_attempt(1, "2") == 2
