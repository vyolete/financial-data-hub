"""The only component that sends discovery requests.

It enforces the allowed hosts, the deadline of each attempt, the retry policy and the size
limit for every platform. Errors carry fixed messages: never URLs, headers or bodies.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from fdh.dataplane.connectors.contract import ErrorKind, HttpRequest, HttpResponse
from fdh.dataplane.discovery.retry import RETRYABLE_STATUSES, backoff_delay, parse_retry_after
from fdh.domain.locators import is_https_url
from fdh.domain.sources import DiscoveryLimits

MAX_RESPONSE_BYTES = 10 * 1024 * 1024
log = logging.getLogger(__name__)

Classify = Callable[[HttpResponse], ErrorKind | None]


@dataclass(frozen=True)
class RequestResult:
    response: HttpResponse
    attempts: int
    url: str  # the requested URL with its parameters


class RequestFailed(Exception):
    """A request that produced no usable response.

    ``stop_run`` asks to send nothing else to this provider during the current run.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        http_status: int | None = None,
        attempts: int = 0,
        stop_run: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.attempts = attempts
        self.stop_run = stop_run


@dataclass(frozen=True)
class _Failure:
    code: str
    message: str
    http_status: int | None = None
    retryable: bool = False
    retry_after: float | None = None


class HttpExecutor:
    """Executes the requests of one source. The clock and the waits can be replaced."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        allowed_hosts: tuple[str, ...],
        limits: DiscoveryLimits,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._client = client
        self._hosts = frozenset(host.casefold() for host in allowed_hosts)
        self._limits = limits
        self._sleep = sleep
        self._now = now
        self._pending_wait = 0.0
        self.requests_sent = 0  # attempts, retries included

    async def execute(self, request: HttpRequest, classify: Classify) -> RequestResult:
        url = self._allowed_url(request)
        if self._pending_wait:
            # The provider asked to wait when the previous request was abandoned.
            wait, self._pending_wait = self._pending_wait, 0.0
            await self._sleep(wait)
        attempt = 0
        while True:
            attempt += 1
            self.requests_sent += 1
            outcome = await self._attempt(request, url, classify)
            if isinstance(outcome, HttpResponse):
                return RequestResult(outcome, attempt, str(url))
            too_long = (
                outcome.retry_after is not None
                and outcome.retry_after > self._limits.max_retry_after_s
            )
            retry = outcome.retryable and not too_long and attempt <= self._limits.max_retries
            delay = backoff_delay(attempt, outcome.retry_after) if retry else None
            log.warning(
                "request attempt failed",
                extra={
                    "event": "request_attempt_failed",
                    "code": outcome.code,
                    "http_status": outcome.http_status,
                    "attempt": attempt,
                    "host": url.host,
                    "retry_in_s": delay,
                },
            )
            if delay is not None:
                await self._sleep(delay)
                continue
            if too_long:
                raise RequestFailed(
                    "retry_after_too_long",
                    "the provider asked to wait longer than the accepted maximum",
                    http_status=outcome.http_status,
                    attempts=attempt,
                    stop_run=True,
                )
            self._pending_wait = outcome.retry_after or 0.0
            raise RequestFailed(
                outcome.code,
                outcome.message,
                http_status=outcome.http_status,
                attempts=attempt,
            )

    def _allowed_url(self, request: HttpRequest) -> httpx.URL:
        refused = RequestFailed(
            "host_not_allowed", "the request targets a host that is not allowed"
        )
        if not is_https_url(request.url):
            raise refused
        try:
            url = httpx.URL(request.url)
            if request.params:
                url = url.copy_merge_params(dict(request.params))
        except httpx.InvalidURL:
            raise refused from None
        # Checked on the parsed URL that will be sent, not on the configured text.
        if url.scheme != "https" or url.userinfo or url.host.casefold() not in self._hosts:
            raise refused
        return url

    async def _attempt(
        self, request: HttpRequest, url: httpx.URL, classify: Classify
    ) -> HttpResponse | _Failure:
        try:
            async with asyncio.timeout(self._limits.attempt_timeout_s):
                return await self._send(request, url, classify)
        except (TimeoutError, httpx.TimeoutException):
            return _Failure("timeout", "the attempt exceeded its deadline", retryable=True)
        except httpx.TransportError:
            return _Failure("connection_error", "the connection failed", retryable=True)
        except httpx.HTTPError:
            return _Failure("invalid_response", "the response could not be decoded")

    async def _send(
        self, request: HttpRequest, url: httpx.URL, classify: Classify
    ) -> HttpResponse | _Failure:
        body = None if request.json_body is None else dict(request.json_body)
        async with self._client.stream(
            request.method, url, json=body, follow_redirects=False
        ) as answer:
            status = answer.status_code
            headers = dict(answer.headers)
            if 300 <= status < 400:
                return _Failure("redirect_rejected", "redirects are not followed", status)
            if not 200 <= status < 300:
                # The body of an error is neither needed nor read.
                response = HttpResponse(status, headers, b"")
                retryable = (
                    status in RETRYABLE_STATUSES and classify(response) is not ErrorKind.PERMANENT
                )
                return _Failure(
                    "rate_limited" if status == 429 else "http_error",
                    f"the provider answered with HTTP status {status}",
                    status,
                    retryable=retryable,
                    retry_after=parse_retry_after(
                        answer.headers.get("retry-after"), now=self._now()
                    )
                    if status in RETRYABLE_STATUSES
                    else None,
                )
            content = bytearray()
            async for chunk in answer.aiter_bytes():
                content += chunk
                if len(content) > MAX_RESPONSE_BYTES:
                    return _Failure(
                        "response_too_large", "the response exceeds the size limit", status
                    )
        response = HttpResponse(status, headers, bytes(content))
        kind = classify(response)
        if kind is None:
            return response
        if kind is ErrorKind.INVALID_RESPONSE:
            return _Failure("invalid_response", "the response was not valid", status)
        return _Failure("provider_error", "the provider reported an error", status)
