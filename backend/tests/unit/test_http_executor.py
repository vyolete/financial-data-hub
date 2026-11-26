"""Network policy of discovery requests with a synthetic transport (AC-22, AC-23, AC-24).

No request leaves the process. Waits are recorded instead of slept.
"""

import asyncio
import io
import itertools
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime

import httpx
import pytest

from fdh.dataplane.connectors.contract import ErrorKind, HttpRequest, HttpResponse
from fdh.dataplane.discovery.http import MAX_RESPONSE_BYTES, HttpExecutor, RequestFailed
from fdh.dataplane.discovery.retry import backoff_delay, parse_retry_after
from fdh.domain.sources import DiscoveryLimits
from fdh.observability.logging import configure_logging

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
URL = "https://api.example.org/catalog"
REQUEST = HttpRequest("GET", URL, {"q": "budget", "scroll_id": ""})


def accept(_: HttpResponse) -> ErrorKind | None:
    return None


class Harness:
    """An executor over a scripted transport. The last step of the script repeats."""

    def __init__(
        self,
        *script: object,
        limits: DiscoveryLimits | None = None,
        secret_headers: dict[str, str] | None = None,
    ) -> None:
        self.script = list(script)
        self.requests: list[httpx.Request] = []
        self.waits: list[float] = []
        self.time = 100.0  # advances only with the recorded waits
        self.starts: list[float] = []
        self.client = httpx.AsyncClient(transport=httpx.MockTransport(self._handle), timeout=None)  # noqa: S113
        self.executor = HttpExecutor(
            self.client,
            allowed_hosts=("api.example.org",),
            limits=limits or DiscoveryLimits(),
            sleep=self._sleep,
            now=lambda: NOW,
            monotonic=lambda: self.time,
            secret_headers=secret_headers,
        )

    async def _sleep(self, seconds: float) -> None:
        self.waits.append(seconds)
        self.time += seconds

    async def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        self.starts.append(self.time)
        step = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(step, Exception):
            raise step
        if callable(step):
            result = await step()
            assert isinstance(result, httpx.Response)
            return result
        assert isinstance(step, httpx.Response)
        return httpx.Response(step.status_code, headers=step.headers, content=step.content)

    async def failure(
        self,
        request: HttpRequest = REQUEST,
        classify: Callable[[HttpResponse], ErrorKind | None] = accept,
    ) -> RequestFailed:
        with pytest.raises(RequestFailed) as caught:
            await self.executor.execute(request, classify)
        return caught.value


def status(code: int, **headers: str) -> httpx.Response:
    return httpx.Response(code, headers={k.replace("_", "-"): v for k, v in headers.items()})


OK = httpx.Response(200, content=b"{}")


async def test_success_returns_the_response_and_the_requested_url() -> None:
    harness = Harness(OK)
    result = await harness.executor.execute(REQUEST, accept)
    assert (result.response.status, result.response.body, result.attempts) == (200, b"{}", 1)
    assert result.url == f"{URL}?q=budget&scroll_id="
    assert harness.executor.requests_sent == 1
    assert harness.waits == []


async def test_post_sends_the_json_body() -> None:
    harness = Harness(OK)
    await harness.executor.execute(HttpRequest("POST", URL, json_body={"top": 1}), accept)
    assert harness.requests[0].method == "POST"
    assert harness.requests[0].content == b'{"top":1}'


@pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
async def test_retryable_status_is_attempted_four_times_with_growing_waits(code: int) -> None:
    harness = Harness(status(code))
    error = await harness.failure()
    assert (error.http_status, error.attempts, error.stop_run) == (code, 4, False)
    assert error.code == ("rate_limited" if code == 429 else "http_error")
    assert len(harness.requests) == harness.executor.requests_sent == 4
    assert harness.waits == [1, 2, 4]


@pytest.mark.parametrize("code", [400, 401, 403, 404, 418, 501])
async def test_other_errors_are_attempted_once(code: int) -> None:
    harness = Harness(status(code, retry_after="1"))
    error = await harness.failure(classify=lambda _: ErrorKind.TRANSIENT)
    assert (error.code, error.http_status, error.attempts) == ("http_error", code, 1)
    assert len(harness.requests) == 1
    assert harness.waits == []


async def test_an_adapter_can_declare_a_retryable_status_permanent() -> None:
    harness = Harness(status(500))
    error = await harness.failure(classify=lambda _: ErrorKind.PERMANENT)
    assert error.attempts == 1


@pytest.mark.parametrize(
    ("kind", "code"),
    [
        (ErrorKind.PERMANENT, "provider_error"),
        (ErrorKind.TRANSIENT, "provider_error"),
        (ErrorKind.INVALID_RESPONSE, "invalid_response"),
    ],
)
async def test_an_adapter_error_on_success_status_is_not_retried(
    kind: ErrorKind, code: str
) -> None:
    harness = Harness(OK)
    error = await harness.failure(classify=lambda _: kind)
    assert (error.code, error.attempts, len(harness.requests)) == (code, 1, 1)


