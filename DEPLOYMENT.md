# Maptimize EC2 Deployment Guide

## Current Status

**Fixed Issues:**
- ✅ user-data.sh now properly configured for Debian 12
- ✅ Docker, Docker Compose v2, AWS CLI v2, SSSD all installed
- ✅ SSSD configured with Adobe LDAP integration
- ✅ SSH pubkey auth enabled with EC2 metadata key
- ✅ ECR login and hourly refresh configured
- ✅ SSH PAM auth issues fixed (UsePAM no, allow_users added)

**Latest Commit:** `6d373c1` - "fix: disable UsePAM for SSH and allow local users in SSSD access control"

## DNS Configuration

The maptimize-prod EC2 instance is now accessible via a DNS hostname in the `campaign.adobe.com` zone:

**Hostname:** `maptimize-prod.campaign.adobe.com`
**IP Address:** `52.213.19.55`
**Record Type:** A
**TTL:** 300 seconds
**Hosted Zone ID:** Z1FJAPF7U1MEJC
**Status:** Active and propagated to AWS Route53

### Verification

Verify DNS resolution is working:

```bash
# Test DNS resolution
nslookup maptimize-prod.campaign.adobe.com
dig maptimize-prod.campaign.adobe.com

# Expected output
# maptimize-prod.campaign.adobe.com has address 52.213.19.55

# Test HTTPS connectivity
curl -v https://maptimize-prod.campaign.adobe.com/

# Test SSH connectivity
ssh -i ~/.ssh/maptimize-ec2-keypair.pem ubuntu@maptimize-prod.campaign.adobe.com
```

### DNS Propagation

The A record was created in AWS Route53 and is immediately available from Route53 nameservers. Global DNS propagation across all public resolvers takes 24-48 hours due to DNS cache TTLs. The record is accessible immediately from:

- AWS Route53 nameservers (ns-1122.awsdns-12.org, etc.)
- Corporate networks using Route53 resolvers
- Local resolvers after initial cache timeout

For more details, see:
- `DNS-CONFIGURATION-REPORT.md` - Route53 setup and verification
- `HOSTNAME_SETUP_VERIFICATION.md` - Configuration reference
- `DNS_TEST_REPORT.md` - Detailed DNS testing results

## Next Steps

### 1. Launch New EC2 Instance (Required)

The current running instance (i-0c2e4e955afab806a) was launched with an earlier version of user-data.sh that has SSH auth issues. Launch a fresh instance with the corrected user-data:

```bash
cd /Users/harrison/Documents/Github/camp-ops-emea/maptimize-worktree/maptimize
bash infrastructure/launch-ec2.sh maptimize-prod
```

This will:
- Create a new t3.xlarge Debian 12 instance
- Create SSH key pair: `maptimize-ec2-keypair.pem`
- Run user-data.sh with all fixes
- Return public IP (e.g., `XX.XXX.XXX.XXX`)

**Note:** User-data script takes 5-10 minutes to complete. Wait before proceeding to next steps.

### 2. Verify Instance is Ready

Once user-data completes, verify SSH access works:

```bash
# Update SSH config if IP is different from current
ssh -i ~/.ssh/maptimize-ec2-keypair.pem -o ProxyCommand=none admin@<NEW_IP>

# Verify Docker is working
docker --version
docker-compose --version

# Verify SSSD is running
sudo systemctl status sssd

# Check EC2 user-data completion
tail /var/log/user-data.log
```

### 3. Deploy Application Configuration

From your local machine:

```bash
# Create /opt/maptimize on remote
ssh -i ~/.ssh/maptimize-ec2-keypair.pem -o ProxyCommand=none admin@<IP> \
  'sudo mkdir -p /opt/maptimize && sudo chown admin:admin /opt/maptimize'

# Copy docker-compose file
scp -i ~/.ssh/maptimize-ec2-keypair.pem -o ProxyCommand=none \
  maptimize/infrastructure/docker-compose.production.yml \
  admin@<IP>:/opt/maptimize/

# Copy systemd service file
scp -i ~/.ssh/maptimize-ec2-keypair.pem -o ProxyCommand=none \
  maptimize/infrastructure/maptimize.service \
  admin@<IP>:/tmp/

# Move service file to systemd directory
ssh -i ~/.ssh/maptimize-ec2-keypair.pem -o ProxyCommand=none admin@<IP> \
  'sudo mv /tmp/maptimize.service /etc/systemd/system/ && sudo chmod 644 /etc/systemd/system/maptimize.service'
```

### 4. Start the Maptimize Service

```bash
ssh -i ~/.ssh/maptimize-ec2-keypair.pem -o ProxyCommand=none admin@<IP> \
  'sudo systemctl daemon-reload && \
   sudo systemctl enable maptimize && \
   sudo systemctl start maptimize'

# Verify service is running
ssh -i ~/.ssh/maptimize-ec2-keypair.pem -o ProxyCommand=none admin@<IP> \
  'sudo systemctl status maptimize'

# Check for Socket Mode connection
ssh -i ~/.ssh/maptimize-ec2-keypair.pem -o ProxyCommand=none admin@<IP> \
  'sudo journalctl -u maptimize -n 30 --follow'
```

**Expected output in journalctl:**
```
Socket Mode connected to https://wss-primary.slack.com/link/?ticket=...
```

### 5. Test Bot in Slack Workspace

In your Slack workspace:

1. **Test @mention:**
   - Type: `@maptimize` in any channel
   - Expected: Ephemeral message appears with "Service Review Process" wiki link

2. **Test slash command:**
   - Type: `/maptimize` in any channel
   - Expected: Same ephemeral response

3. **Verify bot status:**
   ```bash
   ssh -i ~/.ssh/maptimize-ec2-keypair.pem -o ProxyCommand=none admin@<IP> \
     'sudo journalctl -u maptimize -n 50 | grep -E "event|Socket|request"'
   ```

## Troubleshooting

### SSH Authentication Fails
- Verify you're using the correct key: `~/.ssh/maptimize-ec2-keypair.pem`
- Check user-data.sh has completed: `tail /var/log/user-data.log`
- Verify instance is fully booted (may take 2-3 minutes)

### Docker Image Pull Fails
- ECR credentials refresh every hour via cron job
- Manually refresh: `aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin 483013340174.dkr.ecr.eu-west-1.amazonaws.com`

### Service Doesn't Start
- Check logs: `sudo journalctl -u maptimize -n 50`
- Verify docker image exists: `docker images | grep maptimize`
- Check Slack tokens in AWS Secrets Manager

### Bot Doesn't Respond in Slack
- Verify service is running: `sudo systemctl status maptimize`
- Check for "Socket Mode connected" in logs
- Verify bot has permissions in Slack workspace
- Check for request/response in journalctl: `sudo journalctl -u maptimize -f`

## Files Reference

- **user-data.sh** - EC2 instance initialization script
- **docker-compose.production.yml** - Docker container configuration
- **maptimize.service** - systemd service definition
- **launch-ec2.sh** - EC2 instance launcher script
- **AWS Secrets Manager** - Stores Slack tokens and credentials

## Important Notes

- The maptimize-ec2-keypair.pem file is excluded from git (see .gitignore)
- Always use `-o ProxyCommand=none` for direct SSH (no bastion needed from new AWS region setup)
- EC2 instance is in eu-west-1 region with production security groups
- SSSD/LDAP integration requires Adobe corporate LDAP access
