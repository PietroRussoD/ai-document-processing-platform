"""Create documents table.

Revision ID: 20260913_01
Revises:
Create Date: 2026-09-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260913_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("media_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "id <> '00000000-0000-0000-0000-000000000000'",
            name="ck_documents_id_not_nil",
        ),
        sa.CheckConstraint(
            "length(btrim(original_filename)) > 0",
            name="ck_documents_filename_not_blank",
        ),
        sa.CheckConstraint(
            "media_type = 'application/pdf'",
            name="ck_documents_media_type_pdf",
        ),
        sa.CheckConstraint("size_bytes > 0", name="ck_documents_size_bytes_positive"),
        sa.CheckConstraint("page_count > 0", name="ck_documents_page_count_positive"),
        sa.CheckConstraint(
            "content_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_documents_content_sha256_format",
        ),
        sa.CheckConstraint(
            "length(btrim(storage_key)) > 0",
            name="ck_documents_storage_key_not_blank",
        ),
        sa.CheckConstraint(
            "status IN ('UPLOADED', 'PROCESSING', 'REVIEW_REQUIRED', 'APPROVED', 'REJECTED')",
            name="ck_documents_status_valid",
        ),
        sa.CheckConstraint(
            "status_changed_at >= accepted_at",
            name="ck_documents_timestamps_ordered",
        ),
        sa.CheckConstraint("version >= 0", name="ck_documents_version_not_negative"),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
    )
    op.create_index("ix_documents_content_sha256", "documents", ["content_sha256"])
    op.create_index(
        "ix_documents_status_accepted_at",
        "documents",
        ["status", "accepted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_documents_status_accepted_at", table_name="documents")
    op.drop_index("ix_documents_content_sha256", table_name="documents")
    op.drop_table("documents")
