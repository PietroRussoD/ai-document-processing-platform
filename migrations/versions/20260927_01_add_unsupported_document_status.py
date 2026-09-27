"""Record successful workflows that do not support their document type.

Revision ID: 20260927_01
Revises: 20260923_01
Create Date: 2026-09-27
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260927_01"
down_revision: str | None = "20260923_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None

_STATUS_CHECK = "ck_documents_status_valid"
_PREVIOUS_STATUSES = "'UPLOADED', 'PROCESSING', 'REVIEW_REQUIRED', 'APPROVED', 'REJECTED', 'FAILED'"


def upgrade() -> None:
    op.drop_constraint(_STATUS_CHECK, "documents", type_="check")
    op.create_check_constraint(
        _STATUS_CHECK,
        "documents",
        f"status IN ({_PREVIOUS_STATUSES}, 'UNSUPPORTED')",
    )
    op.execute(
        """
        UPDATE documents AS document
        SET status = 'UNSUPPORTED',
            status_changed_at = processing_run.finished_at,
            version = document.version + 1
        FROM processing_runs AS processing_run
        JOIN document_classifications AS classification
          ON classification.processing_run_id = processing_run.id
        WHERE document.id = processing_run.document_id
          AND document.status = 'PROCESSING'
          AND processing_run.status = 'COMPLETED'
          AND classification.document_type <> 'INVOICE'
          AND NOT EXISTS (
              SELECT 1
              FROM processing_runs AS later_run
              WHERE later_run.document_id = document.id
                AND (later_run.queued_at, later_run.id)
                    > (processing_run.queued_at, processing_run.id)
          )
        """
    )


def downgrade() -> None:
    op.execute("UPDATE documents SET status = 'PROCESSING' WHERE status = 'UNSUPPORTED'")
    op.drop_constraint(_STATUS_CHECK, "documents", type_="check")
    op.create_check_constraint(
        _STATUS_CHECK,
        "documents",
        f"status IN ({_PREVIOUS_STATUSES})",
    )
