"""Record whether an invoice correction used an AI proposal.

Revision ID: 20260927_04
Revises: 20260927_03
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260927_04"
down_revision: str | None = "20260927_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "invoice_review_corrections",
        sa.Column("source", sa.String(length=16), server_default="MANUAL", nullable=False),
    )
    op.create_check_constraint(
        "ck_invoice_review_corrections_source_valid",
        "invoice_review_corrections",
        "source IN ('MANUAL', 'AI_PROPOSAL')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_invoice_review_corrections_source_valid",
        "invoice_review_corrections",
        type_="check",
    )
    op.drop_column("invoice_review_corrections", "source")
