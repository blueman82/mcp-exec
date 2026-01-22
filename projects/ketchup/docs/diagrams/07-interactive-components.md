# Interactive Components Flow

This sequence diagram shows how Ketchup handles interactive Slack components (buttons, modals, select menus). The primary example is the Access Request flow, which demonstrates the complete lifecycle from button click to approval workflow, with additional examples of other interactive component types.

```mermaid
sequenceDiagram
    autonumber
    participant User as 👤 User<br/>(Alice)
    participant Slack as 📱 Slack API
    participant ALB as ⚖️ AWS ALB
    participant FastAPI as 🚀 FastAPI<br/>(main.py)
    participant Verify as 🔐 Signature Verifier
    participant BG as ⏳ BackgroundTasks
    participant Router as 🔀 Payload Router<br/>(payload_processor.py)
    participant Handler as ⚙️ Access Request<br/>Handler
    participant DDB as 💾 DynamoDB
    participant Secrets as 🔐 Secrets Manager
    participant Admin as 👨‍💼 Admin<br/>(Bob)

    Note over User,Admin: 📋 PHASE 1: Initial Request (Button Click)
    
    User->>Slack: /ketchup access request
    Note right of User: User wants to request<br/>access to Ketchup
    
    Slack->>FastAPI: POST /slack/commands
    FastAPI->>FastAPI: Process command
    FastAPI->>User: Show access request form<br/>(Modal or message)
    
    User->>Slack: Fill justification:<br/>"Need access for on-call duties"<br/>Click "Submit Request"
    
    Slack->>+ALB: POST /slack/interactions<br/>(Interactive payload)
    Note right of Slack: Payload type:<br/>block_actions
    
    ALB->>+FastAPI: Route to ketchup-app
    FastAPI->>+Verify: Verify Slack signature
    Verify->>Verify: Check timestamp + HMAC
    Verify-->>-FastAPI: ✅ Valid
    
    FastAPI-->>-ALB: HTTP 200 OK
    ALB-->>-Slack: 200 OK
    Slack-->>User: ✅ Request submitted
    
    Note over BG,Handler: 📋 PHASE 2: Background Processing
    
    FastAPI->>+BG: Spawn background task
    BG->>+Router: Route payload by type
    
    Router->>Router: Parse payload JSON:<br/>- type: "block_actions"<br/>- action_id: "request_access"<br/>- user_id: "U123"<br/>- value: "justification"
    
    Router->>+Handler: Route to:<br/>access_request_handler.py
    
    Handler->>Handler: Extract data:<br/>- user_id: U123<br/>- user_name: @alice<br/>- justification: "Need access..."<br/>- timestamp: 1699876543
    
    Handler->>+DDB: Store access request
    DDB->>DDB: Write to access_requests table
    DDB-->>-Handler: ✅ Stored
    
    Handler->>Handler: Format approval message:<br/>Blocks with:<br/>- User info<br/>- Justification<br/>- Approve/Deny buttons
    
    Handler->>Slack: POST to ACCESS_REQUEST_CHANNEL<br/>(C0ADMIN123)
    Note right of Handler: Message includes:<br/>• User: @alice (U123)<br/>• Justification<br/>• Timestamp<br/>• [Approve] [Deny] buttons
    
    Slack-->>Handler: 200 OK (message posted)
    Handler-->>-Router: Request processed
    Router-->>-BG: Complete
    BG-->>-FastAPI: Background task done
    
    Note over Admin,Slack: 📋 PHASE 3: Admin Approval (Button Click)
    
    Admin->>Slack: Views message in<br/>ACCESS_REQUEST_CHANNEL
    Admin->>Slack: Clicks "Approve" button
    
    Slack->>+ALB: POST /slack/interactions<br/>(Approval payload)
    Note right of Slack: Payload type:<br/>block_actions<br/>action_id: approve_access
    
    ALB->>+FastAPI: Route to ketchup-app
    FastAPI->>+Verify: Verify signature
    Verify-->>-FastAPI: ✅ Valid
    FastAPI-->>-ALB: HTTP 200 OK
    ALB-->>-Slack: 200 OK
    
    FastAPI->>+BG: Spawn background task
    BG->>+Router: Route approval payload
    
    Router->>Router: Parse payload:<br/>- action_id: "approve_access"<br/>- approved_user_id: U123<br/>- admin_user_id: U456<br/>- request_id: req_789
    
    Router->>+Handler: Route to access handler
    
    Handler->>+DDB: Get access request
    DDB-->>-Handler: Request data
    
    Handler->>Handler: Validate:<br/>- Request exists<br/>- Not already processed<br/>- Admin has permission
    
    Handler->>+Secrets: Get authorized_slack_user_ids
    Secrets-->>-Handler: Current list:<br/>[U999, U888, U777]
    
    Handler->>Handler: Add U123 to list:<br/>[U999, U888, U777, U123]
    
    Handler->>+Secrets: Update authorized_slack_user_ids
    Secrets->>Secrets: Update secret value
    Secrets-->>-Handler: ✅ Updated
    
    Handler->>+DDB: Update request status
    DDB->>DDB: SET status = "approved"<br/>SET approved_by = U456<br/>SET approved_at = timestamp
    DDB-->>-Handler: ✅ Updated
    
    Handler->>Slack: Update message in<br/>ACCESS_REQUEST_CHANNEL
    Note right of Handler: Update shows:<br/>✅ APPROVED by @bob<br/>Buttons disabled
    
    Handler->>Slack: Send DM to @alice
    Note right of Handler: Welcome message:<br/>"Your access has been approved!<br/>Try /ketchup status"
    
    Handler->>Slack: Notify admin channel
    Note right of Handler: "@alice has been granted<br/>access by @bob"
    
    Slack-->>Handler: All messages sent
    Handler-->>-Router: Approval processed
    Router-->>-BG: Complete
    BG-->>-FastAPI: Background task done
    
    Note over User: ✅ User now has access
    
    User->>Slack: /ketchup status
    Slack->>FastAPI: POST /slack/commands
    FastAPI->>Secrets: Check authorized users
    Secrets-->>FastAPI: U123 is authorized ✅
    FastAPI->>User: ✅ Command executed

    rect rgb(230, 240, 255)
        Note over User,Admin: 🔄 OTHER INTERACTIVE COMPONENTS
    end
```

