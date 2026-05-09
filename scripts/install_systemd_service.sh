#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script with sudo."
  exit 1
fi

SERVICE_NAME="${SERVICE_NAME:-quantsync-compose}"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
RUN_USER="${RUN_USER:-${SUDO_USER:-ec2-user}}"
UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

if ! id "${RUN_USER}" >/dev/null 2>&1; then
  echo "User '${RUN_USER}' not found."
  exit 1
fi

if [[ ! -f "${PROJECT_DIR}/docker-compose.yml" ]]; then
  echo "docker-compose.yml not found in PROJECT_DIR=${PROJECT_DIR}"
  exit 1
fi

cat > "${UNIT_PATH}" <<EOF
[Unit]
Description=QuantSync Docker Compose Stack
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
User=${RUN_USER}
Group=${RUN_USER}
SupplementaryGroups=docker
WorkingDirectory=${PROJECT_DIR}
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"

echo "Installed ${UNIT_PATH}"
echo "Next commands:"
echo "  sudo systemctl start ${SERVICE_NAME}"
echo "  sudo systemctl status ${SERVICE_NAME}"
