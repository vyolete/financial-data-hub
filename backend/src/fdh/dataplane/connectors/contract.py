"""Common contract of discovery adapters (contracts/adapter-contract.md).

Adapters are pure: the core performs requests and owns retries, persistence and permissions.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from fdh.domain.datasets import DiscoveredDataset, RejectedRecord
from fdh.domain.sources import DiscoveryQuery


class ErrorKind(StrEnum):
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    INVALID_RESPONSE = "invalid_response"


@dataclass(frozen=True)
class AdapterCapabilities:
    text_search: bool
    declares_total: bool
    cursor_pagination: bool
    supported_filters: tuple[str, ...] = ()
    max_page_size: int | None = None  # None: not established


@dataclass(frozen=True)
class AdapterContext:
    """What an adapter may know about a source. Permissions are deliberately absent."""

    source_id: str
    base_url: str
    page_size: int
    options: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class HttpRequest:
    method: str  # "GET" or "POST"; discovery requests only read
    url: str
    params: Mapping[str, str] = field(default_factory=dict)
    json_body: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.method not in ("GET", "POST"):
            raise ValueError("discovery only sends GET or POST requests")


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


@dataclass(frozen=True)
class DiscoveryPage:
    datasets: tuple[DiscoveredDataset, ...]
    rejected: tuple[RejectedRecord, ...]
    total_declared: int | None
    next_cursor: str | None  # opaque; None means no more results


class InvalidResponse(Exception):
    """Raised when a response as a whole cannot be interpreted."""


class UnsupportedConfiguration(Exception):
    """The configuration asks for something the adapter does not support."""


class DiscoveryAdapter(Protocol):
    platform: str
    capabilities: AdapterCapabilities

    def validate(self, context: AdapterContext, queries: tuple[DiscoveryQuery, ...]) -> None: ...

    def build_request(
        self, context: AdapterContext, query: DiscoveryQuery, cursor: str | None
    ) -> HttpRequest: ...

    def classify(self, response: HttpResponse) -> ErrorKind | None: ...

    def parse(
        self,
        context: AdapterContext,
        request: HttpRequest,
        response: HttpResponse,
        cursor: str | None,
    ) -> DiscoveryPage: ...


def check_capabilities(
    capabilities: AdapterCapabilities,
    context: AdapterContext,
    queries: tuple[DiscoveryQuery, ...],
) -> None:
    """Reject, before any request, a configuration the capabilities cannot satisfy."""
    if capabilities.max_page_size is not None and context.page_size > capabilities.max_page_size:
        raise UnsupportedConfiguration("page_size exceeds the maximum of the platform")
    for query in queries:
        if query.term is not None and not capabilities.text_search:
            raise UnsupportedConfiguration("the platform does not support text search")
        unknown = sorted(set(query.filters) - set(capabilities.supported_filters))
        if unknown:
            raise UnsupportedConfiguration(f"unsupported filters: {', '.join(unknown)}")
