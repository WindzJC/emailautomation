#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
unset TMUX_TMPDIR
mkdir -p "$HOME/.local/state/tmux"
chmod 700 "$HOME/.local/state/tmux"
export TMUX_TMPDIR="$HOME/.local/state/tmux"

for env_file in ".env.local" ".env"; do
  if [[ -f "$env_file" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$env_file"
    set +a
    break
  fi
done

BOOTSTRAP_SESSION="${TMUX_WORKER_BOOTSTRAP_SESSION:-runtime_worker}"
BOOTSTRAP_COMMAND="${TMUX_WORKER_BOOTSTRAP_COMMAND:-tail -f /dev/null}"
HEARTBEAT_SECONDS="${TMUX_WORKER_HEARTBEAT_SECONDS:-30}"

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
