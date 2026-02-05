#!/bin/bash
set -euo pipefail

TABLE_NAME="splunk-bot-sessions"
REGION="eu-west-1"
GSI_NAME="usage-by-timestamp"

# Check if GSI already exists
EXISTING=$(aws dynamodb describe-table \
  --table-name "$TABLE_NAME" \
  --region "$REGION" \
  --query "Table.GlobalSecondaryIndexes[?IndexName=='$GSI_NAME'].IndexName" \
  --output text 2>/dev/null || echo "")

if [ "$EXISTING" = "$GSI_NAME" ]; then
  echo "GSI $GSI_NAME already exists"
  exit 0
fi

echo "Creating GSI $GSI_NAME..."
aws dynamodb update-table \
  --table-name "$TABLE_NAME" \
  --region "$REGION" \
  --attribute-definitions \
    AttributeName=entity_type,AttributeType=S \
    AttributeName=timestamp,AttributeType=S \
  --global-secondary-index-updates \
    "[{\"Create\":{\"IndexName\":\"$GSI_NAME\",\"KeySchema\":[{\"AttributeName\":\"entity_type\",\"KeyType\":\"HASH\"},{\"AttributeName\":\"timestamp\",\"KeyType\":\"RANGE\"}],\"Projection\":{\"ProjectionType\":\"KEYS_ONLY\"}}}]"

echo "Waiting for GSI to become ACTIVE..."
aws dynamodb wait table-exists --table-name "$TABLE_NAME" --region "$REGION"
echo "GSI $GSI_NAME created successfully"
