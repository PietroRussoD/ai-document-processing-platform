"""Add durable workflow-start request claims.

Revision ID: 20260915_02
Revises: 20260915_01
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_02"
down_revision: str | None = "20260915_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workflow_start_requests",
        sa.Column("dispatch_owner", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "workflow_start_requests",
        sa.Column("dispatch_token", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "workflow_start_requests",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "workflow_start_requests",
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.alter_column("workflow_start_requests", "attempt_count", server_default=None)
    op.drop_constraint(
        "ck_workflow_start_requests_status_valid",
        "workflow_start_requests",
        type_="check",
    )
    op.create_check_constraint(
        "ck_workflow_start_requests_status_valid",
        "workflow_start_requests",
        "status IN ('PENDING', 'DISPATCHING', 'DISPATCHED')",
    )
    op.create_check_constraint(
        "ck_workflow_start_requests_dispatching_has_claim",
        "workflow_start_requests",
        "(status = 'DISPATCHING') = "
        "(dispatch_owner IS NOT NULL AND dispatch_token IS NOT NULL "
        "AND lease_expires_at IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_workflow_start_requests_lease_time_ordered",
        "workflow_start_requests",
        "lease_expires_at IS NULL OR lease_expires_at > requested_at",
    )
    op.create_check_constraint(
        "ck_workflow_start_requests_attempt_count_not_negative",
        "workflow_start_requests",
        "attempt_count >= 0",
    )
    op.create_check_constraint(
        "ck_workflow_start_requests_pending_has_no_attempts",
        "workflow_start_requests",
        "status <> 'PENDING' OR attempt_count = 0",
    )
    op.create_check_constraint(
        "ck_workflow_start_requests_claimed_has_attempt",
        "workflow_start_requests",
        "status = 'PENDING' OR attempt_count >= 1",
    )
    op.drop_index(
        "ix_workflow_start_requests_status_requested_at",
        table_name="workflow_start_requests",
    )
    op.create_index(
        "ix_workflow_start_requests_status_lease_requested_at",
        "workflow_start_requests",
        ["status", "lease_expires_at", "requested_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workflow_start_requests_status_lease_requested_at",
        table_name="workflow_start_requests",
    )
    op.create_index(
        "ix_workflow_start_requests_status_requested_at",
        "workflow_start_requests",
        ["status", "requested_at"],
    )
    op.drop_constraint(
        "ck_workflow_start_requests_claimed_has_attempt",
        "workflow_start_requests",
        type_="check",
    )
    op.drop_constraint(
        "ck_workflow_start_requests_pending_has_no_attempts",
        "workflow_start_requests",
        type_="check",
    )
    op.drop_constraint(
        "ck_workflow_start_requests_attempt_count_not_negative",
        "workflow_start_requests",
        type_="check",
    )
    op.drop_constraint(
        "ck_workflow_start_requests_lease_time_ordered",
        "workflow_start_requests",
        type_="check",
    )
    op.drop_constraint(
        "ck_workflow_start_requests_dispatching_has_claim",
        "workflow_start_requests",
        type_="check",
    )
    op.drop_constraint(
        "ck_workflow_start_requests_status_valid",
        "workflow_start_requests",
        type_="check",
    )
    op.create_check_constraint(
        "ck_workflow_start_requests_status_valid",
        "workflow_start_requests",
        "status IN ('PENDING', 'DISPATCHED')",
    )
    op.drop_column("workflow_start_requests", "attempt_count")
    op.drop_column("workflow_start_requests", "lease_expires_at")
    op.drop_column("workflow_start_requests", "dispatch_token")
    op.drop_column("workflow_start_requests", "dispatch_owner")
