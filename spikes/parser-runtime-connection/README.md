# Parser runtime controller connection spike

This standalone prototype validates the connection contract proposed in the
[integration plan](../../docs/security/pdf-parser-integration-proposal.md).
The v1.3.0 development application now uses the Kubernetes SDK from its
Temporal worker to create isolated parser Jobs. This spike remains a standalone
connection and RBAC probe; the application integration and its live evidence
are documented in the integration plan.

## Connection contract

The command requires four explicit inputs. It does not load a kubeconfig,
in-cluster credentials, client certificates or the current kubectl context.

| CLI input | Worker setting | Requirement |
| --- | --- | --- |
| `--endpoint` | `DOCUMENT_PLATFORM_PARSER_KUBERNETES_ENDPOINT` | HTTPS with an explicit port. Only `127.0.0.1`, `localhost`, `::1` and `host.docker.internal` are allowed in this local spike. No credentials, API path, query or fragment. |
| `--namespace` | `DOCUMENT_PLATFORM_PARSER_KUBERNETES_NAMESPACE` | A dedicated namespace; `default` and Kubernetes system namespaces are rejected. |
| `--ca-file` | `DOCUMENT_PLATFORM_PARSER_KUBERNETES_CA_FILE` | A readable CA PEM file. Certificate and hostname verification stay enabled. |
| `--token-file` | `DOCUMENT_PLATFORM_PARSER_KUBERNETES_TOKEN_FILE` | A readable file containing one bounded bearer token, read again before each request. |

The CLI uses only its arguments. The worker consumes the environment settings
shown above. Both SDK configurations start fresh, without ambient administrator
credentials or proxy settings. Requests have a 3-second connect timeout,
5-second read timeout and no automatic retries.

Rereading a token does not renew it. Provision a short-lived token outside the
worker and replace it before expiry. An absent, invalid or refused token fails
the operation. CA replacement requires a new client. Error output contains no
raw SDK response bodies or credentials.

Compose mounts the host credential directory read-only into a separate sync
service. That service publishes owner-10001 files into a named volume, which
the worker mounts read-only outside its document volume. Atomic replacement
becomes visible to the SDK refresh hook. Neither the API nor parser Jobs
receive the controller credential. A worker container needs a reachable
endpoint, not its own loopback address; `host.docker.internal` must also appear
in the server's certificate SAN. The [container companion](CONTAINER.md)
verified the target volume and UID-10001 read-only access separately from the
Temporal worker.

## Permission checks

The probe lists at most one Pod in the dedicated namespace to exercise the
authenticated connection. It then uses SelfSubjectAccessReview requests to
check this declared matrix:

| Scope and resource | Expected verbs |
| --- | --- |
| Dedicated namespace, `batch/jobs` | Allow `create`, `get`, `list`, `watch`, `delete` |
| Dedicated namespace, `pods` | Allow `get`, `list`, `watch`; deny `create` |
| Dedicated namespace, `pods/exec` | Allow `get`, `create` |
| Dedicated namespace, `secrets` | Deny `get`, `list` |
| Dedicated namespace, `serviceaccounts/token` | Deny `create` |
| Dedicated namespace, `rolebindings` | Deny `create` |
| `default` namespace, `pods` | Deny `list` |
| `default` namespace, `batch/jobs` | Deny `create` |

The probe requests no Secret contents and does not create Jobs or exec into
Pods. These selected denials do not enumerate every possible privilege.
Permission to create Jobs can provide indirect access to resources in their
namespace. Keep application Secrets and privileged service accounts out of the
parser namespace. These checks do not enforce parser Job templates, token
automount settings or network isolation.

## Run against a disposable cluster

Run from the repository root. Every kubectl command must use the dedicated
bootstrap kubeconfig. Never substitute `hub` or a remote cluster. The
administrator kubeconfig stays on the host and is not an input to the probe.

```sh
umask 077
probe_dir=$(mktemp -d /private/tmp/ai-doc-parser-connection.XXXXXX)
probe_python="$probe_dir/venv/bin/python"
uv venv --python 3.13 "$probe_dir/venv"
uv pip install --python "$probe_python" -r spikes/parser-runtime-connection/requirements.txt
kind create cluster --name ai-doc-parser-connection-probe \
  --kubeconfig "$probe_dir/admin.kubeconfig" \
  --image kindest/node:v1.37.0 --wait 60s
kubectl --kubeconfig "$probe_dir/admin.kubeconfig" apply \
  -f spikes/parser-runtime-connection/controller-rbac.yaml
kubectl --kubeconfig "$probe_dir/admin.kubeconfig" -n pdf-parser-probe \
  create token parser-controller --duration=30m > "$probe_dir/token"
```

Extract only the public CA and endpoint from the bootstrap configuration:

