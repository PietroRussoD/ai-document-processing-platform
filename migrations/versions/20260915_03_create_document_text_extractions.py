"""Create immutable document-text extraction records.

Revision ID: 20260915_03
Revises: 20260915_02
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_03"
down_revision: str | None = "20260915_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_text_extractions",
        sa.Column("processing_run_id", sa.Uuid(), nullable=False),
        sa.Column("method", sa.String(length=32), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("non_whitespace_character_count", sa.Integer(), nullable=False),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "processing_run_id <> '00000000-0000-0000-0000-000000000000'",
            name="ck_document_text_extractions_processing_run_id_not_nil",
        ),
        sa.CheckConstraint(
            "method IN ('PYMUPDF')",
            name="ck_document_text_extractions_method_valid",
        ),
        sa.CheckConstraint(
            "page_count > 0",
            name="ck_document_text_extractions_page_count_positive",
        ),
        sa.CheckConstraint(
            "character_count = char_length(text)",
            name="ck_document_text_extractions_character_count_matches_text",
        ),
        sa.CheckConstraint(
            "non_whitespace_character_count >= 0",
            name="ck_document_text_extractions_non_whitespace_count_valid",
        ),
        sa.ForeignKeyConstraint(
            ["processing_run_id"],
            ["processing_runs.id"],
            name="fk_document_text_extractions_processing_run_id_processing_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("processing_run_id", name="pk_document_text_extractions"),
    )


def downgrade() -> None:
    op.drop_table("document_text_extractions")
