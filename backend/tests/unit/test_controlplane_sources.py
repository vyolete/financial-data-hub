"""Pure planning of the sources synchronisation. Synthetic sources only."""

from datetime import date

import pytest

from fdh.controlplane.sources import (
    RegisteredSource,
    UnauditedChange,
    plan_source_sync,
)
from fdh.domain.permissions import Permission
from fdh.domain.sources import PublicationDecision, SourceDefinition

TODAY = date(2026, 2, 1)


def decision(value: Permission) -> PublicationDecision:
    return PublicationDecision(
        value=value, declared_by="person", declared_on=date(2026, 1, 1), evidence="proof"
    )


def source(source_id: str, publication: PublicationDecision) -> SourceDefinition:
    return SourceDefinition(
        source_id=source_id,
        provider="P",
        platform="socrata",
        base_url="https://api.example.org",
        allowed_hosts=("api.example.org",),
        official_url="https://www.example.org",
        verified_at=date(2026, 1, 1),
        publication=publication,
    )


def test_new_allowed_source_records_the_decision() -> None:
    plan = plan_source_sync([source("a", decision(Permission.ALLOWED))], [], today=TODAY)
    (change,) = plan.publication_changes
    assert (change.old, change.new) == (Permission.UNDETERMINED, Permission.ALLOWED)
    assert (change.decided_by, change.evidence) == ("person", "proof")


def test_unchanged_permission_records_nothing() -> None:
    plan = plan_source_sync(
        [source("a", decision(Permission.ALLOWED))],
        [RegisteredSource("a", Permission.ALLOWED)],
        today=TODAY,
    )
    assert plan.publication_changes == ()
    assert [s.source_id for s in plan.upserts] == ["a"]


@pytest.mark.parametrize("new", [Permission.DENIED, Permission.UNDETERMINED])
def test_revocation_is_planned_with_its_evidence(new: Permission) -> None:
    plan = plan_source_sync(
        [source("a", decision(new))], [RegisteredSource("a", Permission.ALLOWED)], today=TODAY
    )
    (change,) = plan.publication_changes
    assert (change.old, change.new, change.evidence) == (Permission.ALLOWED, new, "proof")


def test_a_change_without_person_and_evidence_is_refused() -> None:
    with pytest.raises(UnauditedChange, match="a"):
        plan_source_sync(
            [source("a", PublicationDecision())],
            [RegisteredSource("a", Permission.ALLOWED)],
            today=TODAY,
        )


def test_removed_source_becomes_undetermined() -> None:
    plan = plan_source_sync([], [RegisteredSource("gone", Permission.ALLOWED)], today=TODAY)
    assert plan.retirements == ("gone",)
    (change,) = plan.publication_changes
    assert change.new is Permission.UNDETERMINED
    assert change.decided_on == TODAY
    assert change.evidence and change.decided_by


def test_removed_undetermined_source_records_nothing() -> None:
    plan = plan_source_sync([], [RegisteredSource("gone", Permission.UNDETERMINED)], today=TODAY)
    assert plan.retirements == ("gone",)
    assert plan.publication_changes == ()
