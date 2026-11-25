# syntax=docker/dockerfile:1
FROM ubuntu:22.04

# Avoid interaction during apt installation
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    NODE_ENV=production \
    PORT=8000 \
    FASTAPI_PORT=8123 \
    GATEWAY_PORT=4000 \
    UV_NO_SYNC=1

# Install base packages & Node.js 22 LTS (supports amd64 and arm64 natively)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    tzdata \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y --no-install-recommends \
    nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy uv (multi-arch binary for python virtualenvs) and Caddy (multi-arch reverse proxy)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY --from=caddy:2-alpine /usr/bin/caddy /usr/bin/caddy

WORKDIR /app

# 1. Install Node.js dependencies (including agent-browser CLI with architecture-specific native binary)
COPY package.json package-lock.json ./
RUN npm ci \
    && ln -sf /app/node_modules/.bin/agent-browser /usr/local/bin/agent-browser

# 2. Install Python dependencies with uv (fetches prebuilt Python 3.13 and wheels for TARGETARCH)
COPY pyproject.toml uv.lock ./
RUN uv python install 3.13 \
    && uv sync --frozen --no-dev

# 3. Copy application files and configs
COPY app/ ./app/
COPY src/ ./src/
COPY main.py ./
COPY Caddyfile /etc/caddy/Caddyfile
COPY docker-entrypoint.sh /app/docker-entrypoint.sh

RUN chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /app/uploads /app/logs

ENV PATH="/app/.venv/bin:/app/node_modules/.bin:${PATH}"

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
