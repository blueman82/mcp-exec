---
paths:
  - "packages/agent/**"
  - "ketchup_unified_scheduler/tasks/handover*"
---
# Agent & ChromaDB Architecture

## Two-tier service registration
Registered in `packages/core/typed_di/service_registrations/registrations/agent_services.py`:

**Tier 1 — ChromaDB foundation (4 services)**
Gated by: `KETCHUP_CHROMADB_ENABLED` OR `KETCHUP_AGENT_ENABLED`
- AzureEmbeddingsClient (text-embedding-ada-002)
- ChromaVectorStore (cosine distance, `ketchup_messages` collection)
- ConversationStore (DynamoDB conversation turns + watermarks)
- RealtimeIngestor (async message streaming into ChromaDB)

**Tier 2 — Agent chat/RAG (8 services)**
Gated by: `KETCHUP_AGENT_ENABLED` only
- Retriever, ContextBuilder, AgentThreadFilter, AgentThreadManager
- JiraBackfillIngestor, BackfillIngestor
- AgentEngine, AgentSlackHandler

**Why two tiers**: Handover summary uses ChromaDB (tier 1) without the full agent stack (tier 2).

## HTTP layer — raw aiohttp, NOT the openai SDK
All Azure OpenAI calls use `AzureAsyncClient` (custom aiohttp client). Do NOT import `openai` for API calls. The `openai` package is a transitive dependency of `tiktoken` only.

To add function calling / tools support, add `tools` key to the payload in `packages/ai/core/operations/api_interaction.py:build_openai_payload()`.

## RAG pipeline
```
@Ketchup mention → AgentSlackHandler → AgentEngine.answer()
  → Retriever (embed query → ChromaDB cosine search, top_k=20)
  → ContextBuilder (system prompt + retrieved chunks + history)
  → Azure OpenAI (gpt-5.4-mini, temperature=0.3)
  → Response posted to Slack thread
```

## Thread isolation
Status updater, JIRA reporter, and /status command all filter out agent conversation threads via `AgentThreadFilterProtocol` — prevents bot chatter from polluting summaries.
