"""Create processing runs table.

Revision ID: 20260913_02
Revises: 20260913_01
Create Date: 2026-09-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260913_02"
down_revision: str | None = "20260913_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "processing_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "id <> '00000000-0000-0000-0000-000000000000'",
            name="ck_processing_runs_id_not_nil",
        ),
        sa.CheckConstraint(
            "document_id <> '00000000-0000-0000-0000-000000000000'",
            name="ck_processing_runs_document_id_not_nil",
        ),
        sa.CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'WAITING_RETRY', 'REVIEW_REQUIRED', "
            "'COMPLETED', 'FAILED', 'CANCELLED')",
            name="ck_processing_runs_status_valid",
        ),
        sa.CheckConstraint(
            "status_changed_at >= queued_at",
            name="ck_processing_runs_status_time_ordered",
        ),
        sa.CheckConstraint(
            "started_at IS NULL OR (started_at >= queued_at AND status_changed_at >= started_at)",
            name="ck_processing_runs_started_time_ordered",
        ),
        sa.CheckConstraint(
            "finished_at IS NULL OR "
            "(finished_at >= COALESCE(started_at, queued_at) AND finished_at = status_changed_at)",
            name="ck_processing_runs_finished_time_ordered",
        ),
        sa.CheckConstraint(
            "status <> 'QUEUED' OR started_at IS NULL",
            name="ck_processing_runs_queued_not_started",
        ),
        sa.CheckConstraint(
            "status NOT IN ('RUNNING', 'WAITING_RETRY', 'REVIEW_REQUIRED', 'COMPLETED', 'FAILED') "
            "OR started_at IS NOT NULL",
            name="ck_processing_runs_started_status_has_time",
        ),
        sa.CheckConstraint(
            "(status IN ('COMPLETED', 'FAILED', 'CANCELLED')) = (finished_at IS NOT NULL)",
            name="ck_processing_runs_terminal_status_has_time",
        ),
        sa.CheckConstraint(
            "(started_at IS NULL AND attempt_count = 0) "
            "OR (started_at IS NOT NULL AND attempt_count >= 1)",
            name="ck_processing_runs_attempt_count_consistent",
        ),
        sa.CheckConstraint("version >= 0", name="ck_processing_runs_version_not_negative"),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_processing_runs_document_id_documents",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_processing_runs"),
    )
    op.create_index(
        "ix_processing_runs_document_id_queued_at",
        "processing_runs",
        ["document_id", "queued_at"],
    )
    op.create_index(
        "ix_processing_runs_status_queued_at",
        "processing_runs",
        ["status", "queued_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_processing_runs_status_queued_at", table_name="processing_runs")
    op.drop_index("ix_processing_runs_document_id_queued_at", table_name="processing_runs")
    op.drop_table("processing_runs")
