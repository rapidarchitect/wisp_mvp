# Task 19 Plan: Terraform, nginx, certbot, deployment

## Objective
Deliver production infrastructure as code for WISPGen: a single encrypted EC2 host running the FastAPI backend and the React static build behind nginx, with wildcard TLS for `*.app.wisp.llc`, systemd service management, a simple backup script, and a documented deploy path. This is an infrastructure task; it is scenario-exempt per SPEC.md Section 8.

## Out of scope (Non-Goal 5 + current constraints)
- No Docker, RDS, queue broker, container orchestration, or multi-region.
- No live `terraform apply` from this agent; we will validate with `terraform plan` and leave the actual apply to the human operator.
- No real Stripe webhook endpoint wiring beyond environment variables; that remains a runtime configuration step.

## Deliverables

### Terraform (`infra/`)
1. `provider.tf`
   - AWS provider, profile from `~/.aws/credentials` (default profile unless overridden by `aws_profile` variable).
   - Region variable, default `us-east-1`.
2. `variables.tf`
   - `aws_profile`
   - `region`
   - `instance_type` (default `t3.large`)
   - `allowed_ssh_cidr` (no default; must be supplied; plan will fail if omitted to force explicit allowlist)
   - `key_name` (new keypair name, default `wispgen-deploy`)
   - `base_domain` (default `app.wisp.llc`)
   - `data_volume_size` (default 20 GiB)
3. `main.tf`
   - New RSA 4096-bit keypair; private key written to `../.keys/wispgen-deploy.pem` via `local_sensitive_file`.
   - Security group:
     - Ingress 443/80 from `0.0.0.0/0`
     - Ingress 22 from `var.allowed_ssh_cidr`
     - Egress all
   - Encrypted EBS root volume (gp3) via launch template / block-device mapping.
   - EC2 instance running Ubuntu 24.04 LTS AMI (latest from `canonical` owner).
   - Elastic IP attached to the instance.
   - S3 bucket for tenant DB backups with versioning disabled, encryption AES256.
   - IAM instance profile granting the bucket `PutObject`/`GetObject` only.
4. `outputs.tf`
   - `public_ip`
   - `instance_id`
   - `backup_bucket_name`
   - `ssh_command`
   - `key_file_path` (sensitive)
5. `userdata.sh`
   - Bootstrap script run on first launch:
     - Install python3.12-venv, nginx, certbot, certbot-dns-route53.
     - Create `wispgen` user and group.
     - Create `/srv/wispgen/{data,frontend,backup,src,env}`.
     - Clone (or later rsync) project source to `/srv/wispgen/src`.
     - Install uv and project dependencies in a venv owned by `wispgen`.
     - Place systemd service file and backup script.
     - Reload systemd.
   - Does **not** run certbot automatically; initial cert issuance is a manual step documented in `infra/README.md` because DNS-01 requires live Route 53 delegation and credentials.

### nginx configuration (`infra/files/nginx-wispgen.conf`)
- Listen 443 with wildcard cert paths from certbot (`/etc/letsencrypt/live/app.wisp.llc/`).
- Server names: `app.wisp.llc` and `*.app.wisp.llc`.
- HTTP-to-HTTPS redirect on port 80.
- HSTS header.
- Serve `/` and static assets from `/srv/wispgen/frontend/dist/`.
- Proxy `/api`, `/openapi.json`, `/docs`, `/redoc` to `http://127.0.0.1:8000`.
- Fallback to `index.html` for non-asset routes (React Router).
- `client_max_body_size 50m`.

### Systemd service (`infra/files/wispgen.service`)
- Runs as `wispgen` user.
- Working directory `/srv/wispgen/src`.
- ExecStart: `/srv/wispgen/src/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers`.
- Environment file `/srv/wispgen/env`.
- Restart on-failure.

### Environment template (`infra/files/env.template`)
Lists all required environment variables with placeholders:
- `WISPGEN_ENV=production`
- `WISPGEN_DATA_DIR=/srv/wispgen/data`
- `WISPGEN_BASE_DOMAIN=app.wisp.llc`
- `WISPGEN_SECRET_KEY=<generate>`
- `LLM_PROVIDER=bedrock`
- `BEDROCK_REGION=us-east-1`
- `BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-6`
- `TAVILY_API_KEY=<...>`
- `STRIPE_SECRET_KEY=<...>`
- `STRIPE_WEBHOOK_SECRET=<...>`
- `SES_REGION=us-east-1`
- `EMAIL_FROM=noreply@app.wisp.llc`
- `EMAIL_BACKEND=ses`
- `WISPGEN_ENABLE_TEST_ENDPOINTS=false`

### Backup script (`infra/files/wispgen-backup.sh`)
- Sync `/srv/wispgen/data` to the Terraform-created S3 bucket nightly via `aws s3 sync`.
- Run via systemd timer or cron (timer unit included).

### Deploy script (`scripts/deploy.sh`)
- Build frontend: `cd frontend && npm ci && npm run build`.
- Rsync `frontend/dist` to `/srv/wispgen/frontend/dist`.
- Rsync backend source to `/srv/wispgen/src`, run `uv sync` inside it.
- Reload systemd daemon, restart `wispgen` service, reload nginx.
- Supports `--target <host>` override.

### CI workflow (`.github/workflows/ci.yml`)
- Trigger on PRs to `main`.
- Job 1: backend `uv run pytest tests/`, `uv run ruff check .`.
- Job 2: frontend `npm ci`, `npm run build`, `npm run test` (if frontend tests exist).
- No deployment step in CI per Non-Goal 5 manual deploy path.

### Documentation updates
- Update `infra/README.md` with:
  - Prerequisites: AWS CLI, Terraform, SSH key management.
  - How to set `allowed_ssh_cidr`.
  - `terraform init/plan/apply` flow.
  - DNS requirements in Route 53.
  - Initial certbot DNS-01 command.
  - Post-deploy checks: EBS encryption, security group rules, wildcard cert, `https://demo.app.wisp.llc/`.
- Update `README.md` deployment section to reference `infra/README.md`.
- Update `TESTPLAN.md` Section 8 Task 19 status to `committed` after verification.

## Verification plan
1. `uv run ruff check .` clean after any Python additions.
2. `cd infra && terraform init` succeeds.
3. `cd infra && terraform validate` succeeds.
4. `cd infra && terraform plan` succeeds and shows no unexpected changes, failing if `allowed_ssh_cidr` is missing.
5. `infra/files/nginx-wispgen.conf` passes `nginx -t` if nginx is locally installed.
6. `scripts/deploy.sh --dry-run` syntax check (we will not run a real deploy).
7. Update `TESTPLAN.md` Task 19 row status.

## Open questions for the user
1. What is your current public IPv4 address so I can set the default `allowed_ssh_cidr` in the plan (or do you want to supply it at apply time only)?
2. Do you already own the `app.wisp.llc` domain in Route 53, or should the plan assume manual DNS setup?
3. Do you want a `Dockerfile` for CI/local parity despite Non-Goal 5, or stick to direct EC2 systemd deployment?
4. Should the deploy script use `git pull` on the server, or rsync from the local working tree?

## Assumptions
- AWS personal profile exists locally at `~/.aws/credentials`.
- Production LLM is Bedrock; Ollama stays dev-only.
- The `weasyprint` dependency in `pyproject.toml` is acceptable for dev but production PDFs use `fpdf2` already implemented in Task 16; no system Pango needed on the server.