## Additional Interactive Component Examples

### 2. Trust Endorsement Flow

```mermaid
sequenceDiagram
    participant User1 as 👤 User A
    participant User2 as 👤 User B
    participant Slack as 📱 Slack
    participant Ketchup as 🤖 Ketchup
    participant DDB as 💾 DynamoDB

    User1->>Slack: @User B is trustworthy!
    Slack->>Ketchup: event_callback (message)
    
    Ketchup->>Ketchup: Detect endorsement pattern
    Ketchup->>DDB: Check if trust_endorsement_enabled
    DDB-->>Ketchup: ✅ Enabled
    
    Ketchup->>Slack: Post endorsement confirmation<br/>with "Record" button
    
    User1->>Slack: Click "Record Endorsement"
    Slack->>Ketchup: POST /slack/interactions<br/>(block_actions)
    
    Ketchup->>DDB: Store endorsement:<br/>- endorser: User A<br/>- endorsed: User B<br/>- context: message text
    
    Ketchup->>Slack: Update message:<br/>"✅ Endorsement recorded"
    Ketchup->>User2: Send DM:<br/>"User A endorsed you!"
```

**Handler**: `trust_endorsement_handler.py`

**Flow**:
1. User mentions another user with trust-related keywords
2. Ketchup detects pattern and posts confirmation button
3. User clicks "Record Endorsement"
4. Endorsement stored in DynamoDB
5. Endorsed user receives notification

---

### 3. CSOPM Notification Interactive Buttons

