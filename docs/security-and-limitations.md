# Local Security and Limitations

This is a development fixture for synthetic documents, not a deployment for
confidential data or untrusted users. Its trust boundary is the developer's
machine and the private Compose network, not a public HTTP service.

## Data and Entry Points

- The console forwards `/api` requests to FastAPI. Upload, work-queue, status,
  health, metrics and OpenAPI endpoints are unauthenticated. Knowing a document
  ID is not an authorization check.
- Review resolution and reprocessing require one configured local bearer token.
  Compose supplies a local-only demo token unless overridden; host-run APIs
  require it to be configured. The token is not a user, role or tenant system.
- Source-PDF retrieval requires the same bearer token. Any holder of the shared
  token can retrieve every stored document through this route.
- PostgreSQL owns document metadata and processing evidence. A named volume
  holds PDF blobs; Temporal has its own database and an unauthenticated UI.
  The console, API, worker and dispatcher share a Compose network.

## Controls Present

- Published Compose ports bind to `127.0.0.1`, including the optional
  observability profile. This limits host-network exposure, but does not
  authenticate local processes or peers on the Compose network.
- API and console images run without root. Uploads have byte and page limits;
  PDF structure is checked before registration. Blob paths are derived from
  content hashes rather than client filenames.
- Application request logs use matched route templates and allowlisted fields.
  Routine NGINX access logging is disabled for `/api` so document IDs in URLs
  are not copied to proxy access logs. Error diagnostics may still contain
  request details and should not be treated as a secret-free audit trail.
- Database retention is explicit and dry-run-first. Blob auditing reports
  potential orphans but never deletes files.
- The browser console does not yet preview source PDFs; use the authenticated
  API route for local inspection. Blob bytes are returned with `no-store` and
  `nosniff`, and document IDs are resolved to storage keys server-side. This
  remains a local demo control, not production authorization. See
  [ADR 0011](decisions/0011-protect-local-source-document-preview.md).

## Gaps Before Real Use

| Risk | Current boundary |
| --- | --- |
| Unauthorized local access | Most HTTP endpoints and Temporal UI have no authentication; Grafana and PostgreSQL use documented development credentials. No TLS, per-user authorization or tenant isolation exists. |
| Hostile PDFs | Size, page and parser checks limit routine inputs, but there is no malware scan, dedicated parser sandbox or container CPU/memory budget. Do not upload untrusted files. |
| Vulnerable image packages | A 2026-09-27 Trivy 0.74.0 scan of freshly rebuilt images reported 1 CRITICAL and 76 HIGH API package findings (34 distinct IDs), including `libxml2` and Tesseract, and no HIGH/CRITICAL console findings. These are point-in-time scanner results, not distinct exploitable paths or security clearance. Rebuild, rescan and review exposure before later releases; do not claim a clean API image. |
| Data at rest | Local named volumes are not application-encrypted and have no managed backup or recovery policy. Database retention does not remove blob bytes. |
| Operational assurance | Readiness and local smoke tests are not production SLOs, alerting or a security review. The UI has accessibility checks but no formal WCAG conformance claim. |

Use only synthetic, non-sensitive documents. `docker compose down` stops the
stack but retains named volumes; deleting those volumes is a separate,
destructive operator action. Do not expose these services through a tunnel,
public reverse proxy or shared host without first designing authentication,
authorization, transport security, document isolation and data lifecycle.
