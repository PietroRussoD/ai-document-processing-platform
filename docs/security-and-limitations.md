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
- Invoice currency values are checked against the ISO 4217 alpha-code data
  bundled by the locked `iso4217` dependency; supported codes change only when
  that dependency is updated.
- The review console can fetch and display a source PDF only after an explicit
  operator action, using the in-memory review bearer token. It revokes its
  temporary object URL when the preview closes or unmounts. Blob bytes are
  returned with `no-store` and `nosniff`, and document IDs are resolved to
  storage keys server-side. This remains a local demo control, not production
  authorization. See
  [ADR 0011](decisions/0011-protect-local-source-document-preview.md).

## Gaps Before Real Use

| Risk | Current boundary |
| --- | --- |
| Unauthorized local access | Most HTTP endpoints and Temporal UI have no authentication; Grafana and PostgreSQL use documented development credentials. No TLS, per-user authorization or tenant isolation exists. |
| Hostile PDFs | Size, page and parser checks limit routine inputs, but there is no malware scan, dedicated parser sandbox or container CPU/memory budget. Do not upload untrusted files. |
| Vulnerable image packages | Images rebuilt from candidate `efa06f0` with `--pull --no-cache` and scanned on 2026-10-02 using Trivy 0.74.0 reported 1 CRITICAL and 76 HIGH API package findings (34 distinct IDs), including `libxml2` and Tesseract, and no HIGH/CRITICAL console findings. The cached vulnerability database was last updated 2026-10-01 because refreshing it from the configured registries was too slow; treat this as a comparison, not the final current-database scan. An OS-package upgrade had cleared three HIGH CVEs for which Debian had fixes; the remaining API report lists no fixed versions. The CRITICAL `libxml2` finding is `CVE-2026-6653` on `2.12.7+dfsg+really2.9.14-2.1+deb13u3`. Debian tracks Trixie as `no-dsa (Minor issue)`, while Trivy still reports CRITICAL; this is not treated as a false positive or a clean image. These are point-in-time findings, not distinct exploitable paths or security clearance. See the [Debian tracker](https://security-tracker.debian.org/tracker/CVE-2026-6653); repeat with a current database for the release candidate. |

The [Debian security tracker for CVE-2026-6653](https://security-tracker.debian.org/tracker/CVE-2026-6653)
lists the installed Trixie `libxml2` version as vulnerable but marks the issue
`no-dsa`/minor for that release. That is Debian's remediation assessment, not
proof that crafted XML cannot reach the package here. The local-only,
synthetic-document boundary is retained; this finding is not accepted for a
publicly exposed document-processing service.
| Data at rest | Local named volumes are not application-encrypted and have no managed backup or recovery policy. Database retention does not remove blob bytes. |
| Advisory model availability | An unavailable Ollama connection records a failed AI execution without changing deterministic extraction or the human-review outcome. Later documents can succeed after connectivity returns; a failed proposal is not automatically replayed, and an in-flight Ollama process restart was not verified. |
| Operational assurance | Readiness and local smoke tests are not production SLOs, alerting or a security review. The UI has accessibility checks but no formal WCAG conformance claim. |

Use only synthetic, non-sensitive documents. `docker compose down` stops the
stack but retains named volumes; deleting those volumes is a separate,
destructive operator action. Do not expose these services through a tunnel,
public reverse proxy or shared host without first designing authentication,
authorization, transport security, document isolation and data lifecycle.
