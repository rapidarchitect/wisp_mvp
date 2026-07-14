#!/bin/bash
set -euo pipefail

# Backup WISPGen data directory to S3.
# The S3 bucket name is read from /srv/wispgen/env/wispgen.env if set,
# otherwise the script exits cleanly so the timer does not alarm.

ENV_FILE="/srv/wispgen/env/wispgen.env"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
fi

BUCKET="${WISPGEN_BACKUP_BUCKET:-}"
if [[ -z "$BUCKET" ]]; then
  echo "WISPGEN_BACKUP_BUCKET not set; skipping backup."
  exit 0
fi

aws s3 sync /srv/wispgen/data "s3://${BUCKET}/$(date -u +%Y-%m-%d)/" --delete
aws s3 sync /srv/wispgen/data "s3://${BUCKET}/latest/" --delete
