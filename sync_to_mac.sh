#!/usr/bin/env bash
set -euo pipefail

cat >&2 <<'EOF'
REFUSED: sync_to_mac.sh is retired.

Its old rsync --delete flow did not freeze runtime state, did not transfer the
complete Lead Ops state, and could overwrite a dirty Mac checkout.

Use docs/handoff/mac_cutover_runbook.md and tools/mac_runtime_migration.py after an
operator-approved freeze. This wrapper performs no transfer.
EOF
exit 2
