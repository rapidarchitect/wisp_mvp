#!/bin/sh
set -e

# Install/sync Python dependencies.
uv sync --frozen

# Seed the control DB and demo tenant into the container data volume.
# This script is shared with the Playwright E2E global setup.
uv run python frontend/e2e/setup.py

# Start uvicorn in the foreground so signals are handled correctly.
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app --proxy-headers
