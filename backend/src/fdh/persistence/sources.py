"""Apply the sources synchronisation plan in a single transaction."""

from datetime import UTC, datetime, time
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fdh.controlplane.ports import SyncPlanner
from fdh.controlplane.sources import RegisteredSource, SyncPlan
from fdh.domain.permissions import Permission
from fdh.domain.sources import SourceDefinition
from fdh.persistence.models import PermissionDecisionRow, Source

_LOCK_KEY = "fdh.sources_sync"
_COPIED = (
    "source_id",
    "provider",
    "platform",
    "official_url",
    "verified_at",
    "access_conditions",
    "redistribution_conditions",
    "license_name",
    "license_url",
    "terms_url",
    "terms_checked_on",
)


def _values(definition: SourceDefinition) -> dict[str, Any]:
    data = {name: getattr(definition, name) for name in _COPIED}
    decision = definition.publication
    data.update(
        metadata_publication=decision.value,
        publication_evidence_url=decision.evidence,
        publication_declared_by=decision.declared_by,
        publication_declared_on=decision.declared_on,
        attribution_text=definition.attribution,
    )
    return data


class SqlSourceRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def synchronise(self, planner: SyncPlanner) -> SyncPlan:
        """Read, plan and apply under a lock. Dataset rows are never touched."""
        async with self._sessions() as session, session.begin():
            await session.execute(select(func.pg_advisory_xact_lock(func.hashtext(_LOCK_KEY))))
            rows = await session.execute(select(Source.source_id, Source.metadata_publication))
            plan = planner([RegisteredSource(row[0], row[1]) for row in rows])
            for definition in plan.upserts:
                values = _values(definition)
                statement = insert(Source).values(**values)
                values.pop("source_id")
                await session.execute(
                    statement.on_conflict_do_update(index_elements=["source_id"], set_=values)
                )
            if plan.retirements:
                await session.execute(
                    update(Source)
                    .where(Source.source_id.in_(plan.retirements))
                    .values(
                        metadata_publication=Permission.UNDETERMINED,
                        publication_evidence_url=None,
                        publication_declared_by=None,
                        publication_declared_on=None,
                    )
                )
            for change in plan.publication_changes:
                session.add(
                    PermissionDecisionRow(
                        source_id=change.source_id,
                        field="metadata_publication",
                        old_value=change.old.value,
                        new_value=change.new.value,
                        evidence=change.evidence,
                        decided_by=change.decided_by,
                        decided_at=datetime.combine(change.decided_on, time(), UTC),
                    )
                )
        return plan
