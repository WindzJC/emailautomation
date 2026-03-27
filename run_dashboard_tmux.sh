#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

SESSION_NAME="${TMUX_DASHBOARD_SESSION:-dashboard}"
ATTACH_MODE="${TMUX_DASHBOARD_ATTACH:-0}"
UVICORN_PATTERN="${TMUX_DASHBOARD_PATTERN:-uvicorn live_dashboard:app}"
HOST="${LIVE_DASHBOARD_HOST:-${APP_HOST:-0.0.0.0}}"
PORT="${LIVE_DASHBOARD_PORT:-${APP_PORT:-8000}}"

printf -v ESCAPED_ROOT '%q' "$ROOT"
printf -v ESCAPED_HOST '%q' "$HOST"
printf -v ESCAPED_PORT '%q' "$PORT"
LAUNCH_CMD="cd $ESCAPED_ROOT && LIVE_DASHBOARD_HOST=$ESCAPED_HOST LIVE_DASHBOARD_PORT=$ESCAPED_PORT ./run_live_dashboard.sh"

tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true
pkill -f "$UVICORN_PATTERN" 2>/dev/null || true

tmux new-session -d -s "$SESSION_NAME" -n dashboard "$LAUNCH_CMD"

echo "Started tmux session: $SESSION_NAME"
echo "Dashboard: http://localhost:$PORT"

if [[ "$ATTACH_MODE" == "1" && -t 1 ]]; then
  exec tmux attach -t "$SESSION_NAME"
fi
