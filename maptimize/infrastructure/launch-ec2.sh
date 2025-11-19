#!/bin/bash
set -e

# EC2 Launch Script - Maptimize Production
# Mirrors asksplunk-prod configuration exactly
# Usage: ./launch-ec2.sh [instance-name]

INSTANCE_NAME="${1:-maptimize-prod}"
INSTANCE_TYPE="t3.xlarge"  # Match asksplunk-prod (4 vCPU, 16GB RAM)
AMI_ID="ami-0f9647c4c08a170a6"  # Same as asksplunk-prod
AWS_REGION="eu-west-1"
AWS_PROFILE="${AWS_PROFILE:-campaign_prod_v7}"
VPC_ID="vpc-0853eb6d"  # Same VPC as asksplunk-prod
SUBNET_ID="subnet-ce8e12b9"  # Same subnet as asksplunk-prod
SG_PRODUCTION="sg-7997a71c"  # Production SG from asksplunk
SG_PUBLIC_WEB="sg-7633b010"  # Public-web-access SG from asksplunk
IAM_INSTANCE_PROFILE="maptimize-ec2-instance-profile"
IAM_ROLE_NAME="maptimize-ec2-role"
KEY_PAIR_NAME="maptimize-ec2-keypair"

log_message() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

log_message "Starting EC2 instance launch script"
log_message "Creating instance: $INSTANCE_NAME (mirroring asksplunk-prod)"

# Validate AWS credentials
log_message "Validating AWS credentials with profile: $AWS_PROFILE"
if ! aws sts get-caller-identity --profile "$AWS_PROFILE" --region "$AWS_REGION" &>/dev/null; then
    log_message "ERROR: AWS credentials not configured or invalid"
    exit 1
fi

log_message "AWS credentials validated"

# Get AWS Account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --profile "$AWS_PROFILE" --query Account --output text)
log_message "AWS Account ID: $AWS_ACCOUNT_ID"

# Verify VPC and Subnet exist
log_message "Verifying VPC: $VPC_ID"
if ! aws ec2 describe-vpcs --profile "$AWS_PROFILE" --region "$AWS_REGION" --vpc-ids "$VPC_ID" &>/dev/null; then
    log_message "ERROR: VPC not found: $VPC_ID"
    exit 1
fi

log_message "Verifying Subnet: $SUBNET_ID"
if ! aws ec2 describe-subnets --profile "$AWS_PROFILE" --region "$AWS_REGION" --subnet-ids "$SUBNET_ID" &>/dev/null; then
    log_message "ERROR: Subnet not found: $SUBNET_ID"
    exit 1
fi

# Verify security groups exist
log_message "Verifying Security Groups (from asksplunk-prod)"
for sg in "$SG_PRODUCTION" "$SG_PUBLIC_WEB"; do
    if ! aws ec2 describe-security-groups --profile "$AWS_PROFILE" --region "$AWS_REGION" --group-ids "$sg" &>/dev/null; then
        log_message "ERROR: Security Group not found: $sg"
        exit 1
    fi
    sg_name=$(aws ec2 describe-security-groups --profile "$AWS_PROFILE" --region "$AWS_REGION" --group-ids "$sg" --query 'SecurityGroups[0].GroupName' --output text)
    log_message "  ✓ $sg ($sg_name)"
done

log_message "SSH Access: Restricted to 98 corporate CIDR ranges (mirrored from asksplunk-prod)"

# Check if IAM role exists, create if not
log_message "Checking IAM role: $IAM_ROLE_NAME"
if ! aws iam get-role --profile "$AWS_PROFILE" --role-name "$IAM_ROLE_NAME" &>/dev/null; then
    log_message "Creating IAM role: $IAM_ROLE_NAME"
    aws iam create-role \
        --profile "$AWS_PROFILE" \
        --role-name "$IAM_ROLE_NAME" \
        --assume-role-policy-document file://infrastructure/iam/trust-policy.json
    log_message "IAM role created: $IAM_ROLE_NAME"

    # Attach Secrets Manager policy
    log_message "Attaching Secrets Manager policy"
    aws iam put-role-policy \
        --profile "$AWS_PROFILE" \
        --role-name "$IAM_ROLE_NAME" \
        --policy-name maptimize-secrets-access \
        --policy-document file://infrastructure/iam/secrets-policy.json

    # Attach ECR policy
    log_message "Attaching ECR policy"
    aws iam put-role-policy \
        --profile "$AWS_PROFILE" \
        --role-name "$IAM_ROLE_NAME" \
        --policy-name maptimize-ecr-access \
        --policy-document file://infrastructure/iam/ecr-policy.json

    log_message "Policies attached"
else
    log_message "IAM role already exists: $IAM_ROLE_NAME"
fi

# Check if instance profile exists, create if not
log_message "Checking IAM instance profile: $IAM_INSTANCE_PROFILE"
if ! aws iam get-instance-profile --profile "$AWS_PROFILE" --instance-profile-name "$IAM_INSTANCE_PROFILE" &>/dev/null; then
    log_message "Creating IAM instance profile: $IAM_INSTANCE_PROFILE"
    aws iam create-instance-profile --profile "$AWS_PROFILE" --instance-profile-name "$IAM_INSTANCE_PROFILE"

    # Add role to instance profile
    log_message "Adding role to instance profile"
    aws iam add-role-to-instance-profile \
        --profile "$AWS_PROFILE" \
        --instance-profile-name "$IAM_INSTANCE_PROFILE" \
        --role-name "$IAM_ROLE_NAME"

    log_message "Instance profile created and role attached"
else
    log_message "IAM instance profile already exists: $IAM_INSTANCE_PROFILE"
fi

