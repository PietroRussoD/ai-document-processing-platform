"""Record the authenticated reviewer on immutable resolutions.

Revision ID: 20260917_03
Revises: 20260917_02
Create Date: 2026-09-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260917_03"
down_revision: str | None = "20260917_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LEGACY_REVIEWER_ID = "legacy-unattributed"


def upgrade() -> None:
    op.add_column(
        "review_resolutions",
        sa.Column("reviewer_id", sa.String(length=200), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE review_resolutions "
            f"SET reviewer_id = '{_LEGACY_REVIEWER_ID}' "
            "WHERE reviewer_id IS NULL"
        )
    )
    op.alter_column("review_resolutions", "reviewer_id", nullable=False)
    op.create_check_constraint(
        "ck_review_resolutions_reviewer_id_valid",
        "review_resolutions",
        "length(btrim(reviewer_id)) BETWEEN 1 AND 200",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_review_resolutions_reviewer_id_valid",
        "review_resolutions",
        type_="check",
    )
    op.drop_column("review_resolutions", "reviewer_id")
