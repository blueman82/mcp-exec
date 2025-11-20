# Maptimize Deployment Guide

Complete step-by-step instructions for deploying Maptimize to production on AWS.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [AWS Setup](#aws-setup)
3. [Slack Configuration](#slack-configuration)
4. [Local Testing](#local-testing)
5. [Docker Image Preparation](#docker-image-preparation)
6. [ECR Registry Setup](#ecr-registry-setup)
7. [EC2 Deployment](#ec2-deployment)
8. [Production Configuration](#production-configuration)
9. [Monitoring and Health Checks](#monitoring-and-health-checks)
10. [Updates and Rollback](#updates-and-rollback)
11. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Software

- **Git**: For cloning and version control
- **Docker**: Version 20.10+ for building images
- **Docker Compose**: Version 1.29+ for local testing
- **AWS CLI**: Version 2.0+ configured with appropriate credentials
- **Python**: 3.11+ for running tests (optional, for local development)

### Required AWS Resources

- AWS account with appropriate permissions
- IAM user with EC2, ECR, Secrets Manager, and CloudWatch access
- EC2 key pair for SSH access
- VPC and security groups configured

### Required Slack Configuration

- Slack workspace admin access
- Slack app created with Socket Mode enabled
- Bot token and app token generated

## AWS Setup

### Step 1: Create IAM User

Create a dedicated IAM user for deployments:

```bash
# Using AWS CLI
aws iam create-user --user-name maptimize-deployer

# Attach necessary policies
aws iam attach-user-policy \
  --user-name maptimize-deployer \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2FullAccess

aws iam attach-user-policy \
  --user-name maptimize-deployer \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser

aws iam attach-user-policy \
  --user-name maptimize-deployer \
  --policy-arn arn:aws:iam::aws:policy/SecretsManagerReadWrite
```

### Step 2: Create EC2 Key Pair

Generate a key pair for SSH access:

```bash
aws ec2 create-key-pair \
  --key-name maptimize-key \
  --query 'KeyMaterial' \
  --output text > maptimize-key.pem

# Secure the key
chmod 400 maptimize-key.pem
```

Store the key safely and never commit it to version control.

### Step 3: Create Security Group

Create a security group for the bot instance:

```bash
# Get your VPC ID
VPC_ID=$(aws ec2 describe-vpcs --query 'Vpcs[0].VpcId' --output text)

# Create security group
SG_ID=$(aws ec2 create-security-group \
  --group-name maptimize-bot-sg \
  --description "Security group for Maptimize bot" \
  --vpc-id $VPC_ID \
  --query 'GroupId' \
  --output text)

# Allow SSH inbound
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 22 \
  --cidr 0.0.0.0/0

# Allow outbound (already enabled by default)
echo "Security group created: $SG_ID"
```

### Step 4: Store Slack Tokens in Secrets Manager

Create a secret for Slack tokens:

```bash
# Create secret
aws secretsmanager create-secret \
  --name maptimize/slack-tokens \
  --description "Slack tokens for Maptimize bot" \
  --secret-string '{
    "app_token": "xapp-YOUR_APP_TOKEN_HERE",
    "bot_token": "xoxb-YOUR_BOT_TOKEN_HERE"
  }' \
  --region eu-west-1

# Verify secret was created
aws secretsmanager get-secret-value \
  --secret-id maptimize/slack-tokens \
  --region eu-west-1
```

## Slack Configuration

See [SLACK_APP_SETUP.md](SLACK_APP_SETUP.md) for detailed Slack app setup instructions.

Key requirements:
- Enable Socket Mode
- Grant required bot token scopes
- Configure OAuth settings
- Set up event subscriptions

## Local Testing

### Step 1: Clone Repository

```bash
git clone https://github.com/camp-ops-emea/maptimize.git
cd maptimize
```

### Step 2: Set Up Environment

```bash
# Create .env file
cp .env.example .env

# Edit .env with your Slack tokens (for local testing)
echo "app_token=xapp-YOUR_TOKEN" >> .env
```

### Step 3: Run with Docker Compose

```bash
# Build and start the bot
docker-compose up --build

# In another terminal, run tests
docker-compose exec maptimize pytest

# View logs
docker-compose logs -f maptimize
```

### Step 4: Test Basic Functionality

```bash
# Run integration tests
docker-compose exec maptimize pytest -m integration

# Check health
docker-compose exec maptimize python -c "import maptimize; print('healthy')"
```

### Step 5: Cleanup

```bash
docker-compose down
```

## Docker Image Preparation

### Step 1: Build Docker Image

```bash
# Navigate to project root
cd /path/to/maptimize

# Build the image
docker build \
  --tag maptimize:0.1.0 \
  --file infrastructure/Dockerfile \
  .
```

### Step 2: Verify Image

```bash
# Test the image locally
docker run --rm \
  -e SLACK_TOKENS_SECRET_ID=maptimize/slack-tokens \
  -e AWS_REGION=eu-west-1 \
  -e ENVIRONMENT=production \
  -e LOG_LEVEL=INFO \
  --mount type=bind,source=$HOME/.aws,target=/home/maptimize/.aws,readonly \
  maptimize:0.1.0

# Run health check
docker run --rm \
  maptimize:0.1.0 \
  python -c "import maptimize; print('healthy')"
```

### Step 3: Tag Image for ECR

```bash
# Set variables
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=eu-west-1
REPOSITORY_NAME=maptimize
IMAGE_TAG=0.1.0

# Tag the image
docker tag maptimize:${IMAGE_TAG} \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPOSITORY_NAME}:${IMAGE_TAG}

docker tag maptimize:${IMAGE_TAG} \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPOSITORY_NAME}:latest
```

## ECR Registry Setup

### Step 1: Create ECR Repository

```bash
# Set variables
AWS_REGION=eu-west-1
REPOSITORY_NAME=maptimize

# Create repository
aws ecr create-repository \
  --repository-name $REPOSITORY_NAME \
  --region $AWS_REGION \
  --image-tag-mutability MUTABLE \
  --image-scanning-configuration scanOnPush=true
```

### Step 2: Authenticate Docker to ECR

```bash
# Get login token
aws ecr get-login-password --region eu-west-1 | \
  docker login --username AWS --password-stdin \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
```

### Step 3: Push Image to ECR

```bash
# Push the image
docker push \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPOSITORY_NAME}:${IMAGE_TAG}

docker push \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPOSITORY_NAME}:latest

# Verify image in ECR
aws ecr describe-images \
  --repository-name $REPOSITORY_NAME \
  --region $AWS_REGION
```

## EC2 Deployment

### Step 1: Prepare User Data Script

The `infrastructure/user-data.sh` script automates instance initialization:

```bash
#!/bin/bash
set -e

# Update system packages
apt-get update
apt-get upgrade -y
apt-get install -y \
  docker.io \
  docker-compose \
  awscli \
  curl

# Start Docker service
systemctl start docker
systemctl enable docker

# Create maptimize user
useradd -m -s /bin/bash maptimize || true

# Create log directory
mkdir -p /var/log/maptimize
chown maptimize:maptimize /var/log/maptimize

# Download and start bot
export AWS_REGION=eu-west-1
su - maptimize -c "
  aws ecr get-login-password --region eu-west-1 | \
    docker login --username AWS --password-stdin \
    ${AWS_ACCOUNT_ID}.dkr.ecr.eu-west-1.amazonaws.com

  docker pull \
    ${AWS_ACCOUNT_ID}.dkr.ecr.eu-west-1.amazonaws.com/maptimize:latest

  docker run -d \
    --name maptimize-bot \
    --restart always \
    --log-driver json-file \
    --log-opt max-size=50m \
    --log-opt max-file=3 \
    -e SLACK_TOKENS_SECRET_ID=maptimize/slack-tokens \
    -e AWS_REGION=eu-west-1 \
    -e ENVIRONMENT=production \
    -e LOG_LEVEL=INFO \
    ${AWS_ACCOUNT_ID}.dkr.ecr.eu-west-1.amazonaws.com/maptimize:latest
"
```

### Step 2: Launch EC2 Instance

Use the automated launch script:

```bash
bash infrastructure/launch-ec2.sh
```

Or manually:

```bash
# Set variables
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
INSTANCE_TYPE=t3.micro
KEY_NAME=maptimize-key
SECURITY_GROUP=maptimize-bot-sg
SUBNET_ID=subnet-xxxxx  # Your VPC subnet

# Launch instance
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id ami-0c55b159cbfafe1f0 \
  --instance-type $INSTANCE_TYPE \
  --key-name $KEY_NAME \
  --security-groups $SECURITY_GROUP \
  --user-data file://infrastructure/user-data.sh \
  --iam-instance-profile Name=ec2-maptimize-role \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=maptimize-bot}]" \
  --query 'Instances[0].InstanceId' \
  --output text)

echo "Instance launched: $INSTANCE_ID"

# Wait for instance to be running
aws ec2 wait instance-running --instance-ids $INSTANCE_ID

# Get public IP
PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids $INSTANCE_ID \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)

echo "Instance IP: $PUBLIC_IP"
```

### Step 3: Verify Instance is Running

```bash
# Check instance status
aws ec2 describe-instances \
  --instance-ids $INSTANCE_ID \
  --query 'Reservations[0].Instances[0].[State.Name,PublicIpAddress]'

# SSH into instance (wait 2-3 minutes for user data to complete)
ssh -i maptimize-key.pem ubuntu@$PUBLIC_IP

# Check if bot is running
docker ps
docker logs maptimize-bot

# Check health
docker inspect --format='{{.State.Health.Status}}' maptimize-bot
```

## Production Configuration

### Step 1: Configure IAM Instance Role

Create an instance profile for EC2 to access AWS services:

```bash
# Create trust policy
cat > ec2-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name ec2-maptimize-role \
  --assume-role-policy-document file://ec2-trust-policy.json

# Attach policies for Secrets Manager and CloudWatch
aws iam attach-role-policy \
  --role-name ec2-maptimize-role \
  --policy-arn arn:aws:iam::aws:policy/SecretsManagerReadOnlyAccess

aws iam attach-role-policy \
  --role-name ec2-maptimize-role \
  --policy-arn arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy

# Create instance profile
aws iam create-instance-profile \
  --instance-profile-name ec2-maptimize-role

aws iam add-role-to-instance-profile \
  --instance-profile-name ec2-maptimize-role \
  --role-name ec2-maptimize-role
```

## SSSD/LDAP Configuration

This section covers LDAP user authentication setup using SSSD (System Security Services Daemon).

### Prerequisites

- LDAP server configured and accessible (e.g., `ldap-proxy.camp-infra.adobe.net:10636`)
- Network connectivity from EC2 instance to LDAP server
- Root/sudo access to the EC2 instance

### Step 1: Install SSSD and LDAP Packages

```bash
# SSH into the EC2 instance
ssh -i maptimize-key.pem harrison@$PUBLIC_IP

# Update package lists
sudo apt-get update

# Install SSSD and LDAP packages
sudo apt-get install -y \
  sssd \
  sssd-ldap \
  sssd-common \
  libsss-certmap0 \
  libsss-idmap0 \
  libsss-nss-idmap0 \
  ldap-utils
```

### Step 2: Deploy SSSD Configuration

Create `/etc/sssd/sssd.conf` with LDAP configuration:

```bash
sudo tee /etc/sssd/sssd.conf > /dev/null <<'EOF'
[sssd]
debug_level = 0
config_file_version = 2
services = nss, pam, ssh, sudo
domains = default

[domain/default]
debug_level = 0
ldap_disable_paging = True
ldap_id_use_start_tls = True
ldap_schema = rfc2307bis
ldap_search_base = o=adbe
ldap_deref_threshold = 0
id_provider = ldap
auth_provider = ldap
chpass_provider = ldap

ldap_uri = ldaps://ldap-proxy.camp-infra.adobe.net:10636
ldap_backup_uri = ldaps://camp-infra.adobe.net:636

ldap_tls_cacert = /etc/ssl/certs/ca-certificates.crt
cache_credentials = True
ldap_tls_reqcert = demand
ldap_group_member = uniqueMember
enumerate = False
ldap_enumeration_refresh_timeout = 18000
entry_cache_timeout = 14400
entry_cache_user_timeout = 14400
entry_cache_group_timeout = 14400
entry_cache_netgroup_timeout = 14400
entry_cache_service_timeout = 14400

sudo_provider = ldap
ldap_sudo_search_base = ou=SUDOers,o=adbe
ldap_user_ssh_public_key = sshPublicKey

access_provider = simple
ignore_group_members = True
simple_allow_groups = campaign, Campaign_LB_Admin, campaignbastionhosts, Campaign_Temp_Users, campaign_sustenance, campaign_cc
EOF

# Set proper permissions
sudo chmod 600 /etc/sssd/sssd.conf
sudo chown root:root /etc/sssd/sssd.conf
```

### Step 3: Update NSS Configuration

Update `/etc/nsswitch.conf` to enable SSSD:

```bash
sudo sed -i 's/^passwd:\s*files$/passwd:\t\tfiles sss/' /etc/nsswitch.conf
sudo sed -i 's/^group:\s*files$/group:\t\tfiles sss/' /etc/nsswitch.conf
sudo sed -i 's/^shadow:\s*files$/shadow:\t\tfiles sss/' /etc/nsswitch.conf
```

### Step 4: Enable Automatic Home Directory Creation

Add PAM module for automatic home directory creation:

```bash
sudo tee -a /etc/pam.d/common-session > /dev/null <<'EOF'
session      optional      pam_mkhomedir.so
session required  pam_mkhomedir.so umask=0022
EOF
```

### Step 5: Configure SSH Authentication

Allow both public key and password authentication with LDAP fallback:

```bash
sudo sed -i 's/^PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config
sudo sshd -t  # Verify config
sudo systemctl reload sshd
```

### Step 6: Configure Sudo Access

Create sudoers entry for LDAP group access:

```bash
echo '%Campaign_LB_Admin ALL=(ALL) NOPASSWD:ALL' | sudo tee /etc/sudoers.d/91-ldap-campaign
sudo chmod 440 /etc/sudoers.d/91-ldap-campaign
sudo visudo -c  # Verify syntax
```

### Step 7: Start and Enable SSSD

```bash
sudo systemctl start sssd
sudo systemctl enable sssd
sudo systemctl status sssd
```

### Step 8: Verify LDAP Resolution

```bash
# Test user resolution
sleep 2
id <ldap-username>

# Test group membership
getent group

# Test sudo access
sudo -l
```

### Troubleshooting

**SSSD service won't start:**
```bash
sudo journalctl -xe -u sssd
sudo sssctl config-check
```

**LDAP users not resolving:**
```bash
sudo systemctl stop sssd
sudo rm -rf /var/lib/sss/db/*
sudo systemctl start sssd

# Test connectivity
ldapsearch -x -H ldaps://ldap-proxy.camp-infra.adobe.net:10636 -b "o=adbe" -s base
```

**SSH password authentication not working:**
```bash
sudo grep -E "PasswordAuthentication|PubkeyAuthentication" /etc/ssh/sshd_config
sudo sshd -T | grep -i password
```

### Step 2: Configure CloudWatch Logging

```bash
# Create log group
aws logs create-log-group \
  --log-group-name /aws/ec2/maptimize

# Set retention
aws logs put-retention-policy \
  --log-group-name /aws/ec2/maptimize \
  --retention-in-days 30
```

### Step 3: Set Up Alarms

```bash
# Create alarm for high error rate
aws cloudwatch put-metric-alarm \
  --alarm-name maptimize-high-errors \
  --alarm-description "Alert when error rate is high" \
  --metric-name ErrorCount \
  --namespace Maptimize \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2
```

## Monitoring and Health Checks

### Step 1: View Logs

```bash
# From EC2 instance
ssh -i maptimize-key.pem ubuntu@$PUBLIC_IP
docker logs -f maptimize-bot

# Or from local machine with AWS CLI
aws logs tail /aws/ec2/maptimize --follow
```

### Step 2: Check Health Status

```bash
# Check container health
ssh -i maptimize-key.pem ubuntu@$PUBLIC_IP
docker inspect --format='{{.State.Health}}' maptimize-bot

# Health endpoint
docker exec maptimize-bot python -c "import maptimize; print('OK')"
```

### Step 3: Monitor Metrics

Key metrics to monitor:

- **CPU Usage**: Instance CPU utilization
- **Memory Usage**: Container memory consumption
- **Error Rate**: Failed request percentage
- **Response Time**: Average message processing time
- **Restart Count**: Container restart frequency

```bash
# Get metrics from CloudWatch
aws cloudwatch get-metric-statistics \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --dimensions Name=InstanceId,Value=$INSTANCE_ID \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z \
  --period 300 \
  --statistics Average,Maximum
```

### Step 4: Set Up Slack Alerts

Configure CloudWatch to send alerts to Slack:

```bash
# Create SNS topic for alerts
SNS_TOPIC=$(aws sns create-topic \
  --name maptimize-alerts \
  --query 'TopicArn' \
  --output text)

# Subscribe to Slack webhook
aws sns subscribe \
  --topic-arn $SNS_TOPIC \
  --protocol https \
  --notification-endpoint https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

## Updates and Rollback

### Step 1: Deploy New Version

```bash
# Build new image
docker build \
  --tag maptimize:0.1.1 \
  --file infrastructure/Dockerfile \
  .

# Tag for ECR
docker tag maptimize:0.1.1 \
  ${AWS_ACCOUNT_ID}.dkr.ecr.eu-west-1.amazonaws.com/maptimize:0.1.1

# Push to ECR
docker push \
  ${AWS_ACCOUNT_ID}.dkr.ecr.eu-west-1.amazonaws.com/maptimize:0.1.1

# Stop old container
ssh -i maptimize-key.pem ubuntu@$PUBLIC_IP
docker stop maptimize-bot
docker rm maptimize-bot

# Pull and start new container
docker pull \
  ${AWS_ACCOUNT_ID}.dkr.ecr.eu-west-1.amazonaws.com/maptimize:0.1.1

docker run -d \
  --name maptimize-bot \
  --restart always \
  --log-driver json-file \
  --log-opt max-size=50m \
  --log-opt max-file=3 \
  -e SLACK_TOKENS_SECRET_ID=maptimize/slack-tokens \
  -e AWS_REGION=eu-west-1 \
  -e ENVIRONMENT=production \
  -e LOG_LEVEL=INFO \
  ${AWS_ACCOUNT_ID}.dkr.ecr.eu-west-1.amazonaws.com/maptimize:0.1.1

# Verify new version
docker logs maptimize-bot
docker inspect --format='{{.State.Health.Status}}' maptimize-bot
```

### Step 2: Verify Deployment

```bash
# Wait for container to be healthy
sleep 30

# Check logs for errors
docker logs maptimize-bot | tail -20

# Test functionality
# Send test message to Slack and verify bot responds
```

### Step 3: Rollback to Previous Version

```bash
# Stop current container
ssh -i maptimize-key.pem ubuntu@$PUBLIC_IP
docker stop maptimize-bot
docker rm maptimize-bot

# Start previous version
docker run -d \
  --name maptimize-bot \
  --restart always \
  --log-driver json-file \
  --log-opt max-size=50m \
  --log-opt max-file=3 \
  -e SLACK_TOKENS_SECRET_ID=maptimize/slack-tokens \
  -e AWS_REGION=eu-west-1 \
  -e ENVIRONMENT=production \
  -e LOG_LEVEL=INFO \
  ${AWS_ACCOUNT_ID}.dkr.ecr.eu-west-1.amazonaws.com/maptimize:0.1.0

# Verify health
docker logs maptimize-bot
```

### Step 4: Zero-Downtime Deployment (Advanced)

For critical deployments, use container orchestration:

```bash
# Using ECS or Kubernetes
# See infrastructure documentation for advanced setup
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker logs maptimize-bot

# Check image exists
docker images | grep maptimize

# Try running manually to see errors
docker run --rm \
  -e SLACK_TOKENS_SECRET_ID=maptimize/slack-tokens \
  -e AWS_REGION=eu-west-1 \
  maptimize:0.1.0
```

### AWS Credentials Issues

```bash
# Verify instance role
aws sts get-caller-identity

# Check role permissions
aws iam get-role-policy \
  --role-name ec2-maptimize-role \
  --policy-name policy-name

# Test Secrets Manager access
aws secretsmanager get-secret-value \
  --secret-id maptimize/slack-tokens
```

### Slack Connection Issues

```bash
# Check Slack token in Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id maptimize/slack-tokens

# Check logs for connection errors
docker logs maptimize-bot | grep -i "slack\|socket"

# Verify Socket Mode is enabled in Slack app
```

### Memory Issues

```bash
# Check memory usage
docker stats maptimize-bot

# Increase container memory limit
docker update --memory 512m maptimize-bot
```

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for more detailed troubleshooting.

## Post-Deployment Checklist

- [ ] Instance is running and healthy
- [ ] Container is running without errors
- [ ] Bot responds to Slack mentions
- [ ] Slash commands work correctly
- [ ] Logs are being generated
- [ ] CloudWatch alarms are configured
- [ ] Monitoring is active
- [ ] Team has access to run commands
- [ ] Documentation is updated
- [ ] Backup procedure is documented

## Security Considerations

- Keep Slack tokens in Secrets Manager, never in code
- Restrict EC2 security group to necessary IPs
- Use IAM roles instead of access keys
- Enable CloudTrail for audit logging
- Regularly update Docker images
- Monitor and review logs regularly
- Implement log rotation to manage disk space
- Use VPC endpoints for AWS API calls when possible

## Support

For issues or questions:
1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. Review logs in CloudWatch
3. Contact the Camp Ops EMEA team at team@campops.com
