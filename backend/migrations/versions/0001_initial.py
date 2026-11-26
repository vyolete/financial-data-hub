"""Initial schema of FDH-001.

Generated with Alembic against PostgreSQL 18 and edited to add the unaccent extension and
the explicit creation of shared enum types.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Enum types are shared between tables, so they are created once and explicitly.
ENUMS = {
    "permission": ("allowed", "denied", "undetermined"),
    "review_status": ("pending", "verified", "restricted"),
    "run_status": ("running", "succeeded", "partial", "failed"),
    "locator_status": ("unverified", "invalid"),
}


def enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    for name in ENUMS:
        enum(name).create(op.get_bind(), checkfirst=False)
    op.create_table(
        "sources",
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("official_url", sa.Text(), nullable=False),
        sa.Column("verified_at", sa.Date(), nullable=False),
        sa.Column("access_conditions", sa.Text(), nullable=True),
        sa.Column("redistribution_conditions", sa.Text(), nullable=True),
        sa.Column("license_name", sa.Text(), nullable=True),
        sa.Column("license_url", sa.Text(), nullable=True),
        sa.Column("terms_url", sa.Text(), nullable=True),
        sa.Column("terms_checked_on", sa.Date(), nullable=True),
        sa.Column(
            "metadata_publication",
            enum("permission"),
            server_default="undetermined",
            nullable=False,
        ),
        sa.Column("publication_evidence_url", sa.Text(), nullable=True),
        sa.Column("publication_declared_by", sa.Text(), nullable=True),
        sa.Column("publication_declared_on", sa.Date(), nullable=True),
        sa.Column("attribution_text", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "metadata_publication = 'undetermined' OR (publication_evidence_url IS NOT NULL "
            "AND publication_declared_by IS NOT NULL AND publication_declared_on IS NOT NULL)",
            name=op.f("ck_sources_publication_is_audited"),
        ),
        sa.PrimaryKeyConstraint("source_id", name=op.f("pk_sources")),
    )
    op.create_table(
        "runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("status", enum("run_status"), nullable=False),
        sa.Column(
            "parameters",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pages_processed", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("received", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("updated", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("unchanged", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("rejected", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("failures", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "errors",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.source_id"], name=op.f("fk_runs_source_id_sources")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_runs")),
    )
    op.create_index(
        "ix_runs_source_id_started_at",
        "runs",
        ["source_id", sa.literal_column("started_at DESC")],
        unique=False,
    )
    op.create_table(
        "datasets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("publisher", sa.Text(), nullable=True),
        sa.Column("official_url", sa.Text(), nullable=True),
        sa.Column(
            "categories",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "topics",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "category_keys",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "data_sources",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "licenses",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("citation_requirement", sa.Text(), nullable=True),
        sa.Column("created_at_source", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at_source", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_updated_at_source", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_updated_at_source", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at_source", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_conditions", sa.Text(), nullable=True),
        sa.Column("redistribution_conditions", sa.Text(), nullable=True),
        sa.Column("review_status", enum("review_status"), server_default="pending", nullable=False),
        sa.Column(
            "extraction_permission",
            enum("permission"),
            server_default="undetermined",
            nullable=False,
        ),
        sa.Column(
            "redistribution_permission",
            enum("permission"),
            server_default="undetermined",
            nullable=False,
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("first_seen_run_id", sa.Uuid(), nullable=False),
        sa.Column("last_seen_run_id", sa.Uuid(), nullable=False),
        sa.Column("metadata_hash", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "btrim(external_id) <> ''", name=op.f("ck_datasets_external_id_not_blank")
        ),
        sa.CheckConstraint("btrim(title) <> ''", name=op.f("ck_datasets_title_not_blank")),
        sa.ForeignKeyConstraint(
            ["first_seen_run_id"], ["runs.id"], name=op.f("fk_datasets_first_seen_run_id_runs")
        ),
        sa.ForeignKeyConstraint(
            ["last_seen_run_id"], ["runs.id"], name=op.f("fk_datasets_last_seen_run_id_runs")
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.source_id"], name=op.f("fk_datasets_source_id_sources")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_datasets")),
        sa.UniqueConstraint(
            "source_id", "external_id", name=op.f("uq_datasets_source_id_external_id")
        ),
    )
    op.create_index(
        "ix_datasets_category_keys",
        "datasets",
        ["category_keys"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "ix_datasets_source_id_review_status",
        "datasets",
        ["source_id", "review_status"],
        unique=False,
    )
    op.create_table(
        "run_queries",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("query_index", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("term", sa.Text(), nullable=True),
        sa.Column(
            "filters",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("pages_processed", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_declared", sa.Integer(), nullable=True),
        sa.Column("truncated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_run_queries_run_id_runs")),
        sa.PrimaryKeyConstraint("run_id", "query_index", name=op.f("pk_run_queries")),
    )
    op.create_table(
        "access_locators",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("source_field", sa.Text(), nullable=False),
        sa.Column("status", enum("locator_status"), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"], ["datasets.id"], name=op.f("fk_access_locators_dataset_id_datasets")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_access_locators")),
    )
    op.create_index(
        "uq_access_locators_identity",
        "access_locators",
        ["dataset_id", "kind", sa.literal_column("md5(url)"), "source_field"],
        unique=True,
    )
    op.create_table(
        "dataset_observations",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("query_index", sa.Integer(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column(
            "request_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "observed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name=op.f("fk_dataset_observations_dataset_id_datasets"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_dataset_observations_run_id_runs")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataset_observations")),
        sa.UniqueConstraint(
            "dataset_id",
            "run_id",
            "query_index",
            name=op.f("uq_dataset_observations_dataset_id_run_id_query_index"),
        ),
    )
    op.create_index(
        "ix_dataset_observations_dataset_id_observed_at",
        "dataset_observations",
        ["dataset_id", sa.literal_column("observed_at DESC")],
        unique=False,
    )
    op.create_table(
        "permission_decisions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=True),
        sa.Column("field", sa.Text(), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("decided_by", sa.Text(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "btrim(decided_by) <> ''", name=op.f("ck_permission_decisions_decided_by_not_blank")
        ),
        sa.CheckConstraint(
            "btrim(evidence) <> ''", name=op.f("ck_permission_decisions_evidence_not_blank")
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name=op.f("fk_permission_decisions_dataset_id_datasets"),
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.source_id"],
            name=op.f("fk_permission_decisions_source_id_sources"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_permission_decisions")),
    )


def downgrade() -> None:
    op.drop_table("permission_decisions")
    op.drop_index(
        "ix_dataset_observations_dataset_id_observed_at", table_name="dataset_observations"
    )
    op.drop_table("dataset_observations")
    op.drop_index("uq_access_locators_identity", table_name="access_locators")
    op.drop_table("access_locators")
    op.drop_table("run_queries")
    op.drop_index("ix_datasets_source_id_review_status", table_name="datasets")
    op.drop_index("ix_datasets_category_keys", table_name="datasets", postgresql_using="gin")
    op.drop_table("datasets")
    op.drop_index("ix_runs_source_id_started_at", table_name="runs")
    op.drop_table("runs")
    op.drop_table("sources")
    for name in ENUMS:
        enum(name).drop(op.get_bind(), checkfirst=False)
    op.execute("DROP EXTENSION IF EXISTS unaccent")
