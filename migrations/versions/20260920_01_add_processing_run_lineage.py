"""Add immutable processing-run lineage.

Revision ID: 20260920_01
Revises: 20260918_01
Create Date: 2026-09-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260920_01"
down_revision: str | None = "20260918_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "processing_runs",
        sa.Column("previous_run_id", sa.Uuid(), nullable=True),
    )
    op.create_check_constraint(
        "ck_processing_runs_previous_run_id_not_self",
        "processing_runs",
        "previous_run_id IS NULL OR previous_run_id <> id",
    )
    op.create_foreign_key(
        "fk_processing_runs_previous_run_id_processing_runs",
        "processing_runs",
        "processing_runs",
        ["previous_run_id"],
        ["id"],
    )
    op.create_index(
        "ix_processing_runs_previous_run_id",
        "processing_runs",
        ["previous_run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_processing_runs_previous_run_id", table_name="processing_runs")
    op.drop_constraint(
        "fk_processing_runs_previous_run_id_processing_runs",
        "processing_runs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "ck_processing_runs_previous_run_id_not_self",
        "processing_runs",
        type_="check",
    )
    op.drop_column("processing_runs", "previous_run_id")
