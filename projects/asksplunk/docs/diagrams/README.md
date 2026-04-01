# Architecture Diagrams

Visual documentation of AskSplunk system architecture and workflows.

**Format**: Mermaid diagrams (rendered on GitHub as SVG)

---

## Diagrams

### 1. Agent State Machine
**File**: `agent-state-machine.mmd`

GPT-5 agent workflow with 7 states:
1. **INITIALIZE** - Create session, store question, RAG retrieval
2. **EVALUATE** - GPT assesses confidence, routes based on thresholds
3. **CLARIFY** - Generate 2-4 numbered options (confidence 30-49%)
4. **WAIT** - Parse user's number reply, map to option
5. **REFINE** - Append to history, re-retrieve docs
6. **GENERATE** - Create SPL query with explanations (confidence ≥50%)
7. **COMPLETE** - Reset session to EVALUATE for follow-up questions

**Key Features**:
- Loop breaker after 2 clarifications (forces generation)
- UNCERTAIN state for confidence <30%
- Status callbacks (🔍 🤔 ✨) during processing
- Privacy: session persists until 30-min TTL for multi-turn, then auto-deleted

---

### 2. RAG Pipeline
**File**: `rag-pipeline.mmd`

Retrieval-Augmented Generation workflow:

**Offline Phase** (indexer):
- Adobe Campaign schema JSON → 103 chunks
- Breakdown: 1 overview + ~84 fields + 6 patterns + 12 use cases
- ADA-002 embeddings → ChromaDB

**Runtime Phase**:
- User question → ADA-002 embedding → semantic search
- Top-K docs → GPT-5 agent → SPL query + explanations

---

### 3. Deployment Pipeline
**File**: `deployment-pipeline.mmd`

Manual deployment workflow (no CI/CD):

**Validation**:
- `./infrastructure/validate.sh` - black, ruff, pytest
- `--fix` flag for auto-formatting

**Deployment**:
- `./infrastructure/deploy-build-push.sh` - full pipeline
- `--dry-run` for testing
- `--reindex` to force ChromaDB reindexing

**Steps**: Docker build → ECR push → SSH to EC2 → docker-compose restart

---

### 4. Slack Event Flow
**File**: `slack-event-flow.mmd`

End-to-end message handling:

**Flows**:
- New conversation: mention → Agent.process_question() → response
- Continuation (WAIT state): reply → Agent handles clarification
- DMs: channel_type="im" → same Agent flow

**Features**:
- Status callbacks during processing
- Response routing: query_generated, clarify, uncertain
- Privacy: metadata logging only

---

### 5. Slack Message Formatting
**File**: `slack-message-formatting.mmd`

Block Kit message templates:

**format_final_query()**: Plain explanation + SPL code block + technical details + follow-up hint

**format_clarifying_question()**: Question + numbered options list + "Reply with a number" context

**format_uncertainty_message()**: Warning + missing info + request for details

---

### 6. Slack Socket Mode Connection
**File**: `slack-socket-mode-connection.mmd`

WebSocket connection lifecycle: startup → connected (auto-reconnect) → shutdown with cleanup

---

### 7. Slack Thread-Session Mapping
**File**: `slack-thread-session-mapping.mmd`

Thread ID logic: new message uses `ts`, reply uses `thread_ts`. Session TTL resets on updates, persists for multi-turn follow-ups.

---

### 8. Infrastructure Architecture
**File**: `infrastructure-architecture.mmd`

AWS topology: EC2 + DynamoDB + ECR + Secrets Manager + external integrations

---

### 9. LDAP Authentication Flow
**File**: `ldap-authentication-flow.mmd`

SSH authentication via SSSD/LDAP for production server access

---

## How to View

- **GitHub**: Renders automatically as SVG
- **VS Code**: Install Mermaid extension
- **Online**: Paste into [mermaid.live](https://mermaid.live)

---

## Diagram Status

| Diagram | Status | Last Updated |
|---------|--------|--------------|
| agent-state-machine.mmd | ✅ Current | 2025-12-05 |
| rag-pipeline.mmd | ✅ Current | 2025-12-05 |
| deployment-pipeline.mmd | ✅ Current | 2025-12-05 |
| slack-event-flow.mmd | ✅ Current | 2025-12-05 |
| slack-message-formatting.mmd | ✅ Current | 2025-12-05 |
| slack-socket-mode-connection.mmd | ✅ Current | 2025-11-20 |
| slack-thread-session-mapping.mmd | ✅ Current | 2025-11-20 |
| infrastructure-architecture.mmd | ✅ Current | 2025-11-20 |
| ldap-authentication-flow.mmd | ✅ Current | 2025-11-20 |
