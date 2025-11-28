# Meta-MCP token flooding: Which solution is best? 1) Modify tool descriptions 2) Throttle parallel calls 3) Add search_tools semantic search 4) Paginate tools 5) Add suggest_server 6) Two-tier lazy loading (tool index + schema). Context: get_server_tools returns ALL schemas (~16k tokens for Jira's 25 tools). Goal: reduce tokens while maintaining discoverability.

# AI Counsel Deliberation Transcript

**Status:** complete
**Mode:** quick
**Rounds Completed:** 1
**Participants:** claude-sonnet-4-5-20250929@claude, gemini-2.5-pro@gemini

---

## Summary

**Consensus:** No clear consensus reached. Only one model (Claude Sonnet 4.5) provided analysis; Gemini 2.5 Pro failed with a CLI error, preventing multi-model deliberation.

### Key Agreements

- Current token flooding problem is real: 16k tokens for 25 Jira tools via `get_server_tools`
- Throttling parallel calls (#2) doesn't address token usage
- Modifying descriptions (#1) provides marginal savings (~10-20%) at cost of discoverability
- Solution must balance token reduction with MCP's core discoverability value
- Backward compatibility is valuable for adoption

### Key Disagreements

- No significant disagreements

**Final Recommendation:** **Implement Option 6: Two-tier lazy loading** with `summary_only` and `tools` parameters. Delivers 87% token reduction (16k → ~2k) while maintaining backward compatibility. Aligns with industry patterns (REST APIs, LSP protocol) and requires minimal implementation (~40 LOC in `get-server-tools.ts`). Natural workflow: summary-first discovery → on-demand schema fetching for actual tool calls.

---

**Note**: Re-run deliberation with working Gemini configuration to validate this recommendation through multi-model consensus.

---

## Voting Results

### Final Tally

- **Option 6: Two-tier lazy loading**: 1 vote(s) ✓

**Consensus Reached:** Yes

**Winning Option:** Option 6: Two-tier lazy loading

### Votes by Round

#### Round 1

**claude-sonnet-4-5-20250929@claude**
- Option: Option 6: Two-tier lazy loading
- Confidence: 0.95
- Continue Debate: Yes
- Rationale: 87% token reduction with backward compatibility, minimal code change (~40 LOC), scales to 100+ tool servers, aligns with industry patterns. Summary-first discovery + on-demand schemas solves both discoverability AND token flooding.


---

## Tool Executions

### read_file (Round 1)

**Requested by:** gpt-5.1-codex@codex
**Timestamp:** 2025-11-27T15:28:13.794848

**Arguments:**
```json
{'path': 'src/file.py'}
```

**Status:** ❌ Failed

**Error:** File not found: /Users/harrison/Documents/Github/camp-ops-emea/projects/meta-mcp-server/src/file.py

💡 TIP: Use discovery tools first!
  1. List files: TOOL_REQUEST: {"name": "list_files", "arguments": {"pattern": "**/*.py"}}
  2. Search code: TOOL_REQUEST: {"name": "search_code", "arguments": {"pattern": "pattern"}}
  3. Then read what you found

### read_file (Round 2)

**Requested by:** gpt-5.1-codex@codex
**Timestamp:** 2025-11-27T15:28:41.596851

**Arguments:**
```json
{'path': 'src/file.py'}
```

**Status:** ❌ Failed

**Error:** File not found: /Users/harrison/Documents/Github/camp-ops-emea/projects/meta-mcp-server/src/file.py

💡 TIP: Use discovery tools first!
  1. List files: TOOL_REQUEST: {"name": "list_files", "arguments": {"pattern": "**/*.py"}}
  2. Search code: TOOL_REQUEST: {"name": "search_code", "arguments": {"pattern": "pattern"}}
  3. Then read what you found

### list_files (Round 2)

**Requested by:** gpt-5.1-codex@codex
**Timestamp:** 2025-11-27T15:28:41.623343

**Arguments:**
```json
{'pattern': '**/*.py'}
```

**Status:** ✅ Success

**Output:**
```
No files found
```

### search_code (Round 2)

**Requested by:** gpt-5.1-codex@codex
**Timestamp:** 2025-11-27T15:28:41.669695

**Arguments:**
```json
{'pattern': 'pattern'}
```

**Status:** ✅ Success

**Output:**
```
./CLAUDE.md:21:# Run tests matching pattern
./docs/plans/meta-mcp-server.yaml:4:# Implements Anthropic's "Code Execution with MCP" pattern for token-efficient
./docs/plans/meta-mcp-server.yaml:89:      - "Follow MCP SDK patterns from corp-jira reference"
./docs/plans/meta-mcp-server.yaml:1296:        - "Follows corp-jira pattern: Server constructor, setRequestHandler for request types"
./docs/plans/meta-mcp-server.yaml:1357:          - point: "Follow corp-jira pattern"
./docs/plans/meta-mcp-server.yaml:1358:            details: "Server constructor, setRequestHandler pattern"
./docs/plans/meta-mcp-server.yaml:1407:            [typescript-pro] Task 9 implementation passes all success criteria. The main MCP server entry point is correctly wired with all 3 tools (list_servers, get_server_tools, call_tool), follows the corp-jira pattern with Server constructor and setRequestHandler, implements graceful shutdown on SIGINT/SIGTERM, and all 7 tests pass.
./docs/plans/meta-mcp-server.yaml:1408:            [backend-architect] All criteria satisfied. Implementation follows corp-jira pattern with Server constructor and setRequestHandler pattern. Main MCP server starts on stdio, registers all 3 tools, handles ListToolsRequest and CallToolRequest correctly, includes graceful shutdown on SIGINT/SIGTERM. No TODO comments, placeholder structs, or unused variables. All imports resolve, handlers wired with correct dependencies, error handling propagates via ToolNotFoundError.
./docs/plans/meta-mcp-server.yaml:1718:          --env-file is correctly passed. Use the same test pattern as Task 10
./docs/plans/meta-mcp-server.yaml:1810:            [mcp-protocol-expert] Test files exist at correct paths and TypeScript compiles successfully. Tests skip gracefully when config/Docker unavailable. However, key success criteria are not fully met: (1) `--env-file` flag verification is missing - tests don't check for this Docker flag, (2) unused import `beforeEach` in docker-servers.test.ts violate
... (truncated)
```

### read_file (Round 2)

**Requested by:** gpt-5.1-codex@codex
**Timestamp:** 2025-11-27T15:28:41.670138

**Arguments:**
```json
{'path': 'src/file.py'}
```

**Status:** ❌ Failed

**Error:** File not found: /Users/harrison/Documents/Github/camp-ops-emea/projects/meta-mcp-server/src/file.py

💡 TIP: Use discovery tools first!
  1. List files: TOOL_REQUEST: {"name": "list_files", "arguments": {"pattern": "**/*.py"}}
  2. Search code: TOOL_REQUEST: {"name": "search_code", "arguments": {"pattern": "pattern"}}
  3. Then read what you found

---

## Full Debate

### Round 1

**claude-sonnet-4-5-20250929@claude**

## Analysis

**Problem:** Jira's 25 tools = ~16k tokens when `get_server_tools` returns ALL schemas. Current flow: `list_servers` → `get_server_tools` → AI sees full schemas.

**Option Evaluation:**

### 1) Modify tool descriptions ❌
- **Impact**: Marginal. Descriptions are small vs. `inputSchema` objects.
- **Downside**: Hurts discoverability—the core value of MCP.
- **Token savings**: ~10-20% at best.

### 2) Throttle parallel calls ❌
- **Impact**: None on token usage, only latency.
- **Wrong problem**: Doesn't address schema bloat.

### 3) Add search_tools semantic search ⭐⭐
- **Pros**: 
  - Natural AI workflow ("find tools for X")
  - Reduces over-fetching
- **Cons**: 
  - New dependency (embeddings/vector search)
  - Complexity vs. benefit ratio
  - Doesn't solve "I need all Jira tools" scenario

### 4) Paginate tools ⭐
- **Pros**: Limits single-response token load
- **Cons**: 
  - Poor UX (multiple round-trips)
  - AI must know page structure upfront
  - Doesn't reduce total tokens, just spreads them

### 5) Add suggest_server ⭐⭐⭐
- **Pros**: 
  - Minimal code (enhance `list_servers` with better metadata)
  - Natural discovery: `list_servers` → `suggest_server` → `get_server_tools` (filtered)
  - No new protocols
- **Cons**: 
  - Still doesn't solve "get all 25 Jira tools" case
  - Adds tool/round-trip

### 6) Two-tier lazy loading ⭐⭐⭐⭐⭐
**Structure:**
```
get_server_tools({server, summary_only: true})
→ [{name, description}] // ~100 tokens for 25 tools

get_server_tools({server, tools: ["create_issue"]})
→ [full schema] // ~640 tokens for 1 tool
```

**Pros:**
- **Backward compatible**: Default `summary_only=false` maintains current behavior
- **Surgical precision**: AI fetches schemas only when calling tool
- **Scales linearly**: 1 tool = 1 schema load, not 25
- **Leverage existing cache**: `ToolCache` already stores full schemas
- **Minimal code change**: 30-40 LOC in `get-server-tools.ts`

**Cons:**
- Extra round-trip for tool calls (but negligible vs. 16k token savings)
- AI must adapt workflow (but backward compatible eases transition)

**Implementation (pseudo):**
```ts
// get-server-tools.ts:48
export async function getServerToolsHandler(
  input: { server_name: string; summary_only?: boolean; tools?: string[] },
  ...
) {
  const tools = await getFullTools(); // existing logic
  
  if (input.summary_only) {
    return tools.map(t => ({ name: t.name, description: t.description }));
  }
  
  if (input.tools) {
    return tools.filter(t => input.tools.includes(t.name));
  }
  
  return tools; // backward compat
}
```

## Token Math
- **Current**: 16k tokens × 1 call = 16k
- **Option 6 (summary)**: 100 tokens × 1 call + 640 tokens × 3 tool calls = **2020 tokens** (87% reduction)

## Best Practice Alignment
Two-tier loading mirrors:
- REST API conventions (list vs. detail endpoints)
- LSP protocol (symbol list → hover for details)
- Database query patterns (SELECT id vs. SELECT *)

VOTE: {"option": "Option 6: Two-tier lazy loading", "confidence": 0.95, "rationale": "87% token reduction with backward compatibility, minimal code change (~40 LOC), scales to 100+ tool servers, aligns with industry patterns. Summary-first discovery + on-demand schemas solves both discoverability AND token flooding."}

*2025-11-27T15:28:49.544390*

---

**gemini-2.5-pro@gemini**

[ERROR: RuntimeError: CLI process failed: Options:
  -m, --model                    Model      [string] [default: "gemini-2.5-pro"]
  -p, --prompt                   Prompt. Appended to input on stdin (if any).
                                                                        [string]
  -s, --sandbox                  Run in sandbox?                       [boolean]
      --sandbox-image            Sandbox image URI.                     [string]
  -d, --debug                    Run in debug mode?   [boolean] [default: false]
  -a, --all_files                Include ALL files in context?
                                                      [boolean] [default: false]
      --show_memory_usage        Show memory usage in status bar
                                                      [boolean] [default: false]
  -y, --yolo                     Automatically accept all actions (aka YOLO
                                 mode, see
                                 https://www.youtube.com/watch?v=xvFZjo5PgG0 for
                                 more details)?       [boolean] [default: false]
      --telemetry                Enable telemetry? This flag specifically
                                 controls if telemetry is sent. Other
                                 --telemetry-* flags set specific values but do
                                 not enable telemetry on their own.    [boolean]
      --telemetry-target         Set the telemetry target (local or gcp).
                                 Overrides settings files.
                                              [string] [choices: "local", "gcp"]
      --telemetry-otlp-endpoint  Set the OTLP endpoint for telemetry. Overrides
                                 environment variables and settings files.
                                                                        [string]
      --telemetry-log-prompts    Enable or disable logging of user prompts for
                                 telemetry. Overrides settings files.  [boolean]
  -c, --checkpointing            Enables checkpointing of file edits
                                                      [boolean] [default: false]
  -v, --version                  Show version number                   [boolean]
  -h, --help                     Show help                             [boolean]

Unknown arguments: include-directories, includeDirectories
]

*2025-11-27T15:28:49.878156*

---
