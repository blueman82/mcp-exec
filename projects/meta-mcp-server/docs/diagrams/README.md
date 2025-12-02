# Meta-MCP Diagrams

Ultra-dense technical documentation for developers with MCP knowledge.

## Documents (3 total, ~2,200 lines)

| Document | Lines | Focus | Content |
|----------|-------|-------|---------|
| [**architecture.md**](architecture.md) | ~600 | System + Config + Lifecycle | System diagram, config loading, startup/shutdown sequences |
| [**core-mechanics.md**](core-mechanics.md) | ~1,000 | Pool + Connections + Caching + Tools | ServerPool (LRU), connections (4 transports), tool cache, 3 handlers |
| [**token-economics.md**](token-economics.md) | ~600 | ROI + Optimization | Request flows with token counts, strategy comparison, break-even analysis |

**Consolidates:** 10 previous diagrams (01-10) into 3 focused documents

---

## Quick Reference

### Implementation
- **Pool setup** → core-mechanics.md lines 1-350
- **Request flow** → token-economics.md lines 250-450
- **Configuration** → architecture.md lines 200-400

### Optimization
- **Strategy selection** → token-economics.md lines 500-600
- **Token savings** → token-economics.md lines 1-150
- **Cache behavior** → core-mechanics.md lines 400-550

### Debugging
- **Connection issues** → core-mechanics.md lines 250-450
- **Pool eviction** → core-mechanics.md lines 1-250
- **Tool discovery** → core-mechanics.md lines 650-850

---

## Reading Paths

### Path 1: Quick Start (15 min)
1. architecture.md → System Overview (100 lines)
2. token-economics.md → Token Comparison (150 lines)
3. core-mechanics.md → skim diagrams

### Path 2: Implementation (60 min)
1. architecture.md → complete read
2. core-mechanics.md → ServerPool + Tool System
3. token-economics.md → Implementation Reference

### Path 3: Specific Component
- **Pool** → core-mechanics.md lines 1-350
- **Handlers** → core-mechanics.md lines 650-850
- **ROI** → token-economics.md complete

---

## Format
- ❌ No prose / "Why This Works" sections
- ✅ Diagrams first (20+ Mermaid diagrams)
- ✅ Code examples (TypeScript)
- ✅ Tables for reference data
- ✅ Assumes MCP knowledge

---

## What Was Consolidated

### architecture.md (from 3 docs)
- 01-system-architecture.md → system overview
- 08-registry-configuration.md → config loading
- 09-full-integration.md → lifecycle

### core-mechanics.md (from 5 docs)
- 03-pool-lifecycle.md → pool states
- 04-caching-strategy.md → cache behavior
- 05-server-pool-architecture.md → LRU algorithm
- 06-connection-components.md → connection lifecycle
- 07-tool-system-architecture.md → 3 handlers

### token-economics.md (from 2 docs)
- 02-request-flow.md → request sequences
- 10-token-optimization.md → savings analysis
