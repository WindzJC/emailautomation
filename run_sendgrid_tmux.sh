#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
unset TMUX_TMPDIR
mkdir -p "$HOME/.local/state/tmux"
chmod 700 "$HOME/.local/state/tmux"
export TMUX_TMPDIR="$HOME/.local/state/tmux"

PY="${PYTHON_BIN:-./.venv/bin/python}"
SESSION_NAME="${TMUX_SENDGRID_SESSION:-sendgrid}"
ATTACH_MODE="${TMUX_SENDGRID_ATTACH:-1}"
MAX_TOTAL_OVERRIDE="${SENDGRID_DASHBOARD_MAX_TOTAL:-}"
MAX_MESSAGES_1H_OVERRIDE="${SENDGRID_DASHBOARD_MAX_MESSAGES_1H:-}"
STARTUP_PRUNE_GUARD="${SENDGRID_SKIP_PRUNE_ON_STARTUP:-0}"
DRY_RUN="${TMUX_SENDGRID_DRY_RUN:-0}"
PREFLIGHT_LOG_DIR="${SENDGRID_PREFLIGHT_LOG_DIR:-data/logs/sendgrid_start_all_preflight}"
PROFILES=(
  sendgrid_annette
  sendgrid_jordan
  sendgrid_jodi
  sendgrid_alison
  sendgrid_fiorela
)

