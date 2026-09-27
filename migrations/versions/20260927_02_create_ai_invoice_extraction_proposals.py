"""Store immutable, provenance-aware AI invoice proposals.

Revision ID: 20260927_02
Revises: 20260927_01
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260927_02"
down_revision: str | None = "20260927_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "ai_invoice_extraction_proposals",
        sa.Column("processing_run_id", sa.Uuid(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model_reference", sa.String(length=200), nullable=False),
        sa.Column("model_digest", sa.String(length=71), nullable=True),
        sa.Column("prompt_version", sa.String(length=100), nullable=False),
        sa.Column("selected_text_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("invoice_number", sa.String(length=200), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("supplier_name", sa.String(length=250), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("total_amount", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("issues", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("proposed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "processing_run_id <> '00000000-0000-0000-0000-000000000000'",
            name=op.f("ck_ai_invoice_extraction_proposals_processing_run_id_not_nil"),
        ),
        sa.CheckConstraint(
            "schema_version = 1",
            name=op.f("ck_ai_invoice_extraction_proposals_schema_version_supported"),
        ),
        sa.CheckConstraint(
            "provider = 'OLLAMA'",
            name=op.f("ck_ai_invoice_extraction_proposals_provider_supported"),
        ),
        sa.CheckConstraint(
            "btrim(model_reference) <> ''",
            name=op.f("ck_ai_invoice_extraction_proposals_model_reference_not_blank"),
        ),
        sa.CheckConstraint(
            "btrim(prompt_version) <> ''",
            name=op.f("ck_ai_invoice_extraction_proposals_prompt_version_not_blank"),
        ),
        sa.CheckConstraint(
            "selected_text_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_ai_invoice_extraction_proposals_selected_text_sha256_valid"),
        ),
        sa.CheckConstraint(
            "model_digest IS NULL OR model_digest ~ '^(sha256:)?[0-9a-fA-F]{64}$'",
            name=op.f("ck_ai_invoice_extraction_proposals_model_digest_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('VALID', 'PARTIAL', 'INVALID')",
            name=op.f("ck_ai_invoice_extraction_proposals_status_valid"),
        ),
        sa.CheckConstraint(
            "invoice_number IS NULL OR btrim(invoice_number) <> ''",
            name=op.f("ck_ai_invoice_extraction_proposals_invoice_number_not_blank"),
        ),
        sa.CheckConstraint(
            "supplier_name IS NULL OR btrim(supplier_name) <> ''",
            name=op.f("ck_ai_invoice_extraction_proposals_supplier_name_not_blank"),
        ),
        sa.CheckConstraint(
            "currency IS NULL OR currency ~ '^[A-Z]{3}$'",
            name=op.f("ck_ai_invoice_extraction_proposals_currency_valid"),
        ),
        sa.CheckConstraint(
            "total_amount IS NULL OR total_amount >= 0",
            name=op.f("ck_ai_invoice_extraction_proposals_total_amount_not_negative"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(issues) = 'array'",
            name=op.f("ck_ai_invoice_extraction_proposals_issues_array"),
        ),
        sa.CheckConstraint(
            "status <> 'VALID' OR (invoice_number IS NOT NULL AND issue_date IS NOT NULL "
            "AND supplier_name IS NOT NULL AND currency IS NOT NULL AND total_amount IS NOT NULL "
            "AND jsonb_array_length(issues) = 0)",
            name=op.f("ck_ai_invoice_extraction_proposals_valid_proposal_complete"),
        ),
        sa.CheckConstraint(
            "status <> 'PARTIAL' OR ((invoice_number IS NOT NULL OR issue_date IS NOT NULL "
            "OR supplier_name IS NOT NULL OR currency IS NOT NULL OR total_amount IS NOT NULL) "
            "AND jsonb_array_length(issues) > 0)",
            name=op.f("ck_ai_invoice_extraction_proposals_partial_proposal_has_fields_and_issues"),
        ),
        sa.CheckConstraint(
            "status <> 'INVALID' OR (invoice_number IS NULL AND issue_date IS NULL "
            "AND supplier_name IS NULL AND currency IS NULL AND total_amount IS NULL "
            "AND jsonb_array_length(issues) > 0)",
            name=op.f(
                "ck_ai_invoice_extraction_proposals_invalid_proposal_has_no_fields_and_issues"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["processing_run_id"],
            ["processing_runs.id"],
            name="fk_ai_invoice_proposals_processing_run_id_processing_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "processing_run_id",
            name=op.f("pk_ai_invoice_extraction_proposals"),
        ),
    )


def downgrade() -> None:
    op.drop_table("ai_invoice_extraction_proposals")