```mermaid
sequenceDiagram
    participant Scheduler as ⏰ CSOPM Scheduler<br/>(prod1)
    participant JIRA as 🎫 JIRA API<br/>(via MCP)
    participant Slack as 📱 Slack
    participant User as 👤 Assignee
    participant DDB as 💾 DynamoDB
    participant App as 🚀 ketchup-app

    Note over Scheduler,App: 📋 PHASE 1: Notification (08:00/16:00 UTC)

    Scheduler->>JIRA: Poll CSOPM assignments
    JIRA-->>Scheduler: New ticket CPGNCX-12345<br/>assigned to alice@adobe.com

    Scheduler->>Scheduler: Look up Slack ID<br/>for alice@adobe.com

    Scheduler->>DDB: Check if already notified
    DDB-->>Scheduler: Not found

    Scheduler->>Slack: Send DM to @alice<br/>with ticket details +<br/>interactive buttons
    Note right of Scheduler: Buttons:<br/>• Acknowledge<br/>• Mark Complete<br/>• Close Ticket<br/>• Snooze<br/>• Stop Reminders

    Scheduler->>DDB: Store notification record<br/>(PK: CSOPM_NOTIFICATION#CPGNCX-12345)

    Note over User,App: 📋 PHASE 2: User Interaction (Acknowledge)

    User->>Slack: Click "Acknowledge"
    Slack->>App: POST /slack/interactions<br/>(block_actions)

    App->>App: Route to CSOPMButtonActionHandler
    App->>DDB: Update notification_status = "ack"
    App->>Slack: Update message:<br/>"✅ Acknowledged"

    Note over User,App: 📋 PHASE 3: Mark Complete (with Modal)

    User->>Slack: Click "Mark Complete"
    Slack->>App: POST /slack/interactions

    App->>JIRA: Get transition fields<br/>for "Complete" status
    JIRA-->>App: Required fields:<br/>resolution, comment

    App->>Slack: Open modal with<br/>dynamic JIRA fields

    User->>Slack: Fill fields + Submit
    Slack->>App: POST /slack/interactions<br/>(view_submission)

    App->>JIRA: Transition ticket<br/>with user's PAT
    JIRA-->>App: ✅ Transitioned

    App->>DDB: Update completed_at
    App->>Slack: Update DM:<br/>"✅ Ticket marked complete"
```

**Handler**: `packages/slack/csopm/actions.py` → `CSOPMButtonActionHandler`

**Button Actions:**

| Action ID | Description | Handler Method |
|-----------|-------------|----------------|
| `csopm_acknowledge` | Mark notification as seen | `_handle_acknowledge()` |
| `csopm_mark_complete` | Open modal for ticket completion | `_handle_mark_complete()` |
| `csopm_close_ticket` | Open modal for ticket closure | `_handle_close_ticket()` |
| `csopm_snooze` | Pause reminders temporarily | `_handle_snooze()` |
| `csopm_unsnooze` | Resume reminders | `_handle_unsnooze()` |
| `csopm_stop_reminders` | Stop all reminders | `_handle_stop_reminders()` |
| `csopm_enable_reminders` | Re-enable reminders | `_handle_enable_reminders()` |

**Modal Submissions:**

| Callback ID | Description |
|-------------|-------------|
| `csopm_complete_modal` | Transition ticket to complete with dynamic fields |
| `csopm_close_modal` | Transition ticket to closed with dynamic fields |

**DynamoDB State Keys:**
- `PK`: `CSOPM_NOTIFICATION#{ticket_key}`
- `SK`: `NOTIFICATION` (main record) or `FOLLOWUP#{followup_key}` (followups)

**Split Architecture:**
- **Scheduler container** (`ketchup-csopm-notifier`): Polls JIRA, sends initial DMs
- **App container** (`ketchup-app`): Handles button callbacks via shared `packages/slack/csopm/` code

---

### 4. Flag Review Interactive Form

```mermaid
sequenceDiagram
    participant Admin as 👨‍💼 Admin
    participant Slack as 📱 Slack
    participant Ketchup as 🤖 Ketchup
    participant DDB as 💾 DynamoDB

    Admin->>Slack: /ketchup feature flag-review
    Slack->>Ketchup: POST /slack/commands
    
    Ketchup->>DDB: Fetch all feature flags
    DDB-->>Ketchup: Flag states
    
    Ketchup->>Slack: Open modal with:<br/>- Feature toggles<br/>- Current states<br/>- Enable/disable buttons
    
    Admin->>Slack: Toggle "status_updater"<br/>for channel C123
    Slack->>Ketchup: POST /slack/interactions<br/>(view_submission)
    
    Ketchup->>DDB: Update flag:<br/>features.status_updater_enabled = true
    DDB-->>Ketchup: ✅ Updated
    
    Ketchup->>Slack: Close modal
    Ketchup->>Admin: Post confirmation:<br/>"✅ status_updater enabled for C123"
```

