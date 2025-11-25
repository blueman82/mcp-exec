#!/bin/bash

# LocalStack initialization script to create required secrets
# This script creates the Ketchup_Token_Secrets for local development

set -euo pipefail

echo "Initializing LocalStack secrets for Ketchup development..."

# Wait for LocalStack to be ready
echo "Waiting for LocalStack to be ready..."
until curl -s http://localhost:4566/_localstack/health | grep -q '"secretsmanager": "available"'; do
  echo "Waiting for SecretManager service..."
  sleep 2
done

echo "LocalStack is ready. Creating secrets..."

# Create the Ketchup_Token_Secrets with dummy values for local development
SECRET_VALUE='{
  "slack_signing_secret": "local_development_signing_secret_placeholder",
  "slack_bot_token": "xoxb-local-dev-placeholder-token",
  "slack_app_token": "xapp-local-dev-placeholder-token",
  "openai_api_key": "sk-local-dev-placeholder-key",
  "jira_username": "local-dev-user", 
  "jira_password": "local-dev-placeholder-password",
  "jira_server_url": "http://localhost:8080/jira"
}'

# Create the secret using LocalStack endpoint
aws --endpoint-url=http://localhost:4566 secretsmanager create-secret \
    --name "Ketchup_Token_Secrets" \
    --description "Ketchup application secrets for local development" \
    --secret-string "$SECRET_VALUE" \
    --region eu-west-1

echo "✅ Successfully created Ketchup_Token_Secrets"

# Verify the secret was created
echo "Verifying secret creation..."
aws --endpoint-url=http://localhost:4566 secretsmanager describe-secret \
    --secret-id "Ketchup_Token_Secrets" \
    --region eu-west-1

echo "🚀 LocalStack secrets initialization completed successfully!"