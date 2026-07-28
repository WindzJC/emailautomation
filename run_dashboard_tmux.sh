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

SESSION_NAME="${TMUX_DASHBOARD_SESSION:-dashboard}"
ATTACH_MODE="${TMUX_DASHBOARD_ATTACH:-0}"
UVICORN_PATTERN="${TMUX_DASHBOARD_PATTERN:-uvicorn live_dashboard:app}"
HOST="${LIVE_DASHBOARD_HOST:-${APP_HOST:-0.0.0.0}}"
PORT="${LIVE_DASHBOARD_PORT:-${APP_PORT:-8001}}"
PY="${PYTHON_BIN:-./.venv/bin/python}"

if [[ ! -x "$PY" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PY="$(command -v python3)"
  else
    echo "Missing Python runtime. Expected $PY or python3 in PATH."
    exit 1
  fi
fi

"$PY" dashboard_security.py --host "$HOST"

printf -v ESCAPED_ROOT '%q' "$ROOT"
printf -v ESCAPED_HOST '%q' "$HOST"
printf -v ESCAPED_PORT '%q' "$PORT"
LAUNCH_CMD="cd $ESCAPED_ROOT && LIVE_DASHBOARD_HOST=$ESCAPED_HOST LIVE_DASHBOARD_PORT=$ESCAPED_PORT bash ./run_live_dashboard.sh"

tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true
pkill -f "$UVICORN_PATTERN" 2>/dev/null || true

tmux new-session -d -s "$SESSION_NAME" -n dashboard "$LAUNCH_CMD"

echo "Started tmux session: $SESSION_NAME"
echo "Dashboard: http://localhost:$PORT"

if [[ "$ATTACH_MODE" == "1" && -t 1 ]]; then
  exec tmux attach -t "$SESSION_NAME"
fi
