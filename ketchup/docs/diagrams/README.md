# Ketchup Technical Diagrams

Complete visual documentation of Ketchup's infrastructure, event processing, services, and command workflows.

## 📊 Diagram Index

### 1. **System Architecture** [`1-system-architecture.md`](./1-system-architecture.md)
**Visual overview of the complete Ketchup infrastructure**

- AWS infrastructure with ALB, 2 production servers, and EC2 instances
- Container layout on prod1 and prod2
- AWS services: DynamoDB, Secrets Manager, SQS
- All 7 services and their relationships
- Shared `packages/` directory structure

**Use for**: Understanding the complete system topology, infrastructure setup, server layout
**Audience**: DevOps, SREs, new team members

---

### 2. **Slack Event Processing Flow** [`2-slack-event-processing.md`](./2-slack-event-processing.md)
**Complete request-response lifecycle from Slack to services**

- Slack event arrives → ALB routes → FastAPI processes
- Event type routing (mention, message, reaction, channel)
- Command routing (/status, /report, /jira-sync, /access, /help)
- Two-phase processing: quick response + background work
- Event handler registration pattern

**Use for**: Understanding how Slack events are processed, debugging event flow issues, adding new commands
**Audience**: Backend developers, product engineers, debuggers

---

### 3. **TypedDI Dependency Injection Architecture** [`3-typed-di-architecture.md`](./3-typed-di-architecture.md)
**Modern type-safe dependency injection system**

- Protocol definitions (interfaces)
- Service implementations and registration
- Dependency resolution flow with topological sorting
- Singleton vs transient service lifecycle
- File structure and best practices

**Use for**: Understanding DI patterns, adding new services, resolving dependency errors
**Audience**: Backend developers, architects, code reviewers

---

### 4. **Command & Event Routing** [`4-command-event-routing.md`](./4-command-event-routing.md)
**How slash commands and events are routed to handlers**

- Command routing: /command → handler lookup
- Event routing: event_type → handler dispatch
- Detailed request flow for /status command example
- Handler registration patterns
- Adding new commands/events step-by-step

**Use for**: Feature development, adding slash commands, debugging routing issues
**Audience**: Feature engineers, new developers

---

### 5. **Container Topology** [`5-container-topology.md`](./5-container-topology.md)
**What runs where on prod1 vs prod2**

- prod1 full stack (includes singleton services)
- prod2 core services only (singletons disabled)
- Service comparison and responsibilities
- Load balancing across servers
- Resource allocation per container

**Use for**: Understanding deployment strategy, debugging container issues, capacity planning
**Audience**: DevOps, SREs, infrastructure engineers

---

### 6. **Two-Phase Processing Model** [`6-two-phase-processing.md`](./6-two-phase-processing.md)
**How Ketchup meets Slack's 3-second response requirement**

- Phase 1: Quick response (synchronous, <250ms)
- Phase 2: Background processing (asynchronous, 5-30s)
- Sequence diagrams with actual timings
- Control flow for both phases
- Concurrency and worker management
- Performance impact metrics

**Use for**: Understanding performance architecture, troubleshooting slow responses, optimization
**Audience**: Performance engineers, SREs, backend developers

---

### 7. **Service Data Flows** [`7-service-data-flows.md`](./7-service-data-flows.md)
**Data flow for each Ketchup service**

**Services covered**:
- Status Updater: Hourly status reports
- JIRA Reporter: Automated ticket management
- Channel Metadata Updater: Metadata scanning & storage
- Maintenance Fetcher: Event detection & alerting
- Access Request Monitor: Request processing & approval
- Command Handlers: /status command execution
- Event Handlers: Message/mention processing

- Data models: DynamoDB table structures
- Service interaction summary table

**Use for**: Understanding service responsibilities, debugging specific services, data model reference
**Audience**: Full-stack developers, data engineers, debuggers

---

### 8. **Feature Flags** [`8-feature-flags.md`](./8-feature-flags.md)
**Feature flag architecture and safe rollout pattern**

- All feature flags and their purposes
- Flag resolution flow and caching
- Safe rollout pattern: disabled → staging → prod2 canary → prod1
- Performance impact by feature
- Adding new feature flags step-by-step

**Use for**: Enabling/disabling features, safe rollouts, performance optimization
**Audience**: DevOps, feature engineers, release managers

---

## 🗺️ Navigation by Use Case

