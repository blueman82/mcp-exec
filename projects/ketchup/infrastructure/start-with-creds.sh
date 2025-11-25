#!/bin/bash

# Export AWS credentials from profile
export AWS_ACCESS_KEY_ID=$(aws configure get aws_access_key_id --profile campaign_prod_v7)
export AWS_SECRET_ACCESS_KEY=$(aws configure get aws_secret_access_key --profile campaign_prod_v7)
export AWS_SESSION_TOKEN=$(aws configure get aws_session_token --profile campaign_prod_v7)

# Start services
docker-compose -f docker-compose.local.yml up -d mcp-jira

echo "Started MCP JIRA with AWS credentials"