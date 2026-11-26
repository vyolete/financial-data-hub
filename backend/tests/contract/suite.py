"""Cases every discovery adapter passes (contracts/adapter-contract.md, "Suite de contrato").

All responses are synthetic and the network is blocked. A platform subclasses
``AdapterContract`` and provides its fixtures and expectations.
"""

from pathlib import Path
from typing import ClassVar

import pytest

from fdh.dataplane.connectors.contract import (
    AdapterContext,
    DiscoveryAdapter,
    DiscoveryPage,
    ErrorKind,
    HttpRequest,
    HttpResponse,
    InvalidResponse,
    UnsupportedConfiguration,
    check_capabilities,
)
from fdh.domain.datasets import DiscoveredDataset
from fdh.domain.locators import LocatorStatus, locator_status
from fdh.domain.sources import DiscoveryQuery

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic"
QUERY = DiscoveryQuery("budget")


class AdapterContract:
    fixtures: ClassVar[str]
    # Values that exist in the fixtures but must never leave the adapter.
    personal_data: ClassVar[tuple[str, ...]]
    expected_total: ClassVar[int] = 3
    mixed_rejections: ClassVar[tuple[str, ...]]

    def adapter(self) -> DiscoveryAdapter:
        raise NotImplementedError

    def context(self, **options: str) -> AdapterContext:
        raise NotImplementedError

    def expected_first_dataset(self) -> DiscoveredDataset:
        raise NotImplementedError

    def response(self, name: str, status: int = 200) -> HttpResponse:
        (path,) = (FIXTURES / self.fixtures).glob(f"{name}.*")
        return HttpResponse(status, {}, path.read_bytes())

    def parse(self, name: str, cursor: str | None = None) -> tuple[HttpRequest, DiscoveryPage]:
        adapter, context = self.adapter(), self.context()
        request = adapter.build_request(context, QUERY, cursor)
        return request, adapter.parse(context, request, self.response(name), cursor)

    def test_the_default_configuration_is_supported(self) -> None:
        adapter, context = self.adapter(), self.context()
        check_capabilities(adapter.capabilities, context, (QUERY,))
        adapter.validate(context, (QUERY,))

    def test_first_page_and_continuation(self) -> None:
        first_request, first = self.parse("first_page")
        assert len(first.datasets) == 2
        assert first.total_declared == self.expected_total
        assert first.next_cursor is not None
        second_request, second = self.parse("last_page", first.next_cursor)
        assert second_request != first_request
        assert second.next_cursor is None

    def test_empty_result(self) -> None:
        _, page = self.parse("empty")
        assert (page.datasets, page.rejected, page.total_declared, page.next_cursor) == (
            (),
            (),
            0,
            None,
        )

    def test_an_empty_page_ends_the_query_even_below_the_total(self) -> None:
        _, page = self.parse("exhausted")
        assert page.total_declared == self.expected_total
        assert page.next_cursor is None

    def test_invalid_records_do_not_discard_valid_ones(self) -> None:
        _, page = self.parse("mixed")
        assert len(page.datasets) == 2
        assert tuple(r.reason for r in page.rejected) == self.mixed_rejections

    def test_all_records_invalid(self) -> None:
        _, page = self.parse("all_invalid")
        assert page.datasets == ()
        assert len(page.rejected) == 2

    @pytest.mark.parametrize("name", ["not_json", "unexpected_shape"])
    def test_an_uninterpretable_response_is_rejected_as_a_whole(self, name: str) -> None:
        with pytest.raises(InvalidResponse):
            self.parse(name)

    @pytest.mark.parametrize(
        "body", [b"", b"[]", b"null", b"\xff\xfe", b"[" * 100_000, b'{"results": []}']
    )
    def test_hostile_bodies_are_rejected(self, body: bytes) -> None:
        adapter, context = self.adapter(), self.context()
        request = adapter.build_request(context, QUERY, None)
        with pytest.raises(InvalidResponse):
            adapter.parse(context, request, HttpResponse(200, {}, body), None)

    @pytest.mark.parametrize("status", [400, 401, 403, 404])
    def test_permanent_statuses_are_never_transient(self, status: int) -> None:
        kind = self.adapter().classify(HttpResponse(status, {}, b"{}"))
        assert kind is not ErrorKind.TRANSIENT

    def test_success_is_not_classified_as_an_error(self) -> None:
        assert self.adapter().classify(self.response("first_page")) is None

    def test_unknown_options_are_rejected(self) -> None:
        adapter = self.adapter()
        with pytest.raises(UnsupportedConfiguration):
            adapter.validate(self.context(unexpected="1"), (QUERY,))

    def test_unsupported_filters_are_rejected(self) -> None:
        query = DiscoveryQuery("x", {"unsupported": "y"})
        with pytest.raises(UnsupportedConfiguration):
            check_capabilities(self.adapter().capabilities, self.context(), (query,))

    def test_no_personal_data_is_returned(self) -> None:
        _, page = self.parse("first_page")
        text = repr(page)
        body = self.response("first_page").body.decode()
        for value in self.personal_data:
            assert value in body
            assert value not in text

    def test_every_field_is_mapped(self) -> None:
        _, page = self.parse("first_page")
        assert page.datasets[0] == self.expected_first_dataset()

    def test_absent_values_stay_unknown(self) -> None:
        _, page = self.parse("first_page")
        minimal = page.datasets[1]
        assert (minimal.description, minimal.publisher, minimal.official_url) == (None, None, None)
        assert (minimal.categories, minimal.topics, minimal.tags) == ((), (), ())
        assert (minimal.licenses, minimal.locators) == ((), ())
        assert minimal.dates == type(minimal.dates)()

    def test_non_https_locators_are_preserved(self) -> None:
        _, page = self.parse("mixed")
        urls = [locator.url for locator in page.datasets[-1].locators]
        assert any(locator_status(url) is LocatorStatus.INVALID for url in urls)

    def test_parsing_is_deterministic(self) -> None:
        assert self.parse("first_page") == self.parse("first_page")
