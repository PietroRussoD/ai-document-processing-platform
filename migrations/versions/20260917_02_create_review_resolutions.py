"""Create immutable manual review resolutions.

Revision ID: 20260917_02
Revises: 20260917_01
Create Date: 2026-09-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260917_02"
down_revision: str | None = "20260917_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_resolutions",
        sa.Column("processing_run_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "processing_run_id <> '00000000-0000-0000-0000-000000000000'",
            name="ck_review_resolutions_processing_run_id_not_nil",
        ),
        sa.CheckConstraint(
            "decision IN ('APPROVE', 'REJECT')",
            name="ck_review_resolutions_decision_valid",
        ),
        sa.CheckConstraint(
            "review_note IS NULL OR length(btrim(review_note)) BETWEEN 1 AND 2000",
            name="ck_review_resolutions_review_note_valid",
        ),
        sa.ForeignKeyConstraint(
            ["processing_run_id"],
            ["processing_runs.id"],
            name="fk_review_resolutions_processing_run_id_processing_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("processing_run_id", name="pk_review_resolutions"),
    )


def downgrade() -> None:
    op.drop_table("review_resolutions")