```sh
"$probe_python" - "$probe_dir" <<'PY'
import base64
import json
from pathlib import Path
import subprocess
import sys

root = Path(sys.argv[1])
configuration = json.loads(subprocess.check_output([
    "kubectl", "--kubeconfig", str(root / "admin.kubeconfig"),
    "config", "view", "--raw", "--minify", "-o", "json",
]))
cluster = configuration["clusters"][0]["cluster"]
(root / "ca.pem").write_bytes(base64.b64decode(cluster["certificate-authority-data"]))
(root / "endpoint").write_text(cluster["server"])
PY
"$probe_python" spikes/parser-runtime-connection/connection_probe.py \
  --endpoint "$(cat "$probe_dir/endpoint")" --namespace pdf-parser-probe \
  --ca-file "$probe_dir/ca.pem" --token-file "$probe_dir/token"
```

Success returns JSON with `result=passed`, `tls=verified`,
`required_rbac=allowed` and `checked_denials=denied`. Failure exits with status
1 and a bounded message without raw API response bodies.

Run the standalone tests in the spike environment. Override the application
pytest addopts because this environment does not install application or
coverage dependencies. The type check uses the repository's development
Pyright executable with the spike's separate Python environment:

```sh
"$probe_python" -m pytest -o addopts= spikes/parser-runtime-connection/test_connection_probe.py -q
.venv/bin/pyright --project spikes/parser-runtime-connection --pythonpath "$probe_python"
```

Remove the cluster and temporary credentials after testing:

```sh
kind delete cluster --name ai-doc-parser-connection-probe
rm -rf "$probe_dir"
```

## Automated Kind/Calico session

The repository command automates the dedicated local runtime and its cleanup.
It creates a uniquely named Kind cluster with the default CNI disabled, installs
the pinned Calico 3.33.0 operator, and waits for Calico and the node. A
restricted Pod using the parser image must first establish verified TLS to
`1.1.1.1:443`; after applying the namespace-wide default-deny policy, the same
connection must fail. The command then checks the host-side controller TLS and
RBAC contract and exercises automatic token renewal and SIGTERM cleanup. The
Calico manifests follow its [official quickstart](https://docs.tigera.io/calico/latest/getting-started/kubernetes/quickstart),
using the CRDs, operator and custom resources pinned to v3.33.0.

Run the disposable verification without starting or changing Compose:

```sh
uv run --no-sync python scripts/parser_runtime.py verify
```

To supervise the full local processing session, stop any running services in
the Compose project first and configure `DOCUMENT_PLATFORM_REVIEW_OPERATOR_TOKEN`
in `.env`, then run:

```sh
uv run --no-sync python scripts/parser_runtime.py up
```

`up` builds the current API/worker and console images, tags the API image for
parser Jobs, and loads it into the new Kind node. It checks the external egress
baseline and its denial before creating the controller credential. It starts
the host issuer in renewal mode and then starts the processing Compose profile
with the loopback Kind endpoint, verified CA, scoped token and private host
credential directory. Press Ctrl-C to stop the Compose services, stop the
issuer so the sync service removes its copied token, delete the bound Secret to
revoke outstanding tokens, clean parser Jobs and remove only that session's
Kind cluster and temporary directory. Compose data volumes are retained.
Shutdown stops the API, console, Temporal UI and dispatcher first, then the
worker while Temporal is still available, then Temporal and the databases. The
Python worker and dispatcher receive SIGINT so their entrypoints can close
cleanly; the worker has three minutes to cancel active parser work.

Every Kubernetes call uses the session's explicit kubeconfig and context. The
cluster name is random; `hub` and the default kubeconfig are never selected.
The parser NetworkPolicy test covers direct IPv4 TLS egress to the tested
endpoint. It does not prove every protocol, IPv6 path or every possible route.
The runtime remains per-Job containment on `runc`, not a kernel sandbox.

## Recorded validation

On 2026-10-17, the host-side CLI passed with Kubernetes 1.37 and Python client
37.0.1 using the scoped service-account token and TLS verification. A bogus
`KUBECONFIG` environment value did not affect the connection. Live negative
checks rejected an untrusted CA, an invalid token (HTTP 401), a valid token
without the required Role (HTTP 403), and a temporary extra grant for Secret
access. Removing that grant restored success. No Secret data was read.

This cluster used Kind's default CNI because this spike checks authentication
and configuration only. A separate Calico check verified that a restricted
Pod using `document-platform-api:dev` could establish TLS 1.3 to `1.1.1.1:443`
before an egress-only NetworkPolicy and timed out afterward; the host-side
baseline succeeded. This does not verify the final parser runtime topology or
all possible routes and protocols. This standalone connection CLI does not
validate worker-driven Job cancellation or resource limits. The separate
[lifecycle companion](LIFECYCLE.md) verifies standalone controller cleanup
after success, parser failure and SIGINT, plus deadline/TTL fallback after
SIGKILL. Temporal integration and its current live results are tracked in the
integration plan.

The [credential lifecycle companion](CREDENTIALS.md) adds a host provisioner
with automatic atomic token renewal, expiry handling and a UID-pinned binding
for server-side session revocation. Compose now mirrors renewed credentials into
its worker volume; the companion's live delivery checks remain separate from
the actual Temporal worker.
