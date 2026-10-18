# Controller credential lifecycle

This standalone host provisioner extends the [connection spike](README.md).
It requests short-lived, object-bound tokens and publishes the same plaintext
`token` file consumed by the existing client refresh hook. Compose mirrors the
private host directory into a worker-owned named volume through a dedicated
credential-sync service; the worker receives that volume read-only.

## Provisioning and renewal policy

Run one trusted provisioner per credential directory outside the worker.
The provisioner uses an explicit absolute bootstrap kubeconfig and the fixed
`kind-ai-doc-parser-credential-probe` context. It checks the configured endpoint
locally before issuance, rejecting remote endpoints, disabled TLS verification
and an explicit proxy. This prototype uses the disposable cluster's
administrator identity on the host only. That identity must not enter worker
or parser containers.

The controller Role permits neither Secret access nor token issuance through
`serviceaccounts/token`. The connection probe now checks the latter denial.
Only the external provisioner can request the next controller credential.

Create `credential-anchor.yaml` in the dedicated namespace. This is an empty
Opaque Secret used solely as a lifetime anchor; it contains no token or
application secret and is never mounted. Pass its UID to the provisioner.
Every TokenRequest binds to that exact Secret name and UID. The issuer never
adopts a replacement UID automatically.

The default requested lifetime is one hour, with renewal five minutes before
the returned `expirationTimestamp`. The accepted request range is 600–3600
seconds. Validate the actual returned expiration rather than decoding an
unverified JWT. The provisioner rejects expired responses and lifetimes beyond
the requested duration plus a 60-second clock allowance. Keep the host clock
synchronized with the cluster.

Publish into an existing directory owned by the provisioner with mode 0700.
Each renewal writes a fresh mode-0600 temporary file, flushes it, then uses
`os.replace` to publish `token`. Tokens are sent to neither command arguments
nor logs. The process logs bounded event names only.

If renewal fails, retain the current token only until its original expiration;
the failed request never extends that deadline. Retry after at most ten
seconds. The loop normally wakes at most 30 seconds apart; requests have a
ten-second timeout. These are polling/request bounds, not an exact real-time
file-removal guarantee. Once known to be expired, remove the local token before
retrying. Failed initial issuance removes any stale token whose expiry the new
process does not know. Stopping watch mode with SIGINT or SIGTERM removes its
published token. SIGKILL cannot run this cleanup; server expiration and explicit
revocation remain necessary.

## Revocation and recovery