# Check if key pair exists, create if not
log_message "Checking EC2 key pair: $KEY_PAIR_NAME"
if ! aws ec2 describe-key-pairs --profile "$AWS_PROFILE" --key-names "$KEY_PAIR_NAME" --region "$AWS_REGION" &>/dev/null; then
    log_message "Creating EC2 key pair: $KEY_PAIR_NAME"
    aws ec2 create-key-pair \
        --profile "$AWS_PROFILE" \
        --key-name "$KEY_PAIR_NAME" \
        --region "$AWS_REGION" \
        --query 'KeyMaterial' \
        --output text > "${KEY_PAIR_NAME}.pem"

    chmod 600 "${KEY_PAIR_NAME}.pem"
    log_message "Key pair created and saved to ${KEY_PAIR_NAME}.pem"
else
    log_message "Key pair already exists: $KEY_PAIR_NAME"
fi

# Prepare user-data script
log_message "Preparing user-data script"
USER_DATA=$(cat infrastructure/user-data.sh | base64 | tr -d '\n')

# Launch EC2 instance with asksplunk-prod mirroring
log_message "Launching EC2 instance: $INSTANCE_NAME"
INSTANCE_ID=$(aws ec2 run-instances \
    --profile "$AWS_PROFILE" \
    --image-id "$AMI_ID" \
    --instance-type "$INSTANCE_TYPE" \
    --key-name "$KEY_PAIR_NAME" \
    --subnet-id "$SUBNET_ID" \
    --security-group-ids "$SG_PRODUCTION" "$SG_PUBLIC_WEB" \
    --iam-instance-profile "Name=$IAM_INSTANCE_PROFILE" \
    --user-data "file://infrastructure/user-data.sh" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME},{Key=Environment,Value=production},{Key=CostCenter,Value=MSIO-EMEA},{Key=ManagedBy,Value=MSIO-EMEA},{Key=Owner,Value=harrison},{Key=Project,Value=maptimize-slack-bot}]" \
    --region "$AWS_REGION" \
    --query 'Instances[0].InstanceId' \
    --output text)

log_message "EC2 instance launched: $INSTANCE_ID"

# Wait for instance to be running
log_message "Waiting for instance to reach running state"
aws ec2 wait instance-running --profile "$AWS_PROFILE" --instance-ids "$INSTANCE_ID" --region "$AWS_REGION"
log_message "Instance is now running"

# Get instance details
INSTANCE_INFO=$(aws ec2 describe-instances \
    --profile "$AWS_PROFILE" \
    --instance-ids "$INSTANCE_ID" \
    --region "$AWS_REGION" \
    --query 'Reservations[0].Instances[0]')

PUBLIC_IP=$(echo "$INSTANCE_INFO" | jq -r '.PublicIpAddress // "pending"')
PRIVATE_IP=$(echo "$INSTANCE_INFO" | jq -r '.PrivateIpAddress')
AVAILABILITY_ZONE=$(echo "$INSTANCE_INFO" | jq -r '.Placement.AvailabilityZone')

log_message "Instance Details:"
log_message "  Instance ID: $INSTANCE_ID"
log_message "  Name: $INSTANCE_NAME"
log_message "  Instance Type: $INSTANCE_TYPE"
log_message "  Availability Zone: $AVAILABILITY_ZONE"
log_message "  Private IP: $PRIVATE_IP"
log_message "  Public IP: $PUBLIC_IP"
log_message "  VPC: $VPC_ID"
log_message "  Subnet: $SUBNET_ID"
log_message "  Security Groups: $SG_PRODUCTION (production), $SG_PUBLIC_WEB (public-web-access)"
log_message "  IAM Instance Profile: $IAM_INSTANCE_PROFILE"
log_message "  Region: $AWS_REGION"
log_message "  Mirrors: asksplunk-prod configuration"

# Save instance configuration
CONFIG_FILE="instance-config.json"
cat > "$CONFIG_FILE" <<EOF
{
  "instance_id": "$INSTANCE_ID",
  "instance_name": "$INSTANCE_NAME",
  "instance_type": "$INSTANCE_TYPE",
  "region": "$AWS_REGION",
  "availability_zone": "$AVAILABILITY_ZONE",
  "vpc_id": "$VPC_ID",
  "subnet_id": "$SUBNET_ID",
  "private_ip": "$PRIVATE_IP",
  "public_ip": "$PUBLIC_IP",
  "security_groups": ["$SG_PRODUCTION", "$SG_PUBLIC_WEB"],
  "security_group_names": ["production", "public-web-access"],
  "iam_instance_profile": "$IAM_INSTANCE_PROFILE",
  "iam_role_name": "$IAM_ROLE_NAME",
  "key_pair_name": "$KEY_PAIR_NAME",
  "ssh_access": "Restricted to 98 corporate CIDR ranges (mirrored from asksplunk-prod)",
  "mirrors": "asksplunk-prod",
  "launch_time": "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
}
EOF

log_message "Instance configuration saved to $CONFIG_FILE"

log_message ""
log_message "═══════════════════════════════════════════════════════════"
log_message "✓ EC2 instance launch complete! (Mirroring asksplunk-prod)"
log_message "═══════════════════════════════════════════════════════════"
log_message ""
log_message "Next steps:"
log_message "1. Wait 2-3 minutes for user-data script to complete"
log_message "2. SSH into instance: ssh -i ${KEY_PAIR_NAME}.pem ec2-user@${PUBLIC_IP}"
log_message "3. Follow post-launch setup instructions in infrastructure/ec2-setup.md"
log_message "4. Deploy Docker container: docker-compose -f infrastructure/docker-compose.production.yml up -d"
log_message ""
