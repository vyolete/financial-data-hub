"""Measurements of discovery runs (E2).

The columns are nullable and have no default: runs recorded before this revision keep unknown
metrics. Nothing is derived for them.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COUNTS = ("requests", "duration_ms", "persistence_ms")


def upgrade() -> None:
    for column in COUNTS:
        op.add_column("runs", sa.Column(column, sa.Integer(), nullable=True))
        op.create_check_constraint(op.f(f"ck_runs_{column}_not_negative"), "runs", f"{column} >= 0")
    op.add_column(
        "runs", sa.Column("rejection_reasons", postgresql.JSONB(none_as_null=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("runs", "rejection_reasons")
    for column in reversed(COUNTS):
        op.drop_column("runs", column)  # drops its constraint too
