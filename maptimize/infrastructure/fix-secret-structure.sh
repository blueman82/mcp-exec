#!/bin/bash
# Fix AWS Secrets Manager secret structure for Maptimize

set -e

echo "=========================================="
echo "Fix Maptimize Secret Structure"
echo "=========================================="
echo ""

SECRET_ID=${SLACK_TOKENS_SECRET_ID:-"maptimize/slack-tokens"}
AWS_REGION=${AWS_REGION:-"eu-west-1"}

echo "This script will help you update the secret structure."
echo "Secret ID: $SECRET_ID"
echo "Region: $AWS_REGION"
echo ""

# Check current secret
echo "Current secret structure:"
CURRENT_SECRET=$(aws secretsmanager get-secret-value \
    --secret-id "$SECRET_ID" \
    --region "$AWS_REGION" \
    --query SecretString \
    --output text 2>/dev/null) || {
    echo "ERROR: Cannot access secret. Make sure:"
    echo "  1. You have AWS credentials configured"
    echo "  2. The secret exists: $SECRET_ID"
    echo "  3. You have permission to read secrets"
    exit 1
}

echo "$CURRENT_SECRET" | jq . || {
    echo "ERROR: Secret is not valid JSON"
    exit 1
}

echo ""
echo "Required structure:"
cat <<'EOF'
{
  "bot_token": "xoxb-...",
  "app_token": "xapp-...",
  "signing_secret": "..."
}
EOF

echo ""
echo "=========================================="
echo "Getting values for new secret..."
echo "=========================================="
echo ""

# Try to extract values from current secret
BOT_TOKEN=$(echo "$CURRENT_SECRET" | jq -r '.bot_token // .SLACK_BOT_TOKEN // empty')
APP_TOKEN=$(echo "$CURRENT_SECRET" | jq -r '.app_token // .SLACK_APP_TOKEN // empty')
SIGNING_SECRET=$(echo "$CURRENT_SECRET" | jq -r '.signing_secret // .SLACK_SIGNING_SECRET // empty')

# Prompt for missing values
if [ -z "$BOT_TOKEN" ]; then
    echo "Bot Token (xoxb-...) not found in current secret."
    read -p "Enter Bot Token (or press Enter to skip): " BOT_TOKEN
fi

if [ -z "$APP_TOKEN" ]; then
    echo "App Token (xapp-...) not found in current secret."
    read -p "Enter App Token (or press Enter to skip): " APP_TOKEN
fi

if [ -z "$SIGNING_SECRET" ]; then
    echo "Signing Secret not found in current secret."
    echo "Get it from: https://api.slack.com/apps -> Your App -> Basic Information -> Signing Secret"
    read -p "Enter Signing Secret: " SIGNING_SECRET
fi

# Validate we have all required values
if [ -z "$BOT_TOKEN" ] || [ -z "$APP_TOKEN" ] || [ -z "$SIGNING_SECRET" ]; then
    echo ""
    echo "ERROR: Missing required values:"
    [ -z "$BOT_TOKEN" ] && echo "  - bot_token"
    [ -z "$APP_TOKEN" ] && echo "  - app_token"
    [ -z "$SIGNING_SECRET" ] && echo "  - signing_secret"
    echo ""
    echo "Get these values from: https://api.slack.com/apps"
    exit 1
fi

# Create new secret JSON
NEW_SECRET=$(jq -n \
    --arg bot "$BOT_TOKEN" \
    --arg app "$APP_TOKEN" \
    --arg signing "$SIGNING_SECRET" \
    '{bot_token: $bot, app_token: $app, signing_secret: $signing}')

echo ""
echo "New secret structure (values hidden):"
echo "$NEW_SECRET" | jq 'with_entries(.value = "***")'

echo ""
read -p "Update secret with this structure? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

# Update secret
echo ""
echo "Updating secret..."
aws secretsmanager update-secret \
    --secret-id "$SECRET_ID" \
    --region "$AWS_REGION" \
    --secret-string "$NEW_SECRET"

echo ""
echo "✓ Secret updated successfully!"
echo ""
echo "Next steps:"
echo "1. Restart the Docker container:"
echo "   docker restart maptimize-bot"
echo ""
echo "2. Monitor logs:"
echo "   docker logs -f maptimize-bot"
echo ""
echo "3. Test in Slack:"
echo "   - Try: @maptimize help"
echo "   - Try: /maptimize"
echo ""
