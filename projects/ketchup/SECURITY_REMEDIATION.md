# Security Remediation Report — Ketchup

**Date**: 2026-02-26
**Investigator**: Theo
**Scan Tool**: pip-audit 2.10.0 + OSV API
**Status**: ALL 9 CVEs REMEDIATED ✅

---

## 1. CVE Triage Summary

| # | CVE ID | GHSA | Package | Affected Version | Fix Version | CVSS Severity | Rank | Reasoning |
|---|--------|------|---------|-----------------|-------------|---------------|------|-----------|
| 1 | CVE-2025-69223 | GHSA-6mq8-rvhq-8wgg | aiohttp | <3.13.3 | 3.13.3 | **HIGH** | 1 | Zip bomb via auto_decompress — only HIGH severity; active decompression path in every HTTP response handler |
| 2 | CVE-2026-21441 | GHSA-38jv-5279-wg99 | urllib3 | <2.6.3 | 2.6.3 | HIGH | 2 | Decompression bomb via redirect responses, streaming API; ketchup uses urllib3 via requests/boto3 to untrusted endpoints (Slack API, JIRA) |
| 3 | CVE-2025-69228 | GHSA-6jhg-hg63-jvvf | aiohttp | <3.13.3 | 3.13.3 | MODERATE | 3 | DoS via large payloads — directly exposed in FastAPI request handling for Slack webhooks |
| 4 | CVE-2025-69229 | GHSA-g84x-mcqj-x9qq | aiohttp | <3.13.3 | 3.13.3 | MODERATE | 4 | DoS via chunked messages — chunked transfer is common in Slack event payloads |
| 5 | CVE-2025-69227 | GHSA-jj3x-wxrx-4x23 | aiohttp | <3.13.3 | 3.13.3 | MODERATE | 5 | DoS by bypassing asserts — triggered by Python's `-O` (optimize) flag which removes assert statements |
| 6 | CVE-2025-69224 | GHSA-69f9-5gxw-wvc2 | aiohttp | <3.13.3 | 3.13.3 | LOW | 6 | Unicode processing discrepancy in header values — could cause parsing desync; lower exploitability in internal Slack traffic |
| 7 | CVE-2025-69225 | GHSA-mqqc-3gqh-h2x8 | aiohttp | <3.13.3 | 3.13.3 | LOW | 7 | Unicode match groups in regexes for ASCII protocol — same class as CVE-2025-69224 but narrower scope |
| 8 | CVE-2025-69230 | GHSA-fh55-r93g-j68g | aiohttp | <3.13.3 | 3.13.3 | LOW | 8 | Cookie parser warning storm — log flooding only; no functional impact unless log-rate limiting is misconfigured |
| 9 | CVE-2025-69226 | GHSA-54jq-c3m8-4m76 | aiohttp | <3.13.3 | 3.13.3 | LOW | 9 | Brute-force leak of static file path components — ketchup has no static file serving exposed to untrusted clients |

**Ranking logic**:
- Severity (HIGH > MODERATE > LOW) is primary factor
- Within same severity tier: code path reachability determines order
- CVE-2025-69223 (zip bomb) ranked #1 as HIGH + directly triggered by any compressed HTTP response body
- CVE-2026-21441 ranked #2 because ketchup makes outbound requests to Slack/JIRA (external, potentially redirected) via boto3/requests which depend on urllib3
- All 8 aiohttp CVEs are DoS-class — no RCE, no data exfiltration risk
- urllib3 CVE is also DoS-class (memory exhaustion via decompression of redirect body)

---

## 2. Top CVE Deep-Dive — CVE-2025-69223 (aiohttp zip bomb)

### Vulnerability Description
aiohttp's `auto_decompress=True` (default) decompresses content based on `Content-Encoding` header. A malicious server returning a small compressed response that decompresses to gigabytes can cause unbounded memory allocation on the client.

### Code Path Analysis — Is Ketchup Vulnerable?

