# CSOPM Scheduler Investigation

**Date**: 2026-02-26
**Investigator**: Theo
**Codebase**: `/Users/harrison/Documents/Github/camp-ops-emea/projects/ketchup`

---

## Retrieved Prerequisites

**Theo MCP**: Unavailable (connection failed). Context derived from injected session memories.

**Problem statement (from injected memory context)**:
- `fix(csopm): wire snooze check into check_closure_reminders (#282)` — recent commit wired the snooze *read* check into `check_closure_reminders()`, but the snooze *write* (persisting `closure_snoozed_until` to DynamoDB) was never implemented.
- 4 CSOPM notification records stuck in `pending` status since Feb 20 〔m_e0c45d8cdb484ab2a1a440116e00ec3f〕
- Ketchup deployment expected to resolve stuck records 〔m_e0c45d8cdb484ab2a1a440116e00ec3f〕

**Prerequisite confidence**: Medium. No transcript data available (Theo MCP down). Problem reconstructed from commit history, injected memories, and codebase inspection.

---

## Scheduler Location

| Component | File | Key Functions |
|-----------|------|---------------|
| Entry point | `ketchup_csopm_notifier/scheduler.py` | `CSOPMScheduler.run_task()` L:144 |
| Schedule control | `ketchup_csopm_notifier/scheduler.py` | `get_sleep_seconds()` L:101 |
| Notification dispatch | `ketchup_csopm_notifier/scheduler.py` | Step 3 loop L:260–323 |
| Reminder logic | `ketchup_csopm_notifier/services/reminder_service.py` | `check_closure_reminders()` L:582, `check_rca_reminders()` L:510 |
| State persistence | `packages/slack/csopm/state.py` | `CSOPMStateTracker` L:41 |
| Button action handler | `packages/slack/csopm/actions.py` | `CSOPMButtonActionHandler._handle_snooze()` L:783 |
| Status tracker | `ketchup_csopm_notifier/services/status_poller.py` | `CSOPMTicketStatusPoller.poll_ticket_statuses()` L:129 |

**Schedule**: 08:00, 12:00, 16:00, 20:00, 00:00 UTC (5×/day, `CSOPM_SCHEDULE_TIMES` env var)
**Run-on-start**: `True` — runs immediately on container start before entering schedule loop.

---

## Issue Ranking Table

| Issue ID | Description | Fixability (in-codebase %) | Impact scope | Reproducibility | Selected |
|----------|-------------|---------------------------|--------------|-----------------|----------|
| ISS-1 | Snooze state never persisted to DynamoDB | 100% | All users who click Snooze (every cycle fires reminder anyway) | High — deterministic no-op | **YES** |
| ISS-2 | Notification record stays `pending` if `update_notification_status` fails after DM sent | 95% | 4 known stuck records since Feb 20; any future DM+update race | Medium — transient failure dependent | No |
| ISS-3 | `get_all_active_notifications` includes `pending` records in reminder eligibility | 90% | Reminders may fire for tickets where initial notification is unconfirmed | Medium | No |

**Ranking notes**: ISS-1 scores highest on all three axes. ISS-2 and ISS-3 do not tie. Proceeding with ISS-1.

---

## Root Cause Analysis — ISS-1: Snooze State Never Persisted

### Execution Flow

```
User clicks "Snooze" button in Slack DM
  → ketchup-app receives interaction payload
  → CSOPMButtonActionHandler.handle_button_action("csopm_snooze", ...)
      packages/slack/csopm/actions.py:134–135
  → _handle_snooze(user_id, ticket_key, payload)
      packages/slack/csopm/actions.py:783–825
        → _update_message_toggle_snooze_button(show_unsnooze=True)  ✓ UI updated
        → _show_confirmation_modal("Snoozed", "won't receive closure reminders for 7 days")  ✓ Modal shown
        → return True
        ← closure_snoozed_until NEVER written to DynamoDB

Next scheduler cycle (up to 8 hours later):
  → CSOPMScheduler.run_task()
      ketchup_csopm_notifier/scheduler.py:369
  → reminder_service.check_closure_reminders()
      ketchup_csopm_notifier/services/reminder_service.py:582
  → for each record, checks record.closure_snoozed_until  (line 642)
      ← Always None (never written)
  → Reminder fires anyway
```

### Evidence

**actions.py:799–800** — explicit stub comment:
```python
# Note: Snooze implementation would update StateTracker with snooze_until
logger.info("Snoozing closure reminder for %s for 7 days", ticket_key)
```
No `state_tracker` call follows. `self._state_tracker` is available in scope (injected at `__init__`, L:85) but unused in `_handle_snooze`.

**actions.py:845–847** — same for unsnooze:
```python
# Clear snooze by setting closure_snoozed_until to 0/None
# This would be done via state_tracker if we had such a method
logger.info("Unsnoozed closure reminder for %s", ticket_key)
```

**reminder_service.py:828–833** — `snooze_closure_reminder()` also a stub:
```python
# Note: This would require adding a new method to StateTracker
# For now, we log the action
logger.info("Snooze applied for %s: closure_snoozed_until=%d", ...)
return True
```

**state.py** — `CSOPMStateTracker` has no `set_closure_snooze()` or `clear_closure_snooze()` method. The `closure_snoozed_until` field is read in `_item_to_notification_record()` (L:142–144) and by `check_closure_reminders()` (L:642–651), but no write path exists in the entire codebase.