async def test_recovers_after_a_transient_failure() -> None:
    harness = Harness(httpx.ConnectError("synthetic"), status(503), OK)
    result = await harness.executor.execute(REQUEST, accept)
    assert result.attempts == 3
    assert harness.waits == [1, 2]


async def test_connection_failures_are_retried() -> None:
    harness = Harness(httpx.ConnectError("synthetic secret=abc"))
    error = await harness.failure()
    assert (error.code, error.http_status, error.attempts) == ("connection_error", None, 4)
    assert "abc" not in str(error)


async def test_retry_after_raises_the_wait_but_never_lowers_it() -> None:
    harness = Harness(status(429, retry_after="3"), status(429, retry_after="0"), OK)
    await harness.executor.execute(REQUEST, accept)
    assert harness.waits == [3, 2]


async def test_retry_after_accepts_an_http_date() -> None:
    harness = Harness(status(503, retry_after="Thu, 01 Jan 2026 12:00:30 GMT"), OK)
    await harness.executor.execute(REQUEST, accept)
    assert harness.waits == [30]


async def test_retry_after_of_sixty_seconds_is_honoured() -> None:
    harness = Harness(status(429, retry_after="60"), OK)
    await harness.executor.execute(REQUEST, accept)
    assert harness.waits == [60]


@pytest.mark.parametrize("value", ["61", "Thu, 01 Jan 2026 12:02:00 GMT"])
async def test_a_longer_retry_after_stops_without_retrying(value: str) -> None:
    harness = Harness(status(429, retry_after=value))
    error = await harness.failure()
    assert (error.code, error.http_status, error.attempts, error.stop_run) == (
        "retry_after_too_long",
        429,
        1,
        True,
    )
    assert harness.waits == []


async def test_a_pending_retry_after_delays_the_next_request() -> None:
    limits = DiscoveryLimits(max_retries=0)
    harness = Harness(status(429, retry_after="7"), OK, limits=limits)
    await harness.failure()
    assert harness.waits == []
    await harness.executor.execute(REQUEST, accept)
    assert harness.waits == [7]


async def test_each_attempt_has_a_deadline() -> None:
    async def never() -> httpx.Response:
        await asyncio.sleep(30)
        return httpx.Response(200)

    harness = Harness(never, limits=DiscoveryLimits(attempt_timeout_s=0.02))
    error = await harness.failure()
    assert (error.code, error.attempts) == ("timeout", 4)
    assert harness.waits == [1, 2, 4]


class SlowBody(httpx.AsyncByteStream):
    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield b"{"
        await asyncio.sleep(30)
        yield b"}"


async def test_the_deadline_includes_reading_the_body() -> None:
    async def headers_then_stall() -> httpx.Response:
        return httpx.Response(200, stream=SlowBody())

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: headers_then_stall()),
        timeout=None,  # noqa: S113
    )
    executor = HttpExecutor(
        client,
        allowed_hosts=("api.example.org",),
        limits=DiscoveryLimits(attempt_timeout_s=0.02, max_retries=0),
    )
    with pytest.raises(RequestFailed) as caught:
        await executor.execute(REQUEST, accept)
    assert caught.value.code == "timeout"


def test_the_default_deadline_and_retries_are_the_specified_ones() -> None:
    limits = DiscoveryLimits()
    assert (limits.attempt_timeout_s, limits.max_retries, limits.max_retry_after_s) == (10, 3, 60)


@pytest.mark.parametrize(
    "url",
    [
        "https://other.example.org/catalog",
        "http://api.example.org/catalog",
        "https://api.example.org.attacker.test/catalog",
        "https://user:pass@api.example.org/catalog",
        "https://api.example.org@attacker.test/catalog",
    ],
)
async def test_only_allowed_https_hosts_are_requested(url: str) -> None:
    harness = Harness(OK)
    error = await harness.failure(HttpRequest("GET", url))
    assert (error.code, error.attempts) == ("host_not_allowed", 0)
    assert harness.requests == []
    assert harness.executor.requests_sent == 0


@pytest.mark.parametrize("code", [301, 302, 307, 308])
async def test_redirects_are_rejected_and_not_followed(code: int) -> None:
    harness = Harness(status(code, location="https://attacker.test/"))
    error = await harness.failure()
    assert (error.code, error.http_status, error.attempts) == ("redirect_rejected", code, 1)
    assert [str(r.url.host) for r in harness.requests] == ["api.example.org"]


async def test_an_oversized_response_is_a_permanent_error() -> None:
    harness = Harness(httpx.Response(200, content=b"x" * (MAX_RESPONSE_BYTES + 1)))
    error = await harness.failure()
    assert (error.code, error.attempts) == ("response_too_large", 1)


