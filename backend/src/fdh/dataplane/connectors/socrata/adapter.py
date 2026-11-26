"""Translate between the common contract and the Socrata Discovery API.

Reference: https://dev.socrata.com/docs/other/discovery (reviewed 2026-11-26, see
research/sources/colombia/socrata/README.md). Only the fields listed in
contracts/adapter-contract.md are read: owner, creator, contact e-mail and domain metadata are
never accessed.
"""

import json
import re
from datetime import UTC, datetime
from typing import Any

from fdh.dataplane.connectors.contract import (
    AdapterCapabilities,
    AdapterContext,
    DiscoveryPage,
    ErrorKind,
    HttpRequest,
    HttpResponse,
    InvalidResponse,
    UnsupportedConfiguration,
)
from fdh.domain.datasets import (
    AccessLocator,
    DatasetDates,
    DeclaredLicense,
    DiscoveredDataset,
    RejectedRecord,
)
from fdh.domain.sources import DiscoveryQuery

_HOSTNAME = re.compile(
    r"(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+"
)
_MAX_ID_LENGTH = 200  # identifiers are indexed
_MAX_CATEGORY_LENGTH = 600  # category keys are indexed
_MAX_TOTAL = 2**31 - 1


class _Rejected(Exception):
    def __init__(self, reason: str, external_id: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.external_id = external_id


def _domains(context: AdapterContext) -> tuple[str, ...]:
    names = tuple(name.strip() for name in context.options.get("domains", "").split(","))
    if not all(_HOSTNAME.fullmatch(name) for name in names):
        raise UnsupportedConfiguration("domains must be a comma-separated list of host names")
    return names


def _mapping(value: object) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise _Rejected("malformed")
    return value


def _text(value: object) -> str | None:
    """A string kept verbatim; blank or absent means unknown."""
    if value is None:
        return None
    if not isinstance(value, str) or "\x00" in value:
        raise _Rejected("malformed")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise _Rejected("malformed") from None
    return value if value.strip() else None


def _texts(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise _Rejected("malformed")
    return [text for item in value if (text := _text(item)) is not None]


def _distinct(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _date(value: object) -> datetime | None:
    """A timestamp with an explicit offset, in UTC. Anything else stays unknown."""
    text = _text(value)
    if text is None:
        return None
    try:
        moment = datetime.fromisoformat(text)
        return None if moment.tzinfo is None else moment.astimezone(UTC)
    except (ValueError, OverflowError):
        return None


def _dataset(item: object, domains: frozenset[str]) -> DiscoveredDataset:
    if not isinstance(item, dict) or not isinstance(item.get("resource"), dict):
        raise _Rejected("malformed")
    resource: dict[str, Any] = item["resource"]
    external_id = _text(resource.get("id"))
    if external_id is None:
        raise _Rejected("missing_id")
    if len(external_id) > _MAX_ID_LENGTH:
        raise _Rejected("malformed")
    try:
        if resource.get("type") != "dataset":
            raise _Rejected("unexpected_type")
        metadata = _mapping(item.get("metadata"))
        domain = _text(metadata.get("domain"))
        # The publication permission covers the configured portals only.
        if domain is not None and domain.casefold() not in domains:
            raise _Rejected("unexpected_domain")
        title = _text(resource.get("name"))
        if title is None:
            raise _Rejected("missing_title")
        classification = _mapping(item.get("classification"))
        own_category = _text(classification.get("domain_category"))
        categories = _distinct(
            ([own_category] if own_category else []) + _texts(classification.get("categories"))
        )
        if any(len(category) > _MAX_CATEGORY_LENGTH for category in categories):
            raise _Rejected("malformed")
        license_name = _text(metadata.get("license"))
        permalink = _text(item.get("permalink"))
        links = (("permalink", permalink), ("link", _text(item.get("link"))))
        return DiscoveredDataset(
            external_id=external_id,
            title=title,
            description=_text(resource.get("description")),
            publisher=_text(resource.get("attribution")),
            official_url=permalink,
            categories=categories,
            tags=_distinct(
                _texts(classification.get("domain_tags")) + _texts(classification.get("tags"))
            ),
            licenses=(DeclaredLicense(name=license_name),) if license_name else (),
            dates=DatasetDates(
                created_at=_date(resource.get("createdAt")),
                published_at=_date(resource.get("publication_date")),
                metadata_updated_at=_date(resource.get("metadata_updated_at")),
                data_updated_at=_date(resource.get("data_updated_at")),
            ),
            locators=tuple(AccessLocator("web", url, field) for field, url in links if url),
        )
    except _Rejected as rejected:
        raise _Rejected(rejected.reason, external_id) from None


class SocrataAdapter:
    platform = "socrata"
    capabilities = AdapterCapabilities(
        text_search=True,
        declares_total=True,
        cursor_pagination=True,
        max_page_size=10000,  # maximum of `limit` in the official reference
        token_header="X-App-Token",  # noqa: S106  (a header name, not a value)
    )

    def validate(self, context: AdapterContext, queries: tuple[DiscoveryQuery, ...]) -> None:
        # An unknown parameter would silently empty the results of the provider.
        unknown = sorted(set(context.options) - {"domains"})
        if unknown:
            raise UnsupportedConfiguration(f"unsupported options: {', '.join(unknown)}")
        _domains(context)

    def build_request(
        self, context: AdapterContext, query: DiscoveryQuery, cursor: str | None
    ) -> HttpRequest:
        # Deep scrolling: `scroll_id` starts empty and excludes `order` and `offset`.
        last_id = "" if cursor is None else cursor.partition(":")[2]
        params = {
            "domains": ",".join(_domains(context)),
            "only": "datasets",
            "limit": str(context.page_size),
            "scroll_id": last_id,
        }
        if query.term is not None:
            params["q"] = query.term
        return HttpRequest("GET", context.base_url, params)

    def classify(self, response: HttpResponse) -> ErrorKind | None:
        return None  # the HTTP status says all this platform declares

    def parse(
        self,
        context: AdapterContext,
        request: HttpRequest,
        response: HttpResponse,
        cursor: str | None,
    ) -> DiscoveryPage:
        try:
            document = json.loads(response.body)
        except (ValueError, RecursionError):
            raise InvalidResponse("the body is not valid JSON") from None
        if not isinstance(document, dict):
            raise InvalidResponse("the body is not a JSON object")
        results, total = document.get("results"), document.get("resultSetSize")
        if not isinstance(results, list):
            raise InvalidResponse("results is not a list")
        if type(total) is not int or not 0 <= total <= _MAX_TOTAL:
            raise InvalidResponse("resultSetSize is not a count")

        domains = frozenset(name.casefold() for name in _domains(context))
        datasets: list[DiscoveredDataset] = []
        rejected: list[RejectedRecord] = []
        for item in results:
            try:
                datasets.append(_dataset(item, domains))
            except _Rejected as error:
                rejected.append(RejectedRecord(error.external_id, error.reason))

        seen_text, _, previous_id = (cursor or "0:").partition(":")
        seen = int(seen_text) + len(results)
        next_cursor = None
        if results and seen < total:
            last_id = _last_identifier(results)
            if last_id is None:
                raise InvalidResponse("the page has no identifier to continue the cursor")
            if last_id == previous_id:
                raise InvalidResponse("the cursor did not advance")
            next_cursor = f"{seen}:{last_id}"
        return DiscoveryPage(tuple(datasets), tuple(rejected), total, next_cursor)


def _last_identifier(results: list[object]) -> str | None:
    for item in reversed(results):
        if isinstance(item, dict) and isinstance(resource := item.get("resource"), dict):
            try:
                identifier = _text(resource.get("id"))
            except _Rejected:
                continue
            if identifier is not None and len(identifier) <= _MAX_ID_LENGTH:
                return identifier
    return None
