"""Create immutable structured invoice extractions.

Revision ID: 20260916_03
Revises: 20260916_02
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260916_03"
down_revision: str | None = "20260916_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invoice_extractions",
        sa.Column("processing_run_id", sa.Uuid(), nullable=False),
        sa.Column("method", sa.String(length=32), nullable=False),
        sa.Column("invoice_number", sa.String(length=128), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("supplier_name", sa.String(length=512), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("total_amount", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "processing_run_id <> '00000000-0000-0000-0000-000000000000'",
            name="ck_invoice_extractions_processing_run_id_not_nil",
        ),
        sa.CheckConstraint(
            "method IN ('DETERMINISTIC_RULES', 'OLLAMA')",
            name="ck_invoice_extractions_method_valid",
        ),
        sa.CheckConstraint(
            "invoice_number IS NULL OR btrim(invoice_number) <> ''",
            name="ck_invoice_extractions_invoice_number_not_blank",
        ),
        sa.CheckConstraint(
            "supplier_name IS NULL OR btrim(supplier_name) <> ''",
            name="ck_invoice_extractions_supplier_name_not_blank",
        ),
        sa.CheckConstraint(
            "currency IS NULL OR currency ~ '^[A-Z]{3}$'",
            name="ck_invoice_extractions_currency_valid",
        ),
        sa.CheckConstraint(
            "total_amount IS NULL OR total_amount >= 0",
            name="ck_invoice_extractions_total_amount_not_negative",
        ),
        sa.ForeignKeyConstraint(
            ["processing_run_id"],
            ["processing_runs.id"],
            name="fk_invoice_extractions_processing_run_id_processing_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("processing_run_id", name="pk_invoice_extractions"),
    )


def downgrade() -> None:
    op.drop_table("invoice_extractions")
