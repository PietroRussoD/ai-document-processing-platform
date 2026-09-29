"""Store advisory execution progress without altering document status.

Revision ID: 20260929_01
Revises: 20260927_04
Create Date: 2026-09-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260929_01"
down_revision: str | None = "20260927_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "ai_invoice_proposal_executions",
        sa.Column("processing_run_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "processing_run_id <> '00000000-0000-0000-0000-000000000000'",
            name=op.f("ck_ai_invoice_proposal_executions_processing_run_id_not_nil"),
        ),
        sa.CheckConstraint(
            "status IN ('DISABLED', 'RUNNING', 'COMPLETED', 'FAILED')",
            name=op.f("ck_ai_invoice_proposal_executions_status_supported"),
        ),
        sa.CheckConstraint(
            "(status = 'DISABLED' AND started_at IS NULL AND finished_at IS NOT NULL "
            "AND finished_at = status_changed_at) OR "
            "(status = 'RUNNING' AND started_at IS NOT NULL AND finished_at IS NULL "
            "AND started_at = status_changed_at) OR "
            "(status IN ('COMPLETED', 'FAILED') AND started_at IS NOT NULL "
            "AND finished_at IS NOT NULL AND finished_at = status_changed_at "
            "AND started_at <= finished_at)",
            name=op.f("ck_ai_invoice_proposal_executions_lifecycle_times_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["processing_run_id"],
            ["processing_runs.id"],
            name="fk_ai_proposal_executions_run",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "processing_run_id",
            name=op.f("pk_ai_invoice_proposal_executions"),
        ),
    )


def downgrade() -> None:
    op.drop_table("ai_invoice_proposal_executions")
