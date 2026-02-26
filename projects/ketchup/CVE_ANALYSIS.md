# CVE Analysis: Ketchup HTTP Library Vulnerabilities

**Date**: 2026-02-26
**Scope**: Python (pip-audit), corp_jira_mcp (npm audit), ketchup-log-viewer (npm audit)
**Status**: CVE-2026-21441 remediated and committed

---

## Full CVE Inventory (9 unique advisories)

| # | ID | Severity | CVSS | Package | Stack | Fix Available |
|---|-----|----------|------|---------|-------|---------------|
| 1 | CVE-2026-21441 | HIGH | 7.5 | urllib3 2.6.0→2.6.3 | Python/prod | ✅ Patched |
| 2 | GHSA-jmr7-xgp7-cmfj | CRITICAL | 7.5 | fast-xml-parser 4.x | Node/mcp | ✅ npm audit fix |
| 3 | GHSA-m7jm-9gc2-mpf2 | CRITICAL | — | fast-xml-parser 4.x | Node/mcp | ✅ npm audit fix |
| 4 | GHSA-345p-7cg4-v4c7 | HIGH | — | @modelcontextprotocol/sdk | Node/mcp | ✅ npm audit fix |
| 5 | GHSA-3ppc-4f35-3m26 | HIGH | — | minimatch | Node/both | ✅ npm audit fix |
| 6 | GHSA-mw96-cpmx-2vgc | HIGH | — | rollup | Node/log-viewer | ✅ npm audit fix |
| 7 | GHSA-2g4f-4pwh-qvx6 | MODERATE | — | ajv | Node/both | ✅ npm audit fix |
| 8 | GHSA-w7fw-mjwx-w883 | LOW | — | qs | Node/mcp | ✅ npm audit fix |
| 9 | GHSA-gq3j-xvxp-8hrf | LOW | — | hono | Node/mcp | ✅ npm audit fix |

---

## Priority CVE: CVE-2026-21441

### CVE Identification

| Field | Value |
|-------|-------|
| **CVE ID** | CVE-2026-21441 |
| **CVSS Score** | 7.5 HIGH (CVSS v3.1) |
| **CWE** | CWE-409 (Improper Handling of Highly Compressed Data / Data Amplification) |
| **Affected Component** | urllib3 |
| **Affected Versions** | 1.22 through 2.6.2 |
| **Fixed Version** | 2.6.3 |
| **Ketchup Version (pre-fix)** | 2.6.0 |

### Vulnerability Details

**What is broken**: urllib3's streaming API fails to prevent decompression bomb attacks on redirect responses. When following HTTP redirects, the library unnecessarily decompresses the entire response body *before* any user-initiated read, even when `preload_content=False` is set and read limits are configured. A hostile server can respond to a redirect with a heavily compressed payload that expands to many gigabytes, consuming all client memory.

**Attack vector**: Network (AV:N). Requires no user interaction or special privileges on the client side. The attacker must control or compromise an HTTP server that the client follows a redirect to.

**Prerequisites**:
1. Attacker controls an HTTP endpoint that the application connects to
2. The application follows HTTP redirects (default behavior)
3. urllib3 is used as the HTTP transport layer

**Exploitability in Ketchup's context**: urllib3 is a *transitive* dependency — it is not Ketchup's primary HTTP library. The primary clients are `aiohttp` and `httpx`, which do not use urllib3. urllib3 enters the dependency tree through:
- `botocore` → `boto3` / `aioboto3` (AWS SDK calls: DynamoDB, Secrets Manager, SQS)
- `requests` (transitive via botocore)
- `docker` (used in deploy scripts, not production containers)

All botocore/boto3 calls go to AWS service endpoints (`*.amazonaws.com`), which are highly trusted and not attacker-controlled. The practical exploitation path would require:
- Compromising an AWS service endpoint (nation-state level), OR
- A supply-chain attack on AWS SDK itself

**Practical risk**: LOW despite CVSS 7.5. The CVSS score correctly models the general case (attacker-controlled redirecting server), but Ketchup's specific usage (botocore → AWS only) substantially reduces exploitability.

### Codebase Exposure

**Files/functions affected**: None directly. No production Python file imports or calls urllib3 APIs. All exposure is through botocore's internal HTTP transport.

**Reachability in current code paths**: Every call to `aioboto3`/`boto3` that makes network requests is a potential activation path. Key call sites:

