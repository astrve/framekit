from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, field
from typing import Any

from framekit.core.exceptions import FramekitHttpError

DEFAULT_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
DEFAULT_ACCEPTED_STATUSES = frozenset(range(200, 300))
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_USER_AGENT = "Framekit/1.1.2"
MAX_ERROR_BODY_CHARS = 1200
SENSITIVE_QUERY_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "access_token",
        "auth_token",
        "token",
        "password",
        "secret",
        "client_secret",
    }
)
SENSITIVE_HEADER_KEYS = frozenset({"authorization", "proxy-authorization", "x-api-key"})


@dataclass(slots=True)
class HttpRetryPolicy:
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    retry_statuses: frozenset[int] = DEFAULT_RETRY_STATUSES
    backoff_initial_seconds: float = 0.5
    backoff_factor: float = 2.0
    backoff_max_seconds: float = 10.0

    def delay_for_attempt(self, attempt: int, retry_after: str | None = None) -> float:
        if retry_after:
            parsed = _parse_retry_after_seconds(retry_after)
            if parsed is not None:
                return max(0.0, min(parsed, self.backoff_max_seconds))

        delay = self.backoff_initial_seconds * (self.backoff_factor ** max(attempt - 1, 0))
        return max(0.0, min(delay, self.backoff_max_seconds))


@dataclass(slots=True)
class HttpClientConfig:
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    user_agent: str = DEFAULT_USER_AGENT
    retry_policy: HttpRetryPolicy = field(default_factory=HttpRetryPolicy)


@dataclass(slots=True)
class HttpResponse:
    url: str
    status_code: int
    headers: Mapping[str, str]
    body: bytes

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        try:
            return json.loads(self.text)
        except json.JSONDecodeError as exc:
            raise HttpDecodeError(
                f"HTTP response is not valid JSON: {redact_url(self.url)}",
                url=self.url,
                status_code=self.status_code,
            ) from exc


class HttpError(FramekitHttpError):
    def __init__(
        self,
        message: str,
        *,
        url: str | None = None,
        status_code: int | None = None,
        response_body: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.url = url
        self.status_code = status_code
        self.response_body = response_body
        self.headers = dict(headers or {})


class HttpNetworkError(HttpError):
    """Network-level failure, for example DNS, connection reset, or no route."""


class HttpTimeoutError(HttpNetworkError):
    """HTTP request timed out."""


class HttpStatusError(HttpError):
    """HTTP response had an unexpected status code."""


class HttpAuthError(HttpStatusError):
    """HTTP 401/403 authentication or authorization failure."""


class HttpRateLimitError(HttpStatusError):
    """HTTP 429 rate limit failure."""


class HttpServerError(HttpStatusError):
    """HTTP 5xx server-side failure."""


class HttpDecodeError(HttpError):
    """Response body could not be decoded as expected."""


def _parse_retry_after_seconds(value: str) -> float | None:
    try:
        return float(value.strip())
    except (TypeError, ValueError):
        return None


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return lowered in SENSITIVE_QUERY_KEYS or any(part in lowered for part in SENSITIVE_QUERY_KEYS)


def redact_url(url: str) -> str:
    try:
        parts = urllib.parse.urlsplit(url)
        query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
        redacted_query = [
            (key, "********" if _is_sensitive_key(key) else value) for key, value in query
        ]
        return urllib.parse.urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                urllib.parse.urlencode(redacted_query),
                parts.fragment,
            )
        )
    except Exception:
        return url


def redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {
        key: "********" if key.lower() in SENSITIVE_HEADER_KEYS else value
        for key, value in headers.items()
    }


def _merge_headers(*headers_list: Mapping[str, str] | None) -> dict[str, str]:
    merged: dict[str, str] = {}
    for headers in headers_list:
        if not headers:
            continue
        for key, value in headers.items():
            merged[str(key)] = str(value)
    return merged


def _encode_params(params: Mapping[str, Any] | None) -> str:
    if not params:
        return ""

    normalized: dict[str, str] = {}
    for key, value in params.items():
        if value is None or value == "":
            continue
        if isinstance(value, bool):
            normalized[str(key)] = "true" if value else "false"
        else:
            normalized[str(key)] = str(value)
    return urllib.parse.urlencode(normalized)


def _response_headers(response) -> dict[str, str]:
    try:
        return {key: value for key, value in response.headers.items()}
    except Exception:
        return {}


def _read_error_body(exc: urllib.error.HTTPError) -> str | None:
    try:
        raw = exc.read() or b""
    except Exception:
        return None

    if not raw:
        return None

    text = raw.decode("utf-8", errors="replace").strip()
    if len(text) > MAX_ERROR_BODY_CHARS:
        return text[:MAX_ERROR_BODY_CHARS] + "…"
    return text


