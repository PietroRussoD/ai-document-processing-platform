# ADR 0009: Use Explicit, Safe Document Retention

## Status

Accepted

## Context

Uploaded files are stored by content hash, so multiple documents can reference
one physical blob. The upload flow publishes the file before it registers the
document in PostgreSQL. A failed registration can leave an orphan, while
deleting a blob after removing one document can break another document that
shares the same hash. A new upload can also race a cleanup operation.

Document deletion cascades to processing and reprocessing evidence. Retention
must therefore be an explicit destructive operation, not an implicit status
transition or background timer.

## Decision

- Retention is operator-invoked; no scheduler or HTTP deletion endpoint is
  introduced.
- The operator must supply a positive retention period. A dry run is the
  default; applying deletions requires an explicit `--apply` flag.
- A document is eligible only when its status is `APPROVED`, `REJECTED` or
  `FAILED`, and its `status_changed_at` is older than the calculated cutoff.
  `UPLOADED`, `PROCESSING` and `REVIEW_REQUIRED` documents are never eligible.
- Deleting an eligible document removes its document-owned processing and
  reprocessing records through the existing database cascades. The operation
  emits a bounded audit summary without retaining filenames, document content
  or raw errors.
- Physical blob deletion is a separate garbage-collection operation. It must
  verify that no document references the blob and serialize upload and cleanup
  operations for the same content hash through a shared database-backed blob
  catalog lock. An age/grace period by itself is not sufficient to prevent the
  upload-versus-delete race. Until that coordination exists, orphan scanning
  may report candidates but must not unlink blobs.

## Consequences

- Retention policy is explicit and reviewable before any document data is
  deleted.
- Human review work and active processing cannot be removed by the retention
  selector.
- Processing evidence is intentionally removed with its parent document; the
  aggregate audit summary records the cleanup outcome without preserving
  document identifiers or filenames.
- Blob-catalog coordination is a prerequisite for physical garbage collection
  and must have concurrency tests before deletion is enabled.
- This local portfolio policy is not a legal retention recommendation for a
  production deployment; deployments must choose a period appropriate to their
  data obligations.
