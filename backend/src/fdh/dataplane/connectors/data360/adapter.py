"""Pure Data360 discovery adapter; see contracts/adapter-contract.md."""

import json
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


class _Rejected(ValueError):
    pass


def _text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or "\x00" in value:
        raise _Rejected("malformed")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise _Rejected("malformed") from None
    return value if value.strip() else None


def _mapping(value: object) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise _Rejected("malformed")
    return value


def _objects(value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise _Rejected("malformed")
    return value


def _values(value: object, field: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            text for item in _objects(value) if (text := _text(item.get(field))) is not None
        )
    )


def _date(value: object) -> datetime | None:
    text = _text(value)
    if text is None:
        return None
    try:
        moment = datetime.fromisoformat(text)
        return None if moment.tzinfo is None else moment.astimezone(UTC)
    except (ValueError, OverflowError):
        return None


def _dataset(item: dict[str, Any], identifier: str) -> DiscoveredDataset:
    if item.get("type") != "dataset":
        raise _Rejected("unexpected_type")
    series = _mapping(item.get("series_description"))
    title = _text(series.get("name"))
    if title is None:
        raise _Rejected("missing_title")
    topics = _values(series.get("topics"), "name")
    if any(len(topic) > 600 for topic in topics):
        raise _Rejected("malformed")
    licenses = tuple(
        dict.fromkeys(
            DeclaredLicense(
                _text(entry.get("name")), _text(entry.get("uri")), _text(entry.get("note"))
            )
            for entry in _objects(series.get("license"))
        )
    )
    locators = [
        AccessLocator("source_website", url, "series_description.links[].uri")
        for entry in _objects(series.get("links"))
        if (url := _text(entry.get("uri"))) is not None
    ]
    for field, kind in (
        ("api_link", "api"),
        ("json_link", "json"),
        ("csv_link", "csv"),
        ("api_explorer_link", "api_explorer"),
    ):
        url = _text(series.get(field))
        if url is not None:
            locators.append(AccessLocator(kind, url, f"series_description.{field}"))
    return DiscoveredDataset(
        external_id=identifier,
        title=title,
        description=_text(series.get("definition_long")),
        topics=topics,
        tags=_values(item.get("tags"), "tag"),
        data_sources=_values(series.get("sources"), "organization"),
        licenses=licenses,
        citation_requirement=_text(series.get("citation_requirement")),
        dates=DatasetDates(updated_at=_date(series.get("date_last_update"))),
        locators=tuple(dict.fromkeys(locators)),
    )


def _offset(cursor: str | None) -> int:
    try:
        offset = int(cursor) if cursor is not None else 0
    except ValueError:
        raise InvalidResponse("invalid offset") from None
    if not 0 <= offset <= 100000:
        raise InvalidResponse("offset outside supported range")
    return offset


class Data360Adapter:
    platform = "data360"
    capabilities = AdapterCapabilities(
        text_search=True,
        declares_total=True,
        cursor_pagination=False,
    )

    def validate(self, context: AdapterContext, queries: tuple[DiscoveryQuery, ...]) -> None:
        if context.options:
            raise UnsupportedConfiguration("Data360 does not support options")

    def build_request(
        self, context: AdapterContext, query: DiscoveryQuery, cursor: str | None
    ) -> HttpRequest:
        return HttpRequest(
            "POST",
            context.base_url,
            json_body={
                "search": query.term or "*",
                "filter": "type eq 'dataset'",
                "top": context.page_size,
                "skip": _offset(cursor),
                "count": True,
            },
        )

    def classify(self, response: HttpResponse) -> ErrorKind | None:
        return None

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
        results, total = document.get("value"), document.get("@odata.count")
        if not isinstance(results, list):
            raise InvalidResponse("value is not a list")
        if type(total) is not int or not 0 <= total <= 2**31 - 1:
            raise InvalidResponse("invalid declared count")
        datasets: list[DiscoveredDataset] = []
        rejected: list[RejectedRecord] = []
        for item in results:
            identifier = None
            try:
                if not isinstance(item, dict):
                    raise _Rejected("malformed")
                identifier = _text(item.get("idno"))
                if identifier is None:
                    raise _Rejected("missing_id")
                if len(identifier) > 200:
                    identifier = None
                    raise _Rejected("malformed")
                datasets.append(_dataset(item, identifier))
            except _Rejected as error:
                rejected.append(RejectedRecord(identifier, str(error)))
        seen = _offset(cursor) + len(results)
        next_cursor = None
        if results and seen < total:
            if seen > 100000:
                raise InvalidResponse("next offset outside supported range")
            next_cursor = str(seen)
        return DiscoveryPage(tuple(datasets), tuple(rejected), total, next_cursor)
