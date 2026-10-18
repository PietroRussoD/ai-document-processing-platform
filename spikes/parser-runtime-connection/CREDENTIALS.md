# Controller credential lifecycle

This standalone host provisioner extends the [connection spike](README.md).
It requests short-lived, object-bound tokens and publishes the same plaintext
`token` file consumed by the existing client refresh hook. The application
worker is still unintegrated.

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

Token replacement and local file removal do not revoke a copied JWT. To revoke
the session, stop its provisioner, remove any remaining local token, then
delete its anchor with the dedicated bootstrap kubeconfig. Kubernetes checks
the bound object's existence and UID when authenticating these tokens. See
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

## Remaining integration work

This implements the host-side renewal prototype. It does not supervise the
provisioner or coordinate concurrent provisioners. Run only one per directory.
Automatic delivery into the UID-10001 Docker credential volume is still to be
connected; the [container companion](CONTAINER.md) separately verified its
ownership, read-only consumer mount and atomic replacement behavior. Do not
make host files world-readable to bridge those identities. Application startup,
worker integration and recovery from sustained API outages remain future work.
