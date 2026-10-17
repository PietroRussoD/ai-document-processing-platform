# ADR 0013: Protect Document API Routes with One Local Operator Token

## Status

Proposed for v1.2.0. No implementation changes are included in this decision.

## Context

The application remains a local portfolio demo for synthetic documents, with
published Compose ports bound to `127.0.0.1`. A shared bearer token currently
protects source-PDF retrieval, review decisions and reprocessing. Compose still
provides a known demo token by default, while document upload, work-queue reads
and status reads do not require a token.

The operator console already keeps one shared token in memory and uses it for
the protected operations. Extending that existing pattern would give the
document API one clear access boundary without introducing a user-management
system. This would be a local access gate, not an identity system or protection
for a publicly reachable service.

## Decision

Use one explicitly configured, high-entropy bearer token for every route that
uploads, reads or changes document data:

- `POST /api/v1/documents`
- `GET /api/v1/documents`
- `GET /api/v1/documents/{document_id}`
- `GET /api/v1/documents/{document_id}/source`
- `POST /api/v1/documents/{document_id}/review-resolution`
- `POST /api/v1/documents/{document_id}/reprocessing-requests`

The implementation should follow these constraints:

- Remove the known token fallback from Compose. Require a generated local
  secret supplied through the ignored `.env` file; keep only a placeholder and
  generation instructions in tracked examples. The existing settings
  validation requires at least 32 characters.
- Reject missing or invalid credentials before reading or changing document
  data. Use the existing constant-time bearer-token comparison and never put
  the token in logs, URLs or persistent browser storage.
- Have the Documents console request the token before loading queues or a
  selected document. Keep it in memory, attach it to all document API calls,
  and clear it on reload or explicit sign-out.
- Leave `/health/live`, `/health/ready` and `/metrics` unauthenticated for
  process probes and the local Prometheus scrape. Keep these and the OpenAPI
  documentation reachable only within the existing loopback boundary.
- Keep Temporal, its UI, Grafana, Prometheus and PostgreSQL under the existing
  local-only Compose boundary. This decision does not add authentication to
  those services.
- Do not add accounts, passwords, roles, tenants or per-user sessions. A token
  holder receives the same access as the single local operator.

## Consequences

- The console cannot upload documents or display queues and status without the
  configured token; direct API callers must also present it.
- The credential grants broad access to every stored document and all operator
  actions. It does not distinguish people, provide per-user audit, or protect
  against a local process that can read the secret or inspect the running
  browser.
- Loopback binding and synthetic-only use remain required. This token scheme
  does not make the service suitable for a shared host, real documents or
  Internet exposure.
- Tests must cover missing, invalid and valid credentials for every protected
  route, plus the unauthenticated health and metrics paths. Browser checks must
  cover the token prompt, access errors, clearing and reload behavior.

## Alternatives

- **Keep route-level authentication as it is.** This is adequate for the
  current loopback-only demo but leaves upload, queue and status APIs open to
  local callers. It remains a valid choice if the portfolio exercise is
  deferred.
- **Add accounts, passwords or an external identity provider.** This is not
  justified for one local operator and would imply session, recovery,
  authorization and deployment requirements that this project does not have.
