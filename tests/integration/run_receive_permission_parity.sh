#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
image="astra-receive-parity:${$}"

cleanup() {
  docker image rm -f "${image}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker build \
  --pull=false \
  --file "${repo_root}/tests/integration/Dockerfile.receive" \
  --tag "${image}" \
  "${repo_root}"

docker run --rm "${image}" --mode success
docker run --rm "${image}" --mode resume
docker run --rm \
  --tmpfs /opt/astra/emailautomation/.runtime_handoff/import-staging:rw,nosuid,nodev,noexec,mode=0700,uid=2000,gid=2000 \
  "${image}" --mode cross-filesystem
docker run --rm --user root --entrypoint /bin/bash "${image}" -lc '
  chown root:astra /opt/astra/emailautomation/.runtime_handoff/receive-transactions
  exec runuser -u astra -- \
    /opt/astra/emailautomation/.venv/bin/python \
    /opt/astra/emailautomation/tests/integration/receive_permission_parity.py \
    --mode wrong-owner
'

echo "ubuntu_receive_permission_parity=passed"
