#!/bin/bash
set -euo pipefail

# Deploy WISPGen to the production EC2 host.
# Assumes the repository has already been cloned on the server at /srv/wispgen/src.

HOST="${HOST:-}"
KEY="${KEY:-./.keys/wispgen-deploy.pem}"
USER="${USER:-ubuntu}"

# Allow --target <host> for explicit CLI usage.
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      HOST="$2"
      shift 2
      ;;
    --key)
      KEY="$2"
      shift 2
      ;;
    --user)
      USER="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

if [[ -z "$HOST" ]]; then
  echo "Usage: HOST=1.2.3.4 ./scripts/deploy.sh"
  echo "       ./scripts/deploy.sh --target 1.2.3.4"
  echo "Override defaults with KEY=... USER=... or --key/--user"
  exit 1
fi

echo "Deploying to ${USER}@${HOST} ..."

# Build frontend locally
cd frontend
npm ci
npm run build
cd ..

# Sync frontend build
rsync -avz --delete frontend/dist/ "${USER}@${HOST}:/srv/wispgen/frontend/dist/"

# Pull backend source on the server, install deps, and restart services
ssh -i "$KEY" "${USER}@${HOST}" <<'REMOTE'
  set -euo pipefail

  cd /srv/wispgen/src
  sudo -u wispgen git pull origin main

  sudo -u wispgen /home/wispgen/.local/bin/uv sync --no-dev --frozen

  sudo cp infra/files/wispgen.service /etc/systemd/system/
  sudo cp infra/files/wispgen-backup.service /etc/systemd/system/
  sudo cp infra/files/wispgen-backup.timer /etc/systemd/system/
  sudo cp infra/files/nginx-wispgen.conf /etc/nginx/sites-available/wispgen
  sudo ln -sf /etc/nginx/sites-available/wispgen /etc/nginx/sites-enabled/wispgen
  sudo rm -f /etc/nginx/sites-enabled/default

  sudo systemctl daemon-reload
  sudo systemctl enable wispgen wispgen-backup.timer
  sudo systemctl restart wispgen
  sudo systemctl restart wispgen-backup.timer
  sudo nginx -t
  sudo systemctl reload nginx
REMOTE

echo "Deploy complete."
