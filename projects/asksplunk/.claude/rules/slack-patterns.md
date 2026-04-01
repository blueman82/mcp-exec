---
paths:
  - "src/asksplunk/slack/**"
---
# Slack Patterns

## Output Sanitization (Critical)
GPT-5 output is **untrusted**. Sanitize before inserting into Slack mrkdwn:
```python
import re
sanitized = re.sub(r'<[!@][^>]+>', '', text)  # Strip @channel, @here, @user mentions
```
This prevents AI-generated text from pinging channels or users.

## Token Selection
- **xoxp** (user token): For DMs and user-context operations
- **xoxb** (bot token): For channel messages and bot-context operations

## Block Kit
- Use `formatter.py` builders for all message construction
- Never construct Block Kit JSON inline in handler code
- All blocks must include fallback `text` for notification previews

## Connection Resilience
- **Auth retry**: `_auth_test_with_retry()` with exponential backoff (3 attempts, 10s timeout)
- **Error classification**: `_is_fatal_slack_error()` separates fatal (`invalid_auth`, `token_revoked`) from transient errors
- **Resilient shutdown**: Each cleanup step in try/except/finally — one failure doesn't skip the rest

## Structured Logging
Use descriptive event names with underscore separation:
- `socket_mode_handler_starting`
- `socket_mode_transient_error`
- `socket_mode_fatal_error`
- `slack_client_shutdown_complete`