if [[ ! -x "$PY" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PY="$(command -v python3)"
  else
    echo "Missing Python runtime. Expected $PY or python3 in PATH."
    exit 1
  fi
fi

eval "$("$PY" - <<'PY'
import os
import shlex

import settings
from sendgrid_launch_auth import resolve_sendgrid_api_key

resolution = resolve_sendgrid_api_key(env=os.environ, env_files=settings.ENV_FILES)
if not resolution.ok:
    print("SENDGRID_KEY_OK=0")
    print(f"SENDGRID_KEY_ERROR={shlex.quote(resolution.error)}")
else:
    print("SENDGRID_KEY_OK=1")
    print(f"SENDGRID_API_KEY_RESOLVED={shlex.quote(resolution.key)}")
    print(f"SENDGRID_API_KEY_SOURCE={shlex.quote(resolution.source_label)}")
    print(f"SENDGRID_API_KEY_MASKED={shlex.quote(resolution.masked_key)}")
    print(f"SENDGRID_API_KEY_WARNING={shlex.quote(resolution.warning)}")
PY
)"

if [[ "${SENDGRID_KEY_OK:-0}" != "1" ]]; then
  echo "SendGrid startup aborted: ${SENDGRID_KEY_ERROR:-SENDGRID_API_KEY resolution failed.}"
  echo "Expected SENDGRID_API_KEY in the canonical env files (.env.local, .env) or a valid inherited environment value."
  exit 1
fi

SENDGRID_API_KEY="$SENDGRID_API_KEY_RESOLVED"
export SENDGRID_API_KEY

echo "SendGrid key source: $SENDGRID_API_KEY_SOURCE ($SENDGRID_API_KEY_MASKED)"
if [[ -n "${SENDGRID_API_KEY_WARNING:-}" ]]; then
  echo "WARNING: $SENDGRID_API_KEY_WARNING"
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

EXTRA_ARGS=()
if [[ -n "$MAX_TOTAL_OVERRIDE" ]]; then
  EXTRA_ARGS+=(--max_total "$MAX_TOTAL_OVERRIDE")
  echo "Dashboard send target per-profile cap: $MAX_TOTAL_OVERRIDE"
fi
if [[ -n "$MAX_MESSAGES_1H_OVERRIDE" ]]; then
  EXTRA_ARGS+=(--max_messages_1h "$MAX_MESSAGES_1H_OVERRIDE")
  echo "Dashboard rolling hourly cap override: $MAX_MESSAGES_1H_OVERRIDE total/hour"
fi
if [[ "$STARTUP_PRUNE_GUARD" == "1" ]]; then
  echo "Startup prune guard enabled for SendGrid boot."
fi
EXTRA_ARGS_STR=""
if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
  printf -v EXTRA_ARGS_STR ' %q' "${EXTRA_ARGS[@]}"
fi

echo "Running preflight checks..."
"$PY" send_shard.py --profile sendgrid_annette --status-sendgrid
mkdir -p "$PREFLIGHT_LOG_DIR"
for profile in "${PROFILES[@]}"; do
  echo "Preflight: $profile"
  preflight_log="$PREFLIGHT_LOG_DIR/${profile}.preflight.log"
  if preflight_output="$("$PY" send_shard.py --profile "$profile" --preflight 2>&1)"; then
    printf '%s\n' "$preflight_output" > "$preflight_log"
    if [[ -n "$preflight_output" ]]; then
      printf '%s\n' "$preflight_output"
    fi
  else
    status=$?
    printf '%s\n' "$preflight_output" > "$preflight_log"
    echo "Preflight failed for $profile. Output saved to $preflight_log."
    if [[ -n "$preflight_output" ]]; then
      printf '%s\n' "$preflight_output"
    fi
    exit "$status"
  fi
done

if [[ "$DRY_RUN" == "1" ]]; then
  echo "Dry run enabled; launch commands that would be sent:"
  for profile in "${PROFILES[@]}"; do
    echo "$PY send_shard.py --profile $profile$EXTRA_ARGS_STR"
  done
  exit 0
fi

tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true
tmux new-session -d -s "$SESSION_NAME" -n run

tmux split-window -h -t "$SESSION_NAME":run
tmux split-window -v -t "$SESSION_NAME":run.0
tmux split-window -v -t "$SESSION_NAME":run.1
tmux split-window -v -t "$SESSION_NAME":run.2
tmux select-layout -t "$SESSION_NAME":run tiled

tmux set-environment -t "$SESSION_NAME" SENDGRID_API_KEY "$SENDGRID_API_KEY"
tmux set-environment -t "$SESSION_NAME" SENDGRID_SKIP_PRUNE_ON_STARTUP "$STARTUP_PRUNE_GUARD"

mapfile -t PANE_IDS < <(tmux list-panes -t "$SESSION_NAME:run" -F '#{pane_index} #{pane_id}' | sort -n | awk '{print $2}')
if [[ "${#PANE_IDS[@]}" -lt "${#PROFILES[@]}" ]]; then
  echo "Unable to launch all SendGrid profiles: expected ${#PROFILES[@]} panes, found ${#PANE_IDS[@]}."
  tmux list-panes -t "$SESSION_NAME:run" -F '#{pane_index} #{pane_id} #{pane_current_command}' || true
  exit 1
fi

for idx in "${!PROFILES[@]}"; do
  profile="${PROFILES[$idx]}"
  pane="${PANE_IDS[$idx]}"
  escaped_key="$(printf '%q' "$SENDGRID_API_KEY")"
  escaped_guard="$(printf '%q' "$STARTUP_PRUNE_GUARD")"
  launch_command="cd \"$ROOT\"; export SENDGRID_API_KEY=$escaped_key; export SENDGRID_SKIP_PRUNE_ON_STARTUP=$escaped_guard; $PY send_shard.py --profile $profile$EXTRA_ARGS_STR"
  echo "Launching $profile in pane $pane"
  echo "Launch command: $PY send_shard.py --profile $profile$EXTRA_ARGS_STR"
  tmux send-keys -t "$pane" "$launch_command" C-m
done

missing_profiles=()
deadline=$((SECONDS + 8))
while true; do
  missing_profiles=()
  for profile in "${PROFILES[@]}"; do
    if ! pgrep -af "[s]end_shard.py --profile $profile" >/dev/null; then
      missing_profiles+=("$profile")
    fi
  done
  if [[ "${#missing_profiles[@]}" -eq 0 || "$SECONDS" -ge "$deadline" ]]; then
    break
  fi
  sleep 1
done
if [[ "${#missing_profiles[@]}" -gt 0 ]]; then
  echo "PARTIALLY_STARTED: missing profiles: ${missing_profiles[*]}"
  echo "Current send_shard.py processes:"
  pgrep -af "[s]end_shard.py --profile" || true
  echo "Current tmux panes:"
  tmux list-panes -t "$SESSION_NAME:run" -F '#{pane_index} #{pane_id} #{pane_current_command}' || true
  exit 2
fi

if [[ "$ATTACH_MODE" == "0" ]]; then
  echo "Started tmux session: $SESSION_NAME"
  exit 0
fi

if [[ -t 1 ]]; then
  tmux attach -t "$SESSION_NAME"
else
  echo "Started tmux session: $SESSION_NAME (no attach; non-interactive shell)"
fi
