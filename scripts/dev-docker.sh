#!/bin/bash
set -euo pipefail

# Start the local Docker dev stack for Playwright E2E testing.
# Usage: ./scripts/dev-docker.sh [test-pattern]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

export DOCKER_DEV=1

cd "$ROOT"

echo "Starting Docker dev stack..."
docker compose down --remove-orphans --volumes || true
docker volume rm -f wispgen-data || true
docker compose up -d --build

# Wait for backend health
echo "Waiting for backend health..."
for _ in {1..30}; do
  if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

# Seed deterministic demo data for E2E (avoids AI seeder crew)
echo "Seeding deterministic demo tenant..."
docker compose exec -T backend uv run python frontend/e2e/setup.py || true

echo ""
echo "Stack ready:"
echo "  Frontend: http://demo.localhost:5173"
echo "  Backend:  http://api.localhost:8000"
echo ""

if [[ $# -gt 0 ]]; then
  cd frontend
  npx playwright test "$@"
else
  echo "Run tests with: cd frontend && DOCKER_DEV=1 npx playwright test"
fi
