# EC2 Instance Setup Guide

This document provides step-by-step instructions for setting up a Maptimize EC2 instance after launch.

## Prerequisites

- EC2 instance launched using `launch-ec2.sh`
- SSH key pair saved locally (e.g., `maptimize-ec2-keypair.pem`)
- Instance public IP address (from `instance-config.json`)
- Access to existing instance with SSSD configuration (for copying sssd.conf)

## Overview

The EC2 launch script automates infrastructure creation:
- Creates security group with SSH access
- Creates IAM role with Secrets Manager and ECR policies
- Creates IAM instance profile for EC2 attachment
- Launches EC2 instance with user-data script
- user-data.sh runs during initialization to install dependencies

Post-launch setup requires manual configuration:
- SSSD configuration (LDAP authentication)
- systemd service installation
- Health check verification

## Phase 1: Verify Instance Status

### 1.1 SSH Into Instance

```bash
# Using the key pair from launch
ssh -i maptimize-ec2-keypair.pem ec2-user@<PUBLIC_IP>
```

Replace `<PUBLIC_IP>` with the public IP address from `instance-config.json`.

### 1.2 Check User-Data Script Execution

The user-data script runs automatically during instance launch. Verify completion:

```bash
# View user-data script log
sudo tail -f /var/log/user-data.log

# Check for errors
sudo grep -i error /var/log/user-data.log

# Verify Docker installation
docker --version
docker-compose --version

# Verify SSSD installation
systemctl status sssd
```

Expected output after successful initialization:
- Docker running and accessible
- docker-compose installed
- SSSD service installed but not yet configured
- SSH hardening applied

### 1.3 Verify IAM Instance Profile

Confirm the instance can access AWS services:

```bash
# Check instance metadata
curl http://169.254.169.254/latest/meta-data/iam/security-credentials/

# Should return IAM role name: maptimize-ec2-role
# If empty, instance profile attachment failed
```

## Phase 2: Configure SSSD for LDAP Authentication

SSSD (System Security Services Daemon) handles LDAP authentication. The instance profile has a template configuration that must be completed with actual LDAP details.

### 2.1 Obtain SSSD Configuration

The SSSD configuration must be copied from an existing instance where LDAP is already configured (ketchup template reference). This configuration contains:
- LDAP server URI
- Search base DN
- Bind credentials
- Cache settings

**From the source instance (with working SSSD):**

```bash
# View existing SSSD configuration
sudo cat /etc/sssd/sssd.conf
```

**On the new instance:**

```bash
# Create the SSSD configuration directory
sudo mkdir -p /etc/sssd
sudo chmod 755 /etc/sssd

# Copy the configuration from source (via SCP or manual entry)
# Option 1: Using SCP from source instance
# scp -i <key> ec2-user@<source-ip>:/etc/sssd/sssd.conf /tmp/sssd.conf
# sudo cp /tmp/sssd.conf /etc/sssd/sssd.conf
# sudo chmod 600 /etc/sssd/sssd.conf

# Option 2: Manual configuration (if SCP not available)
# Use the template as reference and fill in actual LDAP details
sudo vi /etc/sssd/sssd.conf
```

### 2.2 Configure SSSD

Update the SSSD configuration with actual LDAP details:

```ini
[domain/ldap]
auth_provider = ldap
id_provider = ldap
ldap_uri = ldap://ldap.example.com          # Update with actual LDAP server
ldap_search_base = dc=example,dc=com        # Update with actual search base
ldap_default_bind_dn = cn=admin,dc=example,dc=com  # Update with actual bind DN
ldap_default_authtok = PLACEHOLDER           # Update with actual password
enumerate = false
cache_credentials = true

[sssd]
domains = ldap
services = nss, pam
```

### 2.3 Verify SSSD Configuration

```bash
# Check syntax
sudo sssctl config-check

# If errors, review configuration
sudo cat /etc/sssd/sssd.conf

# Ensure permissions are correct
sudo ls -la /etc/sssd/sssd.conf
# Should show: -rw------- (600 permissions)
```

### 2.4 Start SSSD Service

```bash
# Enable SSSD to start on boot
sudo systemctl enable sssd

# Start SSSD service
sudo systemctl start sssd

# Check service status
sudo systemctl status sssd

# View service logs
sudo journalctl -u sssd -n 50
```

### 2.5 Test LDAP Authentication