**PR #282 commit message**: `fix(csopm): wire snooze check into check_closure_reminders` — added the *reader* at L:642–653 without the corresponding *writer*. The check is now connected to a field that can never be set.

### Why the Fix Was Incomplete

PR #282 added the snooze check to `check_closure_reminders()` (correct) but the DynamoDB write method was never added to `CSOPMStateTracker`. The stub comment in `actions.py` and `reminder_service.py` predates PR #282 and was not resolved as part of that PR.

---

## Recommendation

### [Code Fix]

**Three files require changes. No external dependencies.**

---

#### 1. `packages/slack/csopm/state.py` — Add write methods

After `mark_closure_reminder_sent()` (line 494), add:

```python
async def set_closure_snooze(
    self, ticket_key: str, snooze_days: int = 7
) -> bool:
    """Set closure_snoozed_until to now + snooze_days."""
    import time as _time
    from datetime import timedelta

    snooze_until = int(
        (datetime.now(timezone.utc) + timedelta(days=snooze_days)).timestamp()
    )
    try:
        current_time = int(_time.time())
        await self.client.update_item(
            table_name=self.table_name,
            key={
                "PK": {"S": self._make_pk(ticket_key)},
                "SK": {"S": SK_NOTIFICATION},
            },
            update_expression=(
                "SET closure_snoozed_until = :snooze_until, updated_at = :updated_at"
            ),
            expression_attribute_values={
                ":snooze_until": {"N": str(snooze_until)},
                ":updated_at": {"N": str(current_time)},
            },
        )
        logger.info(
            "Set closure snooze for %s until %d (%d days)",
            ticket_key,
            snooze_until,
            snooze_days,
        )
        return True
    except Exception as e:
        logger.error("Error setting closure snooze for %s: %s", ticket_key, e)
        return False

async def clear_closure_snooze(self, ticket_key: str) -> bool:
    """Clear closure_snoozed_until (unsnooze)."""
    import time as _time

    try:
        current_time = int(_time.time())
        await self.client.update_item(
            table_name=self.table_name,
            key={
                "PK": {"S": self._make_pk(ticket_key)},
                "SK": {"S": SK_NOTIFICATION},
            },
            update_expression="REMOVE closure_snoozed_until SET updated_at = :updated_at",
            expression_attribute_values={
                ":updated_at": {"N": str(current_time)},
            },
        )
        logger.info("Cleared closure snooze for %s", ticket_key)
        return True
    except Exception as e:
        logger.error("Error clearing closure snooze for %s: %s", ticket_key, e)
        return False
```

---

#### 2. `packages/slack/csopm/actions.py` — Wire `_handle_snooze` and `_handle_unsnooze`

Replace stub comment in `_handle_snooze` (lines 798–801):

```python
# Before (lines 798-801):
# Note: Snooze implementation would update StateTracker with snooze_until
logger.info("Snoozing closure reminder for %s for 7 days", ticket_key)

# After:
if self._state_tracker:
    await self._state_tracker.set_closure_snooze(ticket_key, snooze_days=7)
logger.info("Snoozing closure reminder for %s for 7 days", ticket_key)
```

Replace stub comment in `_handle_unsnooze` (lines 845–847):

```python
# Before (lines 845-847):
# Clear snooze by setting closure_snoozed_until to 0/None
# This would be done via state_tracker if we had such a method
logger.info("Unsnoozed closure reminder for %s", ticket_key)

# After:
if self._state_tracker:
    await self._state_tracker.clear_closure_snooze(ticket_key)
logger.info("Unsnoozed closure reminder for %s", ticket_key)
```

---

#### 3. Protocol addition required

`set_closure_snooze` and `clear_closure_snooze` must be added to `CSOPMStateTrackerProtocol` in `packages/core/typed_di/protocols.py` (search for `CSOPMStateTrackerProtocol`). Without this, type checking will fail if protocol conformance is enforced at container resolution time.

```python
@abstractmethod
async def set_closure_snooze(self, ticket_key: str, snooze_days: int = 7) -> bool: ...

@abstractmethod
async def clear_closure_snooze(self, ticket_key: str) -> bool: ...
```

**Rationale**: The `reminder_service.snooze_closure_reminder()` stub is a separate method that is not called from the main scheduler cycle — the main path goes through `actions.py` button handlers. Leave `reminder_service.snooze_closure_reminder()` as-is for now (it is not wired into any active call path per code review).

**No approval needed**: All changes are within this codebase, no schema migration required (DynamoDB is schemaless; `closure_snoozed_until` is already read and parsed in `_item_to_notification_record` at line 142).

---

## Confidence and Assumptions

**Confidence: 87%**

**Assumptions**:
1. The "scheduler issue from recent finding" refers to snooze being non-functional, triggered by PR #282 wiring the read check without the write. If the intended issue is the stuck-pending records (ISS-2), see the issue ranking table — that fix requires combining `create_notification_record` + `update_notification_status` into a single atomic operation.
2. `CSOPMStateTrackerProtocol` is enforced at TypedDI resolution time and must be updated alongside the concrete implementation.
3. `reminder_service.snooze_closure_reminder()` is not called from any active scheduler path — confirmed by reading `scheduler.py`. If it is wired in a future call, it also needs the same DynamoDB write.
4. Theo MCP was unavailable; no transcript search was performed. Problem statement reconstructed from git log + injected memories.
