"""Index terminal document retention candidate queries.

Revision ID: 20260923_01
Revises: 20260921_02
Create Date: 2026-09-23
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260923_01"
down_revision: str | None = "20260921_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_index(
        "ix_documents_status_status_changed_at",
        "documents",
        ["status", "status_changed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_documents_status_status_changed_at", table_name="documents")
