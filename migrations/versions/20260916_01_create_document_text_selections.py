"""Create immutable canonical-text selections.

Revision ID: 20260916_01
Revises: 20260915_05
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260916_01"
down_revision: str | None = "20260915_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_text_selections",
        sa.Column("processing_run_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "processing_run_id <> '00000000-0000-0000-0000-000000000000'",
            name="ck_document_text_selections_processing_run_id_not_nil",
        ),
        sa.CheckConstraint(
            "source IN ('EMBEDDED', 'OCR')",
            name="ck_document_text_selections_source_valid",
        ),
        sa.CheckConstraint(
            "reason IN ('EMBEDDED_SUFFICIENT', 'OCR_HAS_MORE_TEXT', 'EMBEDDED_NOT_WORSE')",
            name="ck_document_text_selections_reason_valid",
        ),
        sa.CheckConstraint(
            "(reason = 'EMBEDDED_SUFFICIENT' AND source = 'EMBEDDED') OR "
            "(reason = 'OCR_HAS_MORE_TEXT' AND source = 'OCR') OR "
            "(reason = 'EMBEDDED_NOT_WORSE' AND source = 'EMBEDDED')",
            name="ck_document_text_selections_source_matches_reason",
        ),
        sa.ForeignKeyConstraint(
            ["processing_run_id"],
            ["processing_runs.id"],
            name="fk_document_text_selections_processing_run_id_processing_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("processing_run_id", name="pk_document_text_selections"),
    )


def downgrade() -> None:
    op.drop_table("document_text_selections")
