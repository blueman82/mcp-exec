# Slack Event Processing Flow

## Complete Request-Response Lifecycle

```mermaid
sequenceDiagram
    participant Slack as Slack Server
    participant ALB as AWS ALB
    participant Nginx as nginx<br/>Reverse Proxy
    participant FastAPI as FastAPI App<br/>Event Handler
    participant BG as Background<br/>Task Queue
    participant DI as TypedDI<br/>Container
    participant Services as Service Layer<br/>clients, handlers, repos
    participant Slack2 as Slack API<br/>Response
    participant DDB as DynamoDB
    participant Secrets as Secrets<br/>Manager

    Slack->>ALB: 1. POST /slack/events<br/>with signature & timestamp
    ALB->>Nginx: 2. Route to FastAPI replica
    Nginx->>FastAPI: 3. HTTP request

    rect rgb(200, 230, 255)
        Note over FastAPI: PHASE 1: Quick Response (0-3 sec)
        FastAPI->>FastAPI: 4a. Verify Slack signature
        FastAPI->>FastAPI: 4b. Parse event body
        FastAPI->>DI: 5. Request event handler from DI
        DI->>Services: 5a. Resolve all dependencies
        Services->>Secrets: 5a.1. Get credentials
        Services->>DDB: 5a.2. Load context
        DI->>FastAPI: 6. Return resolved handler
        FastAPI->>BG: 7. Queue background task with payload
        FastAPI->>Slack: 8. Immediate HTTP 200 OK
        Note over Slack: Slack confirms receipt
    end

    rect rgb(230, 255, 200)
        Note over FastAPI: PHASE 2: Background Processing (async)
        BG->>BG: 9. Dequeue task
        BG->>DI: 10. Resolve services for task
        DI->>Services: 10a. Initialize service instances
        Services->>Secrets: Get API credentials
        Services->>DDB: Query channel state
        BG->>Services: 11. Execute business logic

        alt Command Handler
            Services->>Services: 11a. Process slash command
            Services->>Services: Parse command args
        else Event Handler
            Services->>Services: 11b. Handle Slack event
            Services->>DDB: Update channel state
        else Status Updater
            Services->>Services: 11c. Generate status report
        else JIRA Reporter
            Services->>Services: 11d. Create/update tickets
        end

        Services->>Slack2: 12. Post response to Slack
        Slack2->>Slack: 12a. Update channel with message
        Services->>DDB: 13. Persist updates
        BG->>BG: 14. Task complete
    end

    alt Error During Processing
        Services->>Services: Catch exception
        Services->>Slack2: Post error message
        Services->>BG: Log error details
    end
```

## Event Types and Handlers

```mermaid
graph TD
    EventReceived["Event Received<br/>from Slack"]

    EventReceived -->|app_mention| MentionHandler["@mention<br/>Handler"]
    EventReceived -->|message| MessageHandler["Message<br/>Handler"]
    EventReceived -->|slash_command| CommandRouter["Command Router"]
    EventReceived -->|reaction_added| ReactionHandler["Reaction<br/>Handler"]
    EventReceived -->|channel_created| ChannelHandler["Channel<br/>Handler"]

    CommandRouter -->|/status| StatusCmd["Status Command<br/>Get latest reports"]
    CommandRouter -->|/report| ReportCmd["Report Command<br/>Generate on-demand"]
    CommandRouter -->|/jira-sync| JiraCmd["JIRA Sync Command<br/>Sync tickets"]
    CommandRouter -->|/access| AccessCmd["Access Command<br/>Request/manage"]
    CommandRouter -->|/help| HelpCmd["Help Command<br/>Usage info"]

    MentionHandler -->|Parse| MentionLogic["Extract context<br/>and trigger AI"]
    MessageHandler -->|Parse| MessageLogic["Extract metadata<br/>for archival"]
    ReactionHandler -->|Parse| ReactionLogic["Track reactions<br/>for analytics"]
    ChannelHandler -->|Parse| ChannelLogic["Scan metadata<br/>on creation"]

    MentionLogic -->|Log Response| Slack["Post to Slack"]
    MessageLogic -->|Log Response| Slack
    ReactionLogic -->|Log Response| Slack
    ChannelLogic -->|Log Response| Slack
    StatusCmd -->|Slack Response| Slack
    ReportCmd -->|Slack Response| Slack
    JiraCmd -->|Slack Response| Slack
    AccessCmd -->|Slack Response| Slack
    HelpCmd -->|Slack Response| Slack

    style EventReceived fill:#36c5f0
    style CommandRouter fill:#ff9900
    style MentionHandler fill:#0099cc
    style MessageHandler fill:#0099cc
    style ReactionHandler fill:#0099cc
    style ChannelHandler fill:#0099cc
    style Slack fill:#36c5f0
```

## Key Processing Phases

### Phase 1: Quick Response (Synchronous, <3 seconds)
1. **Signature Verification**: Validate request came from Slack using HMAC-SHA256
2. **Event Parsing**: Extract event type, user, channel, content
3. **Dependency Resolution**: TypedDI resolves all required services
4. **Credential Loading**: Pull API credentials from Secrets Manager
5. **Context Loading**: Query DynamoDB for channel/user state
6. **Task Queueing**: Enqueue background task with full payload
7. **Immediate Response**: Send HTTP 200 to Slack (confirms receipt)

### Phase 2: Asynchronous Processing
1. **Background Execution**: Process task from queue when workers available
2. **Business Logic**: Run actual command/handler logic
3. **External API Calls**:
   - Post responses to Slack
   - Query/update JIRA tickets
   - Fetch Adobe employee data
4. **State Persistence**: Update DynamoDB with new state
5. **Error Handling**: Log failures and post error messages to Slack

## Why Two Phases?

**Slack's 3-second Response Requirement**:
- Slack expects HTTP 200 response within 3 seconds
- AI operations, JIRA queries, and database updates often take longer
- Solution: Acknowledge immediately, process asynchronously

**Concurrency Benefits**:
- Multiple background workers process tasks in parallel
- Faster request throughput (don't block on slow operations)
- Better resource utilization across servers

---

**Error Handling**: All errors caught in Phase 2, logged to CloudWatch, and error messages posted to Slack
**Retry Logic**: Failed background tasks can be replayed from SQS queue
