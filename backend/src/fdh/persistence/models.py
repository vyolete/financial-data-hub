"""Database schema (specs/001-source-discovery/data-model.md). Timestamps are UTC."""

from datetime import date, datetime
from enum import StrEnum
from typing import Any, ClassVar
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    MetaData,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from fdh.domain.locators import LocatorStatus
from fdh.domain.permissions import Permission, ReviewStatus
from fdh.domain.status import RunStatus

NAMING = {
    "pk": "pk_%(table_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
}


def _enum(kind: type[StrEnum], name: str) -> Enum:
    return Enum(kind, name=name, values_callable=lambda members: [m.value for m in members])


PERMISSION = _enum(Permission, "permission")
REVIEW_STATUS = _enum(ReviewStatus, "review_status")
RUN_STATUS = _enum(RunStatus, "run_status")
LOCATOR_STATUS = _enum(LocatorStatus, "locator_status")
EMPTY_ARRAY = text("'{}'::text[]")


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)
    type_annotation_map: ClassVar[dict[Any, Any]] = {
        str: Text,
        datetime: DateTime(timezone=True),
        date: Date,
        int: Integer,
    }


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (
        CheckConstraint(
            "metadata_publication = 'undetermined' OR (publication_evidence_url IS NOT NULL "
            "AND publication_declared_by IS NOT NULL AND publication_declared_on IS NOT NULL)",
            name="publication_is_audited",
        ),
    )

    source_id: Mapped[str] = mapped_column(primary_key=True)
    provider: Mapped[str]
    platform: Mapped[str]
    official_url: Mapped[str]
    verified_at: Mapped[date]
    access_conditions: Mapped[str | None]
    redistribution_conditions: Mapped[str | None]
    license_name: Mapped[str | None]
    license_url: Mapped[str | None]
    terms_url: Mapped[str | None]
    terms_checked_on: Mapped[date | None]
    metadata_publication: Mapped[Permission] = mapped_column(
        PERMISSION, server_default=Permission.UNDETERMINED.value
    )
    publication_evidence_url: Mapped[str | None]
    publication_declared_by: Mapped[str | None]
    publication_declared_on: Mapped[date | None]
    attribution_text: Mapped[str | None]


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.source_id"))
    status: Mapped[RunStatus] = mapped_column(RUN_STATUS)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None]
    pages_processed: Mapped[int] = mapped_column(server_default=text("0"))
    received: Mapped[int] = mapped_column(server_default=text("0"))
    created: Mapped[int] = mapped_column(server_default=text("0"))
    updated: Mapped[int] = mapped_column(server_default=text("0"))
    unchanged: Mapped[int] = mapped_column(server_default=text("0"))
    rejected: Mapped[int] = mapped_column(server_default=text("0"))
    failures: Mapped[int] = mapped_column(server_default=text("0"))
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))


Index("ix_runs_source_id_started_at", Run.source_id, Run.started_at.desc())


class RunQuery(Base):
    __tablename__ = "run_queries"

    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), primary_key=True)
    query_index: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    term: Mapped[str | None]
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    pages_processed: Mapped[int] = mapped_column(server_default=text("0"))
    total_declared: Mapped[int | None]
    truncated: Mapped[bool] = mapped_column(server_default=text("false"))


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id"),
        CheckConstraint("btrim(title) <> ''", name="title_not_blank"),
        CheckConstraint("btrim(external_id) <> ''", name="external_id_not_blank"),
        Index("ix_datasets_category_keys", "category_keys", postgresql_using="gin"),
        Index("ix_datasets_source_id_review_status", "source_id", "review_status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.source_id"))
    external_id: Mapped[str]
    title: Mapped[str]
    description: Mapped[str | None]
    publisher: Mapped[str | None]
    official_url: Mapped[str | None]
    categories: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=EMPTY_ARRAY)
    topics: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=EMPTY_ARRAY)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=EMPTY_ARRAY)
    category_keys: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=EMPTY_ARRAY)
    data_sources: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=EMPTY_ARRAY)
    licenses: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    citation_requirement: Mapped[str | None]
    created_at_source: Mapped[datetime | None]
    published_at_source: Mapped[datetime | None]
    metadata_updated_at_source: Mapped[datetime | None]
    data_updated_at_source: Mapped[datetime | None]
    updated_at_source: Mapped[datetime | None]
    access_conditions: Mapped[str | None]
    redistribution_conditions: Mapped[str | None]
    review_status: Mapped[ReviewStatus] = mapped_column(
        REVIEW_STATUS, server_default=ReviewStatus.PENDING.value
    )
    extraction_permission: Mapped[Permission] = mapped_column(
        PERMISSION, server_default=Permission.UNDETERMINED.value
    )
    redistribution_permission: Mapped[Permission] = mapped_column(
        PERMISSION, server_default=Permission.UNDETERMINED.value
    )
    first_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())
    first_seen_run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"))
    last_seen_run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"))
    metadata_hash: Mapped[str]


class AccessLocatorRow(Base):
    __tablename__ = "access_locators"
    # The URL is hashed so that very long values fit in the unique index.
    __table_args__ = (
        Index(
            "uq_access_locators_identity",
            "dataset_id",
            "kind",
            text("md5(url)"),
            "source_field",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("datasets.id"))
    kind: Mapped[str]
    url: Mapped[str]
    source_field: Mapped[str]
    status: Mapped[LocatorStatus] = mapped_column(LOCATOR_STATUS)


class DatasetObservation(Base):
    __tablename__ = "dataset_observations"
    __table_args__ = (UniqueConstraint("dataset_id", "run_id", "query_index"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("datasets.id"))
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"))
    query_index: Mapped[int]
    source_url: Mapped[str]
    request_summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    observed_at: Mapped[datetime] = mapped_column(server_default=func.now())


Index(
    "ix_dataset_observations_dataset_id_observed_at",
    DatasetObservation.dataset_id,
    DatasetObservation.observed_at.desc(),
)


class PermissionDecisionRow(Base):
    """Append-only record of every change made by a person or by the sources sync."""

    __tablename__ = "permission_decisions"
    __table_args__ = (
        CheckConstraint("btrim(evidence) <> ''", name="evidence_not_blank"),
        CheckConstraint("btrim(decided_by) <> ''", name="decided_by_not_blank"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.source_id"))
    dataset_id: Mapped[UUID | None] = mapped_column(ForeignKey("datasets.id"))
    field: Mapped[str]
    old_value: Mapped[str | None]
    new_value: Mapped[str]
    evidence: Mapped[str]
    decided_by: Mapped[str]
    decided_at: Mapped[datetime]
    recorded_at: Mapped[datetime] = mapped_column(server_default=func.now())
