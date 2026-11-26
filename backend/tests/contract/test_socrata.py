"""Socrata Discovery adapter (AC-01, AC-07, AC-21, AC-33, AC-34, AC-36). Synthetic data."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from fdh.dataplane.connectors.contract import (
    AdapterContext,
    DiscoveryPage,
    HttpResponse,
    InvalidResponse,
    UnsupportedConfiguration,
    check_capabilities,
)
from fdh.dataplane.connectors.registry import default_registry
from fdh.dataplane.connectors.socrata import SocrataAdapter
from fdh.domain.datasets import (
    AccessLocator,
    DatasetDates,
    DeclaredLicense,
    DiscoveredDataset,
)
from fdh.domain.sources import DiscoveryQuery
from fdh.settings.sources import load_sources
from tests.contract.suite import QUERY, AdapterContract

DOMAIN = "data.example.org"
BASE = "https://api.example.org/api/catalog/v1"
REPOSITORY_CONFIG = Path(__file__).resolve().parents[3] / "config/sources.toml"


def context(page_size: int = 100, **options: str) -> AdapterContext:
    return AdapterContext("synthetic", BASE, page_size, {"domains": DOMAIN, **options})


def response(*results: object, total: object = None) -> HttpResponse:
    document = {"results": list(results), "resultSetSize": len(results) if total is None else total}
    return HttpResponse(200, {}, json.dumps(document).encode())


def result(identifier: str = "syn-0001", **resource: object) -> dict[str, object]:
    return {"resource": {"id": identifier, "type": "dataset", "name": "Synthetic", **resource}}


def parse(answer: HttpResponse, cursor: str | None = None) -> DiscoveryPage:
    adapter = SocrataAdapter()
    request = adapter.build_request(context(), QUERY, cursor)
    return adapter.parse(context(), request, answer, cursor)


class TestSocrataContract(AdapterContract):
    fixtures = "socrata"
    personal_data = (
        "Synthetic Owner Person",
        "Synthetic Creator Person",
        "synthetic.contact@example.org",
        "synthetic.metadata@example.org",
    )
    mixed_rejections = (
        "missing_id",
        "missing_title",
        "unexpected_type",
        "malformed",
        "unexpected_domain",
        "malformed",
    )

    def adapter(self) -> SocrataAdapter:
        return SocrataAdapter()

    def context(self, **options: str) -> AdapterContext:
        return AdapterContext("synthetic", BASE, 100, {"domains": DOMAIN, **options})

    def expected_first_dataset(self) -> DiscoveredDataset:
        return DiscoveredDataset(
            external_id="syn1-0001",
            title="Synthetic dataset syn1-0001",
            description="Synthetic description syn1-0001",
            publisher="Synthetic Publisher",
            official_url=f"https://{DOMAIN}/d/syn1-0001",
            categories=("Synthetic Category", "Second Category"),
            topics=(),
            tags=("synthetic-tag", "other-tag"),
            licenses=(DeclaredLicense(name="Synthetic License 1.0"),),
            dates=DatasetDates(
                created_at=datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC),
                published_at=datetime(2024, 3, 2, 3, 4, 5, tzinfo=UTC),
                metadata_updated_at=datetime(2024, 4, 2, 3, 4, 5, tzinfo=UTC),
                data_updated_at=datetime(2024, 5, 2, 3, 4, 5, tzinfo=UTC),
            ),
            locators=(
                AccessLocator("web", f"https://{DOMAIN}/d/syn1-0001", "permalink"),
                AccessLocator("web", f"https://{DOMAIN}/Synthetic/syn1-0001", "link"),
            ),
        )


def test_the_adapter_is_registered_for_its_platform() -> None:
    assert isinstance(default_registry().create("socrata"), SocrataAdapter)


def test_repository_configuration_requests_only_datasets_of_the_portal() -> None:
    (source,) = [s for s in load_sources(REPOSITORY_CONFIG) if s.platform == "socrata"]
    default_registry().validate(source)
    adapter = SocrataAdapter()
    configured = AdapterContext(
        source.source_id, source.base_url, source.limits.page_size, source.options
    )
    request = adapter.build_request(configured, source.queries[0], None)
    assert request.method == "GET"
    assert request.url == "https://api.us.socrata.com/api/catalog/v1"
    assert request.params == {
        "domains": "www.datos.gov.co",
        "only": "datasets",
        "q": "presupuesto",
        "limit": "100",
        "scroll_id": "",
    }
    assert source.limits.max_pages == 5


def test_configuration_changes_the_request_without_code() -> None:
    adapter = SocrataAdapter()
    changed = context(page_size=25, domains="a.example.org, b.example.org")
    request = adapter.build_request(changed, DiscoveryQuery("salud"), None)
    assert request.params["domains"] == "a.example.org,b.example.org"
    assert (request.params["q"], request.params["limit"]) == ("salud", "25")


def test_a_query_without_a_term_sends_no_search_parameter() -> None:
    request = SocrataAdapter().build_request(context(), DiscoveryQuery(), None)
    assert "q" not in request.params


def test_the_cursor_is_the_last_identifier_without_order_or_offset() -> None:
    adapter = SocrataAdapter()
    first = parse(response(result("aaaa-0001"), result("aaaa-0002"), total=5))
    request = adapter.build_request(context(), QUERY, first.next_cursor)
    assert request.params["scroll_id"] == "aaaa-0002"
    assert not {"order", "offset"} & set(request.params)


def test_the_cursor_counts_what_has_been_seen() -> None:
    first = parse(response(result("a-1"), result("a-2"), total=4))
    second = parse(response(result("a-3"), result("a-4"), total=4), first.next_cursor)
    assert second.next_cursor is None


def test_the_cursor_skips_trailing_records_without_identifier() -> None:
    page = parse(response(result("a-1"), {"resource": {"type": "dataset"}}, total=5))
    request = SocrataAdapter().build_request(context(), QUERY, page.next_cursor)
    assert request.params["scroll_id"] == "a-1"


def test_a_page_that_cannot_be_continued_is_invalid() -> None:
    with pytest.raises(InvalidResponse, match="cursor"):
        parse(response({"resource": {}}, total=5))
    first = parse(response(result("a-1"), total=5))
    with pytest.raises(InvalidResponse, match="advance"):
        parse(response(result("a-1"), total=5), first.next_cursor)


@pytest.mark.parametrize("total", [None, -1, "3", True, 2**31, 1.5])
def test_the_declared_total_must_be_a_count(total: object) -> None:
    body = json.dumps({"results": [], "resultSetSize": total}).encode()
    with pytest.raises(InvalidResponse):
        parse(HttpResponse(200, {}, body))


@pytest.mark.parametrize(
    ("record", "reason"),
    [
        ({}, "malformed"),
        ({"resource": []}, "malformed"),
        ({"resource": {"type": "dataset", "name": "x"}}, "missing_id"),
        ({"resource": {"id": "  ", "type": "dataset", "name": "x"}}, "missing_id"),
        (result(identifier=7), "malformed"),  # type: ignore[arg-type]
        (result(identifier="x" * 201), "malformed"),
        ({"resource": {"id": "a-1", "name": "x"}}, "unexpected_type"),
        (result(name=None), "missing_title"),
        (result(description="null \x00 byte"), "malformed"),
        (result(name="lone \ud800 surrogate"), "malformed"),
        (result(attribution=["a"]), "malformed"),
        (result(createdAt=20240101), "malformed"),
        ({**result(), "classification": []}, "malformed"),
        ({**result(), "classification": {"domain_tags": "one"}}, "malformed"),
        ({**result(), "classification": {"domain_category": "x" * 601}}, "malformed"),
        ({**result(), "metadata": {"license": {"name": "x"}}}, "malformed"),
    ],
)
def test_defective_records_are_rejected_with_a_reason(
    record: dict[str, object], reason: str
) -> None:
    page = parse(response(record, result("ok-1")))
    assert [r.reason for r in page.rejected] == [reason]
    assert [d.external_id for d in page.datasets] == ["ok-1"]


@pytest.mark.parametrize(
    "value",
    ["", "yesterday", "2024-01-01T00:00:00", "0001-01-01T00:00:00+14:00"],
)
def test_an_unusable_date_is_unknown_and_is_not_guessed(value: str) -> None:
    (dataset,) = parse(response(result(createdAt=value))).datasets
    assert dataset.dates.created_at is None


def test_dates_are_normalised_to_utc() -> None:
    (dataset,) = parse(response(result(createdAt="2024-01-01T00:00:00-05:00"))).datasets
    assert dataset.dates.created_at == datetime(2024, 1, 1, 5, tzinfo=UTC)
    assert dataset.dates.updated_at is None


def test_a_record_without_domain_information_is_accepted() -> None:
    assert parse(response(result())).datasets[0].external_id == "syn-0001"


def test_domains_are_compared_without_case() -> None:
    record = {**result(), "metadata": {"domain": DOMAIN.upper()}}
    assert len(parse(response(record)).datasets) == 1


def test_text_is_kept_verbatim_and_repeated_values_once() -> None:
    record = {
        **result(name="  Título  <b>x</b> "),
        "classification": {"domain_tags": ["Ñ", "ñ", "Ñ", " "], "tags": ["Ñ"]},
    }
    (dataset,) = parse(response(record)).datasets
    assert dataset.title == "  Título  <b>x</b> "
    assert dataset.tags == ("Ñ", "ñ")


@pytest.mark.parametrize(
    "domains",
    ["", " ", "https://data.example.org", "data.example.org/path", "a.example.org,,b", "a b"],
)
def test_domains_must_be_host_names(domains: str) -> None:
    with pytest.raises(UnsupportedConfiguration, match="domains"):
        SocrataAdapter().validate(context(domains=domains), (QUERY,))


def test_domains_are_required() -> None:
    with pytest.raises(UnsupportedConfiguration, match="domains"):
        SocrataAdapter().validate(AdapterContext("s", BASE, 100), (QUERY,))


def test_the_documented_maximum_page_size_is_declared() -> None:
    adapter = SocrataAdapter()
    assert adapter.capabilities.max_page_size == 10000
    with pytest.raises(UnsupportedConfiguration, match="page_size"):
        check_capabilities(adapter.capabilities, context(page_size=10001), (QUERY,))
