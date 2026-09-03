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

# Production workers resolve their own exact protected profile credential.
# Do not carry a dashboard/shell key into tmux or worker command text.
unset SENDGRID_API_KEY

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
  escaped_guard="$(printf '%q' "$STARTUP_PRUNE_GUARD")"
  launch_command="cd \"$ROOT\"; export SENDGRID_SKIP_PRUNE_ON_STARTUP=$escaped_guard; $PY send_shard.py --profile $profile$EXTRA_ARGS_STR"
  echo "Launching $profile in pane $pane"
  echo "Launch command: $PY send_shard.py --profile $profile$EXTRA_ARGS_STR"
  tmux send-keys -t "$pane" "$launch_command" C-m
done

missing_profiles=()
deadline=$((SECONDS + 8))
stable_since=-1
startup_verified=0

profile_worker_running() {
  local profile="$1"
  ps -eo comm=,args= | awk -v expected_profile="$profile" '
    $1 ~ /^(python([0-9.]*)?|pypy([0-9.]*)?)$/ {
      sender_script = 0
      matching_profile = 0
      for (index = 2; index <= NF; index += 1) {
        if ($index == "send_shard.py" || $index ~ /\/send_shard[.]py$/) {
          sender_script = 1
        }
        if ($index == "--profile" && $(index + 1) == expected_profile) {
          matching_profile = 1
        }
        if ($index == "--profile=" expected_profile) {
          matching_profile = 1
        }
      }
      if (sender_script && matching_profile) {
        found = 1
      }
    }
    END { exit(found ? 0 : 1) }
  '
}

while true; do
  missing_profiles=()
  for profile in "${PROFILES[@]}"; do
    if ! profile_worker_running "$profile"; then
      missing_profiles+=("$profile")
    fi
  done
  if [[ "${#missing_profiles[@]}" -eq 0 ]]; then
    if [[ "$stable_since" -lt 0 ]]; then
      stable_since=$SECONDS
    elif [[ $((SECONDS - stable_since)) -ge 1 ]]; then
      startup_verified=1
      break
    fi
  else
    stable_since=-1
  fi
  if [[ "$SECONDS" -ge "$deadline" ]]; then
    break
  fi
  sleep 0.2
done
if [[ "$startup_verified" != "1" ]]; then
  if [[ "${#missing_profiles[@]}" -gt 0 ]]; then
    echo "PARTIALLY_STARTED: missing profiles: ${missing_profiles[*]}"
  else
    echo "PARTIALLY_STARTED: workers did not survive the startup stability window"
  fi
  echo "Current send_shard.py processes:"
  ps -eo pid=,comm=,args= | awk '
    $2 ~ /^(python([0-9.]*)?|pypy([0-9.]*)?)$/ && /send_shard[.]py/ && /--profile/ { print }
  ' || true
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
