"""Create upload idempotency records table.

Revision ID: 20260914_01
Revises: 20260913_02
Create Date: 2026-09-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260914_01"
down_revision: str | None = "20260913_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "upload_idempotency_records",
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("processing_run_id", sa.Uuid(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "idempotency_key = btrim(idempotency_key) AND idempotency_key ~ '^[ -~]+$'",
            name="ck_upload_idempotency_records_key_format",
        ),
        sa.CheckConstraint(
            "request_fingerprint ~ '^[0-9a-f]{64}$'",
            name="ck_upload_idempotency_records_fingerprint_format",
        ),
        sa.CheckConstraint(
            "processing_run_id <> '00000000-0000-0000-0000-000000000000'",
            name="ck_upload_idempotency_records_run_id_not_nil",
        ),
        sa.ForeignKeyConstraint(
            ["processing_run_id"],
            ["processing_runs.id"],
            name="fk_upload_idempotency_records_processing_run_id_processing_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "idempotency_key",
            name="pk_upload_idempotency_records",
        ),
        sa.UniqueConstraint(
            "processing_run_id",
            name="uq_upload_idempotency_records_processing_run_id",
        ),
    )
    op.create_index(
        "ix_upload_idempotency_records_recorded_at",
        "upload_idempotency_records",
        ["recorded_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_upload_idempotency_records_recorded_at",
        table_name="upload_idempotency_records",
    )
    op.drop_table("upload_idempotency_records")