### "I need to understand the system..."
1. Start with **System Architecture** - get the big picture
2. Read **Container Topology** - understand what runs where
3. Review **TypedDI Architecture** - understand how services talk to each other

### "I'm adding a new feature..."
1. Read **Command & Event Routing** - how to add handlers
2. Study **Service Data Flows** - where does data go?
3. Review **Two-Phase Processing** - understand the request flow

### "Something is slow or broken..."
1. Check **Two-Phase Processing** - understand the timeline
2. Review **Service Data Flows** - trace the problem
3. Check **Slack Event Processing** - debug the flow

### "I'm deploying..."
1. Review **Container Topology** - what gets deployed where?
2. Study **Feature Flags** - what can I enable/disable safely?
3. Check **System Architecture** - AWS resources needed

### "I'm new to Ketchup..."
1. **System Architecture** - the lay of the land
2. **Slack Event Processing** - how it works
3. **Two-Phase Processing** - why it's designed this way
4. **Command & Event Routing** - adding features
5. **Service Data Flows** - each service's job
6. **TypedDI Architecture** - how to write code
7. **Feature Flags** - safety mechanisms

---

## 📋 Diagram Format

All diagrams are in **Mermaid** format, which means:
- ✅ Renders in GitHub markdown automatically
- ✅ Version controllable (plain text)
- ✅ Supports dark/light themes
- ✅ Can be edited with any text editor
- ✅ Can be converted to PNG/SVG for presentations

---

## 🔍 Key Concepts Across Diagrams

### Slack → FastAPI Request Flow
See diagrams **2-slack-event-processing** and **4-command-event-routing**

### Two-Phase Processing
See diagram **6-two-phase-processing** and referenced in **2-slack-event-processing**

### TypedDI Dependency Injection
See diagram **3-typed-di-architecture** and referenced in **4-command-event-routing**

### Singleton Services (prod1 only)
See diagrams **1-system-architecture** and **5-container-topology**

### Feature Flags & Safe Rollouts
See diagram **8-feature-flags** for safe deployment strategy

### Background Job Services
See diagram **7-service-data-flows** for status-updater, jira-reporter, etc.

---

## 🚀 Recent Performance Optimizations

Documented in **8-feature-flags** and **6-two-phase-processing**:

**Phase 1 (PR #198)**: Pipeline Processing
- 4 concurrent workers for batch operations
- 200-300% overall performance improvement

**Phase 2 (PR #201)**: HTTP Optimization
- HTTP/2 via httpx library
- Connection keep-alive: 94.7% reuse rate
- 5-8% additional performance gain

---

## 📞 Related Documentation

**In this repository**:
- [`CLAUDE.md`](../../CLAUDE.md) - Project overview and guidelines
- [`README.md`](../../README.md) - Quick start guide
- [`code_docs/ketchup_high_level.md`](../code_docs/ketchup_high_level.md) - Architecture deep dive
- [`code_docs/ketchup_code_walkthrough_documentation.md`](../code_docs/ketchup_code_walkthrough_documentation.md) - Component reference
- [`docs/TYPEDDI_MIGRATION_SUMMARY.md`](../TYPEDDI_MIGRATION_SUMMARY.md) - DI system details

**External**:
- [Slack API Documentation](https://api.slack.com)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [AWS Services](https://aws.amazon.com)

---

## ✏️ Maintaining These Diagrams

When updating Ketchup architecture:
1. Identify which diagram(s) need updates
2. Edit the Mermaid code in the `.md` file
3. Commit changes with reference to the component changed
4. Update this README if adding new diagrams

**Update checklist**:
- [ ] System Architecture - if adding/removing AWS services or servers
- [ ] Container Topology - if changing what runs where
- [ ] Service Data Flows - if modifying service logic
- [ ] Feature Flags - if adding new feature control
- [ ] Command/Event Routing - if adding new commands/events
- [ ] TypedDI - if changing dependency structure

---

## 🎓 Learning Resources

**Recommended reading order for new team members**:
1. System Architecture → understand the infrastructure
2. Slack Event Processing → understand the request flow
3. Two-Phase Processing → understand performance design
4. Command & Event Routing → ready to add features
5. Service Data Flows → understand each service
6. TypedDI Architecture → ready to write code
7. Container Topology → understand deployments
8. Feature Flags → understand safety mechanisms

---

Generated: November 18, 2025
Status: Complete (8 diagrams, 100 total diagrams)