**Handler**: `flag_review_handler.py`

**Flow**:
1. Admin executes `/ketchup feature flag-review`
2. Ketchup opens modal with all feature flags
3. Admin toggles features via interactive form
4. Ketchup updates DynamoDB
5. Confirmation posted to channel

---

### 5. Feedback Reactions

```mermaid
sequenceDiagram
    participant User as 👤 User
    participant Slack as 📱 Slack
    participant Ketchup as 🤖 Ketchup
    participant DDB as 💾 DynamoDB

    Ketchup->>Slack: Post status update message
    Note right of Ketchup: Message includes:<br/>👍 👎 reaction options
    
    User->>Slack: Add 👍 reaction to message
    Slack->>Ketchup: event_callback (reaction_added)
    
    Ketchup->>Ketchup: Parse event:<br/>- user_id<br/>- reaction: +1<br/>- message_ts
    
    Ketchup->>DDB: Store feedback:<br/>- user: U123<br/>- sentiment: positive<br/>- message_id: ts<br/>- timestamp
    
    Ketchup->>User: Send DM:<br/>"Thanks for your feedback!"
```

**Handler**: `feedback_handler.py`

**Flow**:
1. Ketchup posts message (status update, report, etc.)
2. User adds reaction (👍 or 👎)
3. Slack sends `reaction_added` event
4. Ketchup stores feedback in DynamoDB
5. Optional: Thank you DM sent to user

---

### 6. Metrics Export

```mermaid
sequenceDiagram
    participant User as 👤 User
    participant Slack as 📱 Slack
    participant Ketchup as 🤖 Ketchup
    participant S3 as 📦 S3

    User->>Slack: /ketchup metrics
    Slack->>Ketchup: POST /slack/commands
    
    Ketchup->>Ketchup: Generate HTML dashboard
    Ketchup->>S3: Upload metrics.html
    S3-->>Ketchup: ✅ URL: https://...
    
    Ketchup->>Slack: Post message with:<br/>- "Download Metrics" button<br/>- "Email Report" button
    
    User->>Slack: Click "Download Metrics"
    Slack->>Ketchup: POST /slack/interactions
    
    Ketchup->>User: Send ephemeral message<br/>with download link
```

**Handler**: `metrics_handler.py`

**Flow**:
1. User executes `/ketchup metrics`
2. Ketchup generates HTML dashboard
3. HTML uploaded to S3
4. Message posted with action buttons
5. User clicks button → receives download link

---

## Interactive Component Types

### 1. Block Actions (button, select, overflow, datepicker)

**Payload Structure**:
```json
{
  "type": "block_actions",
  "user": {"id": "U123", "name": "alice"},
  "actions": [{
    "action_id": "approve_access",
    "block_id": "approval_block",
    "value": "U456",
    "type": "button"
  }],
  "response_url": "https://hooks.slack.com/actions/...",
  "trigger_id": "12345.67890.abcdef"
}
```

**Common Actions**:
- Approve/Deny buttons (access requests)
- Feature toggle buttons (flag review)
- Feedback buttons (thumbs up/down)
- Export buttons (metrics download)

---

### 2. View Submissions (modal forms)

**Payload Structure**:
```json
{
  "type": "view_submission",
  "user": {"id": "U123", "name": "alice"},
  "view": {
    "type": "modal",
    "callback_id": "access_request_modal",
    "state": {
      "values": {
        "justification_block": {
          "justification_input": {
            "type": "plain_text_input",
            "value": "Need access for on-call duties"
          }
        }
      }
    }
  }
}
```

**Common Modals**:
- Access request form (justification input)
- Feature flag review (toggle switches)
- Query form (question input)
- Archive form (date range picker)

---

### 3. View Closed (modal dismissal)

**Payload Structure**:
```json
{
  "type": "view_closed",
  "user": {"id": "U123", "name": "alice"},
  "view": {
    "callback_id": "access_request_modal",
    "id": "V123456"
  },
  "is_cleared": false
}
```

**Use Cases**:
- Track modal abandonment
- Clean up temporary data
- Log user interactions

---

### 4. Shortcut (global or message shortcuts)

