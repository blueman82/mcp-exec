# Meta-MCP Server Diagrams

## Overview

This directory contains comprehensive architectural diagrams for the Meta-MCP Server project. These diagrams provide visual representations of the system's architecture, component interactions, and optimization strategies. Each diagram is designed to help you understand a specific aspect of how Meta-MCP reduces token consumption while maintaining full MCP server functionality.

Meta-MCP Server wraps multiple backend MCP servers and exposes only 3 meta-tools instead of loading 100+ tool schemas upfront. These diagrams illustrate how this architecture achieves an 87% reduction in context token consumption (from ~16k to ~2k tokens).

---

## Quick Start: Which Diagram Should I Read?

Choose your entry point based on your current need:

| If you are... | Start with... |
|--------------|---------------|
| **Just learning Meta-MCP** | [01-system-architecture.md](#01-system-architecturemd) - Get the complete system overview |
| **Confused about token savings** | [10-token-optimization.md](#10-token-optimizationmd) - See concrete token comparisons |
| **Debugging pool issues** | [03-pool-lifecycle.md](#03-pool-lifecyclemd) - Understand connection states and eviction |
| **Adding new backend server** | [06-connection-components.md](#06-connection-componentsmd) - Learn connection lifecycle |
| **Understanding tool discovery** | [02-request-flow.md](#02-request-flowmd) - Follow the two-tier discovery sequence |
| **Implementing caching** | [04-caching-strategy.md](#04-caching-strategymd) - See cache hits/misses and invalidation |
| **Configuring servers** | [08-registry-configuration.md](#08-registry-configurationmd) - Understand config loading |
| **Troubleshooting errors** | [06-connection-components.md](#06-connection-componentsmd) - See error handling flows |
| **Optimizing performance** | [05-server-pool-architecture.md](#05-server-pool-architecturemd) - Learn LRU algorithm |
| **Deploying to production** | [09-full-integration.md](#09-full-integrationmd) - See startup/shutdown lifecycle |

---

## Diagram Index

### Foundation Diagrams (Start Here)

These diagrams provide the essential understanding needed to work with Meta-MCP Server.

#### 01-system-architecture.md
**Purpose**: Complete system overview showing all major components and their interactions

**What you'll learn**:
- How Meta-MCP wraps backend MCP servers
- The role of each major component (ServerPool, ToolCache, Registry)
- High-level lazy loading flow
- Entry point through `index.ts` to stdio transport

**Read this first if**: You're new to Meta-MCP or need a complete mental model

**Key concepts**: Lazy loading, Meta-tools, Component architecture

---

#### 02-request-flow.md
**Purpose**: Detailed sequence diagram of the two-tier tool discovery process

**What you'll learn**:
- Step-by-step flow from AI request to backend execution
- Token counts at each discovery tier
- How `summary_only` and `tools[]` parameters optimize tokens
- Exact request/response payloads

**Read this first if**: You want to understand how Meta-MCP achieves token savings

**Key concepts**: Two-tier discovery, Token optimization, Request routing

---

#### 03-pool-lifecycle.md
**Purpose**: Connection pool state machine and lifecycle management

**What you'll learn**:
- Connection states (idle, active, connecting, error)
- LRU eviction algorithm in action
- Timeout behavior (5min idle, 1min cleanup interval)
- When connections are created vs. reused

**Read this first if**: You're debugging connection issues or pool behavior

**Key concepts**: Connection pooling, LRU eviction, State transitions

---

#### 04-caching-strategy.md
**Purpose**: Tool definition caching architecture and invalidation rules

**What you'll learn**:
- Where tool definitions are cached (per-server)
- Cache hit vs. miss flows
- Cache invalidation triggers (connection close, explicit clear)
- Memory optimization strategies

**Read this first if**: You're working on caching logic or debugging stale tool definitions

**Key concepts**: Tool caching, Cache invalidation, Memory management

---

### Component Architecture (Deep Dives)

These diagrams explore individual components in depth.

#### 05-server-pool-architecture.md
**Purpose**: Internal design of the ServerPool class and LRU algorithm

**What you'll learn**:
- ServerPool class structure and methods
- Detailed LRU implementation (Map-based, max 6 connections)
- Eviction decision logic
- Connection acquisition and release flows

**Read this first if**: You're modifying pool behavior or implementing similar patterns

**Key concepts**: LRU algorithm, Resource pooling, Connection management

---

#### 06-connection-components.md
**Purpose**: Connection lifecycle from spawn to termination

**What you'll learn**:
- Connection class internals
- Transport types (stdio, SSE) and their differences
- Process spawning with stdio streams
- Error handling at each lifecycle stage
- Graceful vs. forced termination

**Read this first if**: You're adding new transport types or debugging connection errors

**Key concepts**: Process management, Transport protocols, Error handling

---

#### 07-tool-system-architecture.md
**Purpose**: Complete tool discovery, caching, and execution pipeline

**What you'll learn**:
- Tool discovery process (list → filter → cache)
- Summary vs. full schema retrieval
- Tool execution routing through pool
- Error propagation from backend to client

**Read this first if**: You're implementing new meta-tools or modifying tool behavior

**Key concepts**: Tool discovery, Schema optimization, Execution routing

---

#### 08-registry-configuration.md
**Purpose**: Configuration loading, validation, and manifest caching

**What you'll learn**:
- `servers.json` format and structure
- Zod validation schemas
- `SERVERS_CONFIG` environment variable handling
- Manifest caching to avoid repeated file reads

**Read this first if**: You're adding new server types or modifying config format

**Key concepts**: Configuration management, Schema validation, Manifest caching

---

### Integration & Optimization (Complete Picture)

These diagrams show how components work together and deliver optimization.

#### 09-full-integration.md
**Purpose**: Complete system lifecycle from startup to shutdown

**What you'll learn**:
- Initialization sequence (config load → pool creation → server start)
- Signal handling (SIGINT, SIGTERM)
- Graceful shutdown process
- Cleanup order and error recovery

**Read this first if**: You're deploying to production or debugging startup/shutdown issues

**Key concepts**: Lifecycle management, Graceful shutdown, Signal handling

---

#### 10-token-optimization.md
**Purpose**: Token comparison showing real-world savings

**What you'll learn**:
- Traditional MCP: 16k tokens upfront (100+ tool schemas)
- Meta-MCP Tier 1: ~100 tokens (tool names only)
- Meta-MCP Tier 2: ~2k tokens (specific schemas only)
- Concrete examples with real tools

**Read this first if**: You need to explain or justify Meta-MCP's value proposition

**Key concepts**: Token optimization, Context window savings, Two-tier discovery benefits

---

## Learning Paths

### Path 1: For Users
**Goal**: Understand how to use Meta-MCP effectively

1. **Start**: [01-system-architecture.md](#01-system-architecturemd) - Understand what Meta-MCP does
2. **Setup**: [08-registry-configuration.md](#08-registry-configurationmd) - Configure your backend servers
3. **Usage**: [02-request-flow.md](#02-request-flowmd) - Learn the three meta-tools
4. **Optimization**: [10-token-optimization.md](#10-token-optimizationmd) - See the token savings in action

**Outcome**: You can configure and use Meta-MCP with any AI tool

---

### Path 2: For Developers
**Goal**: Complete understanding of the codebase

1. **Foundation**: [01-system-architecture.md](#01-system-architecturemd) - Component overview
2. **Request Flow**: [02-request-flow.md](#02-request-flowmd) - Follow a request end-to-end
3. **Pooling**: [03-pool-lifecycle.md](#03-pool-lifecyclemd) → [05-server-pool-architecture.md](#05-server-pool-architecturemd)
4. **Connections**: [06-connection-components.md](#06-connection-componentsmd)
5. **Tools**: [04-caching-strategy.md](#04-caching-strategymd) → [07-tool-system-architecture.md](#07-tool-system-architecturemd)
6. **Config**: [08-registry-configuration.md](#08-registry-configurationmd)
7. **Integration**: [09-full-integration.md](#09-full-integrationmd)

**Outcome**: You can modify any component with confidence

---

### Path 3: For Contributors
**Goal**: Understand architecture decisions and extension points

1. **Why Meta-MCP**: [10-token-optimization.md](#10-token-optimizationmd) - The problem we solve
2. **Architecture**: [01-system-architecture.md](#01-system-architecturemd) - High-level design decisions
3. **Optimization Strategy**: [02-request-flow.md](#02-request-flowmd) → [04-caching-strategy.md](#04-caching-strategymd)
4. **Extension Points**:
   - Adding transports: [06-connection-components.md](#06-connection-componentsmd)
   - Adding meta-tools: [07-tool-system-architecture.md](#07-tool-system-architecturemd)
   - Modifying pool behavior: [05-server-pool-architecture.md](#05-server-pool-architecturemd)

**Outcome**: You can extend Meta-MCP with new features

---

### Path 4: For DevOps
**Goal**: Deploy and monitor Meta-MCP in production

1. **Configuration**: [08-registry-configuration.md](#08-registry-configurationmd) - Environment setup
2. **Lifecycle**: [09-full-integration.md](#09-full-integrationmd) - Startup/shutdown behavior
3. **Resource Management**: [03-pool-lifecycle.md](#03-pool-lifecyclemd) → [05-server-pool-architecture.md](#05-server-pool-architecturemd)
4. **Error Handling**: [06-connection-components.md](#06-connection-componentsmd)
5. **Performance**: [10-token-optimization.md](#10-token-optimizationmd) - Expected resource usage

**Outcome**: You can deploy, monitor, and troubleshoot Meta-MCP

---

## Key Concepts Reference

### Lazy Loading
Connections are created on-demand, not at startup.

**Primary diagram**: [01-system-architecture.md](#01-system-architecturemd)
**Deep dive**: [03-pool-lifecycle.md](#03-pool-lifecyclemd), [06-connection-components.md](#06-connection-componentsmd)

---

### Two-Tier Discovery
AI first gets tool names (Tier 1), then specific schemas (Tier 2).

**Primary diagram**: [02-request-flow.md](#02-request-flowmd)
**Token savings**: [10-token-optimization.md](#10-token-optimizationmd)
**Implementation**: [07-tool-system-architecture.md](#07-tool-system-architecturemd)

---

### Connection Pooling
Reuse connections across requests with LRU eviction.

**Primary diagram**: [05-server-pool-architecture.md](#05-server-pool-architecturemd)
**Lifecycle**: [03-pool-lifecycle.md](#03-pool-lifecyclemd)
**Error handling**: [06-connection-components.md](#06-connection-componentsmd)

---

### Tool Caching
Cache tool definitions per-server to avoid repeated discovery.

**Primary diagram**: [04-caching-strategy.md](#04-caching-strategymd)
**Integration**: [07-tool-system-architecture.md](#07-tool-system-architecturemd)
**Invalidation**: [09-full-integration.md](#09-full-integrationmd)

---

### Token Optimization
Reduce context window usage by 87% (16k → 2k tokens).

**Primary diagram**: [10-token-optimization.md](#10-token-optimizationmd)
**Mechanism**: [02-request-flow.md](#02-request-flowmd)
**Architecture**: [01-system-architecture.md](#01-system-architecturemd)

---

## Troubleshooting Guide

### "Connection failed" errors
**See**: [06-connection-components.md](#06-connection-componentsmd) - Error handling section
**Also**: [03-pool-lifecycle.md](#03-pool-lifecyclemd) - Connection state transitions

### "Tool not found" errors
**See**: [07-tool-system-architecture.md](#07-tool-system-architecturemd) - Tool discovery flow
**Also**: [04-caching-strategy.md](#04-caching-strategymd) - Cache invalidation

### Slow response times
**See**: [05-server-pool-architecture.md](#05-server-pool-architecturemd) - Pool efficiency
**Also**: [03-pool-lifecycle.md](#03-pool-lifecyclemd) - Idle timeouts

### High memory usage
**See**: [04-caching-strategy.md](#04-caching-strategymd) - Cache management
**Also**: [05-server-pool-architecture.md](#05-server-pool-architecturemd) - Max connections

### Server won't start
**See**: [09-full-integration.md](#09-full-integrationmd) - Initialization sequence
**Also**: [08-registry-configuration.md](#08-registry-configurationmd) - Config validation

### Stale tool definitions
**See**: [04-caching-strategy.md](#04-caching-strategymd) - Cache invalidation
**Also**: [07-tool-system-architecture.md](#07-tool-system-architecturemd) - Tool refresh

### Pool exhaustion (max connections)
**See**: [05-server-pool-architecture.md](#05-server-pool-architecturemd) - LRU eviction
**Also**: [03-pool-lifecycle.md](#03-pool-lifecyclemd) - Eviction triggers

### Backend process crashes
**See**: [06-connection-components.md](#06-connection-componentsmd) - Process lifecycle
**Also**: [09-full-integration.md](#09-full-integrationmd) - Cleanup procedures

### Token usage higher than expected
**See**: [10-token-optimization.md](#10-token-optimizationmd) - Expected savings
**Also**: [02-request-flow.md](#02-request-flowmd) - Two-tier usage pattern

### Configuration not loading
**See**: [08-registry-configuration.md](#08-registry-configurationmd) - Config loading flow
**Also**: [09-full-integration.md](#09-full-integrationmd) - Startup validation

---

## Diagram Format

All diagrams in this directory use **Markdown with Mermaid syntax** for portability and version control. They render automatically in:

- GitHub/GitLab
- Visual Studio Code (with Markdown Preview Mermaid extension)
- JetBrains IDEs (with Mermaid plugin)
- Most modern documentation platforms

---

## Contributing

When adding new diagrams:

1. Follow the naming convention: `##-descriptive-name.md`
2. Include a "Purpose" and "What you'll learn" section at the top
3. Update this README with the new diagram in the appropriate section
4. Add the diagram to relevant learning paths
5. Link from troubleshooting guide if applicable
6. Use consistent Mermaid styles and colors

---

## Additional Resources

- **Main Documentation**: `/README.md` - Project overview and quick start
- **Development Guide**: `/CLAUDE.md` - Commands and architecture notes
- **API Reference**: Source code JSDoc comments
- **Examples**: `/tests/integration/` - Real-world usage patterns

---

## Questions?

If you can't find the right diagram:

1. Check the [Quick Start](#quick-start-which-diagram-should-i-read) section
2. Browse the [Learning Paths](#learning-paths) for your role
3. Use the [Troubleshooting Guide](#troubleshooting-guide) for specific issues
4. Open an issue on GitHub if documentation is missing
