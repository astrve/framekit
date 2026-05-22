from __future__ import annotations

import asyncio
import json
import ssl
import time
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx
from loguru import logger

from framekit.core.exceptions import FramekitHttpError

DEFAULT_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
DEFAULT_ACCEPTED_STATUSES = frozenset(range(200, 300))
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_MAX_ATTEMPTS = 3


def _framekit_user_agent() -> str:
    """Return ``Framekit/<version>`` using the installed package metadata."""
    try:
        from importlib.metadata import PackageNotFoundError
        from importlib.metadata import version as pkg_version
    except ImportError:  # pragma: no cover - importlib.metadata is stdlib >= 3.8
        return "Framekit/unknown"
    try:
        return f"Framekit/{pkg_version('framekit-cli')}"
    except PackageNotFoundError:
        return "Framekit/unknown"


DEFAULT_USER_AGENT = _framekit_user_agent()
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

# Connection pool limits for HTTP/2 multiplexing
DEFAULT_MAX_CONNECTIONS = 100
DEFAULT_MAX_KEEPALIVE_CONNECTIONS = 20


@dataclass(slots=True)
class HttpRetryPolicy:
    """Http retry policy."""

    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    retry_statuses: frozenset[int] = DEFAULT_RETRY_STATUSES
    backoff_initial_seconds: float = 0.5
    backoff_factor: float = 2.0
    backoff_max_seconds: float = 10.0

    def delay_for_attempt(self, attempt: int, retry_after: str | None = None) -> float:
        """Handle delay for attempt."""
        if retry_after:
            parsed = _parse_retry_after_seconds(retry_after)
            if parsed is not None:
                return max(0.0, min(parsed, self.backoff_max_seconds))

        delay = self.backoff_initial_seconds * (self.backoff_factor ** max(attempt - 1, 0))
        return max(0.0, min(delay, self.backoff_max_seconds))


@dataclass(slots=True)
class HttpClientConfig:
    """Configuration for http client."""

    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    user_agent: str = field(default_factory=_framekit_user_agent)
    retry_policy: HttpRetryPolicy = field(default_factory=HttpRetryPolicy)
    verify_ssl: bool = True
    ssl_context: ssl.SSLContext | None = None
    # HTTP/2 and connection pooling settings
    http2: bool = True
    max_connections: int = DEFAULT_MAX_CONNECTIONS
    max_keepalive_connections: int = DEFAULT_MAX_KEEPALIVE_CONNECTIONS


@dataclass(slots=True)
class HttpResponse:
    """Http response."""

    url: str
    status_code: int
    headers: Mapping[str, str]
    body: bytes

    @property
    def text(self) -> str:
        """Handle text."""
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        """Handle json."""
        try:
            return json.loads(self.text)
        except json.JSONDecodeError as exc:
            raise HttpDecodeError(
                f"HTTP response is not valid JSON: {redact_url(self.url)}",
                url=self.url,
                status_code=self.status_code,
            ) from exc


class HttpError(FramekitHttpError):
    """HttpError raised on framekit failures."""

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


class HttpCertificateError(HttpNetworkError):
    """SSL/TLS certificate validation failed."""


def _parse_retry_after_seconds(value: str) -> float | None:
    try:
        return float(value.strip())
    except (TypeError, ValueError):
        return None


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return lowered in SENSITIVE_QUERY_KEYS or any(part in lowered for part in SENSITIVE_QUERY_KEYS)


def redact_url(url: str) -> str:
    """Handle redact url."""
    try:
        from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

        parts = urlsplit(url)
        query = parse_qsl(parts.query, keep_blank_values=True)
        redacted_query = [
            (key, "********" if _is_sensitive_key(key) else value) for key, value in query
        ]
        return urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                urlencode(redacted_query),
                parts.fragment,
            )
        )
    except Exception:
        return url


def redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Handle redact headers."""
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


def _encode_params(params: Mapping[str, Any] | None) -> dict[str, str]:
    if not params:
        return {}

    normalized: dict[str, str] = {}
    for key, value in params.items():
        if value is None or value == "":
            continue
        if isinstance(value, bool):
            normalized[str(key)] = "true" if value else "false"
        else:
            normalized[str(key)] = str(value)
    return normalized


def _status_exception(
    *,
    status_code: int,
    url: str,
    headers: Mapping[str, str],
    response_body: str | None,
) -> HttpStatusError:
    redacted_url = redact_url(url)
    message = f"HTTP {status_code} for {redacted_url}"

    if status_code in {401, 403}:
        return HttpAuthError(
            message, url=url, status_code=status_code, headers=headers, response_body=response_body
        )
    if status_code == 429:
        return HttpRateLimitError(
            message, url=url, status_code=status_code, headers=headers, response_body=response_body
        )
    if 500 <= status_code <= 599:
        return HttpServerError(
            message, url=url, status_code=status_code, headers=headers, response_body=response_body
        )
    return HttpStatusError(
        message, url=url, status_code=status_code, headers=headers, response_body=response_body
    )


def _httpx_to_http_response(response: httpx.Response) -> HttpResponse:
    """Convert httpx.Response to our HttpResponse."""
    return HttpResponse(
        url=str(response.url),
        status_code=response.status_code,
        headers=dict(response.headers),
        body=response.content,
    )


def _is_ssl_error(exc: BaseException) -> bool:
    """Return ``True`` when the exception chain involves an SSL failure.

    ``httpx.ConnectError`` covers DNS, refused connections, network unreachable
    and SSL handshake failures. Only the SSL branch should be reported as a
    certificate error; the rest is generic network failure.
    """
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, ssl.SSLError):
            return True
        if isinstance(current, httpx.ConnectError):
            message = str(current).lower()
            ssl_markers = ("ssl", "certificate", "tls", "handshake")
            if any(marker in message for marker in ssl_markers):
                return True
        current = current.__cause__ or current.__context__
    return False


def _classify_connect_error(exc: httpx.ConnectError, url: str) -> HttpNetworkError:
    """Translate ``httpx.ConnectError`` into the right Framekit exception."""
    redacted = redact_url(url)
    if _is_ssl_error(exc):
        message = f"SSL/TLS handshake failed for {redacted}: {exc}"
        logger.error(message)
        return HttpCertificateError(message, url=url)
    message = f"HTTP connection failed for {redacted}: {exc}"
    return HttpNetworkError(message, url=url)


class HttpClient:
    """HTTP client with HTTP/2 support, connection pooling, and async capabilities.

    Uses httpx for modern HTTP features while maintaining backward compatibility
    with the original urllib-based API.
    """

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

        # Create SSL context
        self._ssl_context = self._create_ssl_context()

        # Create httpx clients (lazy initialization)
        self._sync_client: httpx.Client | None = None
        self._async_client: httpx.AsyncClient | None = None

    def _create_ssl_context(self) -> ssl.SSLContext | None:
        """Create SSL context with certificate validation settings."""
        if self.config.ssl_context:
            return self.config.ssl_context

        if not self.config.verify_ssl:
            # Create unverified context (not recommended for production)
            logger.warning("SSL certificate verification is disabled")
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            return context

        # Create secure context with certificate verification
        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED

        # Set minimum TLS version (TLS 1.2+)
        context.minimum_version = ssl.TLSVersion.TLSv1_2

        return context

    def _get_sync_client(self) -> httpx.Client:
        """Get or create sync httpx client with connection pooling."""
        if self._sync_client is None:
            limits = httpx.Limits(
                max_connections=self.config.max_connections,
                max_keepalive_connections=self.config.max_keepalive_connections,
            )

            verify: ssl.SSLContext | bool = (
                self._ssl_context
                if (self.config.verify_ssl and self._ssl_context is not None)
                else self.config.verify_ssl
            )
            self._sync_client = httpx.Client(
                base_url=self.base_url,
                timeout=self.config.timeout_seconds,
                http2=self.config.http2,
                limits=limits,
                verify=verify,
                follow_redirects=False,  # Security: prevent auth header leakage on redirects
            )
        return self._sync_client

    async def _get_async_client(self) -> httpx.AsyncClient:
        """Get or create async httpx client with connection pooling."""
        if self._async_client is None:
            limits = httpx.Limits(
                max_connections=self.config.max_connections,
                max_keepalive_connections=self.config.max_keepalive_connections,
            )

            verify: ssl.SSLContext | bool = (
                self._ssl_context
                if (self.config.verify_ssl and self._ssl_context is not None)
                else self.config.verify_ssl
            )
            self._async_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.config.timeout_seconds,
                http2=self.config.http2,
                limits=limits,
                verify=verify,
                follow_redirects=False,  # Security: prevent auth header leakage on redirects
            )
        return self._async_client

    def build_url(self, path_or_url: str, params: Mapping[str, Any] | None = None) -> str:
        """Build full URL from path and parameters."""
        if path_or_url.startswith(("http://", "https://")):
            base = path_or_url
        elif self.base_url:
            base = f"{self.base_url}/{path_or_url.lstrip('/')}"
        else:
            base = path_or_url

        # httpx handles params internally, but we need this for URL building
        if params:
            from urllib.parse import urlencode, urlsplit, urlunsplit

            parts = urlsplit(base)
            query_params = _encode_params(params)
            if query_params:
                existing_query = parts.query
                new_query = urlencode(query_params)
                combined_query = f"{existing_query}&{new_query}" if existing_query else new_query
                return urlunsplit(
                    (parts.scheme, parts.netloc, parts.path, combined_query, parts.fragment)
                )

        return base

    def _should_retry(self, exc: Exception, attempt: int) -> bool:
        """Determine if request should be retried based on exception."""
        retry_policy = self.config.retry_policy

        if attempt >= retry_policy.max_attempts:
            return False

        # Retry on network errors
        if isinstance(exc, (httpx.NetworkError, httpx.TimeoutException)):
            return True

        # Retry on specific HTTP status codes
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in retry_policy.retry_statuses

        return False

    def _request_headers(self, headers: Mapping[str, str] | None) -> dict[str, str]:
        return _merge_headers(
            {"User-Agent": self.config.user_agent, "Accept": "*/*"},
            self.default_headers,
            headers,
        )

    @staticmethod
    def _resolve_request_body(
        data: bytes | dict[str, Any] | None,
        json_body: Any | None,
        request_headers: dict[str, str],
    ) -> bytes | dict[str, Any] | None:
        if json_body is None:
            return data
        request_headers.setdefault("Content-Type", "application/json")
        return json.dumps(json_body).encode("utf-8")

    @staticmethod
    def _base_request_kwargs(
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        params: Mapping[str, Any] | None,
        timeout: float | None,
    ) -> dict[str, Any]:
        request_kwargs: dict[str, Any] = {
            "method": method.upper(),
            "url": url,
            "headers": headers,
            "params": _encode_params(params) if params else None,
        }
        if timeout is not None:
            request_kwargs["timeout"] = timeout
        return request_kwargs

    @staticmethod
    def _with_body_kwargs(
        request_kwargs: dict[str, Any],
        *,
        body: bytes | dict[str, Any] | None,
        files: Any | None,
    ) -> dict[str, Any]:
        if files is not None:
            request_kwargs["files"] = files
            if isinstance(body, dict):
                request_kwargs["data"] = body
            return request_kwargs
        if isinstance(body, dict):
            request_kwargs["data"] = body
        elif body is not None:
            request_kwargs["content"] = body
        return request_kwargs

    def _should_retry_status(self, status_code: int, attempt: int, max_attempts: int) -> bool:
        retry_policy = self.config.retry_policy
        return status_code in retry_policy.retry_statuses and attempt < max_attempts

    def _wait_before_retry(self, attempt: int, retry_after: str | None = None) -> None:
        retry_policy = self.config.retry_policy
        self._sleep(retry_policy.delay_for_attempt(attempt, retry_after))

    @staticmethod
    def _raise_status_from_response(url: str, response: httpx.Response) -> None:
        raise _status_exception(
            status_code=response.status_code,
            url=url,
            headers=dict(response.headers),
            response_body=response.text[:MAX_ERROR_BODY_CHARS] if response.text else None,
        )

    def _handle_timeout_exception(
        self,
        *,
        attempt: int,
        max_attempts: int,
        exc: httpx.TimeoutException,
        url: str,
    ) -> HttpResponse | None:
        if attempt < max_attempts:
            self._wait_before_retry(attempt)
            return None
        raise HttpTimeoutError(
            f"HTTP request timed out for {redact_url(url)}",
            url=url,
        ) from exc

    def _handle_http_status_exception(
        self,
        *,
        attempt: int,
        max_attempts: int,
        exc: httpx.HTTPStatusError,
        url: str,
    ) -> HttpResponse | None:
        status_code = exc.response.status_code
        if self._should_retry_status(status_code, attempt, max_attempts):
            retry_after = exc.response.headers.get("Retry-After")
            self._wait_before_retry(attempt, retry_after)
            return None
        raise _status_exception(
            status_code=status_code,
            url=url,
            headers=dict(exc.response.headers),
            response_body=exc.response.text[:MAX_ERROR_BODY_CHARS] if exc.response.text else None,
        ) from exc

    def _handle_network_exception(
        self,
        *,
        attempt: int,
        max_attempts: int,
        exc: httpx.NetworkError,
        url: str,
    ) -> HttpResponse | None:
        if attempt < max_attempts:
            self._wait_before_retry(attempt)
            return None
        message = f"HTTP network error for {redact_url(url)}: {exc}"
        raise HttpNetworkError(message, url=url) from exc

    def _attempt_sync_request(
        self,
        *,
        client: httpx.Client,
        method: str,
        url: str,
        request_headers: Mapping[str, str],
        params: Mapping[str, Any] | None,
        body: bytes | dict[str, Any] | None,
        files: Any | None,
        timeout: float | None,
        accepted: set[int],
        attempt: int,
        max_attempts: int,
    ) -> HttpResponse | None:
        try:
            request_kwargs = self._base_request_kwargs(
                method=method,
                url=url,
                headers=request_headers,
                params=params,
                timeout=timeout,
            )
            request_kwargs = self._with_body_kwargs(
                request_kwargs,
                body=body,
                files=files,
            )
            response = client.request(**request_kwargs)
            if response.status_code in accepted:
                return _httpx_to_http_response(response)
            if self._should_retry_status(response.status_code, attempt, max_attempts):
                retry_after = response.headers.get("Retry-After")
                self._wait_before_retry(attempt, retry_after)
                return None
            self._raise_status_from_response(url, response)
        except httpx.TimeoutException as exc:
            return self._handle_timeout_exception(
                attempt=attempt,
                max_attempts=max_attempts,
                exc=exc,
                url=url,
            )
        except httpx.HTTPStatusError as exc:
            return self._handle_http_status_exception(
                attempt=attempt,
                max_attempts=max_attempts,
                exc=exc,
                url=url,
            )
        except httpx.ConnectError as exc:
            raise _classify_connect_error(exc, url) from exc
        except httpx.NetworkError as exc:
            return self._handle_network_exception(
                attempt=attempt,
                max_attempts=max_attempts,
                exc=exc,
                url=url,
            )
        return None

    async def _async_retry_sleep(self, attempt: int, retry_after: str | None = None) -> None:
        retry_policy = self.config.retry_policy
        await asyncio.sleep(retry_policy.delay_for_attempt(attempt, retry_after))

    async def _attempt_async_request(
        self,
        *,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        request_headers: Mapping[str, str],
        params: Mapping[str, Any] | None,
        body: bytes | None,
        accepted: set[int],
        attempt: int,
        max_attempts: int,
    ) -> HttpResponse | None:
        retry_policy = self.config.retry_policy
        try:
            response = await client.request(
                method=method.upper(),
                url=url,
                headers=request_headers,
                content=body,
                params=_encode_params(params) if params else None,
            )
            return await self._handle_async_response(
                response=response,
                accepted=accepted,
                retry_policy=retry_policy,
                attempt=attempt,
                max_attempts=max_attempts,
                url=url,
            )
        except httpx.TimeoutException as exc:
            return await self._handle_async_timeout(
                attempt=attempt,
                max_attempts=max_attempts,
                url=url,
                exc=exc,
            )
        except httpx.HTTPStatusError as exc:
            return await self._handle_async_http_status_exception(
                attempt=attempt,
                max_attempts=max_attempts,
                retry_policy=retry_policy,
                url=url,
                exc=exc,
            )
        except httpx.ConnectError as exc:
            raise _classify_connect_error(exc, url) from exc
        except httpx.NetworkError as exc:
            return await self._handle_async_network_error(
                attempt=attempt,
                max_attempts=max_attempts,
                url=url,
                exc=exc,
            )

    async def _handle_async_response(
        self,
        *,
        response: httpx.Response,
        accepted: set[int],
        retry_policy: HttpRetryPolicy,
        attempt: int,
        max_attempts: int,
        url: str,
    ) -> HttpResponse | None:
        if response.status_code in accepted:
            return _httpx_to_http_response(response)
        if response.status_code in retry_policy.retry_statuses and attempt < max_attempts:
            retry_after = response.headers.get("Retry-After")
            await self._async_retry_sleep(attempt, retry_after)
            return None
        raise _status_exception(
            status_code=response.status_code,
            url=url,
            headers=dict(response.headers),
            response_body=response.text[:MAX_ERROR_BODY_CHARS] if response.text else None,
        )

    async def _handle_async_timeout(
        self,
        *,
        attempt: int,
        max_attempts: int,
        url: str,
        exc: httpx.TimeoutException,
    ) -> HttpResponse | None:
        if attempt < max_attempts:
            await self._async_retry_sleep(attempt)
            return None
        raise HttpTimeoutError(
            f"HTTP request timed out for {redact_url(url)}",
            url=url,
        ) from exc

    async def _handle_async_http_status_exception(
        self,
        *,
        attempt: int,
        max_attempts: int,
        retry_policy: HttpRetryPolicy,
        url: str,
        exc: httpx.HTTPStatusError,
    ) -> HttpResponse | None:
        status_code = exc.response.status_code
        if status_code in retry_policy.retry_statuses and attempt < max_attempts:
            retry_after = exc.response.headers.get("Retry-After")
            await self._async_retry_sleep(attempt, retry_after)
            return None
        raise _status_exception(
            status_code=status_code,
            url=url,
            headers=dict(exc.response.headers),
            response_body=exc.response.text[:MAX_ERROR_BODY_CHARS] if exc.response.text else None,
        ) from exc

    async def _handle_async_network_error(
        self,
        *,
        attempt: int,
        max_attempts: int,
        url: str,
        exc: httpx.NetworkError,
    ) -> HttpResponse | None:
        if attempt < max_attempts:
            await self._async_retry_sleep(attempt)
            return None
        message = f"HTTP network error for {redact_url(url)}: {exc}"
        raise HttpNetworkError(message, url=url) from exc

    def request(
        self,
        method: str,
        path_or_url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        data: bytes | dict[str, Any] | None = None,
        json_body: Any | None = None,
        files: Any | None = None,
        accepted_statuses: Collection[int] = DEFAULT_ACCEPTED_STATUSES,
        timeout: float | None = None,
    ) -> HttpResponse:
        """Make a synchronous HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            path_or_url: Path or full URL
            params: Query parameters
            headers: Request headers
            data: Raw request body (bytes) or form data (dict)
            json_body: JSON request body (mutually exclusive with data)
            files: Multipart file upload dict (e.g., {"file": ("name.txt", file_obj, "text/plain")})
            accepted_statuses: HTTP status codes considered successful
            timeout: Per-request timeout in seconds. If None, uses client-level timeout.

        Returns:
            HttpResponse object

        Raises:
            HttpError: On request failure after retries
        """
        url = self.build_url(path_or_url, params=params)
        request_headers = self._request_headers(headers)
        body = self._resolve_request_body(data, json_body, request_headers)

        retry_policy = self.config.retry_policy
        max_attempts = max(1, retry_policy.max_attempts)
        accepted = set(accepted_statuses)
        client = self._get_sync_client()

        for attempt in range(1, max_attempts + 1):
            maybe_response = self._attempt_sync_request(
                client=client,
                method=method,
                url=url,
                request_headers=request_headers,
                params=params,
                body=body,
                files=files,
                timeout=timeout,
                accepted=accepted,
                attempt=attempt,
                max_attempts=max_attempts,
            )
            if maybe_response is not None:
                return maybe_response

        raise HttpNetworkError(f"HTTP request failed for {redact_url(url)}", url=url)

    async def async_request(
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
        """Make an asynchronous HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            path_or_url: Path or full URL
            params: Query parameters
            headers: Request headers
            data: Raw request body
            json_body: JSON request body (mutually exclusive with data)
            accepted_statuses: HTTP status codes considered successful

        Returns:
            HttpResponse object

        Raises:
            HttpError: On request failure after retries
        """
        url = self.build_url(path_or_url, params=params)
        request_headers = self._request_headers(headers)
        body = self._resolve_request_body(data, json_body, request_headers)
        request_content = body if isinstance(body, bytes) else None

        retry_policy = self.config.retry_policy
        max_attempts = max(1, retry_policy.max_attempts)
        accepted = set(accepted_statuses)
        client = await self._get_async_client()

        for attempt in range(1, max_attempts + 1):
            maybe_response = await self._attempt_async_request(
                client=client,
                method=method,
                url=url,
                request_headers=request_headers,
                params=params,
                body=request_content,
                accepted=accepted,
                attempt=attempt,
                max_attempts=max_attempts,
            )
            if maybe_response is not None:
                return maybe_response

        raise HttpNetworkError(f"HTTP request failed for {redact_url(url)}", url=url)

    def get(
        self,
        path_or_url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse:
        """Make a synchronous GET request."""
        return self.request("GET", path_or_url, params=params, headers=headers, timeout=timeout)

    async def async_get(
        self,
        path_or_url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        """Make an asynchronous GET request."""
        return await self.async_request("GET", path_or_url, params=params, headers=headers)

    def post(
        self,
        path_or_url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        data: bytes | dict[str, Any] | None = None,
        json_body: Any | None = None,
        files: Any | None = None,
        timeout: float | None = None,
    ) -> HttpResponse:
        """Make a synchronous POST request."""
        return self.request(
            "POST",
            path_or_url,
            params=params,
            headers=headers,
            data=data,
            json_body=json_body,
            files=files,
            timeout=timeout,
        )

    def request_json(
        self,
        method: str,
        path_or_url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        json_body: Any | None = None,
    ) -> Any:
        """Make a synchronous request and parse JSON response."""
        response = self.request(
            method,
            path_or_url,
            params=params,
            headers=_merge_headers({"Accept": "application/json"}, headers),
            json_body=json_body,
        )
        return response.json()

    async def async_request_json(
        self,
        method: str,
        path_or_url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        json_body: Any | None = None,
    ) -> Any:
        """Make an asynchronous request and parse JSON response."""
        response = await self.async_request(
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
        """Make a synchronous GET request and parse JSON response."""
        return self.request_json("GET", path_or_url, params=params, headers=headers)

    def download_bytes(
        self,
        path_or_url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> bytes:
        """Download content as bytes (synchronous)."""
        return self.get(path_or_url, params=params, headers=headers).body

    def close(self) -> None:
        """Close synchronous client and release resources."""
        if self._sync_client is not None:
            self._sync_client.close()
            self._sync_client = None

    async def aclose(self) -> None:
        """Close asynchronous client and release resources."""
        if self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, _exc_val, _exc_tb):
        """Context manager exit."""
        self.close()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, _exc_val, _exc_tb):
        """Async context manager exit."""
        await self.aclose()