**Payload Structure**:
```json
{
  "type": "shortcut",
  "callback_id": "summarize_thread",
  "trigger_id": "12345.67890.abcdef",
  "user": {"id": "U123", "name": "alice"},
  "message": {
    "ts": "1699876543.123456",
    "thread_ts": "1699876500.000000"
  }
}
```

**Common Shortcuts**:
- Summarize thread (message shortcut)
- Generate report (global shortcut)
- Archive conversation (message shortcut)

---

## Payload Routing Logic

### Router (`payload_processor.py`)

```python
async def route_interaction(payload: dict):
    interaction_type = payload.get("type")
    
    if interaction_type == "block_actions":
        action_id = payload["actions"][0]["action_id"]
        
        if action_id.startswith("approve_") or action_id.startswith("deny_"):
            return await access_request_handler.handle(payload)
        
        elif action_id.startswith("trust_endorsement_"):
            return await trust_endorsement_handler.handle(payload)
        
        elif action_id.startswith("flag_review_"):
            return await flag_review_handler.handle(payload)

        elif action_id.startswith("csopm_"):
            return await csopm_button_handler.handle(payload)

        elif action_id == "metrics_download":
            return await metrics_handler.handle_download(payload)
    
    elif interaction_type == "view_submission":
        callback_id = payload["view"]["callback_id"]
        
        if callback_id == "access_request_modal":
            return await access_request_handler.handle_submission(payload)
        
        elif callback_id == "flag_review_modal":
            return await flag_review_handler.handle_submission(payload)

        elif callback_id in ("csopm_complete_modal", "csopm_close_modal"):
            return await csopm_button_handler.handle_modal_submission(payload)
    
    elif interaction_type == "shortcut":
        callback_id = payload.get("callback_id")
        
        if callback_id == "summarize_thread":
            return await summary_handler.handle_shortcut(payload)
```

**Routing Strategy**:
1. Extract interaction type
2. Match on action_id, callback_id, or shortcut_id
3. Route to appropriate handler
4. Handler processes and updates Slack

---

## Security Considerations

### Signature Verification

**Every interaction payload verified**:
1. Extract `X-Slack-Signature` and `X-Slack-Request-Timestamp`
2. Verify timestamp within 5 minutes
3. Compute HMAC-SHA256 signature
4. Compare signatures
5. Reject if mismatch

### Authorization Checks

**Different levels for different actions**:
- **Access approval**: Admin only (Secrets Manager list)
- **Flag review**: Admin only
- **Trust endorsement**: Authorized users
- **Feedback**: Any user
- **Metrics download**: Authorized users

### Data Validation

**All user input validated**:
- Sanitize text inputs (prevent XSS)
- Validate user IDs (must be Slack user IDs)
- Validate channel IDs (must exist)
- Rate limiting (prevent abuse)

---

## Performance Optimizations

### Async Processing

**All handlers use async/await**:
- Non-blocking Slack API calls
- Concurrent database queries
- Parallel Secrets Manager fetches

### Response Time

**Immediate acknowledgment**:
- HTTP 200 returned immediately (< 100ms)
- Background processing takes 1-5 seconds
- User sees loading indicator in Slack

### Caching

**Cache frequently accessed data**:
- Authorized user lists (10 minutes)
- Admin user lists (10 minutes)
- Feature flag states (5 minutes)
- Channel metadata (1 hour)

---

## Error Handling

### User-Facing Errors

**Clear error messages**:
```
❌ Unable to process your request

Reason: You don't have permission to approve access requests.

Need help? Contact @ketchup-admins
```

### Technical Errors

**Logged but not shown to users**:
- DynamoDB query failures
- Secrets Manager API errors
- Slack API rate limits
- Invalid payload structures

### Retry Logic

**Automatic retries for transient errors**:
- Network timeouts (3 retries)
- Rate limits (exponential backoff)
- 500 errors (2 retries)

---

## Monitoring and Analytics

### Tracked Metrics

**Interaction Analytics**:
- Button click rates
- Modal completion rates
- Average approval time (access requests)
- Feature flag usage
- Error rates by handler

### Logging

**All interactions logged**:
- User ID, action, timestamp
- Handler execution time
- Errors and stack traces
- Payload samples (sanitized)

### Alerting

**Slack notifications for**:
- High error rates (> 5% per hour)
- Slow response times (> 10 seconds)
- Unusual activity patterns
- Failed authorization attempts
