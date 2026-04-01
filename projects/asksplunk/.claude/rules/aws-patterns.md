---
paths:
  - "src/asksplunk/session/**"
  - "src/asksplunk/secrets.py"
  - "src/asksplunk/usage/**"
---
# AWS Patterns

## Async Context Managers
All AWS clients MUST use async context managers for proper resource cleanup:
```python
async with SecretsManager() as manager:
    tokens = await manager.get_slack_tokens()

async with SessionManager() as manager:
    await manager.delete_session(thread_id)  # Verified deletion
```

## DynamoDB
- Use expression attribute names for reserved keywords (e.g., `#s` for `status`)
- TTL field: `ttl` (epoch seconds), 30-minute window
- Table: `splunk-bot-sessions`
- GSI: `usage-by-timestamp` for usage tracking queries

## Secrets Manager
- Cache secrets for 60 minutes to reduce API calls
- Secret names: `splunk-bot/slack-tokens`, `splunk-bot/azure-openai`
- Authorized user list from `authorized_users` key in slack-tokens secret
- Admin user list from `admin_user_ids` key in slack-tokens secret

## Session Lifecycle
1. Create session on first message in thread
2. Store conversation history (metadata only, no message content)
3. Delete on completion — verify deletion succeeded
4. Retry once on verification failure
5. Raise `SessionDeletionError` if still present after retry
6. TTL is backup only — never rely on it as primary deletion

## Usage Tracking
- Privacy-first: timestamp only, NO user IDs
- Supported timeframes: hours, days, weeks, minutes, yesterday, today
- Natural language queries like "show usage for last 7 days"
