#!/bin/bash

################################################################################
# Maptimize Production Setup Script
# Mirrors asksplunk-prod configuration exactly
# Author: Harrison
# Date: November 19, 2025
################################################################################

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
AWS_PROFILE="${AWS_PROFILE:-campaign_prod_v7}"
AWS_REGION="${AWS_REGION:-eu-west-1}"
INSTANCE_NAME="maptimize-prod"
INSTANCE_TYPE="t3.xlarge"  # Match asksplunk-prod
AMI_ID="ami-0f9647c4c08a170a6"  # Same as asksplunk-prod
VPC_ID="vpc-0853eb6d"  # Same VPC as asksplunk
SUBNET_ID="subnet-ce8e12b9"  # Same subnet as asksplunk
SECURITY_GROUPS="sg-7997a71c sg-7633b010"  # Same SGs as asksplunk

# Tags (mirrored from asksplunk-prod) - simple key=value format
TAG_NAME="maptimize-prod"
TAG_ENVIRONMENT="production"
TAG_COST_CENTER="MSIO-EMEA"
TAG_MANAGED_BY="MSIO-EMEA"
TAG_OWNER="harrison"
TAG_PROJECT="maptimize-slack-bot"

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Maptimize Production Setup - Mirror asksplunk-prod${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Verify AWS credentials
echo -e "${YELLOW}[1/5] Verifying AWS credentials...${NC}"
if ! aws sts get-caller-identity --profile "$AWS_PROFILE" &>/dev/null; then
    echo -e "${RED}✗ Failed to authenticate with AWS profile: $AWS_PROFILE${NC}"
    exit 1
fi
ACCOUNT_ID=$(aws sts get-caller-identity --profile "$AWS_PROFILE" --query Account --output text)
echo -e "${GREEN}✓ Authenticated as account: $ACCOUNT_ID${NC}"
echo ""

# Verify VPC and Subnet exist
echo -e "${YELLOW}[2/5] Verifying VPC and Subnet...${NC}"
VPC_CHECK=$(aws ec2 describe-vpcs --profile "$AWS_PROFILE" --region "$AWS_REGION" \
    --vpc-ids "$VPC_ID" --query 'Vpcs[0].VpcId' --output text 2>/dev/null || echo "NOTFOUND")

if [ "$VPC_CHECK" = "NOTFOUND" ]; then
    echo -e "${RED}✗ VPC not found: $VPC_ID${NC}"
    exit 1
fi
echo -e "${GREEN}✓ VPC verified: $VPC_ID${NC}"

SUBNET_CHECK=$(aws ec2 describe-subnets --profile "$AWS_PROFILE" --region "$AWS_REGION" \
    --subnet-ids "$SUBNET_ID" --query 'Subnets[0].SubnetId' --output text 2>/dev/null || echo "NOTFOUND")

if [ "$SUBNET_CHECK" = "NOTFOUND" ]; then
    echo -e "${RED}✗ Subnet not found: $SUBNET_ID${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Subnet verified: $SUBNET_ID${NC}"
echo ""

# Verify Security Groups exist
echo -e "${YELLOW}[3/5] Verifying Security Groups...${NC}"
for sg in $SECURITY_GROUPS; do
    sg_check=$(aws ec2 describe-security-groups --profile "$AWS_PROFILE" --region "$AWS_REGION" \
        --group-ids "$sg" --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "NOTFOUND")

    if [ "$sg_check" = "NOTFOUND" ]; then
        echo -e "${RED}✗ Security Group not found: $sg${NC}"
        exit 1
    fi

    sg_name=$(aws ec2 describe-security-groups --profile "$AWS_PROFILE" --region "$AWS_REGION" \
        --group-ids "$sg" --query 'SecurityGroups[0].GroupName' --output text)
    echo -e "${GREEN}✓ Security Group verified: $sg ($sg_name)${NC}"
done
echo ""

# Check if instance already exists
echo -e "${YELLOW}[4/5] Checking for existing instance...${NC}"
EXISTING=$(aws ec2 describe-instances --profile "$AWS_PROFILE" --region "$AWS_REGION" \
    --filters "Name=tag:Name,Values=$INSTANCE_NAME" "Name=instance-state-name,Values=running,stopped" \
    --query 'Reservations[0].Instances[0].InstanceId' --output text 2>/dev/null || echo "NONE")

if [ "$EXISTING" != "NONE" ] && [ "$EXISTING" != "None" ] && [ -n "$EXISTING" ]; then
    echo -e "${YELLOW}⚠ Instance already exists: $EXISTING${NC}"
    echo -e "${YELLOW}Would you like to terminate it and create a new one? (yes/no)${NC}"
    read -r response
    if [ "$response" = "yes" ]; then
        echo -e "${BLUE}Terminating existing instance: $EXISTING${NC}"
        aws ec2 terminate-instances --profile "$AWS_PROFILE" --region "$AWS_REGION" \
            --instance-ids "$EXISTING"

        echo -e "${BLUE}Waiting for termination...${NC}"
        aws ec2 wait instance-terminated --profile "$AWS_PROFILE" --region "$AWS_REGION" \
            --instance-ids "$EXISTING"
        echo -e "${GREEN}✓ Instance terminated${NC}"
    else
        echo -e "${YELLOW}Skipping instance creation${NC}"
        exit 0
    fi
fi
echo -e "${GREEN}✓ Ready to create new instance${NC}"
echo ""

# Create instance with exact asksplunk-prod configuration
echo -e "${YELLOW}[5/5] Creating maptimize-prod instance...${NC}"
echo -e "${BLUE}Configuration:${NC}"
echo "  Instance Type: $INSTANCE_TYPE"
echo "  AMI: $AMI_ID"
echo "  VPC: $VPC_ID"
echo "  Subnet: $SUBNET_ID"
echo "  Security Groups: ${SECURITY_GROUPS[*]}"
echo ""

# Build tag specifications
TAG_SPECS="ResourceType=instance,Tags=[{Key=Name,Value=$TAG_NAME},{Key=Environment,Value=$TAG_ENVIRONMENT},{Key=CostCenter,Value=$TAG_COST_CENTER},{Key=ManagedBy,Value=$TAG_MANAGED_BY},{Key=Owner,Value=$TAG_OWNER},{Key=Project,Value=$TAG_PROJECT}]"

# Launch instance
USER_DATA_FILE="$(dirname "$0")/../maptimize/infrastructure/user-data.sh"
INSTANCE_ID=$(aws ec2 run-instances \
    --profile "$AWS_PROFILE" \
    --region "$AWS_REGION" \
    --image-id "$AMI_ID" \
    --instance-type "$INSTANCE_TYPE" \
    --subnet-id "$SUBNET_ID" \
    --security-group-ids $SECURITY_GROUPS \
    --tag-specifications "$TAG_SPECS" \
    --user-data "file://$USER_DATA_FILE" \
    --query 'Instances[0].InstanceId' \
    --output text)

if [ -z "$INSTANCE_ID" ] || [ "$INSTANCE_ID" = "None" ]; then
    echo -e "${RED}✗ Failed to create instance${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Instance created: $INSTANCE_ID${NC}"
echo ""

# Wait for instance to be running
echo -e "${BLUE}Waiting for instance to reach running state...${NC}"
aws ec2 wait instance-running --profile "$AWS_PROFILE" --region "$AWS_REGION" \
    --instance-ids "$INSTANCE_ID"

# Get instance details
echo -e "${BLUE}Retrieving instance details...${NC}"
INSTANCE_INFO=$(aws ec2 describe-instances --profile "$AWS_PROFILE" --region "$AWS_REGION" \
    --instance-ids "$INSTANCE_ID" --query 'Reservations[0].Instances[0]')

PRIVATE_IP=$(echo "$INSTANCE_INFO" | jq -r '.PrivateIpAddress')
PUBLIC_IP=$(echo "$INSTANCE_INFO" | jq -r '.PublicIpAddress // "N/A"')
AVAILABILITY_ZONE=$(echo "$INSTANCE_INFO" | jq -r '.Placement.AvailabilityZone')

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Maptimize Production Setup Complete${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}Instance Details:${NC}"
echo "  Instance ID:        $INSTANCE_ID"
echo "  Instance Name:      $INSTANCE_NAME"
echo "  Instance Type:      $INSTANCE_TYPE"
echo "  Private IP:         $PRIVATE_IP"
echo "  Public IP:          $PUBLIC_IP"
echo "  Availability Zone:  $AVAILABILITY_ZONE"
echo "  VPC:                $VPC_ID"
echo "  Subnet:             $SUBNET_ID"
echo "  Security Groups:    $SECURITY_GROUPS"
echo ""
echo -e "${BLUE}Tags Applied:${NC}"
echo "  Name:               $TAG_NAME"
echo "  Environment:        $TAG_ENVIRONMENT"
echo "  CostCenter:         $TAG_COST_CENTER"
echo "  ManagedBy:          $TAG_MANAGED_BY"
echo "  Owner:              $TAG_OWNER"
echo "  Project:            $TAG_PROJECT"
echo ""

# SSH Access
echo -e "${BLUE}SSH Access (Restricted to Corporate Networks):${NC}"
echo "  SSH Port: 22"
echo "  Allowed CIDR ranges: 98 distinct IP addresses/ranges from asksplunk-prod"
echo "  Includes:"
echo "    - Adobe Corporate Offices (global)"
echo "    - Adobe Datacenters"
echo "    - Campaign Infrastructure"
echo "    - Bastion Hosts"
echo "    - Monitoring/Logging Services"
echo ""

# Save configuration
CONFIG_FILE="maptimize-prod-config.json"
cat > "$CONFIG_FILE" <<EOF
{
  "instance_id": "$INSTANCE_ID",
  "instance_name": "$INSTANCE_NAME",
  "instance_type": "$INSTANCE_TYPE",
  "ami_id": "$AMI_ID",
  "vpc_id": "$VPC_ID",
  "subnet_id": "$SUBNET_ID",
  "availability_zone": "$AVAILABILITY_ZONE",
  "private_ip": "$PRIVATE_IP",
  "public_ip": "$PUBLIC_IP",
  "security_groups": [
    "sg-7997a71c",
    "sg-7633b010"
  ],
  "tags": {
    "Name": "$TAG_NAME",
    "Environment": "$TAG_ENVIRONMENT",
    "CostCenter": "$TAG_COST_CENTER",
    "ManagedBy": "$TAG_MANAGED_BY",
    "Owner": "$TAG_OWNER",
    "Project": "$TAG_PROJECT"
  },
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "mirrors": "asksplunk-prod"
}
EOF

echo -e "${GREEN}✓ Configuration saved to: $CONFIG_FILE${NC}"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "  1. Wait 30-60 seconds for user-data script to complete"
echo "  2. Verify instance is healthy: aws ec2 describe-instances --instance-ids $INSTANCE_ID"
echo "  3. SSH to instance (if authorized):"
echo "     ssh -i <your-key.pem> ec2-user@$PRIVATE_IP"
echo "  4. Deploy Docker container:"
echo "     docker-compose -f infrastructure/docker-compose.production.yml up -d"
echo "  5. Verify health checks:"
echo "     docker inspect $INSTANCE_NAME --format='{{.State.Health.Status}}'"
echo ""
echo -e "${GREEN}Setup complete! Maptimize-prod is ready for deployment.${NC}"
