# Maptimize Deployment Diagnostic Guide

## Problem Summary

Your Slack app isn't communicating with the EC2 instance, resulting in:
- `/maptimize` commands showing `dispatch_failed`
- `@maptimize` mentions not triggering any response
- No events appearing in Docker logs

## Root Cause Analysis

Based on code review, the most likely issues are:

### 1. **Secret Structure Mismatch** (MOST LIKELY)

The application expects specific key names in AWS Secrets Manager:

**What the code expects** (`src/maptimize/config.py`):
```json
{
  "bot_token": "xoxb-...",
  "app_token": "xapp-...",
  "signing_secret": "..."
}
```

**What the docs show**:
```json
{
  "SLACK_BOT_TOKEN": "xoxb-...",
  "SLACK_APP_TOKEN": "xapp-..."
}
```

If your secret uses the documented format, the app will fail to start because it can't find the required keys.

### 2. **Missing Signing Secret**

The code **requires** a `signing_secret` for request verification, but this isn't mentioned in the deployment documentation. Without it, the app cannot verify that incoming Slack requests are authentic.

### 3. **Socket Mode Not Enabled**

Socket Mode must be enabled in your Slack app configuration at `https://api.slack.com/apps`.

## Diagnostic Steps

### Step 1: Run Diagnostics on EC2 Instance

SSH to your EC2 instance and run the diagnostic script:

```bash
# SSH to EC2
ssh -i ~/.ssh/maptimize-ec2-keypair.pem admin@<your-ec2-ip>

# Run diagnostics
cd /opt/maptimize
bash /path/to/diagnose-deployment.sh
```

Or download it first:
```bash
# On EC2 instance
curl -O https://raw.githubusercontent.com/.../diagnose-deployment.sh
chmod +x diagnose-deployment.sh
./diagnose-deployment.sh
```

This script will check:
- Docker container status
- Container logs
- AWS credentials
- Secret structure (keys, not values)
- Network connectivity
- Environment variables

### Step 2: Check Secret Structure

The diagnostic script will show which keys are in your secret. If you see:

```
Keys in secret:
  SLACK_BOT_TOKEN
  SLACK_APP_TOKEN
```

Instead of:
```
Keys in secret:
  bot_token
  app_token
  signing_secret
```

Then you need to fix the secret structure (see below).

### Step 3: Get Your Signing Secret

1. Go to https://api.slack.com/apps
2. Select your Maptimize app
3. Navigate to **Basic Information**
4. Scroll down to **App Credentials**
5. Find **Signing Secret** and click "Show"
6. Copy the value

### Step 4: Fix Secret Structure

Run the fix script on your local machine (or EC2 if you have AWS credentials there):

```bash
cd maptimize/infrastructure
./fix-secret-structure.sh
```

This script will:
1. Read your current secret
2. Extract any existing tokens
3. Prompt for the signing secret
4. Update the secret with the correct structure

Or manually update the secret:

```bash
aws secretsmanager update-secret \
  --secret-id maptimize/slack-tokens \
  --region eu-west-1 \
  --secret-string '{
    "bot_token": "xoxb-YOUR-BOT-TOKEN",
    "app_token": "xapp-YOUR-APP-TOKEN",
    "signing_secret": "YOUR-SIGNING-SECRET"
  }'
```

### Step 5: Verify Slack App Configuration

Check these settings at https://api.slack.com/apps:

#### Socket Mode
- Navigate to: **Socket Mode**
- Toggle: **ON**
- Status should show: "Socket Mode is enabled"

#### Event Subscriptions
- Navigate to: **Event Subscriptions**
- Toggle: **ON**
- Subscribe to bot events:
  - `app_mention`
  - `message.channels`
  - `message.groups`
  - `message.im`

#### Slash Commands
- Navigate to: **Slash Commands**
- Verify `/maptimize` command exists
- Request URL should be blank (Socket Mode handles this)

#### OAuth Scopes
- Navigate to: **OAuth & Permissions** → **Scopes**
- Bot Token Scopes should include:
  - `app_mentions:read`
  - `chat:write`
  - `commands`
  - `users:read`
  - `channels:read`

#### App-Level Token
- Navigate to: **Basic Information** → **App-Level Tokens**
- Verify token exists with scopes:
  - `connections:write`
  - `authorizations:read`

### Step 6: Restart Container

After fixing the secret, restart the Docker container:

```bash
# On EC2 instance
docker restart maptimize-bot

# Watch logs
docker logs -f maptimize-bot
```

Look for these success indicators in logs:
```
Starting Socket Mode handler...
Socket Mode handler created, starting connection...
Socket Mode handler started
```

