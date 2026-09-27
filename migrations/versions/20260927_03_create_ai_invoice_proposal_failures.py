"""Store terminal AI provider failures separately from document failures.

Revision ID: 20260927_03
Revises: 20260927_02
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260927_03"
down_revision: str | None = "20260927_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "ai_invoice_proposal_failures",
        sa.Column("processing_run_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model_reference", sa.String(length=200), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "processing_run_id <> '00000000-0000-0000-0000-000000000000'",
            name=op.f("ck_ai_invoice_proposal_failures_processing_run_id_not_nil"),
        ),
        sa.CheckConstraint(
            "provider = 'OLLAMA'",
            name=op.f("ck_ai_invoice_proposal_failures_provider_supported"),
        ),
        sa.CheckConstraint(
            "btrim(model_reference) <> ''",
            name=op.f("ck_ai_invoice_proposal_failures_model_reference_not_blank"),
        ),
        sa.CheckConstraint(
            "code IN ('TIMEOUT', 'UNAVAILABLE', 'INVALID_RESPONSE')",
            name=op.f("ck_ai_invoice_proposal_failures_code_supported"),
        ),
        sa.ForeignKeyConstraint(
            ["processing_run_id"],
            ["processing_runs.id"],
            name="fk_ai_proposal_failures_run",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "processing_run_id",
            name=op.f("pk_ai_invoice_proposal_failures"),
        ),
    )


def downgrade() -> None:
    op.drop_table("ai_invoice_proposal_failures")
