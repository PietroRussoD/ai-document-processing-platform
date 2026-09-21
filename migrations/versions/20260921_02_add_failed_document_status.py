"""Allow documents to reflect terminal processing failure.

Revision ID: 20260921_02
Revises: 20260921_01
Create Date: 2026-09-21
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260921_02"
down_revision: str | None = "20260921_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STATUS_CHECK = "ck_documents_status_valid"
_PREVIOUS_STATUSES = "'UPLOADED', 'PROCESSING', 'REVIEW_REQUIRED', 'APPROVED', 'REJECTED'"
_CURRENT_STATUSES = f"{_PREVIOUS_STATUSES}, 'FAILED'"


def upgrade() -> None:
    op.drop_constraint(_STATUS_CHECK, "documents", type_="check")
    op.create_check_constraint(
        _STATUS_CHECK,
        "documents",
        f"status IN ({_CURRENT_STATUSES})",
    )


def downgrade() -> None:
    op.drop_constraint(_STATUS_CHECK, "documents", type_="check")
    op.create_check_constraint(
        _STATUS_CHECK,
        "documents",
        f"status IN ({_PREVIOUS_STATUSES})",
    )
