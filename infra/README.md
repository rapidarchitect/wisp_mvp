# Infrastructure

This directory will contain Terraform, nginx, certbot, systemd, and deployment artifacts for WISPGen.

**Owned by Task 19.** Do not create or modify files in this directory outside Task 19 without explicit human approval.

Planned contents:
- `provider.tf`, `variables.tf`, `main.tf`, `outputs.tf` — Terraform AWS infrastructure
- `userdata.sh` — EC2 bootstrap script
- `files/nginx-wispgen.conf` — nginx wildcard vhost for `*.app.wisp.llc`
- `files/wispgen.service` — systemd unit for uvicorn
- `files/env.template` — server environment variable template
- `files/wispgen-backup.sh` — tenant DB backup script

See the master plan at `docs/superpowers/plans/2026-07-12-wispgen-master-plan.md` for Task 19 details.
