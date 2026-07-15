# Production Deployment Guide

This document describes the manual steps to bring up WISPGen on AWS after running `terraform apply` from `infra/`.

## What Terraform creates

- Single EC2 `t3.large` with an encrypted gp3 root volume.
- Security group: world on 80/443, SSH restricted to the CIDR supplied at apply time.
- Elastic IP attached to the instance.
- S3 backup bucket with private, AES256-encrypted storage.
- IAM instance profile allowing the host to write backups to that bucket.
- A 4096-bit RSA deploy key saved to `.keys/wispgen-deploy.pem`.

## 1. Apply Terraform

```bash
cd infra
terraform init
terraform apply -var="allowed_ssh_cidr=24.11.224.55/32"
```

## 2. Collect outputs

```bash
terraform output public_ip
terraform output backup_bucket_name
```

## 3. Configure DNS in Route 53

Create two A records pointing to the elastic IP from step 2:

- `app.wisp.llc`
- `*.app.wisp.llc`

Wait for DNS propagation (`dig demo.app.wisp.llc`).

## 4. Clone the project on the server

```bash
ssh -i .keys/wispgen-deploy.pem ubuntu@<elastic_ip>
sudo -u wispgen git clone https://github.com/<your-org>/wisp_july_10.git /srv/wispgen/src
```

## 5. Obtain the wildcard certificate

```bash
sudo certbot certonly --dns-route53 \
  -d "app.wisp.llc" \
  -d "*.app.wisp.llc"
```

## 6. Populate environment secrets

```bash
scp -i .keys/wispgen-deploy.pem infra/files/env.template \
  ubuntu@<elastic_ip>:/srv/wispgen/env/wispgen.env
ssh -i .keys/wispgen-deploy.pem ubuntu@<elastic_ip>
sudo nano /srv/wispgen/env/wispgen.env
```

Required values:

- `WISPGEN_SECRET_KEY` — generate a random 32+ byte string.
- `WISPGEN_BACKUP_BUCKET` — set to the bucket name from step 2.
- `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` — from Stripe dashboard.
- `TAVILY_API_KEY` — from Tavily dashboard.
- `EMAIL_BACKEND=ses` for production; `SES_REGION` should match.

## 7. Deploy the application

From your local checkout:

```bash
HOST=<elastic_ip> ./scripts/deploy.sh
```

This builds the frontend locally, syncs it to the server, pulls backend source, installs dependencies, and restarts services.

## 8. Seed the demo tenant

```bash
ssh -i .keys/wispgen-deploy.pem ubuntu@<elastic_ip>
sudo -u wispgen /srv/wispgen/src/.venv/bin/python -m app.cli seed-demo
```

## 9. Verify

```bash
curl -fsSI https://demo.app.wisp.llc/
openssl s_client -connect demo.app.wisp.llc:443 -servername demo.app.wisp.llc </dev/null | head
```

You should see a 200 response and a wildcard certificate covering `*.app.wisp.llc`.

## Operational commands

Restart backend:

```bash
ssh -i .keys/wispgen-deploy.pem ubuntu@<elastic_ip>
sudo systemctl restart wispgen
sudo journalctl -u wispgen -f
```

Reload nginx:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

Run a backup manually:

```bash
sudo systemctl start wispgen-backup
```

Renew certificates:

```bash
sudo certbot renew --dry-run
```
