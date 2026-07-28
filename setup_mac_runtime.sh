#!/usr/bin/env bash
set -euo pipefail

cat >&2 <<'EOF'
REFUSED: setup_mac_runtime.sh is retired.

Its old flow did not verify the source commit or runtime checksums and printed
commands that could start live senders.

Use handoff/mac_cutover_runbook.md and tools/mac_runtime_migration.py. This
wrapper creates no environment and starts no process.
EOF
exit 2
