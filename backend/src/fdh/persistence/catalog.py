"""Store discovered datasets with their locators and provenance.

Rediscovery only writes what the source declared. Review states, permissions and conditions
recorded by a person are never part of these statements.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fdh.controlplane.runs import ObservedPage
from fdh.domain.datasets import DiscoveredDataset
from fdh.domain.locators import locator_status
from fdh.persistence.hashing import category_keys, metadata_hash
from fdh.persistence.models import AccessLocatorRow, Dataset, DatasetObservation
from fdh.persistence.runs import add_page


def _declared(dataset: DiscoveredDataset) -> dict[str, Any]:
    """The columns owned by discovery."""
    return {
        "title": dataset.title,
        "description": dataset.description,
        "publisher": dataset.publisher,
        "official_url": dataset.official_url,
        "categories": list(dataset.categories),
        "topics": list(dataset.topics),
        "tags": list(dataset.tags),
        "category_keys": category_keys(dataset.categories, dataset.topics),
        "data_sources": list(dataset.data_sources),
        "licenses": [
            {"name": licence.name, "url": licence.url, "note": licence.note}
            for licence in dataset.licenses
        ],
        "citation_requirement": dataset.citation_requirement,
        "created_at_source": dataset.dates.created_at,
        "published_at_source": dataset.dates.published_at,
        "metadata_updated_at_source": dataset.dates.metadata_updated_at,
        "data_updated_at_source": dataset.dates.data_updated_at,
        "updated_at_source": dataset.dates.updated_at,
        "metadata_hash": metadata_hash(dataset),
    }


class SqlCatalogRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def store_page(self, page: ObservedPage) -> None:
        """Datasets, locators, observations and run counts in one transaction.

        A dataset counts as created, updated or unchanged only the first time a run sees it.
        The source lock guarantees a single writer per source.
        """
        async with self._sessions() as session, session.begin():
            identifiers = {dataset.external_id for dataset in page.datasets}
            rows = {
                row.external_id: row
                for row in await session.scalars(
                    select(Dataset)
                    .where(
                        Dataset.source_id == page.source_id,
                        Dataset.external_id.in_(identifiers),
                    )
                    .with_for_update()
                )
            }
            created = updated = unchanged = 0
            latest: dict[str, DiscoveredDataset] = {}
            for dataset in page.datasets:
                latest[dataset.external_id] = dataset
                values = _declared(dataset)
                row = rows.get(dataset.external_id)
                if row is None:
                    row = Dataset(
                        source_id=page.source_id,
                        external_id=dataset.external_id,
                        first_seen_at=page.observed_at,
                        first_seen_run_id=page.run_id,
                    )
                    session.add(row)
                    rows[dataset.external_id] = row
                    created += 1
                elif row.last_seen_run_id != page.run_id:
                    if row.metadata_hash == values["metadata_hash"]:
                        unchanged += 1
                    else:
                        updated += 1
                for column, value in values.items():
                    setattr(row, column, value)
                row.last_seen_at = page.observed_at
                row.last_seen_run_id = page.run_id
            await session.flush()
            if latest:
                await self._replace_locators(session, {rows[key].id: latest[key] for key in latest})
                await session.execute(
                    insert(DatasetObservation)
                    .values(
                        [
                            {
                                "dataset_id": rows[key].id,
                                "run_id": page.run_id,
                                "query_index": page.query_index,
                                "source_url": page.source_url,
                                "request_summary": dict(page.request_summary),
                                "observed_at": page.observed_at,
                            }
                            for key in latest
                        ]
                    )
                    .on_conflict_do_nothing(index_elements=["dataset_id", "run_id", "query_index"])
                )
            await add_page(session, page, created=created, updated=updated, unchanged=unchanged)

    async def _replace_locators(
        self, session: AsyncSession, datasets: dict[UUID, DiscoveredDataset]
    ) -> None:
        """Each observation replaces the declared set and validates it again."""
        await session.execute(
            delete(AccessLocatorRow).where(AccessLocatorRow.dataset_id.in_(datasets))
        )
        session.add_all(
            AccessLocatorRow(
                dataset_id=dataset_id,
                kind=locator.kind,
                url=locator.url,
                source_field=locator.source_field,
                status=locator_status(locator.url),
            )
            for dataset_id, dataset in datasets.items()
            for locator in dict.fromkeys(dataset.locators)
        )
        await session.flush()