```bash
# Verify LDAP user can be resolved
id <ldap-username>

# Attempt SSH with LDAP credentials
ssh -i maptimize-ec2-keypair.pem <ldap-username>@<INSTANCE_IP>

# If successful, SSSD is properly configured
# If failed, check SSSD logs: sudo journalctl -u sssd
```

## Phase 3: Install Systemd Service

The Maptimize application runs as a systemd service that manages Docker containers.

### 3.1 Prepare Environment Configuration

Create the environment file for the systemd service:

```bash
# Create directory for Maptimize environment configuration
sudo mkdir -p /etc/maptimize
sudo chmod 755 /etc/maptimize

# Create environment file with AWS configuration
sudo cat > /etc/maptimize/maptimize.env <<EOF
AWS_REGION=eu-west-1
AWS_ACCOUNT_ID=<YOUR_ACCOUNT_ID>
ECR_REPOSITORY_NAME=maptimize
APP_VERSION=latest
EOF

# Set permissions
sudo chmod 644 /etc/maptimize/maptimize.env
```

Replace `<YOUR_ACCOUNT_ID>` with your AWS account ID from instance-config.json.

### 3.2 Copy Systemd Service File

The systemd service file is in the infrastructure directory. Copy it to the system:

```bash
# Copy service file to systemd directory
sudo cp /opt/maptimize/scripts/maptimize.service /etc/systemd/system/maptimize.service

# If service file not yet in /opt/maptimize/scripts, copy from infrastructure:
# From your local machine or deployment:
scp -i maptimize-ec2-keypair.pem infrastructure/maptimize.service ec2-user@<INSTANCE_IP>:/tmp/
ssh -i maptimize-ec2-keypair.pem ec2-user@<INSTANCE_IP> 'sudo cp /tmp/maptimize.service /etc/systemd/system/'

# Set permissions
sudo chmod 644 /etc/systemd/system/maptimize.service
```

### 3.3 Create Application Directory Structure

```bash
# Directories are created by user-data.sh, verify they exist
ls -la /opt/maptimize/

# Expected output:
# drwxr-xr-x  app
# drwxr-xr-x  config
# drwxr-xr-x  logs
# drwxr-xr-x  data
# drwxr-xr-x  scripts
```

### 3.4 Deploy docker-compose Configuration

The docker-compose.yml file must be placed in `/opt/maptimize/config`:

```bash
# Copy docker-compose file to config directory
scp -i maptimize-ec2-keypair.pem infrastructure/docker-compose.production.yml \
    ec2-user@<INSTANCE_IP>:/tmp/docker-compose.yml

ssh -i maptimize-ec2-keypair.pem ec2-user@<INSTANCE_IP> \
    'sudo cp /tmp/docker-compose.yml /opt/maptimize/config/docker-compose.yml && \
     sudo chown ec2-user:ec2-user /opt/maptimize/config/docker-compose.yml && \
     sudo chmod 644 /opt/maptimize/config/docker-compose.yml'

# Verify
ssh -i maptimize-ec2-keypair.pem ec2-user@<INSTANCE_IP> 'ls -la /opt/maptimize/config/'
```

### 3.5 Deploy Application Scripts

Copy the deploy script to the scripts directory:

```bash
# Copy deploy script
scp -i maptimize-ec2-keypair.pem infrastructure/deploy.sh \
    ec2-user@<INSTANCE_IP>:/tmp/deploy.sh

ssh -i maptimize-ec2-keypair.pem ec2-user@<INSTANCE_IP> \
    'sudo cp /tmp/deploy.sh /opt/maptimize/scripts/deploy.sh && \
     sudo chown ec2-user:ec2-user /opt/maptimize/scripts/deploy.sh && \
     sudo chmod 755 /opt/maptimize/scripts/deploy.sh'
```

### 3.6 Configure Systemd Service

Reload systemd configuration and enable the service:

```bash
# Reload systemd manager configuration
sudo systemctl daemon-reload

# Verify service file is recognized
sudo systemctl list-unit-files | grep maptimize

# Enable service to start on boot
sudo systemctl enable maptimize.service

# Start the service
sudo systemctl start maptimize.service

# Check service status
sudo systemctl status maptimize.service
```

## Phase 4: Health Check Verification

Verify that the application is running correctly.

### 4.1 Check Service Status

