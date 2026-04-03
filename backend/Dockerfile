# syntax=docker/dockerfile:1

# ══════════════════════════════════════════════════════════════
# Stage 1: Builder — install uv, sync dependencies
# ══════════════════════════════════════════════════════════════
FROM python:3.13-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (layer caching)
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Copy source code and install project
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


# ══════════════════════════════════════════════════════════════
# Stage 2: Development — includes dev deps + Playwright browsers
# ══════════════════════════════════════════════════════════════
FROM python:3.13-slim AS development
ARG PLAYWRIGHT_MCP_VERSION=0.0.70

# Install system deps for Playwright + Xvfb (headed anti-detection)
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libx11-xcb1 \
    libxshmfence1 \
    fonts-noto-color-emoji \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

# Install Playwright browsers
RUN uv run playwright install chromium

# Ensure @playwright/mcp is available (pinned version avoids npx re-download at runtime)
RUN npm install -g @playwright/mcp@${PLAYWRIGHT_MCP_VERSION}

ENV DISPLAY=:99

EXPOSE 8000

CMD ["sh", "-c", "Xvfb :99 -screen 0 1920x1080x24 & uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload"]


# ══════════════════════════════════════════════════════════════
# Stage 3: Production — minimal runtime
# ══════════════════════════════════════════════════════════════
FROM python:3.13-slim AS production
ARG PLAYWRIGHT_MCP_VERSION=0.0.70

RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libx11-xcb1 \
    libxshmfence1 \
    fonts-noto-color-emoji \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install @playwright/mcp globally (pinned version avoids npx re-download at runtime)
RUN npm install -g @playwright/mcp@${PLAYWRIGHT_MCP_VERSION}

WORKDIR /app

# Copy the built virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

# Install Playwright browsers in production
COPY --from=builder /app/pyproject.toml /app/uv.lock ./
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
RUN uv run playwright install chromium
RUN uv run logfire auth

ENV PATH="/app/.venv/bin:$PATH" \
    DISPLAY=:99

EXPOSE 8000

CMD ["sh", "-c", "Xvfb :99 -screen 0 1920x1080x24 & uvicorn src.main:app --host 0.0.0.0 --port 8000"]
