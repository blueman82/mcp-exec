#!/bin/bash
set -e

# EC2 User Data Script for Maptimize Production Instance
# Mirrors asksplunk-prod provisioning exactly
# Provisions t3.xlarge with Docker, AWS CLI, SSSD, and application directory
# OS: Debian 12 (Bookworm)
# Region: eu-west-1

exec > >(tee /var/log/user-data.log)
exec 2>&1

echo "=========================================="
echo "Maptimize EC2 Provisioning Started"
echo "Timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
echo "=========================================="

# Update system packages
echo "[1/12] Updating system packages..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

# Install prerequisites
echo "[2/12] Installing prerequisites..."
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
echo "[3/12] Installing Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
rm get-docker.sh

# Configure Docker daemon
echo "[3.1/12] Configuring Docker daemon..."
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
echo "[4/12] Installing Docker Compose..."
DOCKER_COMPOSE_VERSION="2.23.0"
curl -L "https://github.com/docker/compose/releases/download/v${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" \
    -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Create docker-compose symlink for 'docker compose' command
mkdir -p /usr/libexec/docker/cli-plugins
ln -sf /usr/local/bin/docker-compose /usr/libexec/docker/cli-plugins/docker-compose

# Verify Docker installation
echo "[4.1/12] Verifying Docker installation..."
docker --version
docker-compose --version

# Install AWS CLI v2
echo "[5/12] Installing AWS CLI v2..."
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip -q awscliv2.zip
./aws/install
rm -rf aws awscliv2.zip

# Verify AWS CLI installation
aws --version

# Install SSSD for LDAP authentication
echo "[6/12] Installing SSSD..."
apt-get install -y sssd sssd-tools libnss-sss libpam-sss libsss-sudo

# Create SSSD configuration directory
mkdir -p /etc/sssd
chmod 700 /etc/sssd

# Deploy SSSD configuration (embedded, matching asksplunk-prod)
echo "[6.1/12] Deploying SSSD configuration..."
cat > /etc/sssd/sssd.conf <<'SSSDEOF'
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

[nss]
filter_users = root,neolane,nobody,ntp,named,smtp,postgres,postfix,nagios,nrpe,httpd,hadoop,nssagent,ssh-authkeys,asc-bkaccess,asc-oit,asc-setup,asc-rundeck,asc-airflow,mbplc,mabadhoc,mabRelay
filter_groups = chrooted,asc-users
default_shell = /bin/bash

[pam]

[ssh]

[sudo]
SSSDEOF

chmod 600 /etc/sssd/sssd.conf
chown root:root /etc/sssd/sssd.conf

# Configure NSS to use SSSD for sudo rules
echo "[7/12] Configuring SSSD sudo integration..."
if ! grep -q "^sudoers:" /etc/nsswitch.conf; then
    echo 'sudoers:        files sss' >> /etc/nsswitch.conf
    echo "    ✓ Added sudoers to nsswitch.conf"
else
    echo "    ✓ sudoers already configured in nsswitch.conf"
fi

# Configure SSH (keep defaults, no LDAP key retrieval needed for MVP)
echo "[7.1/12] SSH configuration (using EC2 key metadata)..."

# Enable and start SSSD service
echo "[7.2/12] Enabling and starting SSSD..."
systemctl enable sssd
systemctl start sssd

# Set up SSH key for admin user (from EC2 instance metadata)
echo "[8/12] Setting up SSH key for admin user..."
mkdir -p /home/admin/.ssh
chmod 700 /home/admin/.ssh

# Get public key from instance metadata
PUBLIC_KEY=$(curl -s http://169.254.169.254/latest/meta-data/public-keys/0/openssh-key/)
if [ -n "$PUBLIC_KEY" ]; then
    echo "$PUBLIC_KEY" > /home/admin/.ssh/authorized_keys
    chmod 600 /home/admin/.ssh/authorized_keys
    chown admin:admin /home/admin/.ssh/authorized_keys
    echo "SSH public key installed for admin user"
else
    echo "WARNING: Could not retrieve SSH public key from instance metadata"
fi

# Apply minimal SSH configuration (matching asksplunk-prod)
echo "[8.1/12] Configuring SSH..."
sed -i 's/^#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
if ! grep -q "^PasswordAuthentication no" /etc/ssh/sshd_config; then
    echo "PasswordAuthentication no" >> /etc/ssh/sshd_config
fi

# Disable UsePAM to prevent SSSD access control from blocking pubkey auth
sed -i 's/^#UsePAM yes/UsePAM no/' /etc/ssh/sshd_config
if ! grep -q "^UsePAM no" /etc/ssh/sshd_config; then
    echo "UsePAM no" >> /etc/ssh/sshd_config
fi

# Test SSH configuration
if sshd -t; then
    echo "SSH configuration valid"
    systemctl restart sshd
else
    echo "ERROR: SSH configuration invalid"
    exit 1
fi

# Create application directory
echo "[9/12] Creating application directory..."
mkdir -p /opt/maptimize/logs
chown -R admin:admin /opt/maptimize
chmod 755 /opt/maptimize

# Login to ECR
echo "[10/12] Logging into ECR..."
aws ecr get-login-password --region eu-west-1 | \
    docker login --username AWS --password-stdin \
    483013340174.dkr.ecr.eu-west-1.amazonaws.com

# Create ECR login refresh cron job (12-hour validity)
echo "[10.1/12] Setting up ECR credential refresh..."
cat > /etc/cron.hourly/ecr-login <<'EOF'
#!/bin/bash
# Refresh ECR credentials every hour (they expire after 12 hours)
aws ecr get-login-password --region eu-west-1 | \
    docker login --username AWS --password-stdin \
    483013340174.dkr.ecr.eu-west-1.amazonaws.com >> /var/log/ecr-login.log 2>&1
EOF
chmod +x /etc/cron.hourly/ecr-login

# Set timezone to UTC
echo "[11/12] Configuring system settings..."
timedatectl set-timezone UTC

# Enable automatic security updates
apt-get install -y unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades

# Configure systemd journald
cat > /etc/systemd/journald.conf.d/maptimize.conf <<'EOF'
[Journal]
MaxRetentionSec=7day
MaxFileSec=1day
EOF
systemctl restart systemd-journald

# Create motd banner
cat > /etc/motd <<'EOF'
================================================================================
                        Maptimize Slack Bot Production
================================================================================

Instance Type:  t3.xlarge (4 vCPU, 16GB RAM)
OS:             Debian 12 (Bookworm)
Region:         eu-west-1
Application:    /opt/maptimize

Quick Commands:
  - View application logs:     cd /opt/maptimize && docker-compose logs -f
  - Restart application:       cd /opt/maptimize && docker-compose restart
  - Check container status:    docker ps
  - Update application:        cd /opt/maptimize && docker-compose pull && docker-compose up -d

================================================================================
EOF

echo "[12/12] EC2 provisioning complete!"
echo "Timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
echo "=========================================="
