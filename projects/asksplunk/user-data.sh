#!/bin/bash
set -e

# EC2 User Data Script for AskSplunk Production Instance
# Provisions t3.xlarge with Docker, AWS CLI, SSSD, and application directory
# OS: Debian 12 (Bookworm)
# Region: eu-west-1

exec > >(tee /var/log/user-data.log)
exec 2>&1

echo "=========================================="
echo "AskSplunk EC2 Provisioning Started"
echo "Timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
echo "=========================================="

# Update system packages
echo "[1/10] Updating system packages..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

# Install prerequisites
echo "[2/10] Installing prerequisites..."
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    unzip \
    htop \
    vim \
    wget \
    git \
    jq

# Install Docker
echo "[3/10] Installing Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
rm get-docker.sh

# Configure Docker daemon
echo "[3.1/10] Configuring Docker daemon..."
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "5"
  },
  "live-restore": true,
  "userland-proxy": false
}
EOF

systemctl enable docker
systemctl start docker

# Add admin user to docker group
usermod -aG docker admin

# Install Docker Compose v2
echo "[4/10] Installing Docker Compose..."
DOCKER_COMPOSE_VERSION="2.23.0"
curl -L "https://github.com/docker/compose/releases/download/v${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" \
    -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Create docker-compose symlink for 'docker compose' command
ln -sf /usr/local/bin/docker-compose /usr/libexec/docker/cli-plugins/docker-compose

# Verify Docker installation
echo "[4.1/10] Verifying Docker installation..."
docker --version
docker-compose --version

# Install AWS CLI v2
echo "[5/10] Installing AWS CLI v2..."
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip -q awscliv2.zip
./aws/install
rm -rf aws awscliv2.zip

# Verify AWS CLI installation
aws --version

# Install SSSD for LDAP authentication
echo "[6/10] Installing SSSD..."
apt-get install -y sssd sssd-tools libnss-sss libpam-sss libsss-sudo

# Create SSSD configuration directory
mkdir -p /etc/sssd
chmod 700 /etc/sssd

# SSSD configuration (manual step required)
echo "[6.1/10] SSSD installation complete - manual configuration required"
echo "    To configure SSSD:"
echo "    1. scp root@<existing-ldap-server>:/etc/sssd/sssd.conf /etc/sssd/"
echo "    2. chmod 600 /etc/sssd/sssd.conf"
echo "    3. systemctl enable sssd && systemctl start sssd"
echo "    Note: Replace <existing-ldap-server> with your Adobe LDAP server hostname"

# Configure NSS to use SSSD for sudo rules
echo "[7/10] Configuring SSSD sudo integration..."
if ! grep -q "^sudoers:" /etc/nsswitch.conf; then
    echo 'sudoers:        files sss' >> /etc/nsswitch.conf
    echo "    ✓ Added sudoers to nsswitch.conf"
else
    echo "    ✓ sudoers already configured in nsswitch.conf"
fi

# Configure SSH to use SSSD for public keys
echo "[7.1/10] Configuring SSH to retrieve keys from LDAP..."
if ! grep -q "^AuthorizedKeysCommand /usr/bin/sss_ssh_authorizedkeys" /etc/ssh/sshd_config; then
    cat >> /etc/ssh/sshd_config <<'EOF'

# SSSD integration for SSH public keys from LDAP
AuthorizedKeysCommand /usr/bin/sss_ssh_authorizedkeys
AuthorizedKeysCommandUser root
EOF
    systemctl restart sshd
    echo "    ✓ SSH configured for LDAP public keys"
else
    echo "    ✓ SSH already configured for LDAP public keys"
fi

# Create application directory
echo "[8/10] Creating application directory..."
mkdir -p /opt/asksplunk/logs
chown -R 1000:1000 /opt/asksplunk
chmod 755 /opt/asksplunk

