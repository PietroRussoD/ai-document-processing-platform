"""Create immutable operator invoice corrections.

Revision ID: 20260918_01
Revises: 20260917_03
Create Date: 2026-09-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260918_01"
down_revision: str | None = "20260917_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invoice_review_corrections",
        sa.Column("processing_run_id", sa.Uuid(), nullable=False),
        sa.Column("field", sa.String(length=32), nullable=False),
        sa.Column("corrected_text", sa.String(length=512), nullable=True),
        sa.Column("corrected_date", sa.Date(), nullable=True),
        sa.Column("corrected_amount", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("corrected_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "processing_run_id <> '00000000-0000-0000-0000-000000000000'",
            name="ck_invoice_review_corrections_processing_run_id_not_nil",
        ),
        sa.CheckConstraint(
            "field IN ('INVOICE_NUMBER', 'ISSUE_DATE', 'SUPPLIER_NAME', 'CURRENCY', "
            "'TOTAL_AMOUNT')",
            name="ck_invoice_review_corrections_field_valid",
        ),
        sa.CheckConstraint(
            "(field IN ('INVOICE_NUMBER', 'SUPPLIER_NAME', 'CURRENCY') "
            "AND corrected_text IS NOT NULL AND corrected_date IS NULL "
            "AND corrected_amount IS NULL) "
            "OR (field = 'ISSUE_DATE' AND corrected_text IS NULL "
            "AND corrected_date IS NOT NULL AND corrected_amount IS NULL) "
            "OR (field = 'TOTAL_AMOUNT' AND corrected_text IS NULL "
            "AND corrected_date IS NULL AND corrected_amount IS NOT NULL)",
            name="ck_invoice_review_corrections_value_shape_valid",
        ),
        sa.CheckConstraint(
            "(field = 'INVOICE_NUMBER' AND length(btrim(corrected_text)) BETWEEN 1 AND 128) "
            "OR (field = 'SUPPLIER_NAME' AND length(btrim(corrected_text)) BETWEEN 1 AND 512) "
            "OR (field = 'CURRENCY' AND corrected_text ~ '^[A-Z]{3}$') "
            "OR field IN ('ISSUE_DATE', 'TOTAL_AMOUNT')",
            name="ck_invoice_review_corrections_text_value_valid",
        ),
        sa.CheckConstraint(
            "field <> 'TOTAL_AMOUNT' OR corrected_amount > 0",
            name="ck_invoice_review_corrections_amount_positive",
        ),
        sa.ForeignKeyConstraint(
            ["processing_run_id"],
            ["review_resolutions.processing_run_id"],
            name="fk_invoice_review_corrections_run_id_review_resolutions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "processing_run_id",
            "field",
            name="pk_invoice_review_corrections",
        ),
    )


def downgrade() -> None:
    op.drop_table("invoice_review_corrections")
