"""Create immutable reprocessing operations.

Revision ID: 20260920_02
Revises: 20260920_01
Create Date: 2026-09-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260920_02"
down_revision: str | None = "20260920_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reprocessing_operations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("source_run_id", sa.Uuid(), nullable=False),
        sa.Column("replacement_run_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "id <> '00000000-0000-0000-0000-000000000000'",
            name="ck_reprocessing_operations_id_not_nil",
        ),
        sa.CheckConstraint(
            "document_id <> '00000000-0000-0000-0000-000000000000'",
            name="ck_reprocessing_operations_document_id_not_nil",
        ),
        sa.CheckConstraint(
            "source_run_id <> '00000000-0000-0000-0000-000000000000'",
            name="ck_reprocessing_operations_source_run_id_not_nil",
        ),
        sa.CheckConstraint(
            "replacement_run_id <> '00000000-0000-0000-0000-000000000000'",
            name="ck_reprocessing_operations_replacement_run_id_not_nil",
        ),
        sa.CheckConstraint(
            "source_run_id <> replacement_run_id",
            name="ck_reprocessing_operations_source_run_id_differs",
        ),
        sa.CheckConstraint(
            "requested_by = btrim(requested_by) AND length(requested_by) BETWEEN 1 AND 128",
            name="ck_reprocessing_operations_requested_by_format",
        ),
        sa.CheckConstraint(
            "reason = btrim(reason) AND length(reason) BETWEEN 1 AND 500",
            name="ck_reprocessing_operations_reason_format",
        ),
        sa.CheckConstraint(
            "idempotency_key = btrim(idempotency_key) AND idempotency_key ~ '^[ -~]+$'",
            name="ck_reprocessing_operations_idempotency_key_format",
        ),
        sa.CheckConstraint(
            "request_fingerprint ~ '^[0-9a-f]{64}$'",
            name="ck_reprocessing_operations_request_fingerprint_format",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_reprocessing_operations_document_id_documents",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_run_id"],
            ["processing_runs.id"],
            name="fk_reprocessing_operations_source_run_id_processing_runs",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["replacement_run_id"],
            ["processing_runs.id"],
            name="fk_reprocessing_operations_replacement_run_id_processing_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_reprocessing_operations"),
        sa.UniqueConstraint(
            "document_id",
            "idempotency_key",
            name="uq_reprocessing_operations_document_id_idempotency_key",
        ),
        sa.UniqueConstraint(
            "replacement_run_id",
            name="uq_reprocessing_operations_replacement_run_id",
        ),
    )
    op.create_index(
        "ix_reprocessing_operations_document_id_requested_at",
        "reprocessing_operations",
        ["document_id", "requested_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_reprocessing_operations_document_id_requested_at",
        table_name="reprocessing_operations",
    )
    op.drop_table("reprocessing_operations")
