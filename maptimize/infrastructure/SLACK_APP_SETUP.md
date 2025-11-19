# Slack App Setup and Configuration Guide

This guide provides step-by-step instructions for creating and configuring a Slack app for the Maptimize application. This enables independent Slack app creation without relying on a shared app instance.

## Overview

The Maptimize Slack application uses Socket Mode for real-time event handling, eliminating the need for public-facing webhooks or firewall configuration. This guide covers:
- App creation and basic setup
- Required OAuth token scopes
- Event subscription configuration
- Slash command setup
- Secure token storage in AWS Secrets Manager

## Prerequisites

- Slack workspace with admin access
- AWS account with Secrets Manager access
- Access to api.slack.com

## Step 1: Create a Slack App

1. Navigate to https://api.slack.com/apps
2. Click "Create an App"
3. Select "From scratch"
4. Enter App Name: `Maptimize`
5. Select your Slack workspace
6. Click "Create App"

## Step 2: Configure Basic Information

1. In the app settings, go to "Basic Information"
2. Add app icon and description:
   - Description: "Real-time enterprise location intelligence"
   - Category: "Utilities"
3. Save the changes

## Step 3: Configure Bot Token Scopes

1. Go to "OAuth & Permissions" in the left sidebar
2. Under "Scopes" → "Bot Token Scopes", add the following scopes:
   - `app_mentions:read` - Read app mentions in channels
   - `chat:write` - Post messages to channels
   - `commands` - Register slash commands
   - `users:read` - Read user information
   - `channels:read` - Access basic channel information
   - `groups:read` - Access basic private channel information
   - `im:read` - Access direct messages
   - `team:read` - Access team information

3. Click "Save Scopes"

## Step 4: Configure App-Level Token Scopes (Socket Mode)

1. Navigate to "Socket Mode" in the left sidebar
2. Toggle "Socket Mode" to ON
3. Go back to "Basic Information" and scroll to "App-Level Tokens"
4. Click "Generate Token and Set Scopes"
5. Enter Token Name: `socket-mode-token`
6. Add the following scopes:
   - `connections:write` - Establish Socket Mode connections
   - `authorizations:read` - Read authorization information

7. Click "Generate"
8. Copy the generated token (starts with `xapp-`) and save it securely
9. Note: This token must be stored in AWS Secrets Manager, NOT in local .env files

## Step 5: Install App to Workspace

1. Go to "Install App" in the left sidebar
2. Click "Install to Workspace"
3. Review the requested permissions
4. Click "Allow"
5. You will be redirected to the OAuth credentials page

## Step 6: Retrieve and Store Bot Token

1. Go to "OAuth & Permissions"
2. Copy the "Bot User OAuth Token" (starts with `xoxb-`)
3. Store this token in AWS Secrets Manager using:

```bash
aws secretsmanager create-secret \
  --name maptimize/slack/bot-token \
  --secret-string 'xoxb-YOUR_BOT_TOKEN_HERE'
```

4. For the Socket Mode token, store using:

```bash
aws secretsmanager create-secret \
  --name maptimize/slack/socket-mode-token \
  --secret-string 'xapp-YOUR_SOCKET_MODE_TOKEN_HERE'
```

## Step 7: Configure Event Subscriptions

1. Go to "Event Subscriptions" in the left sidebar
2. Toggle "Events" to ON
3. Under "Subscribe to bot events", add the following events:
   - `app_mention` - When the app is mentioned in a channel
   - `message.channels` - Messages in channels
   - `message.groups` - Messages in private channels
   - `message.im` - Direct messages to the app

4. Do NOT enter a Request URL - Socket Mode handles event delivery
5. Note: Socket Mode initiates outbound connections, eliminating firewall requirements

## Step 8: Configure Slash Command

1. Go to "Slash Commands" in the left sidebar
2. Click "Create New Command"
3. Configure as follows:
   - Command: `/maptimize`
   - Request URL: Leave blank (Socket Mode will handle)
   - Short Description: "View location intelligence"
   - Usage hint: `[action] [options]`

4. Click "Save"

## Step 9: Verify Socket Mode Configuration

1. Go to "Socket Mode" in the left sidebar
2. Confirm that "Socket Mode" is toggled ON
3. The status should show "Socket Mode is enabled"
4. Note: No Request URL is required or used in Socket Mode

## Token Storage in AWS Secrets Manager

Tokens must NEVER be stored in local .env files or committed to version control. Use AWS Secrets Manager:

### Create Secrets

```bash
# Store bot token
aws secretsmanager create-secret \
  --name maptimize/slack/bot-token \
  --secret-string 'xoxb-YOUR_BOT_TOKEN_HERE' \
  --description "Slack Bot Token for Maptimize"

# Store socket mode token
aws secretsmanager create-secret \
  --name maptimize/slack/socket-mode-token \
  --secret-string 'xapp-YOUR_SOCKET_MODE_TOKEN_HERE' \
  --description "Slack App-Level Token for Socket Mode"
```

### Retrieve Secrets in Application

```bash
# Get bot token
aws secretsmanager get-secret-value \
  --secret-id maptimize/slack/bot-token \
  --query 'SecretString' \
  --output text

# Get socket mode token
aws secretsmanager get-secret-value \
  --secret-id maptimize/slack/socket-mode-token \
  --query 'SecretString' \
  --output text
```

### Update Secrets

```bash
# Update bot token
aws secretsmanager update-secret \
  --secret-id maptimize/slack/bot-token \
  --secret-string 'xoxb-NEW_BOT_TOKEN_HERE'

# Update socket mode token
aws secretsmanager update-secret \
  --secret-id maptimize/slack/socket-mode-token \
  --secret-string 'xapp-NEW_SOCKET_MODE_TOKEN_HERE'
```

## Socket Mode Advantages

- No public Request URL required
- No firewall rules or port forwarding needed
- Bidirectional communication initiated by the app
- More secure - connection is outbound only
- Reduced latency for event delivery
- Simplified networking architecture

## Verification Checklist

- [ ] App created at api.slack.com/apps
- [ ] Bot Token Scopes configured (8 scopes)
- [ ] App-Level Token created with connections:write scope
- [ ] Socket Mode enabled
- [ ] Event Subscriptions configured (app_mention, message events)
- [ ] Slash Command /maptimize created
- [ ] Bot token stored in Secrets Manager
- [ ] Socket mode token stored in Secrets Manager
- [ ] No .env files contain Slack tokens
- [ ] Application successfully retrieves tokens from Secrets Manager

## Troubleshooting

### Socket Mode Connection Issues
- Verify that Socket Mode is enabled in app settings
- Check that the App-Level Token is valid (starts with xapp-)
- Ensure the token has connections:write scope
- Check application logs for connection errors

### Event Delivery Issues
- Verify event types are enabled in Event Subscriptions
- Check that the app is properly subscribed to events
- Ensure Socket Mode is actively connected
- Review Slack app logs at https://api.slack.com/apps/[APP_ID]/event-logs

### Slash Command Issues
- Verify the slash command is enabled
- Check that Socket Mode is actively listening
- Ensure the app has the commands scope
- Verify command is properly registered in your application

### Token Issues
- Do not hardcode tokens in source code
- Always retrieve tokens from Secrets Manager at runtime
- Rotate tokens regularly
- If token is compromised, regenerate immediately and update Secrets Manager

## References

- [Slack API Documentation](https://api.slack.com)
- [Socket Mode Documentation](https://slack.dev/bolt-python/concepts#socket-mode)
- [OAuth Scopes Reference](https://api.slack.com/scopes)
- [Event Types Reference](https://api.slack.com/events)
- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)
