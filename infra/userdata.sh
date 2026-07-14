#!/bin/bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

# Base packages
apt-get update
apt-get install -y \
  nginx \
  certbot \
  python3-certbot-dns-route53 \
  python3.12-venv \
  git \
  sqlite3 \
  awscli \
  rsync

# Create service user
useradd --system --create-home --home-dir /srv/wispgen --user-group wispgen || true

# Directories
mkdir -p /srv/wispgen/{src,data/tenants,frontend,backup,env,logs}
chown -R wispgen:wispgen /srv/wispgen

# Install uv (project package manager)
su - wispgen -c "curl -LsSf https://astral.sh/uv/install.sh | sh"

# Initial empty env file (deploy script populates real values)
touch /srv/wispgen/env/wispgen.env
chown wispgen:wispgen /srv/wispgen/env/wispgen.env
chmod 600 /srv/wispgen/env/wispgen.env

# Place systemd and nginx configs from the repository after first deploy.
# Until then, keep nginx stopped so certbot can run cleanly.
systemctl stop nginx || true

# Backup timer placeholder; the real service/timer files are deployed by scripts/deploy.sh.
mkdir -p /etc/systemd/system

echo "Bootstrap complete. Run scripts/deploy.sh after DNS points to this host."