Token replacement and local file removal do not revoke a copied JWT. Let active
parser work settle, then stop the Compose worker and sync service. Stop the
issuer and remove the host token; remove the project-prefixed
`parser-runtime-credentials` Docker volume to delete its copy as well. Delete
the anchor with the dedicated bootstrap kubeconfig. Do not use
`docker compose down -v`, which also removes application data volumes.
Kubernetes checks the bound object's existence and UID when authenticating
these tokens. See
[bound ServiceAccount tokens](https://kubernetes.io/docs/reference/access-authn-authz/service-accounts-admin/#bound-service-account-tokens).
Do not assume immediate invalidation or use successful deletion as the only
verification; poll a retained token until the API refuses it.

To restore access, explicitly create a new anchor, inspect its new UID and
restart provisioning with that UID. The same controller SDK client can then
reload the new token file. Jobs already running when access is revoked may
have to finish through their active deadline and TTL because controller-driven
cleanup can no longer authenticate.

## Run against the disposable cluster

Follow the [bootstrap recipe](README.md), using the separate cluster name
`ai-doc-parser-credential-probe` and its own kubeconfig. Keep the credential
directory separate from that administrator file:

```sh
mkdir -m 700 "$probe_dir/credentials"
kubectl --kubeconfig "$probe_dir/admin.kubeconfig" \
  --context kind-ai-doc-parser-credential-probe config view --raw --minify \
  -o 'jsonpath={.clusters[0].cluster.certificate-authority-data}' \
  | "$probe_python" -c 'import base64,sys; sys.stdout.buffer.write(base64.b64decode(sys.stdin.buffer.read()))' \
  > "$probe_dir/credentials/ca.pem"
chmod 600 "$probe_dir/credentials/ca.pem"
kubectl --kubeconfig "$probe_dir/admin.kubeconfig" \
  --context kind-ai-doc-parser-credential-probe apply \
  -f spikes/parser-runtime-connection/credential-anchor.yaml
anchor_uid=$(kubectl --kubeconfig "$probe_dir/admin.kubeconfig" \
  --context kind-ai-doc-parser-credential-probe -n pdf-parser-probe \
  get secret parser-controller-session -o 'jsonpath={.metadata.uid}')
"$probe_python" spikes/parser-runtime-connection/credential_issuer.py \
  --kubeconfig "$probe_dir/admin.kubeconfig" \
  --credential-dir "$probe_dir/credentials" --bound-uid "$anchor_uid" --watch
```

Omit `--watch` to issue once. Watch mode emits `renewed`, `renewal_failed`,
`expired`, `unavailable`, `stopped` or `failed`; it never prints the token.
For a short renewal probe only, use `--ttl 600 --renew-before 598`, which
renews roughly two seconds after issuance instead of waiting 55 minutes.
The requested token still has a ten-minute lifetime.

In another terminal, revoke the session after stopping the provisioner:

```sh
kubectl --kubeconfig "$probe_dir/admin.kubeconfig" \
  --context kind-ai-doc-parser-credential-probe -n pdf-parser-probe \
  delete secret parser-controller-session
```

Use the spike's separate dependency environment for focused offline checks:

```sh
"$probe_python" -m pytest -o addopts= spikes/parser-runtime-connection -q
.venv/bin/ruff check spikes/parser-runtime-connection
.venv/bin/ruff format --check spikes/parser-runtime-connection
.venv/bin/pyright --project spikes/parser-runtime-connection --pythonpath "$probe_python"
```

Delete the disposable cluster and bootstrap directory after the probe.

## Recorded validation — 2026-10-18

The test used Kind Kubernetes 1.37 with its default CNI, Python client 37.0.1
and the scoped controller Role. No existing cluster or remote context was used.

| Check | Observed result |
| --- | --- |
| Initial provisioning | Bound token authenticated with verified TLS and passed scoped permission checks, including denial of token issuance. |
| Automatic renewal | Watch mode published a different token; the same SDK ApiClient accepted it without restart. The previous token still authenticated before explicit revocation. |
| Provisioner stop | SIGTERM removed the local token and the refresh hook refused subsequent requests. A retained token still authenticated before anchor deletion. |
| Server revocation | After deleting the anchor, both retained tokens were refused with HTTP 401. The check took 9.99 s in one run. |
| Anchor recreation | Recreating the same name produced a new UID. Issuance pinned to the old UID failed; explicit provisioning with the new UID restored access for the original SDK client. |
| Expiration policy | Clock-controlled tests verified that failed renewal preserves the original deadline and removes the token at expiration. Natural JWT expiration at the API server was not awaited in this live check. |
| Offline verification | 69 tests across the connection, lifecycle and issuer modules passed, including 15 issuer cases. Ruff and strict Pyright passed. |

The temporary cluster and credentials were removed after validation.

## Compose delivery

Keep the host directory at mode 0700 and `ca.pem` and `token` at mode 0600.
The issuer owns and renews those files. Set
`DOCUMENT_PLATFORM_PARSER_CREDENTIALS_DIR` to that absolute directory in the
Compose environment, start the issuer in watch mode, then start the processing
profile:

```sh
uv run --no-sync python spikes/parser-runtime-connection/credential_issuer.py \
  --kubeconfig "$probe_dir/admin.kubeconfig" \
  --credential-dir "$probe_dir/credentials" --bound-uid "$anchor_uid" --watch
```

In another terminal, after setting the endpoint, namespace and parser image in
the Compose environment, rebuild the application image so it contains the sync
module:

```sh
docker build -t document-platform-api:dev .
docker compose --profile processing up
```

When Compose stops, stop the issuer in its terminal as well.

The `parser-credential-sync` service waits until both source files are valid,
then copies them atomically into the named `parser-runtime-credentials` volume
with owner 10001:10001 and mode 0600. A changed token is mirrored within one
poll interval. Invalid or missing source credentials remove the target files,
so the worker fails closed. The worker waits for the sync service's healthcheck
and mounts the volume read-only. The sync service has no network, kubeconfig,
database settings, document data or Docker socket. It runs from the existing
application image with only the capabilities needed to read its single
read-only staging mount and assign volume file ownership.

Unit tests cover host-to-volume validation and atomic publication. This does
not automate Kind/Calico creation or start/stop the host issuer; those remain
bootstrap and operator steps. Run only one issuer for a credential directory.
SIGKILL can leave a copied token in the named volume until its server-side
expiry. Do not make host files world-readable to bridge the host and container
identities.

## Recorded Docker delivery check — 2026-10-18

A temporary helper container on Docker Desktop for macOS ran the current sync
module from a read-only bind mount. It used the same dropped-capability,
network-disabled configuration as Compose, with synthetic credentials and a
temporary named volume.

| Check | Observed result |
| --- | --- |
| Host directory access | Mode-0700 staging directory and mode-0600 files were read without broadening host permissions. |
| Initial publication | Named volume received UID/GID 10001 and mode-0700 directory / mode-0600 files. |
| Renewal | Atomic host token replacement appeared in the named volume within two seconds. |
| Missing token | Removing the source token removed both target files; restoring it repopulated the volume. |
| Worker identity | A separate UID-10001 container read the renewed token and received `EROFS` when attempting a write. |

This was a direct helper-container check, not a Compose worker or Kubernetes
API run. The synthetic CA was used to test delivery metadata; TLS validity and
token acceptance remain covered by the separate connection and container
probes. Compose configuration validation and the focused unit tests also pass.
