"""Add safe terminal-failure evidence to processing runs.

Revision ID: 20260921_01
Revises: 20260920_03
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260921_01"
down_revision: str | None = "20260920_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("processing_runs", sa.Column("failure_stage", sa.String(length=64)))
    op.add_column("processing_runs", sa.Column("failure_code", sa.String(length=64)))
    op.execute(
        """
        UPDATE processing_runs
        SET failure_stage = 'UNKNOWN_LEGACY', failure_code = 'LEGACY_UNCLASSIFIED'
        WHERE status = 'FAILED'
        """
    )
    op.create_check_constraint(
        "ck_processing_runs_failure_evidence_consistent",
        "processing_runs",
        "(status = 'FAILED' AND failure_stage IS NOT NULL AND failure_code IS NOT NULL) "
        "OR (status <> 'FAILED' AND failure_stage IS NULL AND failure_code IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_processing_runs_failure_evidence_consistent",
        "processing_runs",
        type_="check",
    )
    op.drop_column("processing_runs", "failure_code")
    op.drop_column("processing_runs", "failure_stage")
