# Diagnosing: Slack Not Delivering Events to Socket Mode

## Problem Statement

- ✅ Secret structure is correct
- ✅ Bot starts successfully
- ✅ Socket Mode connection established
- ✅ "hello" message received from Slack WebSocket
- ❌ **NO events received** (app_mention, slash_command)

This means the Socket Mode **connection** works, but Slack isn't **routing events** to it.

## Root Cause Checklist

### 1. Is the app actually installed in your workspace?

**Check:**
1. Go to https://api.slack.com/apps
2. Select your Maptimize app
3. Click **Install App** in the left sidebar
4. Check the status - it should say "Installed to [Your Workspace]"

**If it says "Not Installed" or "Reinstall Required":**
```
Click "Reinstall to Workspace" → Authorize → Allow
```

This is the #1 cause of events not being delivered.

### 2. Are Event Subscriptions configured correctly?

**Check:**
1. Go to https://api.slack.com/apps → Your App
2. Click **Event Subscriptions** in the left sidebar
3. Toggle should be **ON**
4. **Request URL** field should be **EMPTY** or show an error (this is correct for Socket Mode!)
5. Under "Subscribe to bot events", verify these are listed:
   - `app_mention`
   - `message.channels`
   - `message.groups`
   - `message.im`

**If events are missing:**
```
Click "Add Bot User Event" → Search for and add each missing event → Save Changes
```

**IMPORTANT**: If there's a Request URL filled in:
- This means the app is configured for HTTP delivery, not Socket Mode
- Slack will try to send events to that URL instead of Socket Mode
- **Delete the Request URL** (leave it blank) and save

### 3. Does the bot have the required OAuth scopes?

**Check:**
1. Go to https://api.slack.com/apps → Your App
2. Click **OAuth & Permissions** in the left sidebar
3. Scroll to **Bot Token Scopes**
4. Verify these scopes are present:
   - `app_mentions:read` - Required to receive @mentions
   - `chat:write` - Required to send messages
   - `commands` - Required to receive slash commands
   - `channels:read` - Required to access channel info
   - `users:read` - Required to get user info

**If scopes are missing:**
```
Click "Add an OAuth Scope" → Select missing scope → Save
Then: "Reinstall to Workspace" at the top of the page
```

### 4. Is Socket Mode properly enabled?

**Check:**
1. Go to https://api.slack.com/apps → Your App
2. Click **Socket Mode** in the left sidebar
3. Toggle should be **ON** with green indicator
4. Should show: "Socket Mode is enabled"

**If Socket Mode is OFF:**
```
Toggle it ON → You'll be prompted to create an app-level token
Create token with "connections:write" scope
Update your secret with the new app_token
```

### 5. Does the app-level token have the right scopes?

**Check:**
1. Go to https://api.slack.com/apps → Your App
2. Click **Basic Information** in the left sidebar
3. Scroll to **App-Level Tokens**
4. Click on your token (should be named something like "socket-mode-token")
5. Verify scopes:
   - `connections:write` - **REQUIRED** for Socket Mode
   - `authorizations:read` - Optional but recommended

**If connections:write is missing:**
```
Generate a new app-level token with the correct scope
Update your AWS secret with the new app_token
Restart the Docker container
```

### 6. Is the slash command registered?

**Check:**
1. Go to https://api.slack.com/apps → Your App
2. Click **Slash Commands** in the left sidebar
3. Verify `/maptimize` is listed
4. **Request URL** should be **EMPTY** (Socket Mode handles it)

**If command is missing:**
```
Click "Create New Command"
Command: /maptimize
Short Description: "Maptimize bot commands"
Usage Hint: [action] [parameters]
Request URL: (leave blank)
Save
```

**If Request URL is filled in:**
```
Edit the command → Clear the Request URL field → Save
```

## Diagnostic Commands

### Check Slack App Event Logs

1. Go to https://api.slack.com/apps/[YOUR_APP_ID]/event-subscriptions
2. Scroll down to **Event Logs**
3. This shows all events Slack received and where it tried to deliver them

**What to look for:**
- Events should show "Delivered to Socket Mode"
- If they show "HTTP 404" or "Connection Failed", there's a Request URL configured
- If events aren't listed at all, they're not being generated (app not installed or permissions issue)

### Test App Installation Status

In your Slack workspace:
```
1. Go to your workspace settings
2. Click "Apps" in the left sidebar
3. Search for "Maptimize"
4. Should show as "Added" with the bot icon
```

If not found, the app isn't installed in the workspace.

### Test Bot Permissions

Try this in any channel:
```
/invite @maptimize
```

**Expected results:**
- If it works: Bot has channel access
- If error "This app cannot be added": Missing OAuth scopes or not installed

### Check Your App ID

