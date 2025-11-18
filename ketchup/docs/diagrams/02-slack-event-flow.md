# Slack Event Flow - Complete Request Lifecycle

This sequence diagram shows the complete flow of a Slack event through the Ketchup system. The critical design pattern is **two-phase processing**: an immediate HTTP 200 response within 3 seconds (to satisfy Slack's timeout), followed by asynchronous background processing for expensive operations like AI calls and database queries.

```mermaid
sequenceDiagram
    autonumber
    participant Slack as 📱 Slack API
    participant ALB as ⚖️ AWS ALB
    participant Nginx as 🔀 nginx
    participant FastAPI as 🚀 FastAPI<br/>(main.py)
    participant BG as ⏳ BackgroundTasks
    participant Verify as 🔐 Signature Verifier
    participant Process as ⚙️ process_request()
    participant DI as 🏗️ TypedDI Container
    participant Service as 📊 Service Layer<br/>(AI/DB)
    participant Response as 📤 Response Poster

    Note over Slack,FastAPI: ⏱️ PHASE 1: Quick Response (< 3 seconds)
    
    Slack->>+ALB: POST /slack/events OR<br/>/slack/commands OR<br/>/slack/interactions<br/>(Headers: X-Slack-Signature,<br/>X-Slack-Request-Timestamp)
    Note right of Slack: Slack timeout: 3 seconds<br/>Must receive 200 OK!
    
    ALB->>+Nginx: Route to prod1 or prod2<br/>(Round robin)
    Nginx->>+FastAPI: Forward to ketchup-app:8001<br/>Proxy headers preserved
    
    FastAPI->>FastAPI: Parse endpoint<br/>(events/commands/interactions)
    FastAPI->>+Verify: Verify Slack signature
    Verify->>Verify: Check timestamp freshness<br/>(< 5 minutes)
    Verify->>Verify: Compute HMAC-SHA256<br/>(secret + timestamp + body)
    Verify->>Verify: Compare signatures
    Verify-->>-FastAPI: ✅ Signature valid
    
    FastAPI->>FastAPI: Spawn BackgroundTasks
    FastAPI-->>-Nginx: 🎯 HTTP 200 OK<br/>(Empty body or ack)
    Nginx-->>-ALB: 200 OK
    ALB-->>-Slack: 200 OK
    
    Note over Slack: ✅ Slack satisfied<br/>No timeout error

    Note over BG,Response: ⏱️ PHASE 2: Background Processing (async, no time limit)
    
    FastAPI->>+BG: Execute background task<br/>(async function)
    BG->>+Process: process_request(event_data)
    
    Process->>Process: Create Lambda-compatible<br/>event object<br/>{body, headers, path}
    Process->>Process: Parse event type<br/>(slash_command/event_callback/<br/>interaction)
    
    Process->>+DI: Initialize TypedDI container
    DI->>DI: Topological sort<br/>dependencies
    DI->>DI: Instantiate services<br/>(Slack, Azure, DynamoDB)
    DI-->>-Process: Container ready
    
    Process->>+DI: aget(CommandProtocol)
    DI-->>-Process: Concrete service instance
    
    Process->>+Service: Execute command/handler
    
    alt AI Operation Required
        Service->>Service: Fetch messages from Slack<br/>(Pipeline processing,<br/>4 concurrent workers)
        Service->>Service: Call Azure OpenAI<br/>(gpt-4o, summarization)
        Note right of Service: Takes 5-30 seconds<br/>Would exceed 3s limit!
    else Database Operation
        Service->>Service: Query DynamoDB<br/>(channel metadata)
        Service->>Service: Update feature flags
    else JIRA Operation
        Service->>Service: Call MCP JIRA client<br/>(Create/update tickets)
    end
    
    Service->>+Response: Post response to Slack
    Response->>Response: Format message<br/>(Blocks, attachments)
    Response->>Slack: POST to response_url OR<br/>chat.postMessage
    Slack-->>Response: 200 OK
    Response-->>-Service: Posted successfully
    
    Service-->>-Process: Command completed
    Process-->>-BG: Background task done
    BG-->>-FastAPI: Task finished
    
    Note over Slack: 📬 User sees response<br/>in Slack channel

    rect rgb(230, 240, 255)
        Note over Slack,Response: 🔒 Security: HMAC-SHA256 signature verification prevents unauthorized requests
    end
    
    rect rgb(255, 240, 230)
        Note over BG,Response: ⚡ Performance Optimizations:<br/>- Pipeline processing (59% faster)<br/>- HTTP/2 with keep-alive (5-8% faster)<br/>- Concurrent workers (4 parallel)
    end
```

## Key Timing Constraints

**3-Second Rule:**
- Slack requires HTTP 200 within 3 seconds
- Any response taking longer triggers a timeout error visible to users
- FastAPI immediately returns 200 before processing begins

**Background Processing Benefits:**
- No time limits on AI operations (typically 5-30 seconds)
- Can retry failed operations without user-facing errors
- Multiple requests processed concurrently
- Service crashes don't show timeout errors to users

## Security Layer

**Signature Verification Steps:**
1. Extract `X-Slack-Signature` and `X-Slack-Request-Timestamp` headers
2. Verify timestamp is within 5 minutes (prevent replay attacks)
3. Compute signature: `HMAC-SHA256(signing_secret, timestamp + request_body)`
4. Compare computed signature with provided signature
5. Reject request if signatures don't match

## Performance Optimizations (October 2025)

**Pipeline Processing (59% improvement):**
- 4 concurrent workers for message fetching
- Parallel API calls instead of sequential
- Configured via `USE_PIPELINE_PROCESSING=true`

**HTTP/2 with Keep-Alive (5-8% improvement):**
- 94.7% connection reuse rate
- Reduced TCP handshake overhead
- Configured via `KETCHUP_USE_HTTPX=true` and `KETCHUP_HTTP2_ENABLED=true`

## Response Delivery Methods

**Immediate Response (Phase 1):**
- Empty 200 OK for events
- Text acknowledgment for commands

**Delayed Response (Phase 2):**
- `response_url` from Slack payload (expires in 30 minutes)
- `chat.postMessage` API call (requires channel ID)
- `chat.update` for editing existing messages