### Step 7: Test

Test in Slack:
1. Try: `@maptimize help`
2. Try: `/maptimize`

Monitor logs on EC2:
```bash
docker logs -f maptimize-bot
```

You should see:
```
DEBUG: app_mention event received
DEBUG: slash_command /maptimize received
```

## Testing Tools

### Test Slack Configuration (Local)

Run this from your local machine to test tokens:

```bash
cd maptimize/infrastructure
python3 test-slack-config.py
```

This will:
- Fetch the secret from AWS
- Validate token formats
- Test bot token authentication
- Check required scopes
- Provide a configuration checklist

### Check Container Health

```bash
# On EC2
docker inspect --format='{{.State.Health.Status}}' maptimize-bot

# Should show: healthy
```

### View Container Logs

```bash
# On EC2
docker logs -f maptimize-bot

# Last 100 lines
docker logs --tail 100 maptimize-bot

# Follow with timestamps
docker logs -f --timestamps maptimize-bot
```

## Common Error Messages

### "Failed to fetch Slack tokens: Missing key bot_token in secret"

**Problem**: Secret structure doesn't match code expectations.

**Fix**: Run `fix-secret-structure.sh` to update the secret.

### "dispatch_failed" in Slack

**Problem**: Slack cannot deliver the slash command.

**Possible causes**:
1. Socket Mode not enabled
2. App not connected to Socket Mode
3. Container not running
4. App crashed on startup

**Fix**: Check container logs, verify Socket Mode is enabled.

### No logs appearing when testing

**Problem**: Events aren't reaching the app.

**Possible causes**:
1. Socket Mode connection not established
2. Event subscriptions not configured
3. Bot not installed in workspace
4. Wrong tokens

**Fix**: Run diagnostic script, check Slack app config.

### "RuntimeError: Failed to fetch Slack tokens"

**Problem**: Cannot access AWS Secrets Manager.

**Possible causes**:
1. IAM role not attached to EC2 instance
2. Wrong secret ID
3. Wrong region
4. Secret doesn't exist

**Fix**:
```bash
# Check IAM role
aws sts get-caller-identity

# Check secret exists
aws secretsmanager describe-secret \
  --secret-id maptimize/slack-tokens \
  --region eu-west-1
```

## Quick Reference

### Secret ID
```
maptimize/slack-tokens
```

### Region
```
eu-west-1
```

### Required Secret Keys
```json
{
  "bot_token": "xoxb-...",
  "app_token": "xapp-...",
  "signing_secret": "..."
}
```

### Docker Commands
```bash
# Check status
docker ps | grep maptimize

# View logs
docker logs -f maptimize-bot

# Restart
docker restart maptimize-bot

# Stop/remove
docker stop maptimize-bot
docker rm maptimize-bot

# Check health
docker inspect --format='{{.State.Health.Status}}' maptimize-bot
```

### Slack API Links
- Your Apps: https://api.slack.com/apps
- Socket Mode Docs: https://api.slack.com/apis/connections/socket
- Event Types: https://api.slack.com/events

## Next Steps After Fixing

1. **Monitor for 24 hours**: Check CloudWatch logs, container health
2. **Set up alerts**: Configure CloudWatch alarms for errors
3. **Document any changes**: Update team documentation
4. **Test all features**: Verify slash commands, mentions, etc.
5. **Update deployment docs**: Fix the secret structure documentation

## Files Created

Three diagnostic tools have been created in `infrastructure/`:

1. **`diagnose-deployment.sh`** - Run on EC2 to diagnose issues
2. **`fix-secret-structure.sh`** - Fix AWS secret structure
3. **`test-slack-config.py`** - Test Slack tokens and configuration

## Support

If issues persist after following this guide:

1. Check Slack event logs: https://api.slack.com/apps/[YOUR_APP_ID]/event-subscriptions
2. Review full container logs: `docker logs --tail 1000 maptimize-bot > logs.txt`
3. Verify IAM permissions on EC2 instance
4. Check security group allows outbound HTTPS (443)

## Summary Checklist

- [ ] Run `diagnose-deployment.sh` on EC2
- [ ] Verify secret has correct keys: `bot_token`, `app_token`, `signing_secret`
- [ ] Get signing secret from Slack app settings
- [ ] Run `fix-secret-structure.sh` to update secret
- [ ] Verify Socket Mode is enabled in Slack app
- [ ] Verify Event Subscriptions are configured
- [ ] Restart Docker container
- [ ] Monitor logs: `docker logs -f maptimize-bot`
- [ ] Test: `@maptimize help` and `/maptimize`
- [ ] Verify events appear in Docker logs