class Endless(httpx.AsyncByteStream):
    async def __aiter__(self) -> AsyncIterator[bytes]:
        while True:
            yield b"x" * 1_000_000


async def test_the_size_limit_applies_without_a_declared_length() -> None:
    async def endless() -> httpx.Response:
        return httpx.Response(200, stream=Endless())

    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: endless()), timeout=None)  # noqa: S113
    executor = HttpExecutor(client, allowed_hosts=("api.example.org",), limits=DiscoveryLimits())
    with pytest.raises(RequestFailed) as caught:
        await executor.execute(REQUEST, accept)
    assert caught.value.code == "response_too_large"


async def test_a_response_at_the_limit_is_accepted() -> None:
    harness = Harness(httpx.Response(200, content=b"x" * MAX_RESPONSE_BYTES))
    result = await harness.executor.execute(REQUEST, accept)
    assert len(result.response.body) == MAX_RESPONSE_BYTES


async def test_logs_hide_credentials_and_bodies() -> None:
    stream = io.StringIO()
    configure_logging("INFO", stream)
    harness = Harness(httpx.Response(500, content=b"private-body-marker"))
    request = HttpRequest("GET", URL, {"$$app_token": "fake-token-123456"})
    error = await harness.failure(request)
    logged = stream.getvalue()
    assert '"event": "request_attempt_failed"' in logged
    for hidden in ("fake-token-123456", "private-body-marker"):
        assert hidden not in logged
        assert hidden not in str(error)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        ("soon", None),
        ("-1", None),
        ("1.5", None),
        ("0", 0),
        (" 12 ", 12),
        ("Thu, 01 Jan 2026 12:00:05 GMT", 5),
        ("Thu, 01 Jan 2026 11:00:00 GMT", 0),
    ],
)
def test_parse_retry_after(value: str | None, expected: float | None) -> None:
    assert parse_retry_after(value, now=NOW) == expected


def test_backoff_doubles_and_respects_the_provider() -> None:
    assert [backoff_delay(n, None) for n in (1, 2, 3)] == [1, 2, 4]
    assert backoff_delay(1, 9) == 9
    assert backoff_delay(3, 1) == 4


async def test_consecutive_requests_are_spaced_by_the_minimum_interval() -> None:
    harness = Harness(OK, limits=DiscoveryLimits(min_request_interval_s=5))
    await harness.executor.execute(REQUEST, accept)
    assert harness.waits == []
    harness.time += 2  # the caller spent two seconds before the next request
    await harness.executor.execute(REQUEST, accept)
    harness.time += 9
    await harness.executor.execute(REQUEST, accept)
    assert harness.waits == [3]
    assert harness.starts == [100, 105, 114]


async def test_retries_also_respect_the_minimum_interval() -> None:
    harness = Harness(status(503), limits=DiscoveryLimits(min_request_interval_s=3))
    await harness.failure()
    gaps = [later - earlier for earlier, later in itertools.pairwise(harness.starts)]
    assert gaps == [3, 3, 4]  # backoff of 1, 2 and 4 seconds, never below the interval
    assert harness.waits == [1, 2, 2, 1, 4]


async def test_the_interval_can_be_disabled() -> None:
    harness = Harness(OK, limits=DiscoveryLimits(min_request_interval_s=0))
    await harness.executor.execute(REQUEST, accept)
    await harness.executor.execute(REQUEST, accept)
    assert harness.waits == []


def test_the_default_interval_is_one_second() -> None:
    assert DiscoveryLimits().min_request_interval_s == 1.0


TOKEN = "fake-app-token-0123456789"


async def test_the_application_token_travels_only_in_its_header() -> None:
    harness = Harness(OK, secret_headers={"X-App-Token": TOKEN})
    result = await harness.executor.execute(REQUEST, accept)
    assert harness.requests[0].headers["x-app-token"] == TOKEN
    assert TOKEN not in result.url
    assert TOKEN not in repr(result)


async def test_without_a_token_no_token_header_is_sent() -> None:
    harness = Harness(OK)
    await harness.executor.execute(REQUEST, accept)
    assert "x-app-token" not in harness.requests[0].headers


async def test_the_token_never_reaches_a_refused_host_or_a_redirect() -> None:
    harness = Harness(
        status(302, location="https://attacker.test/"), secret_headers={"X-App-Token": TOKEN}
    )
    await harness.failure(HttpRequest("GET", "https://attacker.test/catalog"))
    assert harness.requests == []
    await harness.failure()
    assert [r.url.host for r in harness.requests] == ["api.example.org"]


async def test_the_token_is_absent_from_debug_logs_and_errors() -> None:
    stream = io.StringIO()
    configure_logging("DEBUG", stream)
    harness = Harness(status(500), secret_headers={"X-App-Token": TOKEN})
    error = await harness.failure()
    assert stream.getvalue()
    assert TOKEN not in stream.getvalue()
    assert TOKEN not in str(error)
    assert TOKEN not in repr(harness.executor)
