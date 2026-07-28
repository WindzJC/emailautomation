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

# Default the profile auto-stop guard off unless the operator explicitly re-enables it.
export DASHBOARD_PROFILE_GUARD_ENABLED="${DASHBOARD_PROFILE_GUARD_ENABLED:-0}"

PY="${PYTHON_BIN:-./.venv/bin/python}"
HOST="${LIVE_DASHBOARD_HOST:-${APP_HOST:-0.0.0.0}}"
PORT="${LIVE_DASHBOARD_PORT:-${APP_PORT:-8001}}"

if [[ ! -x "$PY" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PY="$(command -v python3)"
  else
    echo "Missing Python runtime. Expected $PY or python3 in PATH."
    exit 1
  fi
fi

"$PY" dashboard_security.py --host "$HOST"
exec "$PY" -m uvicorn live_dashboard:app --host "$HOST" --port "$PORT"
