"""Relational representation of a document."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from document_platform.adapters.outbound.postgresql.metadata import Base


class DocumentRecord(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("id <> '00000000-0000-0000-0000-000000000000'", name="id_not_nil"),
        CheckConstraint("length(btrim(original_filename)) > 0", name="filename_not_blank"),
        CheckConstraint("media_type = 'application/pdf'", name="media_type_pdf"),
        CheckConstraint("size_bytes > 0", name="size_bytes_positive"),
        CheckConstraint("page_count IS NULL OR page_count > 0", name="page_count_positive"),
        CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="content_sha256_format"),
        CheckConstraint("length(btrim(storage_key)) > 0", name="storage_key_not_blank"),
        CheckConstraint(
            "status IN ('UPLOADED', 'PROCESSING', 'REVIEW_REQUIRED', 'APPROVED', 'REJECTED', "
            "'FAILED', 'UNSUPPORTED')",
            name="status_valid",
        ),
        CheckConstraint("status_changed_at >= accepted_at", name="timestamps_ordered"),
        CheckConstraint("version >= 0", name="version_not_negative"),
        Index("ix_documents_content_sha256", "content_sha256"),
        Index("ix_documents_status_accepted_at", "status", "accepted_at"),
        Index("ix_documents_status_status_changed_at", "status", "status_changed_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    original_filename: Mapped[str] = mapped_column(Text)
    media_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer)