- `packages/db/` — DynamoDB reads/writes
- `packages/secrets/` — Secrets Manager `get_secret_value()`
- `ketchup_unified_scheduler/tasks/jira_reporter_task.py` — continuous SQS polling
- `packages/integrations/` — various AWS integrations

All of these exclusively contact AWS endpoints. None accept user-supplied URLs or follow redirects to untrusted servers.

### Remediation

#### Option A: Lock file update (implemented)

**Technical approach**: `uv lock --upgrade-package urllib3` updates `uv.lock` from urllib3 2.6.0 → 2.6.3. No changes to `pyproject.toml` required; urllib3 is a transitive dep managed entirely through lock file resolution.

**Effort**: ~2 minutes (already done)

**Risk**: Minimal. urllib3 2.6.3 is a patch release. The fix only changes behavior for redirect responses where `preload_content=False`, which is not called directly by Ketchup code.

**Verification**: All 57 fast tests pass post-upgrade.

#### Option B: Pin urllib3 >= 2.6.3 in pyproject.toml

**Technical approach**: Add explicit `urllib3>=2.6.3` to `[project.dependencies]`. This makes the constraint explicit and documented.

**Effort**: 5 minutes

**Risk**: Minimal. Useful if botocore ever tries to pin to an older urllib3 version in a future update.

**Note**: Option A is sufficient unless you want auditable pinning in pyproject.toml.

---

## Recommended Action

**CVE-2026-21441**: Option A — **DONE**. Lock file updated to urllib3 2.6.3, tests pass.

---

## Remaining CVEs: Node.js Stacks

### corp_jira_mcp (6 advisories)

The MCP JIRA service has 6 vulnerabilities, with one critical:

**GHSA-jmr7-xgp7-cmfj / GHSA-m7jm-9gc2-mpf2 (fast-xml-parser, CRITICAL)**

- **Type**: XML entity expansion DoS + entity encoding bypass via regex injection in DOCTYPE
- **Affected via**: `@aws-sdk/xml-builder` (AWS SDK for JavaScript v3)
- **Fix**: `npm audit fix` in `corp_jira_mcp/` updates fast-xml-parser ≥ 5.3.6
- **Exploitability**: The MCP service calls the JIRA API and receives XML responses. If JIRA's API responses could be influenced by an attacker (e.g., via specially crafted issue content containing DOCTYPE payloads), this could be triggered. Moderate risk.
- **Recommendation**: Run `npm audit fix` in `corp_jira_mcp/`. Effort: ~15 minutes + verify MCP service behavior.

**GHSA-345p-7cg4-v4c7 (@modelcontextprotocol/sdk, HIGH)**

- **Type**: Cross-client data leak via shared server/transport instance reuse
- **Fix**: `npm audit fix` → upgrades to sdk ≥ 1.26.0
- **Exploitability**: Affects multi-client MCP scenarios. The corp_jira_mcp service runs as a single-instance server for Ketchup's internal use. Low practical risk, but should still be updated.

**Remaining (minimatch, ajv, qs, hono)**: All low/moderate, dev dependencies or non-critical paths. `npm audit fix` resolves all.

**Recommended action**: Single `npm audit fix` run in `corp_jira_mcp/` resolves all 6. Requires testing MCP tool calls afterward. Estimated effort: 30 minutes.

### ketchup-log-viewer (3 advisories)

- **GHSA-mw96-cpmx-2vgc (rollup, HIGH)**: Arbitrary file write via path traversal — but rollup is a *build-time* dependency. The log viewer is a Next.js app; rollup is used during `npm run build`, not at runtime. Production containers do not include node_modules. Risk: LOW (build machine exposure only).
- **GHSA-3ppc-4f35-3m26 (minimatch, HIGH)** and **GHSA-2g4f-4pwh-qvx6 (ajv, MODERATE)**: Both dev dependencies, ReDoS vectors. Not reachable at runtime.

**Recommended action**: `npm audit fix` in `ketchup-log-viewer/`. Effort: 15 minutes.

---

## Effort Estimate

| Work Item | Effort |
|-----------|--------|
| CVE-2026-21441 urllib3 fix (Python) | **DONE** |
| corp_jira_mcp: `npm audit fix` + test | ~30 min |
| ketchup-log-viewer: `npm audit fix` | ~15 min |
| **Total remaining** | ~45 min |
