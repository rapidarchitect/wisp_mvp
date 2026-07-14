# CI/local parity image for WISPGen backend.
# Production runs directly on EC2 via systemd; this image is for testing only.
FROM python:3.12-slim

WORKDIR /app

# System deps for build/runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsqlite3-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Copy project files
COPY pyproject.toml uv.lock ./
COPY app ./app

# Install dependencies into the image
RUN uv sync --no-dev --frozen

# Runtime defaults (override in production)
ENV WISPGEN_ENV=production
ENV WISPGEN_DATA_DIR=/app/data
ENV WISPGEN_BASE_DOMAIN=app.wisp.llc
ENV LLM_PROVIDER=bedrock

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
