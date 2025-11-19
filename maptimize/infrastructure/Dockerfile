# Builder stage: Build Python wheel
FROM python:3.11-slim AS builder

WORKDIR /tmp

# Copy source and build dependencies
COPY src/ /tmp/src/
COPY pyproject.toml /tmp/

# Install build tools and create wheel
RUN pip install --no-cache-dir hatchling && \
    python -m pip install --no-cache-dir build && \
    python -m build --no-isolation

# Runtime stage: Minimal production image
FROM python:3.11-slim

# Create non-root user for security
RUN useradd -m -u 1000 maptimize && \
    mkdir -p /app && \
    chown -R maptimize:maptimize /app

WORKDIR /app

# Copy built wheel from builder stage
COPY --from=builder --chown=maptimize:maptimize /tmp/dist/*.whl .

# Install application dependencies
RUN pip install --no-cache-dir --user *.whl && \
    rm *.whl

# Switch to non-root user
USER 1000

# Health check for container monitoring
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import maptimize; print('healthy')" || exit 1

# Entry point: Start Slack bot with Socket Mode
CMD ["python", "-m", "maptimize.bot"]
