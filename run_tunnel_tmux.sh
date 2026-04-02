#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

SESSION_NAME="${TMUX_TUNNEL_SESSION:-tunnel}"
ATTACH_MODE="${TMUX_TUNNEL_ATTACH:-0}"
TARGET_URL="${TMUX_TUNNEL_URL:-http://localhost:${LIVE_DASHBOARD_PORT:-${APP_PORT:-8000}}}"
METRICS_ADDR="${TMUX_TUNNEL_METRICS_ADDR:-127.0.0.1:20241}"
TUNNEL_PATTERN="${TMUX_TUNNEL_PATTERN:-cloudflared tunnel --url $TARGET_URL}"

tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true
pkill -f "$TUNNEL_PATTERN" 2>/dev/null || true

tmux new-session -d -s "$SESSION_NAME" -n tunnel \
  "cd \"$ROOT\" && cloudflared tunnel --metrics \"$METRICS_ADDR\" --url \"$TARGET_URL\""

echo "Started tmux session: $SESSION_NAME"
echo "Target: $TARGET_URL"

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

if [[ "$ATTACH_MODE" == "1" && -t 1 ]]; then
  exec tmux attach -t "$SESSION_NAME"
fi
