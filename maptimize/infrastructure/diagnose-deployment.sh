#!/bin/bash
# Maptimize Deployment Diagnostic Script
# Run this on the EC2 instance to diagnose connectivity issues

set -e

echo "=========================================="
echo "Maptimize Deployment Diagnostics"
echo "=========================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check 1: Docker container status
echo "1. Checking Docker container status..."
if docker ps | grep -q maptimize-bot; then
    echo -e "${GREEN}✓ Container is running${NC}"
    docker ps | grep maptimize-bot
else
    echo -e "${RED}✗ Container is NOT running${NC}"
    echo "Checking stopped containers..."
    docker ps -a | grep maptimize-bot || echo "Container not found at all"
fi
echo ""

# Check 2: Container logs (last 50 lines)
echo "2. Checking container logs (last 50 lines)..."
if docker ps | grep -q maptimize-bot; then
    docker logs --tail 50 maptimize-bot
else
    echo -e "${RED}✗ Cannot check logs - container not running${NC}"
fi
echo ""

# Check 3: AWS credentials and region
echo "3. Checking AWS credentials..."
aws sts get-caller-identity 2>&1 | head -5
echo ""

# Check 4: AWS Secrets Manager access
echo "4. Checking AWS Secrets Manager secret..."
SECRET_ID=${SLACK_TOKENS_SECRET_ID:-"maptimize/slack-tokens"}
AWS_REGION=${AWS_REGION:-"eu-west-1"}

echo "Secret ID: $SECRET_ID"
echo "Region: $AWS_REGION"

if aws secretsmanager get-secret-value --secret-id "$SECRET_ID" --region "$AWS_REGION" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Can access secret${NC}"
    
    # Check secret structure
    echo ""
    echo "5. Checking secret structure (keys only, not values)..."
    SECRET_JSON=$(aws secretsmanager get-secret-value --secret-id "$SECRET_ID" --region "$AWS_REGION" --query SecretString --output text)
    
    echo "Keys in secret:"
    echo "$SECRET_JSON" | jq -r 'keys[]' 2>/dev/null || echo "Failed to parse secret as JSON"
    
    echo ""
    echo "Required keys by config.py:"
    echo "  - bot_token"
    echo "  - app_token"
    echo "  - signing_secret"
    
    # Check if required keys exist
    echo ""
    echo "Validation:"
    for key in bot_token app_token signing_secret; do
        if echo "$SECRET_JSON" | jq -e ".$key" > /dev/null 2>&1; then
            VALUE=$(echo "$SECRET_JSON" | jq -r ".$key")
            if [ -n "$VALUE" ] && [ "$VALUE" != "null" ]; then
                echo -e "  ${GREEN}✓ $key exists and has a value${NC}"
            else
                echo -e "  ${RED}✗ $key exists but is empty/null${NC}"
            fi
        else
            echo -e "  ${RED}✗ $key is MISSING${NC}"
        fi
    done
else
    echo -e "${RED}✗ Cannot access secret${NC}"
    echo "Error details:"
    aws secretsmanager get-secret-value --secret-id "$SECRET_ID" --region "$AWS_REGION" 2>&1 || true
fi
echo ""

# Check 6: Network connectivity
echo "6. Checking network connectivity..."
echo "Testing connection to Slack API:"
if curl -s -o /dev/null -w "%{http_code}" https://slack.com/api/api.test | grep -q "200"; then
    echo -e "${GREEN}✓ Can reach Slack API${NC}"
else
    echo -e "${RED}✗ Cannot reach Slack API${NC}"
fi
echo ""

# Check 7: Docker image info
echo "7. Checking Docker image..."
docker images | grep maptimize || echo "No maptimize image found"
echo ""

# Check 8: Container environment variables
echo "8. Checking container environment variables..."
if docker ps | grep -q maptimize-bot; then
    echo "Environment variables in container:"
    docker exec maptimize-bot env | grep -E "(SLACK|AWS|LOG|PYTHON|ENVIRONMENT)" || echo "No relevant env vars found"
else
    echo -e "${RED}✗ Cannot check - container not running${NC}"
fi
echo ""

# Check 9: Test Python import inside container
echo "9. Testing Python import inside container..."
if docker ps | grep -q maptimize-bot; then
    docker exec maptimize-bot python -c "import maptimize; print('Import successful')" 2>&1 || echo "Import failed"
else
    echo -e "${RED}✗ Cannot test - container not running${NC}"
fi
echo ""

# Summary
echo "=========================================="
echo "DIAGNOSTIC SUMMARY"
echo "=========================================="
echo ""
echo "Common issues to check:"
echo "1. ${YELLOW}Secret structure mismatch${NC}"
echo "   - Secret must have keys: bot_token, app_token, signing_secret"
echo "   - NOT: SLACK_BOT_TOKEN or similar variations"
echo ""
echo "2. ${YELLOW}Signing secret missing${NC}"
echo "   - The signing_secret is required but may not be configured"
echo "   - Get it from: https://api.slack.com/apps -> Your App -> Basic Information"
echo ""
echo "3. ${YELLOW}Socket Mode not enabled${NC}"
echo "   - Check: https://api.slack.com/apps -> Your App -> Socket Mode"
echo "   - Must be toggled ON"
echo ""
echo "4. ${YELLOW}Wrong token scopes${NC}"
echo "   - App token needs: connections:write"
echo "   - Bot token needs: app_mentions:read, chat:write, commands"
echo ""
echo "Next steps:"
echo "1. Fix the secret structure in AWS Secrets Manager"
echo "2. Add signing_secret to your Slack app configuration"
echo "3. Restart the container: docker restart maptimize-bot"
echo "4. Monitor logs: docker logs -f maptimize-bot"
echo ""
