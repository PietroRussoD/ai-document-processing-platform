"""Persist embedded-text quality decisions.

Revision ID: 20260915_04
Revises: 20260915_03
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_04"
down_revision: str | None = "20260915_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "document_text_extractions",
        sa.Column("quality", sa.String(length=32), nullable=True),
    )
    op.execute("UPDATE document_text_extractions SET quality = 'SUFFICIENT' WHERE quality IS NULL")
    op.alter_column("document_text_extractions", "quality", nullable=False)
    op.create_check_constraint(
        "ck_document_text_extractions_quality_valid",
        "document_text_extractions",
        "quality IN ('SUFFICIENT', 'OCR_RECOMMENDED')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_document_text_extractions_quality_valid",
        "document_text_extractions",
        type_="check",
    )
    op.drop_column("document_text_extractions", "quality")
