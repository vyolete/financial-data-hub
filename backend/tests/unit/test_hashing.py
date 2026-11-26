"""Metadata fingerprint and category keys (AC-04, AC-13). Synthetic data."""

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

from fdh.domain.datasets import (
    AccessLocator,
    DatasetDates,
    DeclaredLicense,
    DiscoveredDataset,
)
from fdh.persistence.hashing import category_keys, metadata_hash

DATASET = DiscoveredDataset(
    external_id="x",
    title="Synthetic",
    tags=("a", "b"),
    dates=DatasetDates(created_at=datetime(2024, 1, 1, tzinfo=UTC)),
    licenses=(DeclaredLicense(name="L"),),
    locators=(AccessLocator("web", "https://example.org", "link"),),
)


def test_equal_metadata_has_the_same_fingerprint() -> None:
    assert metadata_hash(DATASET) == metadata_hash(replace(DATASET))
    assert len(metadata_hash(DATASET)) == 64


@pytest.mark.parametrize(
    "change",
    [
        {"title": "Other"},
        {"description": "d"},
        {"publisher": "p"},
        {"official_url": "https://example.org/d"},
        {"categories": ("c",)},
        {"topics": ("t",)},
        {"tags": ("b", "a")},
        {"data_sources": ("s",)},
        {"licenses": ()},
        {"citation_requirement": "cite"},
        {"dates": DatasetDates()},
        {"locators": ()},
    ],
)
def test_every_metadata_field_changes_the_fingerprint(change: dict[str, Any]) -> None:
    assert metadata_hash(replace(DATASET, **change)) != metadata_hash(DATASET)


def test_category_keys_ignore_case_and_merge_categories_and_topics() -> None:
    keys = category_keys(
        ("Participación Ciudadana", "Participación ciudadana", "Straße"), ("STRASSE", "Salud")
    )
    assert keys == ["participación ciudadana", "strasse", "salud"]
    assert category_keys((), ()) == []
