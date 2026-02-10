---
name: slack-read
description: Read Slack channel messages with timestamp filtering
---

# Slack Channel Reader

Read messages from a Slack channel, with optional time filtering.

## Arguments

```
/slack-read <channel_id> [--after HH:MM:SS] [--before HH:MM:SS] [--limit N] [--date YYYY-MM-DD]
```

- `channel_id`: Slack channel ID (e.g., C04U6DQJTL4) - required
- `--after`: Start time in HH:MM:SS format (default: beginning of day)
- `--before`: End time in HH:MM:SS format (default: now)
- `--limit`: Number of messages to retrieve (default: 50, max: 200)
- `--date`: Date to query (default: today, format: YYYY-MM-DD)

## Instructions

### Step 1: Get User Token

The Slack user token is stored in AWS Secrets Manager under Ketchup_Token_Secrets.

```bash
# Get user token (xoxp-...) - for reading channels you're a member of
aws secretsmanager get-secret-value \
  --secret-id Ketchup_Token_Secrets \
  --profile campaign_prod_v7 \
  --region eu-west-1 \
  --output json | jq -r '.SecretString | fromjson | .slack_user_api_token'

# Or get bot token (xoxb-...) - for channels the bot is in
aws secretsmanager get-secret-value \
  --secret-id Ketchup_Token_Secrets \
  --profile campaign_prod_v7 \
  --region eu-west-1 \
  --output json | jq -r '.SecretString | fromjson | .slack_api_token'
```

Store the token in a variable for subsequent API calls.

**Note:** User token requires `channels:history` (public) or `groups:history` (private) OAuth scopes.

### Step 2: Convert Time to Slack Timestamp

Slack uses Unix epoch timestamps with microseconds (e.g., `1706443590.123456`).

To convert HH:MM:SS on a given date to epoch:
```bash
# For today at 12:16:30
date -j -f "%Y-%m-%d %H:%M:%S" "$(date +%Y-%m-%d) 12:16:30" "+%s"

# For specific date
date -j -f "%Y-%m-%d %H:%M:%S" "2026-01-28 12:16:30" "+%s"
```

### Step 3: Fetch Messages

Use the Slack conversations.history API:

```bash
TOKEN="xoxp-..."  # from step 1
CHANNEL="C04U6DQJTL4"
OLDEST="1706443590"  # epoch from step 2 (optional)
LIMIT=50

curl -s "https://slack.com/api/conversations.history" \
  -H "Authorization: Bearer $TOKEN" \
  -G \
  --data-urlencode "channel=$CHANNEL" \
  --data-urlencode "oldest=$OLDEST" \
  --data-urlencode "limit=$LIMIT" | jq '.'
```

### Step 4: Format Output

Parse the JSON response and format as markdown:

```bash
curl -s "https://slack.com/api/conversations.history" \
  -H "Authorization: Bearer $TOKEN" \
  -G \
  --data-urlencode "channel=$CHANNEL" \
  --data-urlencode "oldest=$OLDEST" \
  --data-urlencode "limit=$LIMIT" | jq -r '
  .messages | reverse | .[] |
  "**" + ((.ts | tonumber | strftime("%H:%M:%S")) // .ts) + "** <@" + (.user // "bot") + ">: " + (.text // "[no text]")
'
```

### Step 5: Resolve User Names (Optional)

To get readable usernames instead of IDs:

```bash
curl -s "https://slack.com/api/users.info?user=U12345678" \
  -H "Authorization: Bearer $TOKEN" | jq -r '.user.real_name'
```

## API Response Fields

| Field | Description |
|-------|-------------|
| `ts` | Message timestamp (epoch.microseconds) |
| `user` | User ID who sent the message |
| `text` | Message content |
| `thread_ts` | Thread parent timestamp (if threaded) |
| `reply_count` | Number of replies (if parent) |

## Common Issues

1. **"channel_not_found"**: You're not a member of the channel, or channel ID is wrong
2. **"not_authed"**: Token is invalid or expired
3. **"missing_scope"**: User token doesn't have required permissions (need channels:history, groups:history)

## Example Usage

Read messages from #campaign-ops-dub after 12:16:30 today:
```
/slack-read C04U6DQJTL4 --after 12:16:30
```

Read last 20 messages from yesterday:
```
/slack-read C04U6DQJTL4 --limit 20 --date 2026-01-27
```
