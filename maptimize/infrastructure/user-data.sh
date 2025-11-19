#!/bin/bash
set -e

# EC2 User Data Script
# This script runs on EC2 instance launch to configure the system
# It installs Docker, docker-compose, SSSD for LDAP, and hardens SSH

LOG_FILE="/var/log/user-data.log"

log_message() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_message "Starting EC2 initialization script"

# Update system packages
log_message "Updating system packages"
yum update -y

# Install Docker
log_message "Installing Docker"
amazon-linux-extras install -y docker
systemctl start docker
systemctl enable docker
log_message "Docker installed and started"

# Install docker-compose
log_message "Installing docker-compose"
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
log_message "docker-compose installed"

# Add ec2-user to docker group
log_message "Adding ec2-user to docker group"
usermod -aG docker ec2-user

# Install SSSD for LDAP authentication
log_message "Installing SSSD for LDAP authentication"
yum install -y sssd sssd-ldap openldap-clients nss-pam-ldapd

# Create SSSD configuration directory
mkdir -p /etc/sssd
chmod 755 /etc/sssd

# Create basic SSSD configuration (to be populated by CloudFormation or manual setup)
log_message "Creating SSSD configuration template"
cat > /etc/sssd/sssd.conf.template <<'EOF'
[domain/ldap]
auth_provider = ldap
id_provider = ldap
ldap_uri = ldap://ldap.example.com
ldap_search_base = dc=example,dc=com
ldap_default_bind_dn = cn=admin,dc=example,dc=com
ldap_default_authtok = PLACEHOLDER
enumerate = false
cache_credentials = true

[sssd]
domains = ldap
services = nss, pam
EOF

chmod 600 /etc/sssd/sssd.conf.template

# Harden SSH configuration
log_message "Hardening SSH configuration"
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup

# Apply security hardening settings
cat >> /etc/ssh/sshd_config <<'EOF'

# Security hardening configuration
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
X11Forwarding no
MaxAuthTries 3
MaxSessions 10
ClientAliveInterval 300
ClientAliveCountInterval 2
Compression no
UsePAM yes
AllowUsers ec2-user
EOF

# Test SSH configuration
if sshd -t; then
    log_message "SSH configuration valid"
    systemctl restart sshd
else
    log_message "ERROR: SSH configuration invalid, reverting"
    cp /etc/ssh/sshd_config.backup /etc/ssh/sshd_config
    systemctl restart sshd
    exit 1
fi

# Create application directory structure
log_message "Creating application directory structure"
mkdir -p /opt/maptimize/app
mkdir -p /opt/maptimize/config
mkdir -p /opt/maptimize/logs
mkdir -p /opt/maptimize/data

# Set proper permissions
chown -R ec2-user:ec2-user /opt/maptimize
chmod 755 /opt/maptimize
chmod 755 /opt/maptimize/app
chmod 755 /opt/maptimize/config
chmod 755 /opt/maptimize/logs
chmod 755 /opt/maptimize/data

# Create deploy script directory
mkdir -p /opt/maptimize/scripts
cp /opt/maptimize/scripts/deploy.sh /opt/maptimize/scripts/deploy.sh 2>/dev/null || log_message "Deploy script will be added via deployment"

log_message "EC2 initialization complete"
