# Privacy Pattern Catalog

## Secrets Patterns

| Pattern | Description | Regex |
|---------|-------------|-------|
| Slack bot token | Bot OAuth token | `xoxb-[0-9A-Za-z\-]+` |
| Slack app token | App-level token | `xapp-[0-9A-Za-z\-]+` |
| Slack user token | User OAuth token | `xoxp-[0-9A-Za-z\-]+` |
| OpenAI API key | API key for Azure OpenAI | `sk-[0-9A-Za-z]{20,}` |
| AWS access key | IAM access key ID | `AKIA[0-9A-Z]{16}` |
| AWS secret key | IAM secret access key | `aws_secret_access_key\s*=\s*['"][^'"]+['"]` |

## Logging Violation Patterns

| Pattern | Description | Regex |
|---------|-------------|-------|
| Message content | User message in log call | `logger?\.\w+\([^)]*\bmessage\s*=` |
| Question content | User question in log call | `logger?\.\w+\([^)]*\bquestion\s*=` |
| Text content | Generic text in log call | `logger?\.\w+\([^)]*\btext\s*=` |
| Query content | User query in log call | `logger?\.\w+\([^)]*\bquery\s*=` |
| GPT response | AI response in log call | `logger?\.\w+\([^)]*\bresponse\s*=` |

## PII Patterns

| Pattern | Description | Regex |
|---------|-------------|-------|
| Email address | Email in string literals | `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}` |
| Phone (intl) | International phone number | `\+[0-9]{1,3}[\s.-]?[0-9]{6,14}` |
| IP address | IPv4 address in logs | `\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b` |

## Slack Injection Patterns

| Pattern | Description | Regex |
|---------|-------------|-------|
| @channel | Channel-wide mention | `<!channel>` |
| @here | Active users mention | `<!here>` |
| @everyone | All members mention | `<!everyone>` |
| User mention | Direct user ping | `<@U[A-Z0-9]+>` |

## Safe Logging Examples

```python
# GOOD: metadata only
logger.info("query_received", user=user_id, channel=channel_id, thread_ts=ts)
logger.info("session_created", thread_id=thread_id, ttl=ttl_epoch)
logger.info("agent_complete", state=state.value, confidence=confidence)

# BAD: contains user content
logger.info("query_received", message=text)  # VIOLATION
logger.info("agent_response", content=response)  # VIOLATION
logger.info("search_query", query=user_query)  # VIOLATION
```
