#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PY="./.venv/bin/python"
SESSION_NAME="${TMUX_SENDGRID_SESSION:-sendgrid}"
BACKUP_DIR="${SENDGRID_BACKUP_DIR:-backups}"
REPORT_PATH="${SENDGRID_NORMALIZE_REPORT:-sendgrid_shard_normalize_report.json}"
ENV_FILES=(".env.local" ".env")
ATTACH_MODE="${TMUX_SENDGRID_ATTACH:-1}"
MAX_TOTAL_OVERRIDE="${SENDGRID_DASHBOARD_MAX_TOTAL:-}"
PROFILES=(
  sendgrid_annette
  sendgrid_jordan
  sendgrid_jodi
  sendgrid_alison
  sendgrid_fiorela
)

if [[ ! -x "$PY" ]]; then
  echo "Missing Python venv at $PY"
  exit 1
fi

if [[ -z "${SENDGRID_API_KEY:-}" ]]; then
  for env_file in "${ENV_FILES[@]}"; do
    if [[ -f "$env_file" ]]; then
      set -a
      # shellcheck disable=SC1090
      source "$env_file"
      set +a
      if [[ -n "${SENDGRID_API_KEY:-}" ]]; then
        echo "Loaded SENDGRID_API_KEY from $env_file"
        export SENDGRID_API_KEY
        break
      fi
    fi
  done
fi

if [[ -z "${SENDGRID_API_KEY:-}" ]]; then
  read -r -s -p "SendGrid key: " SENDGRID_API_KEY
  echo
  export SENDGRID_API_KEY
fi

echo "Checking SendGrid credits..."
CREDITS_JSON="$(curl -fsS -H "Authorization: Bearer $SENDGRID_API_KEY" https://api.sendgrid.com/v3/user/credits)" || {
  echo "SendGrid credit check failed. Verify the API key/account."
  exit 1
}

if ! python3 - "$CREDITS_JSON" <<'PY'
import json
import sys

raw = sys.argv[1]
data = json.loads(raw)
remain = data.get("remain")
total = data.get("total")
if isinstance(remain, int) and remain <= 0:
    print(f"SendGrid credits exhausted: remain={remain} total={total}")
    raise SystemExit(1)
print(f"SendGrid credits OK: remain={remain} total={total}")
PY
then
  exit 1
fi

if [[ "${SENDGRID_SKIP_NORMALIZE:-0}" != "1" ]]; then
  echo "Normalizing SendGrid shards..."
  "$PY" tools/normalize_sendgrid_shards.py \
    --shards-glob 'recipients_sendgrid_*.csv' \
    --backup-dir "$BACKUP_DIR" \
    --always-send 'astraproductionsbyjc@gmail.com' \
    --report-path "$REPORT_PATH"
fi

EXTRA_ARGS=()
if [[ -n "$MAX_TOTAL_OVERRIDE" ]]; then
  EXTRA_ARGS+=(--max_total "$MAX_TOTAL_OVERRIDE")
  echo "Dashboard send cap override: $MAX_TOTAL_OVERRIDE per sender"
fi
EXTRA_ARGS_STR=""
if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
  printf -v EXTRA_ARGS_STR ' %q' "${EXTRA_ARGS[@]}"
fi

echo "Running preflight checks..."
"$PY" send_shard.py --profile sendgrid_annette --status-sendgrid
for profile in "${PROFILES[@]}"; do
  "$PY" send_shard.py --profile "$profile" --preflight >/dev/null
done

tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true
tmux new-session -d -s "$SESSION_NAME" -n run

tmux split-window -h -t "$SESSION_NAME":run
tmux split-window -v -t "$SESSION_NAME":run.0
tmux split-window -v -t "$SESSION_NAME":run.1
tmux split-window -v -t "$SESSION_NAME":run.2
tmux select-layout -t "$SESSION_NAME":run tiled

tmux set-environment -t "$SESSION_NAME" SENDGRID_API_KEY "$SENDGRID_API_KEY"

for pane_profile in \
  "$SESSION_NAME:run.0 sendgrid_annette" \
  "$SESSION_NAME:run.1 sendgrid_jordan" \
  "$SESSION_NAME:run.2 sendgrid_jodi" \
  "$SESSION_NAME:run.3 sendgrid_alison" \
  "$SESSION_NAME:run.4 sendgrid_fiorela"; do
  pane="${pane_profile%% *}"
  profile="${pane_profile##* }"
  escaped_key="$(printf '%q' "$SENDGRID_API_KEY")"
  tmux send-keys -t "$pane" "cd \"$ROOT\"; export SENDGRID_API_KEY=$escaped_key; $PY send_shard.py --profile $profile$EXTRA_ARGS_STR" C-m
done

if [[ "$ATTACH_MODE" == "0" ]]; then
  echo "Started tmux session: $SESSION_NAME"
  exit 0
fi

if [[ -t 1 ]]; then
  tmux attach -t "$SESSION_NAME"
else
  echo "Started tmux session: $SESSION_NAME (no attach; non-interactive shell)"
fi
