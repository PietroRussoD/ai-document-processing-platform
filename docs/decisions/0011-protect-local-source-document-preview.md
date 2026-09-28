# ADR 0011: Protect Local Source-Document Preview

## Status

Accepted. Local-demo scope only.

## Context

Operators must compare extracted and proposed invoice fields with the original
PDF before approving or correcting them. The console currently shows structured
results but does not provide the source document. Status APIs intentionally do
not expose document text or storage paths. The existing review credential is a
shared static bearer token, suitable only for this loopback-bound synthetic
demo, not real customer documents.

## Decision

- Add a separate PDF-source endpoint; do not add source bytes, text or storage
  keys to document-status and work-queue responses.
- Require the configured review bearer token before looking up a document or
  reading storage. Reuse the existing constant-time token verification.
- Resolve the document ID to its persisted storage key server-side. Never build
  a path from the request ID or client filename.
- Return only the associated PDF, with `application/pdf`,
  `X-Content-Type-Options: nosniff` and `Cache-Control: no-store`.
- The review console fetches the PDF only after an explicit operator action,
  using the token held in memory. It displays a temporary browser object URL;
  never put the token in a URL or persistent browser storage, and revoke the
  object URL when the preview closes or the component unmounts.
- This is a local demo control, not production authorization. Keep Compose
  ports bound to loopback and use synthetic documents only.

## Consequences

- The separate source endpoint permits evidence inspection without widening
  metadata/status contracts. The console preview is intentionally on-demand and
  shares the review token only in memory.
- The bearer token grants access to source documents as well as review actions;
  anyone who obtains it can read all documents reachable through the endpoint.
- The static token, unauthenticated status reads, absent tenant isolation and
  lack of encryption remain unacceptable for confidential or untrusted data.
- Backend tests cover missing/invalid credentials, unknown documents, storage
  lookup and response headers. Frontend tests cover explicit fetch, token
  forwarding, safe error display and object-URL revocation.