**aiohttp usage in ketchup** (direct):
- `packages/core/async_client.py` — base class for all HTTP clients, uses `aiohttp.ClientSession`
- All service clients inherit from `AsyncClient` and call external APIs (Slack, JIRA, Azure OpenAI, AWS)
- Slack API is Adobe-internal/trusted, but JIRA and Azure OpenAI are external

**Verdict**: Ketchup was **exploitable** on aiohttp ≤3.13.2 if any external endpoint returned a compressed redirect response or compressed payload. Fix already applied.

### Current Mitigations (post-fix)
- aiohttp upgraded to 3.13.3 — zip bomb fix applied at library level
- No application-level workaround needed; no code changes required

### Remediation Applied
- `pyproject.toml`: `aiohttp>=3.13.3` (commit `a46dcf8c`, 2026-02-26)
- `uv.lock`: pinned to `aiohttp==3.13.3`
- pip-audit confirms 0 vulns for aiohttp 3.13.3

---

## 3. Top CVE #2 Deep-Dive — CVE-2026-21441 (urllib3 decompression bomb)

### Vulnerability Description
urllib3 ≤2.6.2 reads and decompresses the **entire** redirect response body before following the redirect when `preload_content=False` (streaming mode). No read limit applies to decompressed data. A malicious redirect target returns a gzip bomb, causing excessive CPU and memory usage.

### Code Path Analysis
- `urllib3` is a transitive dependency via: `requests` → `urllib3` and `botocore` → `urllib3`
- ketchup uses `requests` for synchronous HTTP (utility scripts) and `boto3`/`botocore` for AWS SDK calls
- AWS SDK calls go to AWS endpoints (trusted), but requests calls go to Slack, JIRA (partially trusted/external)
- Streaming (`preload_content=False`) is not commonly used in ketchup's request layer, reducing practical exploitability

### Remediation Applied
- `pyproject.toml`: `urllib3>=2.6.3` added as direct dependency pin (commit `5bc19f90`, 2026-02-26)
- `uv.lock`: already updated to `urllib3==2.6.3` in the pinning commit
- **`uv sync` run 2026-02-26** to apply the lock file change to `.venv` (was stuck at 2.6.0)
- pip-audit now reports 0 vulnerabilities

---

## 4. Recommended Action

| Item | Decision |
|------|----------|
| Effort | <30 minutes (completed) |
| Risk level | None — pure version bumps, no API changes |
| Breaking changes | None — `aiohttp>=3.13.3` and `urllib3>=2.6.3` are drop-in patch upgrades |
| Coverage impact | None — 57/57 tests pass post-upgrade |
| Deploy urgency | Deploy on next regular cycle; no emergency deploy needed (DoS-only, not RCE) |

---

## 5. Outcome

### Changes Made

| Commit | What | When |
|--------|------|------|
| `a46dcf8c` | `aiohttp>=3.13.3` pinned in pyproject.toml + pip-audit added to dev deps | 2026-02-26 |
| `5bc19f90` | `urllib3>=2.6.3` pinned in pyproject.toml + uv.lock updated | 2026-02-26 |
| `uv sync` | urllib3 2.6.0 → 2.6.3 applied to local .venv | 2026-02-26 (this session) |

### Test Results
```
57 passed in 8.99s  (make test-fast, 2026-02-26)
```

### pip-audit Verification
```
No vulnerabilities found. All clean.  (pip-audit 2.10.0, 2026-02-26)
```

### Pending
- **Production deploy**: Neither fix has been deployed yet. Both commits are on `main`. Deploy with `./deploy` on next regular cycle.
- **Commit note**: The `uv sync` applied a local change to `.venv/` — this directory is `.gitignore`'d, no commit needed. The lock file `uv.lock` was already correct at `urllib3==2.6.3`.

---

## 6. Ongoing Security Posture

`pip-audit` is now a dev dependency (`pip-audit>=2.10.0` in `[dependency-groups].dev`). Recommended usage:

```bash
.venv/bin/pip-audit               # scan current venv
.venv/bin/pip-audit --format json  # machine-readable output
```

Add to pre-deploy validation gate or CI to prevent future CVE slippage.
