#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

for env_file in ".env.local" ".env"; do
  if [[ -f "$env_file" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$env_file"
    set +a
    break
  fi
done

TMUX_SOCKET_ROOT="${TMUX_TMPDIR:-$ROOT/data/state/tmux}"
BOOTSTRAP_SESSION="${TMUX_WORKER_BOOTSTRAP_SESSION:-runtime_worker}"
BOOTSTRAP_COMMAND="${TMUX_WORKER_BOOTSTRAP_COMMAND:-tail -f /dev/null}"
HEARTBEAT_SECONDS="${TMUX_WORKER_HEARTBEAT_SECONDS:-30}"

mkdir -p "$TMUX_SOCKET_ROOT"
chmod 700 "$TMUX_SOCKET_ROOT"
export TMUX_TMPDIR="$TMUX_SOCKET_ROOT"

ensure_bootstrap_session() {
  if ! tmux has-session -t "$BOOTSTRAP_SESSION" 2>/dev/null; then
    tmux new-session -d -s "$BOOTSTRAP_SESSION" -n worker "$BOOTSTRAP_COMMAND"
  fi
}

ensure_bootstrap_session
echo "Runtime worker ready. tmux socket root: $TMUX_TMPDIR session: $BOOTSTRAP_SESSION"

while true; do
  ensure_bootstrap_session
  sleep "$HEARTBEAT_SECONDS"
done
