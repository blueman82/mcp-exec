# Builder stage: Build Python wheel
FROM python:3.11-slim AS builder

WORKDIR /tmp

# Copy source and build dependencies
COPY src/ /tmp/src/
COPY config/ /tmp/config/
COPY pyproject.toml /tmp/

# Install build tools and create wheel
RUN pip install --no-cache-dir hatchling && \
    python -m pip install --no-cache-dir build && \
    python -m build --no-isolation

# Runtime stage: Minimal production image
FROM python:3.11-slim

# Install Playwright system dependencies
RUN apt-get update && apt-get install -y \
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libpango-1.0-0 libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 maptimize && \
    mkdir -p /app && \
    chown -R maptimize:maptimize /app

WORKDIR /app

# Copy built wheel from builder stage
COPY --from=builder --chown=maptimize:maptimize /tmp/dist/*.whl .

# Install application dependencies with correct Python path
RUN pip install --no-cache-dir *.whl && \
    rm *.whl

# Set Playwright browser path to shared location accessible by all users
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers

# Install Playwright browsers with dependencies to shared location
RUN mkdir -p /opt/playwright-browsers && \
    playwright install --with-deps chromium && \
    chmod -R 755 /opt/playwright-browsers

# Copy configuration directory
COPY --chown=maptimize:maptimize config/ /app/config/

# Switch to non-root user
USER 1000

# Health check for container monitoring
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import maptimize; print('healthy')" || exit 1

# Entry point: Start Slack bot with Socket Mode
CMD ["python", "-m", "maptimize.bot"]
