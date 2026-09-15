"""Create durable workflow-start requests.

Revision ID: 20260915_01
Revises: 20260914_01
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_01"
down_revision: str | None = "20260914_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_start_requests",
        sa.Column("processing_run_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "processing_run_id <> '00000000-0000-0000-0000-000000000000'",
            name="ck_workflow_start_requests_processing_run_id_not_nil",
        ),
        sa.CheckConstraint(
            "workflow_id = btrim(workflow_id) AND length(workflow_id) > 0",
            name="ck_workflow_start_requests_workflow_id_format",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'DISPATCHED')",
            name="ck_workflow_start_requests_status_valid",
        ),
        sa.CheckConstraint(
            "(status = 'DISPATCHED') = (dispatched_at IS NOT NULL)",
            name="ck_workflow_start_requests_dispatch_status_has_time",
        ),
        sa.CheckConstraint(
            "dispatched_at IS NULL OR dispatched_at >= requested_at",
            name="ck_workflow_start_requests_dispatch_time_ordered",
        ),
        sa.CheckConstraint(
            "version >= 0",
            name="ck_workflow_start_requests_version_not_negative",
        ),
        sa.ForeignKeyConstraint(
            ["processing_run_id"],
            ["processing_runs.id"],
            name="fk_workflow_start_requests_processing_run_id_processing_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "processing_run_id",
            name="pk_workflow_start_requests",
        ),
        sa.UniqueConstraint("workflow_id", name="uq_workflow_start_requests_workflow_id"),
    )
    op.create_index(
        "ix_workflow_start_requests_status_requested_at",
        "workflow_start_requests",
        ["status", "requested_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workflow_start_requests_status_requested_at",
        table_name="workflow_start_requests",
    )
    op.drop_table("workflow_start_requests")
