"""Allow page count to remain unknown until isolated PDF inspection.

Revision ID: 20261019_01
Revises: 20260929_01
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261019_01"
down_revision: str | None = "20260929_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_documents_ck_documents_page_count_positive"),
        "documents",
        type_="check",
    )
    op.alter_column("documents", "page_count", existing_type=sa.Integer(), nullable=True)
    op.create_check_constraint(
        op.f("ck_documents_page_count_positive"),
        "documents",
        "page_count IS NULL OR page_count > 0",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_documents_page_count_positive"), "documents", type_="check")
    op.alter_column("documents", "page_count", existing_type=sa.Integer(), nullable=False)
    op.create_check_constraint(
        op.f("ck_documents_ck_documents_page_count_positive"),
        "documents",
        "page_count > 0",
    )
