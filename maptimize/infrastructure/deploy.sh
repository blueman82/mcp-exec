#!/bin/bash
set -e

# Deployment Script
# This script pulls the Docker image from ECR and starts containers
# Called by systemd service on EC2 startup

LOG_FILE="/opt/maptimize/logs/deploy.log"
APP_DIR="/opt/maptimize/app"
CONFIG_DIR="/opt/maptimize/config"

log_message() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_message "Starting application deployment"

# Validate required environment variables
log_message "Validating environment variables"
if [ -z "$AWS_REGION" ]; then
    log_message "ERROR: AWS_REGION not set"
    exit 1
fi

if [ -z "$AWS_ACCOUNT_ID" ]; then
    log_message "ERROR: AWS_ACCOUNT_ID not set"
    exit 1
fi

if [ -z "$ECR_REPOSITORY_NAME" ]; then
    log_message "ERROR: ECR_REPOSITORY_NAME not set"
    exit 1
fi

if [ -z "$APP_VERSION" ]; then
    log_message "WARNING: APP_VERSION not set, using 'latest'"
    APP_VERSION="latest"
fi

# Set ECR details
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
ECR_IMAGE="${ECR_REGISTRY}/${ECR_REPOSITORY_NAME}:${APP_VERSION}"

log_message "ECR Image: $ECR_IMAGE"

# Login to ECR
log_message "Authenticating with ECR"
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"

if [ $? -eq 0 ]; then
    log_message "Successfully authenticated with ECR"
else
    log_message "ERROR: Failed to authenticate with ECR"
    exit 1
fi

# Change to app directory
cd "$APP_DIR"
log_message "Changed to app directory: $APP_DIR"

# Pull latest docker-compose file from repository or use existing
if [ -f "$CONFIG_DIR/docker-compose.yml" ]; then
    log_message "Using docker-compose.yml from config directory"
    cp "$CONFIG_DIR/docker-compose.yml" "$APP_DIR/docker-compose.yml"
else
    log_message "ERROR: docker-compose.yml not found in config directory"
    exit 1
fi

# Stop existing containers if running
log_message "Stopping existing containers"
docker-compose down || true

# Pull latest image
log_message "Pulling Docker image: $ECR_IMAGE"
docker pull "$ECR_IMAGE"

if [ $? -ne 0 ]; then
    log_message "ERROR: Failed to pull Docker image"
    exit 1
fi

log_message "Successfully pulled Docker image"

# Start containers
log_message "Starting containers with docker-compose"
docker-compose up -d

if [ $? -eq 0 ]; then
    log_message "Containers started successfully"
else
    log_message "ERROR: Failed to start containers"
    exit 1
fi

# Wait for containers to be healthy
log_message "Waiting for containers to become healthy"
sleep 10

# Check container status
docker-compose ps | tee -a "$LOG_FILE"

# Verify containers are running
RUNNING_CONTAINERS=$(docker-compose ps -q)
if [ -z "$RUNNING_CONTAINERS" ]; then
    log_message "ERROR: No containers are running after deployment"
    exit 1
fi

log_message "Application deployment complete"
log_message "Running containers:"
docker-compose ps >> "$LOG_FILE" 2>&1

log_message "Deployment successful"
