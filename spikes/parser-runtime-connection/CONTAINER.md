# Worker image credential mount probe

This extends the [host-side connection spike](README.md). It runs the probe in
a temporary derivative of `document-platform-api:dev`, as UID/GID 10001, on the
existing `ai-document-processing-platform_default` Docker network. It does not
start the Temporal worker. The Compose credential path now uses the same
worker-owned named-volume contract through a separate sync service.

## Credential provisioning contract

Use the Compose named volume `parser-runtime-credentials`. The
`parser-credential-sync` service copies the host issuer's private `ca.pem` and
`token` files into this volume with owner `10001:10001`, directory mode `0700`
and file mode `0600`. The worker mounts it read-only. No application data,
administrator kubeconfig or Docker socket is mounted into the sync service; no
administrator kubeconfig or Docker socket is mounted into the worker.

The sync helper runs separately from the worker, with no network and access
only to a read-only host staging directory and the credential volume. It needs
limited DAC-read, DAC-override and CHOWN capabilities to bridge the Mac host
UID and worker UID. The worker has none of these capabilities. Such a host file
must not be made world-readable to accommodate the container UID. Replacing a
token file does not revoke previously issued JWTs.

## Build and run the companion

Prepare a new cluster and bootstrap credentials using the host-side recipe,
with the separate name `ai-doc-parser-container-probe` and the additional Kind
configuration `spikes/parser-runtime-connection/kind-container.yaml`:

```sh
kind create cluster --name ai-doc-parser-container-probe \
  --kubeconfig "$probe_dir/admin.kubeconfig" \
  --config spikes/parser-runtime-connection/kind-container.yaml \
  --image kindest/node:v1.37.0 --wait 60s
```

The server is published on loopback and includes `host.docker.internal` in
its certificate SAN. The container uses that name and the generated host port,
with the same `host-gateway` mapping as the worker's Compose service.

Keep the image build context separate from all credentials. Install matching
Linux SDK wheels into that context using host-side uv; the Docker build itself
needs no network or package installer. This is the tested ARM64/Python 3.13
recipe; use the corresponding x86_64 platform for an AMD64 base image.

```sh
probe_build="$probe_dir/build"
mkdir "$probe_build"
cp spikes/parser-runtime-connection/Dockerfile \
  spikes/parser-runtime-connection/connection_probe.py \
  spikes/parser-runtime-connection/container_probe.py "$probe_build/"
UV_CACHE_DIR="$probe_dir/uv-cache" uv pip install \
  --python-version 3.13 --python-platform aarch64-manylinux_2_28 \
  --only-binary :all: --target "$probe_build/dependencies" \
  -r spikes/parser-runtime-connection/runtime-requirements.txt
probe_image="ai-doc-parser-container-probe:$(date +%s)"
docker build --pull=false --network=none --tag "$probe_image" "$probe_build"
```

After provisioning the credential volume as described above, set
`credential_volume` to its name and `probe_endpoint` to
`https://host.docker.internal:<generated Kind API port>`. The companion can
then be run interactively:

```sh
docker run --rm -i --network ai-document-processing-platform_default \
  --add-host host.docker.internal:host-gateway \
  --user 10001:10001 --read-only --cap-drop=ALL \
  --security-opt no-new-privileges:true \
  --cpus 1 --memory 256m --pids-limit 64 \
  --env KUBECONFIG=/not-mounted/no-fallback \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=16m,uid=10001,gid=10001,mode=700 \
  --mount "type=volume,src=$credential_volume,dst=/run/parser-controller,readonly" \
  "$probe_image" --endpoint "$probe_endpoint"
```

The companion checks file ownership/modes, rejects a writable credential
filesystem, verifies the scoped connection and emits a `ready` JSON event.
Enter `check` to issue another bounded Pod-list request using the same SDK
client and its token refresh hook. Enter `stop` to exit. A separate provisioner
can replace or remove the token between checks. No tokens are sent through
this control channel; input contains only `check` or `stop`.

Remove the temporary container, credential volume, derived image, dedicated
Kind cluster and bootstrap directory after the probe. Preserve the base
`document-platform-api:dev` image and the existing `hub` cluster.

## Recorded validation — 2026-10-18

The test used Docker Desktop on macOS, the existing Linux ARM64 worker image,
Python 3.13.16 and Kubernetes client 37.0.1. Its derived image contained only
the optional SDK and probe code; credentials were provisioned into a volume
at runtime. The Kind
API remained published on loopback throughout the test.

| Check | Observed result |
| --- | --- |
| UID/GID and ownership | Controller ran as `10001:10001`; directory `0700`, files `0600`, owned by that identity. |
| Credential filesystem | Writing a new file failed with `EROFS`; Docker inspect confirmed the mount was read-only. |
| TLS and RBAC | Connection and scoped permission checks passed over the Compose network with hostname verification enabled. |
| Invalid replacement | Atomic replacement with a deliberately invalid token made the same client receive HTTP 401. |
| Valid replacement | Replacing it with a newly issued scoped token restored successful requests without recreating the client or restarting the container. |
| Missing token | Removing the file caused the refresh hook to refuse the request; restoring the file restored success. |
| Different UID | A separate UID 10002 process was denied token-file access. |
| Invalid mount setup | The companion rejected a writable volume and, separately, a token with mode 0644 before attempting an API connection. |

These checks validate the container credential boundary and client-side token
reload, not expiry-driven renewal, the actual Temporal worker, parser Job
lifecycle or network isolation. The credentials and temporary infrastructure
were removed after the probe.

The subsequent [credential lifecycle companion](CREDENTIALS.md) verifies
automatic host-side renewal and bound-token revocation. Connecting that
provisioner to this Docker volume remains an application-integration task.
