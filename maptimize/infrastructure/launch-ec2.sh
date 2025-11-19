#!/bin/bash
set -e

# EC2 Launch Script
# Automates EC2 instance creation with IAM role, security group, and user-data
# Usage: ./launch-ec2.sh [instance-name]

INSTANCE_NAME="${1:-maptimize-bot}"
INSTANCE_TYPE="t3.micro"
DEBIAN_12_AMI="ami-0c55b159cbfafe1f0"
AWS_REGION="eu-west-1"
SECURITY_GROUP_NAME="maptimize-ec2-sg"
IAM_INSTANCE_PROFILE="maptimize-ec2-instance-profile"
IAM_ROLE_NAME="maptimize-ec2-role"
KEY_PAIR_NAME="maptimize-ec2-keypair"

log_message() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

log_message "Starting EC2 instance launch script"

# Validate AWS credentials
log_message "Validating AWS credentials"
if ! aws sts get-caller-identity --region "$AWS_REGION" &>/dev/null; then
    log_message "ERROR: AWS credentials not configured or invalid"
    exit 1
fi

log_message "AWS credentials validated"

# Get AWS Account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
log_message "AWS Account ID: $AWS_ACCOUNT_ID"

# Check if security group exists, create if not
log_message "Checking security group: $SECURITY_GROUP_NAME"
SG_ID=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=$SECURITY_GROUP_NAME" \
    --region "$AWS_REGION" \
    --query 'SecurityGroups[0].GroupId' \
    --output text 2>/dev/null || echo "")

if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
    log_message "Creating security group: $SECURITY_GROUP_NAME"
    SG_ID=$(aws ec2 create-security-group \
        --group-name "$SECURITY_GROUP_NAME" \
        --description "Security group for Maptimize EC2 instance" \
        --region "$AWS_REGION" \
        --query 'GroupId' \
        --output text)
    log_message "Security group created: $SG_ID"

    # Add SSH ingress rule (restrict to your IP for security)
    log_message "Configuring SSH access in security group"
    aws ec2 authorize-security-group-ingress \
        --group-id "$SG_ID" \
        --protocol tcp \
        --port 22 \
        --cidr 0.0.0.0/0 \
        --region "$AWS_REGION"

    log_message "SSH access configured (0.0.0.0/0 - update for production)"
else
    log_message "Security group already exists: $SG_ID"
fi

# Check if IAM role exists, create if not
log_message "Checking IAM role: $IAM_ROLE_NAME"
if ! aws iam get-role --role-name "$IAM_ROLE_NAME" &>/dev/null; then
    log_message "Creating IAM role: $IAM_ROLE_NAME"
    aws iam create-role \
        --role-name "$IAM_ROLE_NAME" \
        --assume-role-policy-document file://infrastructure/iam/trust-policy.json
    log_message "IAM role created: $IAM_ROLE_NAME"

    # Attach Secrets Manager policy
    log_message "Attaching Secrets Manager policy"
    aws iam put-role-policy \
        --role-name "$IAM_ROLE_NAME" \
        --policy-name maptimize-secrets-access \
        --policy-document file://infrastructure/iam/secrets-policy.json

    # Attach ECR policy
    log_message "Attaching ECR policy"
    aws iam put-role-policy \
        --role-name "$IAM_ROLE_NAME" \
        --policy-name maptimize-ecr-access \
        --policy-document file://infrastructure/iam/ecr-policy.json

    log_message "Policies attached"
else
    log_message "IAM role already exists: $IAM_ROLE_NAME"
fi

# Check if instance profile exists, create if not
log_message "Checking IAM instance profile: $IAM_INSTANCE_PROFILE"
if ! aws iam get-instance-profile --instance-profile-name "$IAM_INSTANCE_PROFILE" &>/dev/null; then
    log_message "Creating IAM instance profile: $IAM_INSTANCE_PROFILE"
    aws iam create-instance-profile --instance-profile-name "$IAM_INSTANCE_PROFILE"

    # Add role to instance profile
    log_message "Adding role to instance profile"
    aws iam add-role-to-instance-profile \
        --instance-profile-name "$IAM_INSTANCE_PROFILE" \
        --role-name "$IAM_ROLE_NAME"

    log_message "Instance profile created and role attached"
else
    log_message "IAM instance profile already exists: $IAM_INSTANCE_PROFILE"
fi

# Check if key pair exists, create if not
log_message "Checking EC2 key pair: $KEY_PAIR_NAME"
if ! aws ec2 describe-key-pairs --key-names "$KEY_PAIR_NAME" --region "$AWS_REGION" &>/dev/null; then
    log_message "Creating EC2 key pair: $KEY_PAIR_NAME"
    aws ec2 create-key-pair \
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

# Launch EC2 instance
log_message "Launching EC2 instance: $INSTANCE_NAME"
INSTANCE_ID=$(aws ec2 run-instances \
    --image-id "$DEBIAN_12_AMI" \
    --instance-type "$INSTANCE_TYPE" \
    --key-name "$KEY_PAIR_NAME" \
    --security-group-ids "$SG_ID" \
    --iam-instance-profile "Name=$IAM_INSTANCE_PROFILE" \
    --user-data "file://infrastructure/user-data.sh" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
    --region "$AWS_REGION" \
    --query 'Instances[0].InstanceId' \
    --output text)

log_message "EC2 instance launched: $INSTANCE_ID"

# Wait for instance to be running
log_message "Waiting for instance to reach running state"
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region "$AWS_REGION"
log_message "Instance is now running"

# Get instance details
INSTANCE_INFO=$(aws ec2 describe-instances \
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
log_message "  Security Group: $SG_ID ($SECURITY_GROUP_NAME)"
log_message "  IAM Instance Profile: $IAM_INSTANCE_PROFILE"
log_message "  Region: $AWS_REGION"

# Save instance configuration
CONFIG_FILE="instance-config.json"
cat > "$CONFIG_FILE" <<EOF
{
  "instance_id": "$INSTANCE_ID",
  "instance_name": "$INSTANCE_NAME",
  "instance_type": "$INSTANCE_TYPE",
  "region": "$AWS_REGION",
  "availability_zone": "$AVAILABILITY_ZONE",
  "private_ip": "$PRIVATE_IP",
  "public_ip": "$PUBLIC_IP",
  "security_group_id": "$SG_ID",
  "security_group_name": "$SECURITY_GROUP_NAME",
  "iam_instance_profile": "$IAM_INSTANCE_PROFILE",
  "iam_role_name": "$IAM_ROLE_NAME",
  "key_pair_name": "$KEY_PAIR_NAME",
  "launch_time": "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
}
EOF

log_message "Instance configuration saved to $CONFIG_FILE"

log_message ""
log_message "EC2 instance launch complete!"
log_message "Next steps:"
log_message "1. Wait 2-3 minutes for user-data script to complete"
log_message "2. SSH into instance: ssh -i ${KEY_PAIR_NAME}.pem ec2-user@${PUBLIC_IP}"
log_message "3. Follow post-launch setup instructions in infrastructure/ec2-setup.md"
log_message ""