# Setup ECR credential helper (auto-refreshes credentials via IAM role)
echo "[9/10] Setting up ECR credential helper..."
apt-get install -y amazon-ecr-credential-helper
mkdir -p /root/.docker
cat > /root/.docker/config.json <<'EOF'
{"credHelpers": {"483013340174.dkr.ecr.eu-west-1.amazonaws.com": "ecr-login"}}
EOF

# Set timezone to UTC
echo "[10/10] Configuring system settings..."
timedatectl set-timezone UTC

# Enable automatic security updates
apt-get install -y unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades

# Configure systemd journald
cat > /etc/systemd/journald.conf.d/asksplunk.conf <<'EOF'
[Journal]
MaxRetentionSec=7day
MaxFileSec=1day
EOF
systemctl restart systemd-journald

# Create motd banner
cat > /etc/motd <<'EOF'
================================================================================
                        AskSplunk Production Instance
================================================================================

Instance Type:  t3.xlarge (4 vCPU, 16GB RAM)
OS:             Debian 12 (Bookworm)
Region:         eu-west-1
Application:    /opt/asksplunk
Logs:           /opt/asksplunk/logs

Quick Commands:
  - View application logs:     cd /opt/asksplunk && docker-compose logs -f
  - Restart application:       cd /opt/asksplunk && docker-compose restart
  - Check container status:    docker ps
  - Update application:        cd /opt/asksplunk && docker-compose pull && docker-compose up -d
  - View system metrics:       htop

Documentation:
  - EC2 Setup:   /opt/asksplunk/docs/infrastructure/ec2-setup.md
  - Deployment:  /opt/asksplunk/docs/deployment.md

Support: gary.harrison@adobe.com
================================================================================
EOF

# Write provisioning summary
cat > /var/log/provisioning-summary.txt <<EOF
========================================
AskSplunk EC2 Provisioning Summary
========================================
Completion Time: $(date -u +"%Y-%m-%d %H:%M:%S UTC")

Installed Components:
  ✓ Docker $(docker --version | awk '{print $3}')
  ✓ Docker Compose $(docker-compose --version | awk '{print $4}')
  ✓ AWS CLI $(aws --version | awk '{print $1}' | cut -d/ -f2)
  ✓ SSSD (requires manual configuration)
  ✓ Unattended upgrades (automatic security updates)

Created Resources:
  ✓ Application directory: /opt/asksplunk
  ✓ Logs directory: /opt/asksplunk/logs
  ✓ ECR credential helper: Auto-refresh via IAM role (no plaintext credentials)
  ✓ Docker group: admin user added
  ✓ Sudo configuration: adobe-ops and adobe-admins LDAP groups

Manual Steps Required:
  1. Configure SSSD for Adobe LDAP authentication
     scp root@<existing-ldap-server>:/etc/sssd/sssd.conf /etc/sssd/
     chmod 600 /etc/sssd/sssd.conf
     systemctl enable sssd && systemctl start sssd
     Note: Replace <existing-ldap-server> with your Adobe LDAP server hostname

  2. Deploy application
     cd /opt/asksplunk
     # Create docker-compose.yml (see docs/infrastructure/ec2-setup.md)
     docker-compose up -d

  3. Verify health checks
     docker ps
     docker-compose logs -f asksplunk

Next Steps:
  - Review documentation: docs/infrastructure/ec2-setup.md
  - Test LDAP authentication: id your-ldap-username
  - Deploy application: see Application Deployment section
  - Configure monitoring: CloudWatch metrics enabled

========================================
EOF

echo ""
echo "=========================================="
echo "AskSplunk EC2 Provisioning Complete!"
echo "Timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
echo "=========================================="
echo ""
echo "Summary written to: /var/log/provisioning-summary.txt"
echo ""
echo "Manual steps required:"
echo "  1. Copy SSSD config from existing Adobe LDAP server"
echo "  2. Start SSSD service"
echo "  3. Verify LDAP authentication"
echo "  4. Deploy application (see docs/infrastructure/ec2-setup.md)"
echo ""
echo "View detailed summary: cat /var/log/provisioning-summary.txt"
echo ""
