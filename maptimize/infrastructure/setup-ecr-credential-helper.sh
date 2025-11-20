#!/bin/bash
# Setup Amazon ECR Docker Credential Helper
# This securely stores Docker credentials for ECR

set -e

echo "=========================================="
echo "Setting up ECR Credential Helper"
echo "=========================================="
echo ""

# Install amazon-ecr-credential-helper
echo "1. Installing amazon-ecr-credential-helper..."
sudo wget -q https://amazon-ecr-credential-helper-releases.s3.us-east-2.amazonaws.com/0.9.0/linux-amd64/docker-credential-ecr-login -O /usr/local/bin/docker-credential-ecr-login
sudo chmod +x /usr/local/bin/docker-credential-ecr-login

# Verify installation
echo "✓ Installed: $(docker-credential-ecr-login -v)"
echo ""

# Configure Docker to use the credential helper
echo "2. Configuring Docker to use ECR credential helper..."

# Create or update Docker config
mkdir -p ~/.docker

# Backup existing config if it exists
if [ -f ~/.docker/config.json ]; then
    cp ~/.docker/config.json ~/.docker/config.json.backup
    echo "✓ Backed up existing config to ~/.docker/config.json.backup"
fi

# Create new config with credential helper
cat > ~/.docker/config.json <<'EOF'
{
  "credHelpers": {
    "483013340174.dkr.ecr.eu-west-1.amazonaws.com": "ecr-login",
    "public.ecr.aws": "ecr-login"
  }
}
EOF

echo "✓ Updated ~/.docker/config.json"
echo ""

# Verify configuration
echo "3. Verifying configuration..."
if docker-credential-ecr-login list 2>/dev/null; then
    echo "✓ ECR credential helper is working"
else
    echo "⚠ Credential helper test returned an error (this may be normal if no credentials are cached yet)"
fi
echo ""

# Test Docker login (this should now not show the warning)
echo "4. Testing Docker login to ECR..."
aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin 483013340174.dkr.ecr.eu-west-1.amazonaws.com

echo ""
echo "=========================================="
echo "✓ ECR Credential Helper Setup Complete"
echo "=========================================="
echo ""
echo "The warning about unencrypted credentials should no longer appear."
echo "Docker will now use the AWS IAM role automatically for ECR authentication."
echo ""