```bash
# View service status
sudo systemctl status maptimize.service

# View service logs
sudo journalctl -u maptimize.service -n 50

# View all logs with follow
sudo journalctl -u maptimize.service -f
```

### 4.2 Verify Docker Containers

```bash
# List running Docker containers
docker ps

# View container logs
docker logs <container-id>

# Check docker-compose status
docker-compose -f /opt/maptimize/config/docker-compose.yml ps
```

### 4.3 Verify Application Deployment

```bash
# Check application logs
sudo tail -f /opt/maptimize/logs/deploy.log

# Verify container health
docker-compose -f /opt/maptimize/config/docker-compose.yml logs

# Check if application is responding
# This depends on your application's health check endpoint
curl http://localhost:<APP_PORT>/health  # Replace with actual port
```

### 4.4 Monitor Application Health

After deployment, monitor the application for issues:

```bash
# Watch service status in real-time
watch -n 2 'sudo systemctl status maptimize.service'

# Check for any startup failures
sudo journalctl -u maptimize.service --since "10 minutes ago"

# Verify container persistence
docker ps --no-trunc
```

## Phase 5: Verification Checklist

Complete these steps to verify the setup:

- [ ] SSH access works with EC2 key pair
- [ ] User-data script completed successfully (check /var/log/user-data.log)
- [ ] Docker and docker-compose are installed and running
- [ ] IAM instance profile is attached and accessible
- [ ] SSSD configuration is valid (sudo sssctl config-check)
- [ ] SSSD service is running (sudo systemctl status sssd)
- [ ] LDAP user authentication works (id <ldap-username>)
- [ ] /etc/maptimize/maptimize.env is configured with AWS details
- [ ] maptimize.service file is installed in /etc/systemd/system/
- [ ] docker-compose.yml is in /opt/maptimize/config/
- [ ] deploy.sh is executable in /opt/maptimize/scripts/
- [ ] maptimize service is enabled and running
- [ ] Docker containers are running (docker ps)
- [ ] Application logs show successful startup
- [ ] Health check endpoint responds correctly

## Troubleshooting

### SSH Connection Issues

```bash
# Verify security group allows SSH
aws ec2 describe-security-groups --group-ids <SG_ID> --region eu-west-1

# Check SSH key permissions
ls -la maptimize-ec2-keypair.pem  # Should be 600

# Try verbose SSH to see connection details
ssh -v -i maptimize-ec2-keypair.pem ec2-user@<PUBLIC_IP>
```

### User-Data Script Failures

```bash
# View complete user-data log
sudo tail -100 /var/log/user-data.log

# Check system messages
sudo dmesg | tail -20

# View cloud-init logs
sudo tail -100 /var/log/cloud-init-output.log
```

### SSSD Configuration Issues

```bash
# Validate SSSD configuration syntax
sudo sssctl config-check

# View SSSD logs
sudo journalctl -u sssd -n 100

# Test LDAP connectivity
ldapsearch -x -H ldap://ldap.example.com -b "dc=example,dc=com"
```

### Docker/Service Startup Issues

```bash
# Check Docker daemon status
sudo systemctl status docker

# View Docker service logs
sudo journalctl -u docker -n 50

# Test Docker functionality
docker ps
docker-compose -f /opt/maptimize/config/docker-compose.yml ps

# View systemd service logs
sudo journalctl -u maptimize.service -n 100
```

### IAM Permission Issues

```bash
# Verify IAM role is attached
curl http://169.254.169.254/latest/meta-data/iam/security-credentials/

# Test ECR access
aws ecr get-login-password --region eu-west-1

# Test Secrets Manager access
aws secretsmanager get-secret-value --secret-id maptimize/test --region eu-west-1
```

## Rollback Procedure

If critical issues occur, you can terminate the instance and relaunch:

```bash
# From local machine
INSTANCE_ID=$(jq -r '.instance_id' instance-config.json)

# Terminate instance
aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region eu-west-1

# Wait for termination
aws ec2 wait instance-terminated --instance-ids $INSTANCE_ID --region eu-west-1

# Relaunch
./launch-ec2.sh maptimize-bot
```

## Next Steps

After successful verification:

1. Set up monitoring and alerting for the instance
2. Configure automated backups if needed
3. Document any custom configurations
4. Set up log aggregation to centralized logging service
5. Configure automated patching schedule
