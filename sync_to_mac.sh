#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./sync_to_mac.sh user@host [target_dir]

Example:
  ./sync_to_mac.sh windellereboquio@192.168.1.25 /Users/windellereboquio/emailautomation

What it does:
  1. clones or updates the repo on the Mac
  2. copies the managed data/ directory
  3. copies .env if present

Notes:
  - Run this only when the source machine is the active source of truth.
  - Do not run senders on Windows and Mac at the same time.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

REMOTE="${1:-}"
if [[ -z "$REMOTE" ]]; then
  usage
  exit 1
fi

if [[ "$REMOTE" != *"@"* ]]; then
  echo "Expected remote in the form user@host"
  exit 1
fi

REMOTE_USER="${REMOTE%@*}"
TARGET_DIR="${2:-/Users/${REMOTE_USER}/emailautomation}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if ! command -v ssh >/dev/null 2>&1; then
  echo "ssh is required"
  exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync is required"
  exit 1
fi

REMOTE_URL="$(git remote get-url origin)"

printf -v ESCAPED_TARGET '%q' "$TARGET_DIR"
printf -v ESCAPED_REMOTE_URL '%q' "$REMOTE_URL"

echo "Preparing remote checkout at $REMOTE:$TARGET_DIR"
ssh "$REMOTE" "if [[ -d $ESCAPED_TARGET/.git ]]; then git -C $ESCAPED_TARGET pull --rebase origin main; else mkdir -p \$(dirname $ESCAPED_TARGET) && git clone $ESCAPED_REMOTE_URL $ESCAPED_TARGET; fi"

echo "Syncing managed data/"
rsync -avz --delete \
  "$ROOT/data/" \
  "$REMOTE:$TARGET_DIR/data/"

if [[ -f "$ROOT/.env" ]]; then
  echo "Copying .env"
  scp "$ROOT/.env" "$REMOTE:$TARGET_DIR/.env"
else
  echo "Skipping .env copy because $ROOT/.env is missing"
fi

cat <<EOF
Sync complete.

On the Mac, run:
  cd "$TARGET_DIR"
  ./setup_mac_runtime.sh
EOF
