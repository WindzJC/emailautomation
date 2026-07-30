#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "REFUSED: run bootstrap.sh as root on the cloud host." >&2
  exit 1
fi

REPO_ROOT="${ASTRA_REPO_ROOT:-/opt/astra/emailautomation}"
SERVICE_USER="${ASTRA_SERVICE_USER:-astra}"
SERVICE_GROUP="${ASTRA_SERVICE_GROUP:-astra}"
ENV_DIR="/etc/astra-emailautomation"
ENV_FILE="${ENV_DIR}/astra.env"
UNIT_DIR="/etc/systemd/system"
BACKUP_DIR="/var/lib/astra-backups"

if [[ ! -f "${REPO_ROOT}/send_shard.py" || ! -f "${REPO_ROOT}/tools/runtime_handoff.py" ]]; then
  echo "REFUSED: expected an existing reviewed checkout at ${REPO_ROOT}." >&2
  exit 1
fi
if [[ "${REPO_ROOT}" != "/opt/astra/emailautomation" ]]; then
  echo "REFUSED: packaged systemd units require /opt/astra/emailautomation." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  git \
  python3 \
  python3-pip \
  python3-venv \
  restic \
  rsync \
  sqlite3 \
  util-linux

if ! getent group "${SERVICE_GROUP}" >/dev/null; then
  groupadd --system "${SERVICE_GROUP}"
fi
if ! id "${SERVICE_USER}" >/dev/null 2>&1; then
  useradd \
    --system \
    --gid "${SERVICE_GROUP}" \
    --home-dir /var/lib/astra \
    --create-home \
    --shell /usr/sbin/nologin \
    "${SERVICE_USER}"
fi

install -d -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0750 "${REPO_ROOT}"
install -d -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0750 "${REPO_ROOT}/data"
install -d -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0750 "${REPO_ROOT}/_important"
install -d -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0700 "${REPO_ROOT}/.runtime_handoff"
install -d -o root -g "${SERVICE_GROUP}" -m 0750 "${ENV_DIR}"
install -d -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0700 "${BACKUP_DIR}"
install -m 0640 "${REPO_ROOT}/deploy/cloud/env.example" "${ENV_DIR}/astra.env.example"
if [[ ! -e "${ENV_FILE}" ]]; then
  install -o root -g "${SERVICE_GROUP}" -m 0640 /dev/null "${ENV_FILE}"
  echo "Created empty ${ENV_FILE}; populate it out of band before starting services."
fi

python3 -m venv "${REPO_ROOT}/.venv"
"${REPO_ROOT}/.venv/bin/python" -m pip install --upgrade pip
"${REPO_ROOT}/.venv/bin/python" -m pip install -r "${REPO_ROOT}/requirements.txt"

for unit in \
  astra-dashboard.service \
  astra-sender.service \
  astra-backup.service \
  astra-backup.timer
do
  install -m 0644 "${REPO_ROOT}/deploy/cloud/${unit}" "${UNIT_DIR}/${unit}"
done
systemctl daemon-reload

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "NOTE: cloudflared is not installed; install it from Cloudflare's signed repository if needed."
fi

echo "Bootstrap complete. No service was enabled or started."
echo "Populate ${ENV_FILE}, review permissions, transfer runtime authority, then run verify.sh."
