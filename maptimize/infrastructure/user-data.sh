#!/bin/bash
set -e

# EC2 User Data Script - Maptimize MVP
# Minimal provisioning: Only Docker, Docker Compose, AWS CLI, SSH key
# Post-deployment steps: SSSD/LDAP, ECR login, bot deployment
# OS: Debian 12 (Bookworm)
# Region: eu-west-1

exec > >(tee /var/log/user-data.log)
exec 2>&1

echo "=========================================="
echo "Maptimize EC2 Minimal Provisioning Started"
echo "Timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
echo "=========================================="

# Update system packages
echo "[1/5] Updating system packages..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

# Install prerequisites
echo "[2/5] Installing prerequisites..."
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    unzip

# Install Docker
echo "[3/5] Installing Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
rm get-docker.sh

# Configure Docker daemon
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
usermod -aG docker admin

# Install Docker Compose v2
echo "[3.1/5] Installing Docker Compose..."
DOCKER_COMPOSE_VERSION="2.23.0"
curl -L "https://github.com/docker/compose/releases/download/v${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" \
    -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
ln -sf /usr/local/bin/docker-compose /usr/libexec/docker/cli-plugins/docker-compose

docker --version
docker-compose --version

# Install AWS CLI v2
echo "[4/5] Installing AWS CLI v2..."
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip -q awscliv2.zip
./aws/install
rm -rf aws awscliv2.zip
aws --version

# Setup SSH key for admin user (from EC2 instance metadata)
echo "[5/5] Setting up SSH key for admin user..."
mkdir -p /home/admin/.ssh
chmod 700 /home/admin/.ssh

PUBLIC_KEY=$(curl -s http://169.254.169.254/latest/meta-data/public-keys/0/openssh-key/)
if [ -n "$PUBLIC_KEY" ]; then
    echo "$PUBLIC_KEY" > /home/admin/.ssh/authorized_keys
    chmod 600 /home/admin/.ssh/authorized_keys
    chown admin:admin /home/admin/.ssh/authorized_keys
    echo "✓ SSH public key installed for admin user"
else
    echo "WARNING: Could not retrieve SSH public key from instance metadata"
fi

# Create application directory
mkdir -p /opt/maptimize/logs
chown -R admin:admin /opt/maptimize
chmod 755 /opt/maptimize

echo ""
echo "=========================================="
echo "EC2 Minimal Provisioning Complete!"
echo "Timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
echo "=========================================="
echo ""
echo "Next Steps (Manual Post-Deployment):"
echo "1. SSH to instance: ssh -i ~/.ssh/maptimize-ec2-keypair.pem admin@<public-ip>"
echo "2. Configure SSSD/LDAP (see docs/infrastructure)"
echo "3. Login to ECR: aws ecr get-login-password --region eu-west-1 | docker login ..."
echo "4. Deploy bot: cd /opt/maptimize && docker-compose -f docker-compose.production.yml up -d"
echo ""
