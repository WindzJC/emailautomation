#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required"
  exit 1
fi

if [[ ! -f ".env" ]]; then
  echo "Missing .env in $ROOT"
  echo "Copy it from the source machine before running this setup."
  exit 1
fi

if [[ ! -d "data/shards" ]]; then
  echo "Missing data/shards in $ROOT"
  echo "Sync the managed data/ directory before running this setup."
  exit 1
fi

if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
fi

source ".venv/bin/activate"
python -m pip install -U pip
python -m pip install -r requirements.txt

if ! command -v tmux >/dev/null 2>&1; then
  cat <<'EOF'
tmux is not installed.

Install it with:
  brew install tmux
EOF
fi

cat <<'EOF'
Mac runtime is ready.

Start the dashboard:
  ./run_live_dashboard.sh

Start the dashboard in tmux:
  TMUX_DASHBOARD_SESSION=email_dashboard LIVE_DASHBOARD_PORT=8001 ./run_dashboard_tmux.sh

Start the senders:
  TMUX_SENDGRID_ATTACH=0 ./run_sendgrid_tmux.sh
EOF
