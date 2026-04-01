---
paths:
  - "src/**/*.py"
---
# Privacy Rules (Critical)

## Logging
- **NEVER log message content** — metadata only (user_id, channel_id, thread_ts)
- **NEVER log user questions**, query text, or GPT responses
- Use structlog with named fields: `logger.info("event_name", user=user_id, channel=channel_id)`
- Forbidden log params: `message=`, `question=`, `content=`, `text=`, `query=` (when containing user data)

## Secrets
- **NEVER hardcode tokens** — no `xoxb-`, `xapp-`, `sk-`, `AKIA` patterns in source
- All secrets from AWS Secrets Manager via `SecretsManager` class
- No secrets in environment variables at build time

## Usage Tracking
- Records **timestamp only** — NO user IDs stored
- DynamoDB GSI `usage-by-timestamp` on `splunk-bot-sessions` table
- Admin access list is dynamic from `admin_user_ids` in `splunk-bot/slack-tokens` secret

## Session Data
- **Verified deletion**: Don't rely on TTL alone, verify after delete, retry once, raise `SessionDeletionError` on failure
- DynamoDB TTL (30 min) is backup mechanism only

## Verification Commands
```bash
rg "log.*user.*message|logger.*question" src/  # Must return nothing
rg "xoxb-|xapp-|sk-" src/                       # Must return nothing
```
