FROM python:3.13-slim AS builder

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    pip install --no-cache-dir uv && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy pyproject.toml first for dependency layer caching
COPY pyproject.toml .

# Install dependencies (without the project itself, for caching)
RUN uv pip install --system --no-cache .

# Copy source code
COPY src/ src/

# Reinstall to register entry points with full source
RUN uv pip install --system --no-cache .

# --- Runtime stage ---
FROM python:3.13-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 bravo && \
    useradd --uid 1000 --gid bravo --shell /bin/bash --create-home bravo

WORKDIR /app

# Copy installed Python packages and entry point scripts from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin/bravo-api /usr/local/bin/bravo-api
COPY --from=builder /usr/local/bin/bravo-worker /usr/local/bin/bravo-worker

# Copy application source
COPY src/ src/

ENV PYTHONPATH=/app

USER bravo

EXPOSE 8000
