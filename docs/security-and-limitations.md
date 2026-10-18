# Local Security and Limitations

This is a development fixture for synthetic documents, not a deployment for
confidential data or untrusted users. Its trust boundary is the developer's
machine and the private Compose network, not a public HTTP service.

## Data and Entry Points

- The console forwards `/api` requests to FastAPI. Every document API route
  requires the configured local bearer token. Knowing a document ID is not an
  authorization check. Health, metrics and OpenAPI endpoints remain
  unauthenticated within the loopback boundary.
- Compose requires the operator to provide the shared token in `.env`; host-run
  APIs require it to be configured as well. The token is not a user, role or
  tenant system.
- Any holder of the shared token can access every stored document and perform
  all operator actions.
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
- OCR checks a configurable pixel limit before allocating each page image
  (20,000,000 pixels by default) and rasterizes the next page only after the
  current page's OCR completes. This avoids keeping all page PNGs in memory;
  it does not bound every native allocation or isolate the PDF parser.
- Compose application containers have explicit CPU, memory, swap and PID
  limits, drop all Linux capabilities and enable no-new-privileges. These are
  aggregate container budgets, not per-document parser isolation. See
  [runtime restrictions and verification](runbooks/v1.1-container-restrictions.md).
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
| Unauthorized local access | Health, metrics, OpenAPI and Temporal UI have no authentication; Grafana and PostgreSQL use documented development credentials. Document routes share one local token. No TLS, per-user authorization or tenant isolation exists. |
| Hostile PDFs | Size/page/raster checks and application-container resource budgets limit routine inputs, but there is no malware scan or dedicated parser sandbox. Resource exhaustion may terminate a process rather than produce a document-level error. Do not upload untrusted files. |
| Vulnerable image packages | Fresh ARM64 scan of the v1.0 candidate on 2026-10-03: API 1 CRITICAL and 76 HIGH findings (34 distinct CVEs total); all 77 are Debian OS-package findings across 26 packages, with no fixed version listed by Trivy. Python and Rust dependency results have no HIGH/CRITICAL findings. The API contains `libxml2` `2.12.7+dfsg+really2.9.14-2.1+deb13u3`; for `CVE-2026-6653`, Trivy selects NVD CVSS v3.1 9.8 Critical, while Canonical reports CVSS v4.0 7.0 High, Ubuntu priority Medium, and Debian marks Trixie `no-dsa`/Minor. Those ratings do not make the installed package fixed. The current OCR path rasterizes PDFs with PyMuPDF and sends PNG bytes to Tesseract; runtime inspection confirms `libxml2` is loaded through `libarchive`, but the path review does not prove the CVE is unreachable. The console, rebuilt after Dependabot PR #9 on `nginxinc/nginx-unprivileged:1.31.6-alpine` (Alpine `3.24.2`), has no HIGH/CRITICAL findings. Neither scanner results nor path analysis clear the API image for untrusted documents or public exposure. See the [Debian tracker](https://security-tracker.debian.org/tracker/CVE-2026-6653), [Ubuntu advisory](https://ubuntu.com/security/CVE-2026-6653), [disclosure](https://www.openwall.com/lists/oss-security/2026/06/22/3) and [v1.0 verification record](runbooks/v1.0-verification.md). |
| Data at rest | Local named volumes are not application-encrypted and have no managed backup or recovery policy. Database retention does not remove blob bytes. |
| Advisory model availability | An unavailable Ollama connection records a failed AI execution without changing deterministic extraction or the human-review outcome. Later documents can succeed after connectivity returns; a failed proposal is not automatically replayed, and an in-flight Ollama process restart was not verified. |
| Operational assurance | Readiness and local smoke tests are not production SLOs, alerting or a security review. The UI has accessibility checks but no formal WCAG conformance claim. |

