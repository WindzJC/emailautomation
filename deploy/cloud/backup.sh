#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

REPO_ROOT="${ASTRA_REPO_ROOT:-/opt/astra/emailautomation}"
PYTHON_BIN="${ASTRA_PYTHON_BIN:-${REPO_ROOT}/.venv/bin/python}"
LOCK_FILE="/run/astra-emailautomation/backup.lock"

for variable in RESTIC_REPOSITORY RESTIC_PASSWORD_FILE; do
  if [[ -z "${!variable:-}" ]]; then
    echo "REFUSED: ${variable} must be set by the protected environment file." >&2
    exit 1
  fi
done
if [[ ! -r "${RESTIC_PASSWORD_FILE}" ]]; then
  echo "REFUSED: RESTIC_PASSWORD_FILE is not readable." >&2
  exit 1
fi

install -d -m 0700 "$(dirname "${LOCK_FILE}")"
exec 9>"${LOCK_FILE}"
flock --nonblock 9 || {
  echo "REFUSED: another Astra backup is already running." >&2
  exit 75
}

cd "${REPO_ROOT}"
STATUS_FILE="$(mktemp)"
trap 'rm -f "${STATUS_FILE}"' EXIT
ASTRA_MACHINE_ID=cloud HANDOFF_PYTHON="${PYTHON_BIN}" \
  ./handoff status >"${STATUS_FILE}"
"${PYTHON_BIN}" - "${STATUS_FILE}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    status = json.load(handle)
blockers = list(status.get("process_blockers") or [])
jobs = list(status.get("active_job_files") or [])
if blockers or jobs:
    raise SystemExit(
        "REFUSED: backup requires an offline cloud runtime maintenance window; "
        f"process_blockers={len(blockers)} active_jobs={len(jobs)}"
    )
PY

restic backup \
  --one-file-system \
  --tag astra-runtime \
  --exclude "${REPO_ROOT}/.env" \
  --exclude "${REPO_ROOT}/.env.*" \
  --exclude ".env" \
  --exclude ".env.*" \
  --exclude "**/.env" \
  --exclude "**/.env.*" \
  --exclude "KEYS" \
  --exclude "**/KEYS" \
  --exclude "ACC GMAIL" \
  --exclude "**/ACC GMAIL" \
  --exclude "${REPO_ROOT}/.venv" \
  --exclude "${REPO_ROOT}/runtime_handoff_bundles" \
  "${REPO_ROOT}/data" \
  "${REPO_ROOT}/_important" \
  "${REPO_ROOT}/.runtime_handoff"
restic check --read-data-subset="${ASTRA_RESTIC_CHECK_SUBSET:-1/100}"

echo "Encrypted, checksummed offline runtime backup completed."
