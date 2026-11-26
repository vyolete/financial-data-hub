"""Synthetic Data360 contract cases (AC-21, AC-33, AC-34, AC-36)."""

import json
from datetime import UTC, datetime

import pytest

from fdh.dataplane.connectors.contract import AdapterContext, HttpResponse, InvalidResponse
from fdh.dataplane.connectors.data360 import Data360Adapter
from fdh.dataplane.connectors.registry import default_registry
from fdh.domain.datasets import AccessLocator, DatasetDates, DeclaredLicense, DiscoveredDataset
from tests.contract.suite import QUERY, AdapterContract


class TestData360Contract(AdapterContract):
    fixtures = "data360"
    personal_data = ("Synthetic Owner Person", "synthetic.contact@example.org")
    mixed_rejections = ("missing_id", "missing_title", "unexpected_type", "malformed")

    def adapter(self) -> Data360Adapter:
        return Data360Adapter()

    def context(self, **options: str) -> AdapterContext:
        return AdapterContext("synthetic", "https://api.example.org/searchv2", 2, options)

    def expected_first_dataset(self) -> DiscoveredDataset:
        return DiscoveredDataset(
            external_id="syn-1",
            title="Synthetic dataset",
            description="Synthetic description",
            topics=("Finance", "Economics"),
            tags=("tag",),
            data_sources=("Synthetic institution",),
            licenses=(
                DeclaredLicense("Synthetic license", "https://example.org/license", "Note"),
                DeclaredLicense("External"),
            ),
            citation_requirement="Synthetic citation",
            dates=DatasetDates(updated_at=datetime(2024, 1, 1, tzinfo=UTC)),
            locators=(
                AccessLocator(
                    "source_website", "https://example.org/source", "series_description.links[].uri"
                ),
                AccessLocator("api", "https://example.org/api", "series_description.api_link"),
            ),
        )

    def test_request(self) -> None:
        request, page = self.parse("first_page")
        assert request.method == "POST"
        assert request.json_body == {
            "search": "budget",
            "filter": "type eq 'dataset'",
            "top": 2,
            "skip": 0,
            "count": True,
        }
        assert page.next_cursor == "2"

    def test_offset_limit(self) -> None:
        with pytest.raises(InvalidResponse):
            self.adapter().build_request(self.context(), QUERY, "100001")

    @pytest.mark.parametrize("total", [None, True, -1, "3", 2**31])
    def test_invalid_total(self, total: object) -> None:
        request = self.adapter().build_request(self.context(), QUERY, None)
        body = json.dumps({"value": [], "@odata.count": total}).encode()
        with pytest.raises(InvalidResponse):
            self.adapter().parse(self.context(), request, HttpResponse(200, {}, body), None)


def test_registered() -> None:
    assert isinstance(default_registry().create("data360"), Data360Adapter)
