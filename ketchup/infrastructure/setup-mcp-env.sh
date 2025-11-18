#!/bin/bash
# Setup MCP JIRA environment variables from AWS Secrets Manager and restart MCP with IPAAS

# Ensure AWS profile is set
export AWS_PROFILE=campaign_prod_v7
export AWS_REGION=eu-west-1

echo "🔧 Setting up MCP JIRA with IPAAS enabled..."

# Export AWS credentials for Docker Compose
echo "📋 Exporting AWS credentials for Docker..."
export AWS_ACCESS_KEY_ID=$(aws configure get aws_access_key_id --profile campaign_prod_v7)
export AWS_SECRET_ACCESS_KEY=$(aws configure get aws_secret_access_key --profile campaign_prod_v7)
export AWS_SESSION_TOKEN=$(aws configure get aws_session_token --profile campaign_prod_v7)

if [ -z "$AWS_ACCESS_KEY_ID" ]; then
    echo "❌ Error: AWS credentials not found for profile campaign_prod_v7"
    echo "Please ensure you have valid AWS credentials configured"
    exit 1
fi

echo "✓ AWS credentials exported successfully"

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/.."

echo "📥 Fetching JIRA credentials from AWS Secrets Manager..."

# Get the secret
SECRET_JSON=$(aws secretsmanager get-secret-value --secret-id Ketchup_Token_Secrets --query SecretString --output text)

# Extract JIRA credentials
export JIRA_API_KEY=$(echo $SECRET_JSON | jq -r '.ipaas_api_key // empty')
export JIRA_USERNAME=$(echo $SECRET_JSON | jq -r '.ipaas_username // empty')
export JIRA_PASSWORD=$(echo $SECRET_JSON | jq -r '.ipaas_password // empty')

# Check if we got the credentials
if [ -z "$JIRA_API_KEY" ] || [ -z "$JIRA_USERNAME" ]; then
    echo "❌ Error: Could not retrieve JIRA credentials from Secrets Manager"
    echo "JIRA_API_KEY: ${JIRA_API_KEY:-not set}"
    echo "JIRA_USERNAME: ${JIRA_USERNAME:-not set}"
    exit 1
else
    echo "✓ JIRA credentials loaded successfully"
    echo "  JIRA_USERNAME: $JIRA_USERNAME"
    echo "  JIRA_API_KEY: [REDACTED]"
fi

# Check if mcp-jira is running
echo ""
echo "🔍 Checking if mcp-jira service is running..."

MCP_RUNNING=$(docker-compose -f infrastructure/docker-compose.local.yml ps -q mcp-jira 2>/dev/null)

if [ -n "$MCP_RUNNING" ]; then
    echo "⚠️  MCP JIRA service is running - recreating with IPAAS enabled..."
    echo "   Stopping mcp-jira..."
    docker-compose -f infrastructure/docker-compose.local.yml stop mcp-jira
    echo "   Removing old container..."
    docker-compose -f infrastructure/docker-compose.local.yml rm -f mcp-jira
else
    echo "ℹ️  MCP JIRA service is not running"
fi

# Rebuild the image to ensure it picks up any changes
echo ""
echo "🔨 Rebuilding MCP JIRA image to ensure latest changes..."
docker-compose -f infrastructure/docker-compose.local.yml build mcp-jira

# Start mcp-jira with IPAAS enabled
echo ""
echo "🚀 Starting MCP JIRA with IPAAS enabled..."
docker-compose -f infrastructure/docker-compose.local.yml up -d mcp-jira

# Wait for service to be ready
echo ""
echo "⏳ Waiting for MCP JIRA to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:8081/health > /dev/null 2>&1; then
        echo "✅ MCP JIRA is ready and running with IPAAS enabled!"
        echo ""
        echo "📊 Service status:"
        docker-compose -f infrastructure/docker-compose.local.yml ps mcp-jira
        echo ""
        echo "🔗 MCP JIRA endpoint: http://localhost:8081"
        echo "🔗 IPAAS endpoint: https://ipaasapi.adobe-services.com/jira/rest/api/2"
        exit 0
    fi
    echo -n "."
    sleep 2
done

echo ""
echo "❌ MCP JIRA failed to start properly"
docker-compose -f infrastructure/docker-compose.local.yml logs --tail=50 mcp-jira
exit 1