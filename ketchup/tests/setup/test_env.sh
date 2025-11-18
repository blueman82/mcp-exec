#!/bin/bash
# AWS Profile Configuration for Testing
export AWS_PROFILE=campaign_prod_v7
export AWS_REGION=eu-west-1
export AWS_DEFAULT_REGION=eu-west-1
export DYNAMODB_TABLE_NAME=ketchup_channel_information
export AWS_SECRET_NAME=Ketchup_Token_Secrets
export PYTHONPATH=/Users/harrison/Documents/Github/camp-ops-tools-emea/ketchup:$PYTHONPATH

echo "AWS testing environment configured:"
echo "- AWS_PROFILE: $AWS_PROFILE"
echo "- AWS_REGION: $AWS_REGION"
echo "- DYNAMODB_TABLE_NAME: $DYNAMODB_TABLE_NAME"
echo "- AWS_SECRET_NAME: $AWS_SECRET_NAME"
echo "- PYTHONPATH: $PYTHONPATH"