# Development and Verification

Run each command block from the repository root unless stated otherwise.
See [Local Demo and Operations](local-demo.md) for the API, worker, console,
metrics and storage setup.

## Prerequisites

Use Python 3.13, `uv`, Node.js 24, pnpm 11.23.0, `jq` and a running Docker
daemon for Testcontainers. The host OCR integration test also needs Tesseract.
Install the locked backend dependencies before running individual checks:

```bash
uv sync --all-groups --locked
```

For individual frontend commands, install dependencies in
`apps/operator-console` with `pnpm install --frozen-lockfile` first.

## Backend and Clean Checkout Checks

Run the quality gates with:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

From a fresh checkout, run the locked backend/frontend checks, Compose
configuration validation and package SBOM exports together with:

```bash
bash scripts/verify_clean_checkout.sh
```

This requires Python 3.13, `uv`, Node.js 24, pnpm 11.23, `jq` and a running
Docker daemon for Testcontainers. It does not start the application stack or
run browser accessibility checks, Gitleaks or image scans; those remain
separate checks. One real OCR integration test is skipped if Tesseract is not
installed. Generated reports and SBOMs stay in ignored paths.

## Operator Console

Run the frontend quality gates with:

```bash
cd apps/operator-console
pnpm check
```

The operator console also has a local Storybook catalogue for reusable visual
components. Run it with `pnpm storybook`; build the static catalogue with
`pnpm build-storybook`. The Storybook a11y addon is enabled for interactive
inspection. Component tests also run axe semantic checks. Browser-based
contrast and keyboard-flow verification remains separate; this project does
not claim formal WCAG conformance.

The review-form stories include on-demand preview of the existing synthetic
invoice, loading and source-loading failure. Storybook serves only synthetic
examples from `examples/documents` under `/fixtures`; its preview API is a demo
stub, not an authenticated backend. Enter any non-empty dummy token and click
**View source PDF**. The application itself still uses the protected endpoint.

The review panel keeps native controls in a tested keyboard order. When a
review decision is rejected by the API, focus moves to the associated alert and
the operator-token field references that error message.

Run the browser accessibility checks locally with:

```bash
cd apps/operator-console
pnpm exec playwright install chromium
pnpm test:a11y:browser
```

The command starts Storybook when necessary, runs axe and layout checks against
component states, and verifies narrow 320 px layouts. It uses full Chromium's
headless mode (`channel: chromium`) so the native PDF viewer renders. Browser
checks are intentionally not part of the ordinary CI gate. Native PDF-viewer
accessibility and other browsers require separate manual verification.

## Backend Coverage and Dependency Inventories

Backend tests enforce branch coverage of at least 85%. `uv run pytest` writes a
local HTML report to `htmlcov/index.html` and a machine-readable report to
`coverage.xml`. CI retains both as the `backend-coverage` artifact for 14 days.

CI also exports the locked Python runtime dependencies as a CycloneDX 1.5 SBOM
in the `python-runtime-sbom` artifact. Generate the same file locally with:

```bash
mkdir -p artifacts
uv export --preview-features sbom-export --format cyclonedx1.5 --no-dev --locked --offline --quiet --output-file artifacts/python-runtime.cdx.json
```

The frontend job likewise exports production dependencies from
`apps/operator-console/pnpm-lock.yaml` as the `frontend-runtime-sbom` artifact.
Generate it locally from `apps/operator-console` with:

```bash
cd apps/operator-console
mkdir -p ../../artifacts
pnpm sbom --sbom-format cyclonedx --sbom-type application --lockfile-only --prod > ../../artifacts/frontend-runtime.cdx.json
```

The preview `uv` export and pnpm lockfile export are package inventories, not
vulnerability scans. They do not inventory OS packages or the final images;
the frontend export also excludes build-only dependencies.

## Image Inventories and Vulnerability Checks

For an optional inventory of freshly built local images, use Docker Scout:

```bash
docker build -t document-platform-api:sbom .
docker build -t document-platform-console:sbom apps/operator-console
mkdir -p artifacts
DOCKER_SCOUT_OFFLINE=true docker scout sbom --format cyclonedx --output artifacts/api-image.cdx.json local://document-platform-api:sbom
DOCKER_SCOUT_OFFLINE=true docker scout sbom --format cyclonedx --output artifacts/console-image.cdx.json local://document-platform-console:sbom
```

`local://` prevents a registry fallback, and Scout's offline mode avoids
outbound lookups during analysis. These scans are not part of default
CI, are not attached to published images, and do not replace the lockfile
inventories: bundled frontend JavaScript may not appear as separate packages
in an image scan. Rebuild before scanning to avoid inventorying an old tag.

Before a release, run advisory checks against both lockfiles:

```bash
uv audit --locked
cd apps/operator-console
pnpm audit
```

These require access to the advisory services and report only vulnerabilities
known at the time of the query. They do not replace a vulnerability scan of
freshly built images or a review of the exact release commit.

For a final-image vulnerability scan, rebuild with `--pull`, export the exact
images with `docker save`, then run Trivy against each archive. The scanner
database is cached under ignored `artifacts/trivy-cache/`:

```bash
mkdir -p artifacts/trivy-cache
docker build --pull --no-cache -t document-platform-api:audit .
docker build --pull --no-cache -t document-platform-console:audit apps/operator-console
docker save -o artifacts/api-audit.tar document-platform-api:audit
docker save -o artifacts/console-audit.tar document-platform-console:audit
docker run --rm -v "$PWD/artifacts:/artifacts" -v "$PWD/artifacts/trivy-cache:/root/.cache/trivy" aquasec/trivy:0.74.0 image --input /artifacts/api-audit.tar --scanners vuln --severity HIGH,CRITICAL --format json --output /artifacts/api-cves.json
docker run --rm -v "$PWD/artifacts:/artifacts" -v "$PWD/artifacts/trivy-cache:/root/.cache/trivy" aquasec/trivy:0.74.0 image --input /artifacts/console-audit.tar --scanners vuln --severity HIGH,CRITICAL --format json --output /artifacts/console-cves.json
```

Inspect each report's `Results[].Vulnerabilities`; a successful scanner exit
does not mean zero findings. These local reports are not part of CI. Remove the
large image archives after review.

## Secret Scanning

CI scans the complete Git history for committed secrets with Gitleaks. Run the
same check locally with:

```bash
docker run --rm --volume "$PWD:/repo" ghcr.io/gitleaks/gitleaks:v8.30.1 git --redact=100 --no-banner /repo
```

This scan blocks CI after a push; it is not installed as a local pre-commit
hook.

## API Contract Generation

The versioned API contract is stored at
[`docs/contracts/document-platform.openapi.json`](contracts/document-platform.openapi.json).
After changing an HTTP contract, regenerate the JSON and frontend types with:

```bash
uv run python scripts/export_openapi.py
cd apps/operator-console
pnpm generate:api
```

Backend tests detect runtime-to-JSON drift; `pnpm check:api` detects
JSON-to-TypeScript drift. Generated TypeScript is never edited manually.
