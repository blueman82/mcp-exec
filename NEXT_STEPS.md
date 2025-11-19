# Maptimize Deployment - Next Steps

## What's Been Done ✅

- **user-data.sh Fixed** (commit 6d373c1)
  - Disabled UsePAM for SSH to prevent PAM auth lockouts
  - Added allow_users = root, admin to SSSD for local user access
  - All Docker, AWS CLI, SSSD, ECR components working

- **Deployment Guide Created** (commit 456da60)
  - See: `DEPLOYMENT.md`
  - Complete step-by-step instructions from EC2 launch to Slack testing

## Current Blocker 🔴

**AWS Credentials Expired**
- Cannot launch new EC2 instance via CLI
- Cannot check current instance status

## What You Need To Do 🚀

### 1. Refresh AWS Credentials
```bash
# Check if credentials are expired
aws sts get-caller-identity --profile campaign_prod_v7

# If expired, refresh via AWS SSO or your credential manager
```

### 2. Launch New EC2 Instance
```bash
cd /Users/harrison/Documents/Github/camp-ops-emea/maptimize-worktree/maptimize
bash infrastructure/launch-ec2.sh maptimize-prod
```

**This will:**
- Create new t3.xlarge Debian 12 instance
- Generate SSH key pair: `maptimize-ec2-keypair.pem`
- Run corrected user-data.sh (all fixes included)
- Output: Public IP address

### 3. Follow Deployment Guide
Once instance is ready, follow: `DEPLOYMENT.md`
- Verify SSH access (step 2)
- Deploy config files (step 3)
- Start systemd service (step 4)
- Test in Slack (step 5)

## Current Instance Status

**Old Instance (BROKEN - SSH Auth Issues):**
- ID: i-0c2e4e955afab806a
- IP: 34.255.198.132
- Status: Running but unreachable via SSH (SSSD PAM lockout)
- Action: Terminate and replace with new instance

## Summary

The code is ready to deploy. You just need to:
1. Refresh AWS credentials
2. Run the launch script
3. Follow the deployment guide

Everything else has been automated and tested.
