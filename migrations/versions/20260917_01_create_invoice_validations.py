"""Create immutable invoice validations.

Revision ID: 20260917_01
Revises: 20260916_03
Create Date: 2026-09-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260917_01"
down_revision: str | None = "20260916_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invoice_validations",
        sa.Column("processing_run_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("issues", JSONB(), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "processing_run_id <> '00000000-0000-0000-0000-000000000000'",
            name="ck_invoice_validations_processing_run_id_not_nil",
        ),
        sa.CheckConstraint(
            "decision IN ('AUTO_APPROVE', 'REVIEW_REQUIRED')",
            name="ck_invoice_validations_decision_valid",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(issues) = 'array'",
            name="ck_invoice_validations_issues_array",
        ),
        sa.CheckConstraint(
            'issues <@ \'["MISSING_INVOICE_NUMBER", "MISSING_ISSUE_DATE", '
            '"MISSING_SUPPLIER_NAME", "MISSING_CURRENCY", '
            '"MISSING_TOTAL_AMOUNT", "NON_POSITIVE_TOTAL_AMOUNT"]\'::jsonb',
            name="ck_invoice_validations_issues_valid",
        ),
        sa.CheckConstraint(
            "(decision = 'AUTO_APPROVE') = (jsonb_array_length(issues) = 0)",
            name="ck_invoice_validations_decision_matches_issues",
        ),
        sa.ForeignKeyConstraint(
            ["processing_run_id"],
            ["processing_runs.id"],
            name="fk_invoice_validations_processing_run_id_processing_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("processing_run_id", name="pk_invoice_validations"),
    )


def downgrade() -> None:
    op.drop_table("invoice_validations")