You need your App ID to check event logs:

1. Go to https://api.slack.com/apps
2. Your app name will have an ID like `A09T3NE9WBB`
3. Use this to access event logs: `https://api.slack.com/apps/A09T3NE9WBB/event-subscriptions`

## Most Common Issues (in order)

### Issue 1: App Not Installed in Workspace
**Symptom:** No events at all, even though Socket Mode connected  
**Fix:** Go to OAuth & Permissions → Install to Workspace → Authorize

### Issue 2: Request URL Configured (HTTP mode)
**Symptom:** Events show in Slack logs but not in bot logs  
**Fix:** Event Subscriptions → Clear Request URL → Save

### Issue 3: Missing Event Subscriptions
**Symptom:** Some events work but not others  
**Fix:** Event Subscriptions → Add missing bot events → Save

### Issue 4: Missing OAuth Scopes
**Symptom:** Events received but bot can't respond  
**Fix:** OAuth & Permissions → Add missing scopes → Reinstall

### Issue 5: Wrong App-Level Token Scope
**Symptom:** Socket Mode connects but immediately disconnects  
**Fix:** Create new app-level token with `connections:write`

## Quick Verification Script

Run this in your Slack workspace:

1. **Test slash command:**
   ```
   /maptimize
   ```
   Expected: Either the bot responds or you see `dispatch_failed`

2. **Test mention:**
   ```
   @maptimize help
   ```
   Expected: Either the bot responds or nothing happens

3. **Check bot presence:**
   Go to any channel → Type `@` → Start typing "maptimize"
   Expected: Bot should appear in autocomplete

4. **Invite to channel:**
   ```
   /invite @maptimize
   ```
   Expected: Bot joins the channel OR error about permissions

## Step-by-Step Fix

Follow these steps in order:

### Step 1: Verify App Installation
```
1. Go to: https://api.slack.com/apps → Your App → Install App
2. Status should show: "Installed to [Workspace]"
3. If not: Click "Install to Workspace" → Authorize
```

### Step 2: Configure Event Subscriptions
```
1. Go to: Event Subscriptions
2. Toggle: ON
3. Request URL: (must be empty)
4. Subscribe to bot events:
   - app_mention
   - message.channels
   - message.groups
   - message.im
5. Click "Save Changes"
```

### Step 3: Verify OAuth Scopes
```
1. Go to: OAuth & Permissions
2. Bot Token Scopes must include:
   - app_mentions:read
   - chat:write
   - commands
   - channels:read
   - users:read
3. If any are missing: Add them → Reinstall to Workspace
```

### Step 4: Verify Socket Mode
```
1. Go to: Socket Mode
2. Toggle: ON
3. Verify app-level token has: connections:write
```

### Step 5: Configure Slash Command
```
1. Go to: Slash Commands
2. Verify /maptimize exists
3. Request URL: (must be empty)
4. If not empty: Edit → Clear URL → Save
```

### Step 6: Test in Slack
```
1. Try: @maptimize help
2. Try: /maptimize
3. Watch Docker logs: docker logs -f maptimize-bot
4. Should see: "DEBUG: app_mention event received"
```

## Still Not Working?

### Check Slack Event Logs
1. Get your App ID from https://api.slack.com/apps
2. Go to: `https://api.slack.com/apps/[APP_ID]/event-subscriptions`
3. Scroll to "Event Logs"
4. Try triggering an event (mention the bot)
5. Check if the event appears in the log and where it was delivered

### Check App Credentials
Make sure you're using tokens from the SAME app:
```
1. Your bot_token should match: OAuth & Permissions → Bot User OAuth Token
2. Your app_token should match: Basic Information → App-Level Tokens → [Your Token]
3. Your signing_secret should match: Basic Information → App Credentials → Signing Secret
```

If you have multiple Maptimize apps, make sure you're using tokens from the deployed one.

## Expected Success Indicators

When everything is working:

1. **Docker logs show:**
   ```
   Starting Socket Mode handler...
   Socket Mode handler created, starting connection...
   Socket Mode handler started
   ```

2. **When you mention the bot:**
   ```
   DEBUG: app_mention event received
   DEBUG: app_mention handled successfully
   ```

3. **When you use slash command:**
   ```
   DEBUG: slash_command /maptimize received
   DEBUG: slash_command handled successfully
   ```

4. **Slack Event Logs show:**
   ```
   Event: app_mention
   Delivery: Socket Mode
   Status: Delivered
   ```

## Summary

The most likely issue is one of these:

1. **App not installed in workspace** (80% of cases)
2. **Request URL configured instead of Socket Mode** (15% of cases)
3. **Missing event subscriptions** (4% of cases)
4. **Wrong app-level token scope** (1% of cases)

Start with Step 1 above and work through each verification step.
