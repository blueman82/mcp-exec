---
name: privacy-audit
description: Comprehensive privacy and secrets audit for the AskSplunk codebase. Use when reviewing code for PII exposure, logging violations, or secrets leakage. Triggers on "audit privacy", "check for PII", "privacy scan", or explicit /privacy-audit.
allowed-tools: Read, Grep, Glob, Bash
---
# Privacy Audit

Run a comprehensive privacy and secrets audit on the AskSplunk codebase.

## Audit Steps

### 1. Secrets Scan
Search the entire `src/` directory for hardcoded tokens and credentials:
```bash
rg "xoxb-|xapp-|xoxp-" src/
rg "sk-[0-9A-Za-z]{20,}" src/
rg "AKIA[0-9A-Z]{16}" src/
rg "aws_secret_access_key" src/
```
**Expected**: All commands return zero results.

### 2. Logging Violations
Search for user content in log statements:
```bash
rg "logger?\.\w+\([^)]*\b(message|question|content|text)\s*=" src/
```
**Expected**: Zero results. All logger calls should use metadata only (user_id, channel_id, thread_ts).

### 3. Usage Tracker Compliance
Read `src/asksplunk/usage/tracker.py` and verify:
- Only timestamps are stored (no user IDs, no IP addresses)
- DynamoDB items contain only `pk`, `sk`, `ttl`, and `timestamp` fields

### 4. Session Deletion Verification
Read `src/asksplunk/session/manager.py` and verify:
- `delete_session()` performs a verification read after deletion
- Retry logic exists for failed verification
- `SessionDeletionError` is raised on final failure

### 5. Error Message Safety
Grep for exception handling that might leak internals:
```bash
rg "str\(e\)|repr\(e\)|traceback" src/asksplunk/slack/
```
Verify that error messages sent to users are generic and don't expose stack traces, ARNs, or internal details.

### 6. Slack Output Sanitization
Read `src/asksplunk/slack/formatter.py` and verify that all GPT-generated text is sanitized before insertion into Slack mrkdwn blocks. Look for `re.sub(r'<[!@][^>]+>', '', text)` or equivalent.

## Reporting

Reference @PRIVACY_PATTERNS.md for the complete pattern catalog.

Report findings in a table:
| Severity | File:Line | Finding | Recommendation |
|----------|-----------|---------|----------------|
