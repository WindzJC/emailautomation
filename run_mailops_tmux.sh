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

SESSION_NAME="${TMUX_MAILOPS_SESSION:-mailops}"
WINDOW_NAME="${TMUX_MAILOPS_WINDOW:-ops}"
ATTACH_MODE="${TMUX_MAILOPS_ATTACH:-0}"

HOST="${LIVE_DASHBOARD_HOST:-${APP_HOST:-0.0.0.0}}"
PORT="${LIVE_DASHBOARD_PORT:-${APP_PORT:-8001}}"
TARGET_URL="${TMUX_TUNNEL_URL:-http://localhost:$PORT}"
METRICS_ADDR="${TMUX_TUNNEL_METRICS_ADDR:-127.0.0.1:20241}"
UVICORN_PATTERN="${TMUX_DASHBOARD_PATTERN:-uvicorn live_dashboard:app}"
TUNNEL_PATTERN="${TMUX_TUNNEL_PATTERN:-cloudflared tunnel --url $TARGET_URL}"

tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true
tmux kill-session -t "${TMUX_DASHBOARD_SESSION:-dashboard}" 2>/dev/null || true
tmux kill-session -t "${TMUX_TUNNEL_SESSION:-tunnel}" 2>/dev/null || true

pkill -f "$UVICORN_PATTERN" 2>/dev/null || true
pkill -f "$TUNNEL_PATTERN" 2>/dev/null || true

tmux new-session -d -s "$SESSION_NAME" -n "$WINDOW_NAME" \
  "cd \"$ROOT\" && ./run_live_dashboard.sh"
tmux split-window -v -t "${SESSION_NAME}:${WINDOW_NAME}" \
  "cd \"$ROOT\" && cloudflared tunnel --metrics \"$METRICS_ADDR\" --url \"$TARGET_URL\""
tmux select-layout -t "${SESSION_NAME}:${WINDOW_NAME}" even-vertical >/dev/null

echo "Started tmux session: $SESSION_NAME"
echo "Window: ${SESSION_NAME}:${WINDOW_NAME}"
echo "Pane 0: dashboard on http://localhost:$PORT"
echo "Pane 1: cloudflared tunnel -> $TARGET_URL"

sleep 2
python3 - "$METRICS_ADDR" <<'PY'
import json
import sys
import urllib.request

metrics_addr = sys.argv[1]
quicktunnel_url = f"http://{metrics_addr}/quicktunnel"
try:
    with urllib.request.urlopen(quicktunnel_url, timeout=5) as response:
        data = json.load(response)
    hostname = (data.get("hostname") or "").strip()
    if hostname:
        print(f"Quick tunnel: https://{hostname}")
        print(f"SendGrid webhook: https://{hostname}/webhooks/sendgrid/events")
    else:
        print("Tunnel started, but quick tunnel hostname is not available yet.")
except Exception as exc:
    print(f"Tunnel started, but quick tunnel hostname lookup failed: {exc}")
PY

echo
echo "Active tmux sessions:"
tmux ls 2>/dev/null || echo "(none)"

if [[ "$ATTACH_MODE" == "1" && -t 1 ]]; then
  exec tmux attach -t "$SESSION_NAME"
fi
