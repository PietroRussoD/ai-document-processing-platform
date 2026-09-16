"""Create immutable document classifications.

Revision ID: 20260916_02
Revises: 20260916_01
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260916_02"
down_revision: str | None = "20260916_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_classifications",
        sa.Column("processing_run_id", sa.Uuid(), nullable=False),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("classified_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "processing_run_id <> '00000000-0000-0000-0000-000000000000'",
            name="ck_document_classifications_processing_run_id_not_nil",
        ),
        sa.CheckConstraint(
            "document_type IN ('INVOICE', 'PURCHASE_ORDER', 'CREDIT_NOTE', 'UNKNOWN')",
            name="ck_document_classifications_document_type_valid",
        ),
        sa.CheckConstraint(
            "reason IN ('KEYWORD_MATCHED', 'NO_MATCH', 'AMBIGUOUS_MATCH')",
            name="ck_document_classifications_reason_valid",
        ),
        sa.CheckConstraint(
            "(document_type = 'UNKNOWN') = (reason <> 'KEYWORD_MATCHED')",
            name="ck_document_classifications_type_matches_reason",
        ),
        sa.ForeignKeyConstraint(
            ["processing_run_id"],
            ["processing_runs.id"],
            name="fk_document_classifications_processing_run_id_processing_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("processing_run_id", name="pk_document_classifications"),
    )


def downgrade() -> None:
    op.drop_table("document_classifications")
