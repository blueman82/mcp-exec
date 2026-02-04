# Multi-stage Dockerfile for AskSplunk Slack Bot
# Target Platform: linux/amd64 (AWS EC2)
# Base: Python 3.11 slim (Debian)

###################
# Stage 1: Builder
###################
FROM python:3.11-slim AS builder

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

###################
# Stage 2: Runtime
###################
FROM python:3.11-slim AS runtime

# Add metadata labels
LABEL maintainer="harrison_adobe" \
      description="AskSplunk: Slack bot that translates natural language to Splunk SPL queries" \
      version="1.0.0"

# Install runtime system dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r asksplunk && useradd -r -g asksplunk -u 1000 asksplunk

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=asksplunk:asksplunk src/ /app/src/
COPY --chown=asksplunk:asksplunk docs/schema/ /app/docs/schema/

# Switch to non-root user
USER asksplunk

# Expose health check port (if needed)
EXPOSE 3000

# Set Python environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

# Health check (optional - adjust based on your app)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Entrypoint for running the Slack bot
ENTRYPOINT ["python", "-m", "asksplunk.main"]
