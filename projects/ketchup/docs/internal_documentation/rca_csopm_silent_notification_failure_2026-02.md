# RCA: CSOPM Notifications Silently Failing (4+ Weeks)

**Filed:** 2026-02-26
**Deadline:** 2026-02-27
**PR:** #271 — `fix(csopm): DynamoDB pagination + notification status transition`
**Severity:** High — production feature silently non-functional since launch
**Service:** `ketchup-csopm-notifier` (singleton on prod1)

---

## Summary

The CSOPM Slack DM notification feature was silently non-functional from approximately launch date (~Jan 21, 2026) through Feb 25, 2026. Two independent bugs in `packages/slack/csopm/state.py` and `ketchup_csopm_notifier/scheduler.py` caused all DynamoDB scan operations to silently truncate results, and all successfully-delivered notifications to remain permanently stuck in `pending` status — producing no errors, no alerts, and no observable signal of failure.

---

## Timeline

| Date | Event |
|------|-------|
| ~2026-01-21 | CSOPM notifier service deployed to production (PR #202) |
| 2026-01-21 – 2026-02-20 | Notifier runs 5x daily; no DM notifications delivered to CSOPM assignees |
| 2026-02-20 | 4 CSOPM_NOTIFICATION# records accumulate in DynamoDB with `notification_status = pending` (stuck) |
| 2026-02-25 | Investigation identifies root causes; PR #271 filed |
| 2026-02-25 21:05 UTC | PR #271 merged to main |
| 2026-02-25 21:16 UTC | Deployed to production via release pipeline |
| 2026-02-26 | Post-deployment verification pending (AWS token refresh required) |
| 2026-02-27 | RCA filing deadline |

---

## Root Causes

### Bug 1: DynamoDB Scan Pagination Truncation (state.py)

**File:** `packages/slack/csopm/state.py`
**Methods affected:**
- `get_pending_notifications()` (line ~583)
- `get_all_active_notifications()` (line ~683)
- `get_all_notification_records()` (line ~735)

**What happened:** All three scan methods called `self.client.scan(...)` without handling DynamoDB's `LastEvaluatedKey` pagination. DynamoDB scans return at most 1MB of data per call; any results beyond that page boundary are silently dropped. The `ketchup_channel_information` table contains ~11,016 items. The CSOPM records use a `CSOPM_NOTIFICATION#` key prefix, which places them at an arbitrary position in the scan order. When those records fell on a page beyond the first 1MB, the scan returned zero CSOPM records.

**Before (broken):**
```python
response = await self.client.scan(
    table_name=self.table_name,
    filter_expression=filter_expression,
    expression_attribute_values={...},
)
items = response.get("Items", [])
```

**After (fixed):**
```python
scan_kwargs: dict = {
    "table_name": self.table_name,
    "filter_expression": filter_expression,
    "expression_attribute_values": {...},
}
items = []
while True:
    response = await self.client.scan(**scan_kwargs)
    items.extend(response.get("Items", []))
    last_key = response.get("LastEvaluatedKey")
    if not last_key:
        break
    scan_kwargs["exclusive_start_key"] = last_key
```

### Bug 2: Notification Status Never Transitioned to `sent` (scheduler.py)

**File:** `ketchup_csopm_notifier/scheduler.py`, line 297
**What happened:** After successfully delivering a Slack DM, the scheduler incremented `notification_count` and logged success — but never called `state_tracker.update_notification_status(ticket.key, "sent")`. Every notified ticket remained `notification_status = "pending"` indefinitely. This meant:
1. The duplicate-prevention logic (which queries for `pending` records before deciding to skip) would never skip a ticket, causing repeated re-notification on every scheduler run — except that Bug 1 prevented those records from being found anyway, so no duplicates were actually sent.
2. Monitoring/metrics for delivered notifications showed zero `sent` transitions, giving no observable signal.

**Before (broken):** No status update after successful DM send.

**After (fixed):**
```python
await state_tracker.update_notification_status(ticket.key, "sent")
```
Wrapped in `try/except` to prevent status update failures from blocking the notification count increment.

---

## Why No Alert Was Raised

1. **No error surfaced:** Both bugs fail silently. Pagination truncation returns `[]` without error. Missing status update produces no exception.
2. **Log inspection required:** The scheduler logs "Sent notification for X to Y" at INFO level — but this message was never reached because the upstream scan returned zero records. The absence of that log line would only be noticed on deliberate audit.
3. **No monitoring for zero-notification runs:** The scheduler had no alerting for runs where 0 notifications were sent despite active CSOPM tickets existing in DynamoDB.
4. **Compound masking:** Bug 1 prevented records from being found by the "already notified" check. Bug 2 would have caused repeated re-notification if Bug 1 were fixed alone. The two bugs partially cancelled each other's observable symptoms.

---

## Impact

- **Duration:** ~35 days (Jan 21 – Feb 25, 2026)
- **Affected users:** All CSOPM ticket assignees during this period — received no Slack DM notification upon ticket assignment
- **Affected records:** 4 CSOPM_NOTIFICATION# records stuck in `pending` state as of Feb 20 investigation (may be more post-fix if new tickets arrived)
- **Downstream effect:** RCA and closure reminders dependent on `notification_status = sent` transition were also never triggered

---

## Fix (PR #271)

**Merged:** 2026-02-25 21:05 UTC
**Changes:**
1. `packages/slack/csopm/state.py` — Added `while/LastEvaluatedKey` pagination loops to all three scan methods (50+ lines, applied uniformly)
2. `ketchup_csopm_notifier/scheduler.py` — Added `update_notification_status(ticket.key, "sent")` call after successful DM delivery

**Scope note:** The same pagination fix was applied in parallel PRs (#274–#277) to all other DynamoDB scan methods across the codebase (access-requests, user-store, command-tracking, flag-review) as a defensive sweep.

---

## Post-Deployment Verification

**Status:** Pending — requires fresh `campaign_prod_v7` AWS credentials.

**Verification command:**
```bash
AWS_PROFILE=campaign_prod_v7 aws dynamodb scan \
  --table-name ketchup_channel_information \
  --filter-expression "begins_with(PK, :pk_prefix) AND SK = :sk" \
  --expression-attribute-values '{":pk_prefix":{"S":"CSOPM_NOTIFICATION#"},":sk":{"S":"NOTIFICATION"}}' \
  --projection-expression "ticket_key, notification_status, created_at, updated_at" \
  --region eu-west-1
```

**Expected outcome:** All records with `created_at` before Feb 25 21:16 UTC should now show `notification_status = sent` (or `pending` if they were created after the deploy and are awaiting the next scheduler run at 08:00/12:00/16:00/20:00/00:00 UTC).

---

## Preventive Actions

| Action | Owner | Status |
|--------|-------|--------|
| Add alerting when CSOPM scheduler runs with 0 notifications sent but active DynamoDB records exist | Gary | TODO |
| Add test coverage for multi-page DynamoDB scan paths (mock `LastEvaluatedKey` response) | Gary | TODO |
| Pagination sweep complete across all other scan methods (PRs #274–#277) | Gary | Done |
| Add `notification_status` transition to `sent` post-delivery | Gary | Done (PR #271) |

---

## Lessons Learned

1. **DynamoDB scans on shared tables require pagination by default.** A scan on a table with O(10k) items will routinely exceed the 1MB single-page limit. Every new scan operation must handle `LastEvaluatedKey` from day one.
2. **Silent zero-result scans are hard to detect.** An empty list is a valid return value. Without asserting "we expect N results given K known records exist," this class of bug is invisible in logs.
3. **Status field writes should be coupled to delivery, not left as implicit.** The `notification_status` field existed and had a defined transition path but no code to drive it. State machine transitions that aren't enforced by the write path will drift.
