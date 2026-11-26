"""Plan of the synchronisation between the configuration and the registered sources.

It only concerns sources. Dataset review states, permissions and conditions are never part of
a plan, so applying one cannot lift a dataset restriction.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from fdh.domain.permissions import Permission
from fdh.domain.sources import SourceDefinition

SYSTEM_ACTOR = "fdh sources sync"
REMOVED_EVIDENCE = "source removed from the sources configuration"


@dataclass(frozen=True)
class RegisteredSource:
    source_id: str
    publication: Permission


@dataclass(frozen=True)
class PublicationChange:
    source_id: str
    old: Permission
    new: Permission
    evidence: str
    decided_by: str
    decided_on: date


@dataclass(frozen=True)
class SyncPlan:
    upserts: tuple[SourceDefinition, ...]
    retirements: tuple[str, ...]  # keep their data; become undetermined
    publication_changes: tuple[PublicationChange, ...]


class UnauditedChange(Exception):
    """A permission would change without a person, a date and evidence."""


def plan_source_sync(
    definitions: Sequence[SourceDefinition],
    registered: Sequence[RegisteredSource],
    *,
    today: date,
) -> SyncPlan:
    current = {source.source_id: source.publication for source in registered}
    changes: list[PublicationChange] = []
    for definition in definitions:
        old = current.get(definition.source_id, Permission.UNDETERMINED)
        decision = definition.publication
        if decision.value is old:
            continue
        if not (decision.evidence and decision.declared_by and decision.declared_on):
            raise UnauditedChange(
                f"changing the publication permission of {definition.source_id} requires "
                "declared_by, declared_on and evidence"
            )
        changes.append(
            PublicationChange(
                definition.source_id,
                old,
                decision.value,
                decision.evidence,
                decision.declared_by,
                decision.declared_on,
            )
        )
    configured = {definition.source_id for definition in definitions}
    retirements = tuple(sorted(set(current) - configured))
    changes.extend(
        PublicationChange(
            source_id,
            current[source_id],
            Permission.UNDETERMINED,
            REMOVED_EVIDENCE,
            SYSTEM_ACTOR,
            today,
        )
        for source_id in retirements
        if current[source_id] is not Permission.UNDETERMINED
    )
    return SyncPlan(tuple(definitions), retirements, tuple(changes))
