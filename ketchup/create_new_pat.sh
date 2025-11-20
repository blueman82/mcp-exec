#!/bin/bash
# Script to create a new JIRA PAT and save details to file

# Get credentials from AWS Secrets Manager
SECRET_JSON=$(aws secretsmanager get-secret-value \
  --secret-id Ketchup_Token_Secrets \
  --region eu-west-1 \
  --profile campaign_prod_v7 \
  --query SecretString \
  --output text)

# Extract individual credentials
IMS_TOKEN=$(echo "$SECRET_JSON" | jq -r '.ims_access_token')
API_KEY=$(echo "$SECRET_JSON" | jq -r '.ipaas_api_key')
CURRENT_PAT=$(echo "$SECRET_JSON" | jq -r '.ketchup_jira_pat')

# Create new PAT with 90-day expiry
echo "Creating new PAT..."
RESPONSE=$(curl -s -X POST 'https://ipaasapi.adobe-services.com/jira/rest/pat/latest/tokens' \
  -H "Authorization: ${IMS_TOKEN}" \
  -H "x-authorization: Bearer ${CURRENT_PAT}" \
  -H "Api_key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ketchup-production-pat-rotation-ready",
    "expirationDuration": 90
  }')

# Parse response
PAT_ID=$(echo "$RESPONSE" | jq -r '.id')
PAT_TOKEN=$(echo "$RESPONSE" | jq -r '.rawToken')
PAT_EXPIRY=$(echo "$RESPONSE" | jq -r '.expiringAt')

# Check if successful
if [ "$PAT_ID" = "null" ] || [ -z "$PAT_ID" ]; then
  echo "ERROR: Failed to create PAT"
  echo "Response: $RESPONSE"
  exit 1
fi

# Save to file
OUTPUT_FILE="/Users/harrison/Documents/Github/camp-ops-emea/ketchup-jira-pat-migration/NEW_PAT_CREDENTIALS.txt"

cat > "$OUTPUT_FILE" << EOF
# New JIRA PAT for Production - Created $(date)
# ================================================================

PAT Token:
${PAT_TOKEN}

PAT ID:
${PAT_ID}

PAT Expiry (ISO 8601):
${PAT_EXPIRY}

# ================================================================
# AWS Secrets Manager Update Instructions
# ================================================================

To update AWS Secrets Manager, run:

aws secretsmanager get-secret-value \\
  --secret-id Ketchup_Token_Secrets \\
  --region eu-west-1 \\
  --profile campaign_prod_v7 \\
  --query SecretString \\
  --output text | jq '. + {
    "ketchup_jira_pat": "${PAT_TOKEN}",
    "ketchup_jira_pat_id": "${PAT_ID}",
    "ketchup_jira_pat_expiry": "${PAT_EXPIRY}"
  }' > /tmp/updated_secrets.json

aws secretsmanager update-secret \\
  --secret-id Ketchup_Token_Secrets \\
  --region eu-west-1 \\
  --profile campaign_prod_v7 \\
  --secret-string file:///tmp/updated_secrets.json

# ================================================================
# IMPORTANT: Old PAT Cleanup
# ================================================================

After verifying the new PAT works, you may want to manually revoke
the old manually-created PAT through JIRA if you know its ID.

Current rotation system will handle this automatically after you
update Secrets Manager and enable JIRA_USE_PAT_AUTH=true.

EOF

echo "✅ SUCCESS: New PAT created and saved to:"
echo "$OUTPUT_FILE"
echo ""
echo "PAT ID: $PAT_ID"
echo "Expiry: $PAT_EXPIRY"
echo ""
echo "Next steps:"
echo "1. Review the credentials file"
echo "2. Run the AWS CLI commands in the file to update Secrets Manager"
echo "3. Enable JIRA_USE_PAT_AUTH=true in docker-compose.yml"
