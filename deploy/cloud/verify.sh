#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

REPO_ROOT="${ASTRA_REPO_ROOT:-/opt/astra/emailautomation}"
PYTHON_BIN="${ASTRA_PYTHON_BIN:-${REPO_ROOT}/.venv/bin/python}"
EXPECTED_COMMIT="${ASTRA_EXPECTED_GIT_COMMIT:-}"
REQUIRE_AUTHORITY=0

if [[ "${1:-}" == "--require-authority" ]]; then
  REQUIRE_AUTHORITY=1
  shift
fi
if [[ "$#" -ne 0 ]]; then
  echo "Usage: verify.sh [--require-authority]" >&2
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
"${PYTHON_BIN}" - "${STATUS_FILE}" "${EXPECTED_COMMIT}" "${REQUIRE_AUTHORITY}" <<'PY'
import json
import sys

status_path, expected_commit, require_authority = sys.argv[1:]
with open(status_path, encoding="utf-8") as handle:
    status = json.load(handle)
if status.get("machine") != "cloud":
    raise SystemExit("REFUSED: handoff status did not resolve machine=cloud.")
if status.get("head") != expected_commit:
    raise SystemExit("REFUSED: handoff status commit mismatch.")
if require_authority == "1" and status.get("real_send_authorized") is not True:
    raise SystemExit("REFUSED: cloud runtime authority is not active and valid.")
print(
    "Handoff status: "
    f"machine=cloud authorized={bool(status.get('real_send_authorized'))} "
    f"generation={status.get('generation_floor', 0)}"
)
PY

"${PYTHON_BIN}" - "${REPO_ROOT}" <<'PY'
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(repo))
from tools import runtime_handoff

profiles = runtime_handoff._profile_runtime_layout()
config = profiles.get("private_jc")
if not isinstance(config, dict) or not config.get("csv"):
    raise SystemExit("REFUSED: private_jc profile has no configured queue.")
queue = repo / "data/shards" / str(config["csv"])
if not queue.is_file():
    raise SystemExit(f"REFUSED: private_jc queue is missing: {queue}")
queue_state = runtime_handoff._read_queue_state(queue, "private_jc")
preview = runtime_handoff._preview_safety(
    repo,
    "private_jc",
    queue,
    queue_state,
)
if not preview["safe"]:
    predicates = ",".join(preview.get("failed_predicates") or ["unknown"])
    raise SystemExit(f"REFUSED: queue/preview verification failed: {predicates}")
fingerprints = {
    str(queue_state["fingerprint"]),
    str(preview["preview_fingerprint"]),
    str(preview["validated_fingerprint"]),
}
if len(fingerprints) != 1 or "" in fingerprints:
    raise SystemExit("REFUSED: queue/generated/validated fingerprints differ.")
print(
    "Queue/preview fingerprints: "
    f"rows={queue_state['row_count']} sha256={queue_state['fingerprint']}"
)
PY

ASTRA_MACHINE_ID=cloud "${PYTHON_BIN}" send_shard.py \
  --profile private_jc \
  --preflight

echo "Cloud deployment verification passed. No sender was started and no message was submitted."
