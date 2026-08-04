#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

REPO_ROOT="${ASTRA_REPO_ROOT:-/opt/astra/emailautomation}"
PYTHON_BIN="${ASTRA_PYTHON_BIN:-${REPO_ROOT}/.venv/bin/python}"
EXPECTED_COMMIT="${ASTRA_EXPECTED_GIT_COMMIT:-}"
REQUIRE_AUTHORITY=0
PROFILE=""

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --require-authority)
      REQUIRE_AUTHORITY=1
      shift
      ;;
    --profile)
      if [[ "$#" -lt 2 || -z "${2}" || -n "${PROFILE}" ]]; then
        echo "Usage: verify.sh --profile PROFILE [--require-authority]" >&2
        exit 2
      fi
      PROFILE="$2"
      shift 2
      ;;
    *)
      echo "Usage: verify.sh --profile PROFILE [--require-authority]" >&2
      exit 2
      ;;
  esac
done
if [[ -z "${PROFILE}" ]]; then
  echo "REFUSED: --profile is required; no sender profile is selected by default." >&2
  exit 2
fi
if [[ -z "${EXPECTED_COMMIT}" ]]; then
  echo "REFUSED: ASTRA_EXPECTED_GIT_COMMIT is required." >&2
  exit 1
fi
if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "REFUSED: Python virtual environment is missing: ${PYTHON_BIN}" >&2
  exit 1
fi

for command in git flock systemctl; do
  command -v "${command}" >/dev/null || {
    echo "REFUSED: missing dependency: ${command}" >&2
    exit 1
  }
done

cd "${REPO_ROOT}"
HEAD_COMMIT="$(git rev-parse HEAD)"
if [[ "${HEAD_COMMIT}" != "${EXPECTED_COMMIT}" ]]; then
  echo "REFUSED: checkout commit does not match ASTRA_EXPECTED_GIT_COMMIT." >&2
  exit 1
fi
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "REFUSED: tracked worktree is dirty." >&2
  exit 1
fi

"${PYTHON_BIN}" -c \
  'import fastapi, uvicorn, cryptography, email_validator, sqlite3; print("Python dependencies: ok")'

STATUS_FILE="$(mktemp)"
trap 'rm -f "${STATUS_FILE}"' EXIT
ASTRA_MACHINE_ID=cloud HANDOFF_PYTHON="${PYTHON_BIN}" \
  ./handoff status >"${STATUS_FILE}"
"${PYTHON_BIN}" - "${STATUS_FILE}" "${EXPECTED_COMMIT}" "${REQUIRE_AUTHORITY}" "${REPO_ROOT}" <<'PY'
import json
import sys
from pathlib import Path

status_path, expected_commit, require_authority, repo_root = sys.argv[1:]
sys.path.insert(0, str(Path(repo_root).resolve()))

from tools.cloud_verify_policy import unsafe_runtime_blockers
with open(status_path, encoding="utf-8") as handle:
    status = json.load(handle)
if status.get("machine") != "cloud":
    raise SystemExit("REFUSED: handoff status did not resolve machine=cloud.")
if status.get("head") != expected_commit:
    raise SystemExit("REFUSED: handoff status commit mismatch.")
blockers = status.get("process_blockers")
if not isinstance(blockers, list):
    raise SystemExit("REFUSED: handoff process-blocker status is malformed.")

try:
    unsafe_blockers = unsafe_runtime_blockers(blockers)
except ValueError as exc:
    raise SystemExit(
        f"REFUSED: handoff process-blocker status is malformed: {exc}"
    ) from exc

if unsafe_blockers:
    raise SystemExit(
        "REFUSED: unsafe runtime process blockers remain "
        f"({len(unsafe_blockers)})."
    )
if require_authority == "1" and status.get("real_send_authorized") is not True:
    raise SystemExit("REFUSED: cloud runtime authority is not active and valid.")
print(
    "Handoff status: "
    f"machine=cloud authorized={bool(status.get('real_send_authorized'))} "
    f"generation={status.get('generation_floor', 0)}"
)
PY

"${PYTHON_BIN}" - "${REPO_ROOT}" "${PROFILE}" "${REQUIRE_AUTHORITY}" <<'PY'
import os
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
profile = sys.argv[2]
require_authority = sys.argv[3] == "1"
sys.path.insert(0, str(repo))
from send_shard import PROFILES
from tools import runtime_handoff

config = PROFILES.get(profile)
if not isinstance(config, dict):
    raise SystemExit("REFUSED: unknown sender profile.")
queue_name = str(config.get("csv") or "").strip()
if not queue_name or Path(queue_name).name != queue_name:
    raise SystemExit("REFUSED: selected profile has an unsafe queue mapping.")
provider = str(config.get("provider") or "").strip().lower()
credential_env = (
    "SENDGRID_API_KEY"
    if provider == "sendgrid"
    else str(config.get("password_env") or "").strip()
)
if not credential_env:
    raise SystemExit("REFUSED: selected profile has no credential mapping.")
if require_authority and not str(os.environ.get(credential_env) or "").strip():
    raise SystemExit(
        "REFUSED: selected profile credential is absent from the protected environment."
    )
queue = repo / "data/shards" / queue_name
if not queue.is_file():
    raise SystemExit("REFUSED: selected profile queue is missing.")
queue_state = runtime_handoff._read_queue_state(queue, profile)
if int(queue_state["row_count"]) <= 0:
    raise SystemExit("REFUSED: selected profile queue has no data rows.")
preview = runtime_handoff._preview_safety(
    repo,
    profile,
    queue,
    queue_state,
)
if not preview["safe"]:
    predicates = ",".join(preview.get("failed_predicates") or ["unknown"])
    raise SystemExit(f"REFUSED: queue/preview verification failed: {predicates}")
print(
    "Profile verification: "
    f"profile={profile} provider={provider} queue={queue_name} "
    f"credential_variable={credential_env} rows={queue_state['row_count']} "
    f"verified_emergency_queue_progress="
    f"{bool(preview.get('verified_emergency_queue_progress'))}"
)
PY

ASTRA_MACHINE_ID=cloud "${PYTHON_BIN}" send_shard.py \
  --profile "${PROFILE}" \
  --preflight

echo "Cloud deployment verification passed for ${PROFILE}. No sender was started and no message was submitted."
