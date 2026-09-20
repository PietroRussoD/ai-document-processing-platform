"""Prevent concurrent active processing runs per document.

Revision ID: 20260920_03
Revises: 20260920_02
Create Date: 2026-09-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260920_03"
down_revision: str | None = "20260920_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIVE_RUN_STATUSES = "'QUEUED', 'RUNNING', 'WAITING_RETRY', 'REVIEW_REQUIRED'"


def upgrade() -> None:
    op.create_index(
        "uq_processing_runs_document_id_active",
        "processing_runs",
        ["document_id"],
        unique=True,
        postgresql_where=sa.text(f"status IN ({ACTIVE_RUN_STATUSES})"),
    )


def downgrade() -> None:
    op.drop_index("uq_processing_runs_document_id_active", table_name="processing_runs")
