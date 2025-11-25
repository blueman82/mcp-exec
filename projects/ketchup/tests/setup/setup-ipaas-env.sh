#!/bin/bash
# setup-ipaas-env.sh
#
# This script exports the iPaaS environment variables needed by docker-compose.yml
# These values should come from AWS Secrets Manager in production.
#
# Usage:
#   source setup-ipaas-env.sh
#   docker-compose up

echo "Setting up iPaaS environment variables for docker-compose..."

# Get secrets from AWS Secrets Manager
# Note: Requires AWS CLI to be configured with appropriate credentials
SECRET_NAME="Ketchup_Token_Secrets"
REGION="eu-west-1"
PROFILE="campaign_prod_v7"

echo "Fetching secrets from AWS Secrets Manager..."
SECRET_JSON=$(aws secretsmanager get-secret-value --secret-id "$SECRET_NAME" --region "$REGION" --query SecretString --output text --profile "$PROFILE" 2>/dev/null)

if [ $? -ne 0 ]; then
    echo "Error: Failed to fetch secrets from AWS Secrets Manager"
    echo "Make sure you have AWS CLI configured with appropriate credentials"
    exit 1
fi

# Parse and export the required environment variables
export JIRA_API_KEY=$(echo "$SECRET_JSON" | jq -r '.ipaas_api_key // empty')
export JIRA_USERNAME=$(echo "$SECRET_JSON" | jq -r '.ipaas_username // empty')
export JIRA_PASSWORD=$(echo "$SECRET_JSON" | jq -r '.ipaas_password // empty')
export JIRA_IMS_TOKEN=$(echo "$SECRET_JSON" | jq -r '.ims_access_token // empty')

# Verify that we got the values
if [ -z "$JIRA_API_KEY" ]; then
    echo "Warning: JIRA_API_KEY is empty"
fi

if [ -z "$JIRA_USERNAME" ]; then
    echo "Warning: JIRA_USERNAME is empty"
fi

if [ -z "$JIRA_PASSWORD" ]; then
    echo "Warning: JIRA_PASSWORD is empty"
fi

if [ -z "$JIRA_IMS_TOKEN" ]; then
    echo "Warning: JIRA_IMS_TOKEN is empty"
fi

echo "Environment variables set:"
echo "  JIRA_API_KEY: ${JIRA_API_KEY:0:10}..." # Show only first 10 chars for security
echo "  JIRA_USERNAME: $JIRA_USERNAME"
echo "  JIRA_PASSWORD: ****"
echo "  JIRA_IMS_TOKEN: ${JIRA_IMS_TOKEN:0:10}..." # Show only first 10 chars for security

echo ""
echo "You can now run: docker-compose up"