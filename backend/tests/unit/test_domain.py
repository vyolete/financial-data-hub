from datetime import date

import pytest

from fdh.domain.datasets import AccessLocator, DiscoveredDataset
from fdh.domain.locators import LocatorStatus, locator_status, usable_for_extraction
from fdh.domain.permissions import Permission, ReviewStatus, metadata_visible
from fdh.domain.sources import PublicationDecision
from fdh.domain.status import RunStatus, final_status


@pytest.mark.parametrize(
    ("valid", "rejected", "failures", "expected"),
    [
        (0, 0, 0, RunStatus.SUCCEEDED),  # AC-10: empty search without errors
        (5, 0, 0, RunStatus.SUCCEEDED),
        (5, 1, 0, RunStatus.PARTIAL),  # AC-11
        (5, 0, 1, RunStatus.PARTIAL),  # AC-08
        (0, 5, 0, RunStatus.FAILED),  # AC-32: every record rejected
        (0, 0, 1, RunStatus.FAILED),  # AC-09
        (0, 2, 1, RunStatus.FAILED),
    ],
)
def test_final_status(valid: int, rejected: int, failures: int, expected: RunStatus) -> None:
    assert final_status(valid=valid, rejected=rejected, failures=failures) is expected


def test_final_status_refuses_negative_counts() -> None:
    with pytest.raises(ValueError, match="negative"):
        final_status(valid=-1, rejected=0, failures=0)


@pytest.mark.parametrize(
    "url",
    ["https://example.org/data.csv", "https://example.org:8443/a?b=1", "HTTPS://EXAMPLE.ORG"],
)
def test_https_locator_is_unverified(url: str) -> None:
    assert locator_status(url) is LocatorStatus.UNVERIFIED
    assert usable_for_extraction(locator_status(url))


@pytest.mark.parametrize(
    "url",
    [
        "http://example.org/data",
        "ftp://example.org/data",
        "https://",
        "https:///path",
        "/relative/path",
        "not a url",
        "",
        " https://example.org",
        "https://exa mple.org",
        "https://example.org/\nheader",
        "https://user:secret@example.org/",
        "https://example.org:99999/",
        "https://[broken",
        "javascript:alert(1)",
    ],
)
def test_invalid_locator_cannot_be_used_for_extraction(url: str) -> None:
    assert locator_status(url) is LocatorStatus.INVALID
    assert not usable_for_extraction(locator_status(url))


def test_invalid_locator_does_not_discard_the_dataset() -> None:
    dataset = DiscoveredDataset(
        external_id="synthetic-1",
        title="Synthetic",
        locators=(AccessLocator(kind="brand-new-kind", url="http://x", source_field="f"),),
    )
    assert dataset.locators[0].url == "http://x"


@pytest.mark.parametrize("publication", list(Permission))
@pytest.mark.parametrize("review", list(ReviewStatus))
def test_visibility_requires_allowed_source_and_unrestricted_dataset(
    publication: Permission, review: ReviewStatus
) -> None:
    expected = publication is Permission.ALLOWED and review is not ReviewStatus.RESTRICTED
    assert metadata_visible(publication, review) is expected


def test_permissions_default_to_undetermined() -> None:
    assert PublicationDecision().value is Permission.UNDETERMINED


@pytest.mark.parametrize("value", [Permission.ALLOWED, Permission.DENIED])
def test_a_decision_requires_person_date_and_evidence(value: Permission) -> None:
    with pytest.raises(ValueError, match="evidence"):
        PublicationDecision(value=value, declared_by="person", declared_on=date(2026, 1, 1))