def _status_exception(
    *,
    status_code: int,
    url: str,
    headers: Mapping[str, str],
    response_body: str | None,
) -> HttpStatusError:
    redacted_url = redact_url(url)
    message = f"HTTP {status_code} for {redacted_url}"

    kwargs = {
        "url": url,
        "status_code": status_code,
        "headers": headers,
        "response_body": response_body,
    }

    if status_code in {401, 403}:
        return HttpAuthError(message, **kwargs)
    if status_code == 429:
        return HttpRateLimitError(message, **kwargs)
    if 500 <= status_code <= 599:
        return HttpServerError(message, **kwargs)
    return HttpStatusError(message, **kwargs)


class HttpClient:
    def __init__(
        self,
        *,
        base_url: str = "",
        default_headers: Mapping[str, str] | None = None,
        config: HttpClientConfig | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_headers = dict(default_headers or {})
        self.config = config or HttpClientConfig()
        self._sleep = sleep

    def build_url(self, path_or_url: str, params: Mapping[str, Any] | None = None) -> str:
        if path_or_url.startswith(("http://", "https://")):
            base = path_or_url
        elif self.base_url:
            base = f"{self.base_url}/{path_or_url.lstrip('/')}"
        else:
            base = path_or_url

        query_string = _encode_params(params)
        if not query_string:
            return base

        separator = "&" if urllib.parse.urlsplit(base).query else "?"
        return f"{base}{separator}{query_string}"

    def request(
        self,
        method: str,
        path_or_url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        data: bytes | None = None,
        json_body: Any | None = None,
        accepted_statuses: Collection[int] = DEFAULT_ACCEPTED_STATUSES,
    ) -> HttpResponse:
        url = self.build_url(path_or_url, params=params)
        request_headers = _merge_headers(
            {"User-Agent": self.config.user_agent, "Accept": "*/*"},
            self.default_headers,
            headers,
        )

        body = data
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")

        retry_policy = self.config.retry_policy
        max_attempts = max(1, retry_policy.max_attempts)
        accepted = set(accepted_statuses)

        for attempt in range(1, max_attempts + 1):
            request = urllib.request.Request(
                url,
                data=body,
                headers=request_headers,
                method=method.upper(),
            )

            try:
                with urllib.request.urlopen(
                    request,
                    timeout=self.config.timeout_seconds,
                ) as response:
                    status_code = int(getattr(response, "status", response.getcode()))
                    response_body = response.read()
                    headers_dict = _response_headers(response)

                if status_code in accepted:
                    return HttpResponse(
                        url=url,
                        status_code=status_code,
                        headers=headers_dict,
                        body=response_body,
                    )

                if status_code in retry_policy.retry_statuses and attempt < max_attempts:
                    self._sleep(
                        retry_policy.delay_for_attempt(
                            attempt,
                            headers_dict.get("Retry-After"),
                        )
                    )
                    continue

                raise _status_exception(
                    status_code=status_code,
                    url=url,
                    headers=headers_dict,
                    response_body=response_body.decode("utf-8", errors="replace"),
                )

            except urllib.error.HTTPError as exc:
                status_code = int(exc.code)
                headers_dict = _response_headers(exc)
                response_body = _read_error_body(exc)

                if status_code in retry_policy.retry_statuses and attempt < max_attempts:
                    self._sleep(
                        retry_policy.delay_for_attempt(
                            attempt,
                            headers_dict.get("Retry-After"),
                        )
                    )
                    continue

                raise _status_exception(
                    status_code=status_code,
                    url=url,
                    headers=headers_dict,
                    response_body=response_body,
                ) from exc

            except TimeoutError as exc:
                if attempt < max_attempts:
                    self._sleep(retry_policy.delay_for_attempt(attempt))
                    continue
                raise HttpTimeoutError(
                    f"HTTP request timed out for {redact_url(url)}",
                    url=url,
                ) from exc

            except urllib.error.URLError as exc:
                reason = getattr(exc, "reason", exc)
                if isinstance(reason, socket.timeout):
                    error_cls: type[HttpNetworkError] = HttpTimeoutError
                    message = f"HTTP request timed out for {redact_url(url)}"
                else:
                    error_cls = HttpNetworkError
                    message = f"HTTP network error for {redact_url(url)}: {reason}"

                if attempt < max_attempts:
                    self._sleep(retry_policy.delay_for_attempt(attempt))
                    continue

                raise error_cls(message, url=url) from exc

        raise HttpNetworkError(f"HTTP request failed for {redact_url(url)}", url=url)

    def get(
        self,
        path_or_url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        return self.request("GET", path_or_url, params=params, headers=headers)

    def request_json(
        self,
        method: str,
        path_or_url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        json_body: Any | None = None,
    ) -> Any:
        response = self.request(
            method,
            path_or_url,
            params=params,
            headers=_merge_headers({"Accept": "application/json"}, headers),
            json_body=json_body,
        )
        return response.json()

    def get_json(
        self,
        path_or_url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        return self.request_json("GET", path_or_url, params=params, headers=headers)

    def download_bytes(
        self,
        path_or_url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> bytes:
        return self.get(path_or_url, params=params, headers=headers).body