The [Debian security tracker for CVE-2026-6653](https://security-tracker.debian.org/tracker/CVE-2026-6653)
lists the installed Trixie `libxml2` version as vulnerable but marks the issue
`no-dsa`/Minor for that release. That is Debian's remediation assessment, not
proof that crafted XML cannot reach the package here.

The [PDF parser isolation design](security/pdf-parser-isolation-design.md)
records why a disposable per-document parser runtime was deferred from v1.2.0.
The [v1.3.0 scope](releases/v1.3.0.md) proposes resuming that work; no parser
containment is implemented in the application yet.

## v1.1 Image Review

For the v1.1 API image reviewed on 2026-10-16, the
[2026-10-15 CVE triage](runbooks/v1.1-image-cve-triage.md) supersedes the
historical scan counts above: 33 distinct CVEs across 76 package findings
(75 HIGH, 1 CRITICAL). All 33 Debian source-package entries still list Trixie
as vulnerable. The review documents missing exploit prerequisites in several
application paths, residual native-parser uncertainty and proposed PDF/OCR
resource limits and container restrictions. The per-page OCR pixel limit and
incremental rasterization and application-container resource/privilege limits
were implemented on 2026-10-16. Disposable per-document parser isolation remains
outside the implemented controls. The historical decision
below is not v1.1 risk acceptance, and the OCR change does not fix package CVEs.

The [final backend verification on 2026-10-16](runbooks/v1.1-final-backend-verification.md)
rescanned the rebuilt ARM64 API image with a newly downloaded database and
confirmed the same 33 CVEs across 76 HIGH/CRITICAL package associations, with
no fixed versions reported by Trivy. The backend suite passed all 615 tests.

The [v1.1 release scope decision](runbooks/v1.1-release-scope-decision.md)
records acceptance of the remaining image findings only for a local demo with
synthetic documents, and defers physical-device checks for that release. The
findings remain open. Public hosting, untrusted documents and API image
distribution remain out of scope; this does not extend the v1.0 acceptance
automatically.

## v1.2 Image Review

On 2026-10-18, Trivy 0.74.0 scanned the locally built ARM64 v1.2 candidate
images using a vulnerability database downloaded at 12:30 UTC. The API image
`document-platform-api:dev` has local image ID
`sha256:37b196acaff9e7b32ffcd788947cd04a0bb4d3e10e1fe6abe36fde0328eabea4`.
Trivy reported 76 Debian 13.7 OS-package findings: 75 HIGH and one CRITICAL,
across 33 distinct CVEs. No HIGH/CRITICAL Python-package findings were
reported. The scan does not establish exploitability or clear the image for
untrusted input.

The console image after a clean rebuild,
`document-platform-console:dev` with local image ID
`sha256:388751872d29c73005ca82e1f6a21fef7678c4fe54216731551256b354942fe8`,
had no HIGH/CRITICAL findings. The first Compose build reused a cached Alpine
upgrade layer and reported HIGH `CVE-2026-77214` in `libexpat 2.8.5-r0`, for
which Trivy listed `2.9.0-r0` as fixed. Rebuilding without cache executed the
existing `apk --no-cache upgrade` step and installed `2.9.0-r0`; the subsequent
scan reported no HIGH/CRITICAL findings. This confirms why a cached local
image scan alone can miss package updates available at build time.

The API findings are accepted for v1.2 only within the local, synthetic-data
scope recorded in the [v1.2 release scope decision](runbooks/v1.2-release-scope-decision.md).
The image is not approved for public hosting, confidential documents, untrusted
PDFs or distribution.

## v1.0 Release Risk Decision

The residual `CVE-2026-6653` finding in the API image is accepted for the
v1.0 **local portfolio demonstration only**, subject to all of these limits:

- use synthetic, non-sensitive documents only;
- keep the stack bound to the local machine; do not expose it through a tunnel,
  public proxy or shared host;
- do not publish or distribute the API runtime image as a release artifact;
- keep the Trivy finding visible; do not suppress it or describe the image as
  vulnerability-free.

This is a scoped release decision, not a claim that the package is fixed or the
vulnerability unreachable. Runtime inspection found `libxml2` loaded by
Tesseract through `libarchive`, and the application's known OCR path supplies
rasterized PNG data. That path review is not proof of non-reachability. Reassess
when Debian publishes a fix or before any use with untrusted documents, public
exposure or image distribution. Such use remains out of scope until the image
is remediated and revalidated.

Use only synthetic, non-sensitive documents. `docker compose down` stops the
stack but retains named volumes; deleting those volumes is a separate,
destructive operator action. Do not expose these services through a tunnel,
public reverse proxy or shared host without first designing authentication,
authorization, transport security, document isolation and data lifecycle.
