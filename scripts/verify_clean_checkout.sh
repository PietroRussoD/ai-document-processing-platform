#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

for tool in uv pnpm docker jq; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    printf 'Required command not found: %s\n' "$tool" >&2
    exit 1
  fi
done

docker info >/dev/null
uv sync --all-groups --locked
(
  cd apps/operator-console
  pnpm install --frozen-lockfile
)

docker compose --profile processing config --quiet
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest

(
  cd apps/operator-console
  pnpm check
)

mkdir -p artifacts
uv export --preview-features sbom-export --format cyclonedx1.5 --no-dev --locked --offline --quiet --output-file artifacts/python-runtime.cdx.json
jq -e '.bomFormat == "CycloneDX" and .specVersion == "1.5" and .metadata.component.name == "ai-document-processing-platform" and ([.components[].name] | index("fastapi") != null and index("pytest") == null)' artifacts/python-runtime.cdx.json

(
  cd apps/operator-console
  pnpm sbom --sbom-format cyclonedx --sbom-type application --lockfile-only --prod > ../../artifacts/frontend-runtime.cdx.json
)
jq -e '.bomFormat == "CycloneDX" and .specVersion == "1.7" and .metadata.component.name == "operator-console" and .metadata.component.type == "application" and ([.components[].name] | index("react") != null and index("typescript") == null)' artifacts/frontend-runtime.cdx.json
