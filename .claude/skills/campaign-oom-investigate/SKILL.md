---
name: campaign-oom-investigate
description: Investigate Out of Memory (OOM) events on Campaign servers
---

# Campaign OOM Investigation

Investigate Out of Memory events.

## Arguments

```
/campaign-oom-investigate <instance> [--container=<n>]
```

- `instance`: Campaign instance name (required)
- `--container`: Container number (default: 1)

## Instructions

### ⚠️ OOM Terminology

When logs say "X invoked oom-killer":
- Process X **triggered** OOM by requesting memory
- Process X did **NOT necessarily cause** the OOM
- **Actual cause** is whatever consumed the memory

Example: "falcon-sensor invoked oom-killer" = CrowdStrike needed memory, NOT that it caused OOM!

### Investigation Commands

**Current Memory:**
```bash
ssh <instance>-<container>.campaign.adobe.com \
  "free -h && echo '---' && ps aux --sort=-%mem | head -15"
```

**OOM Events (Kernel):**
```bash
ssh <instance>-<container>.campaign.adobe.com \
  "sudo journalctl -k --since '24 hours ago' | grep -iE 'oom|out of memory|killed process' | tail -50"
```

**Syslog:**
```bash
ssh <instance>-<container>.campaign.adobe.com \
  "sudo grep -iE 'oom|out of memory|killed' /var/log/syslog | tail -30"
```

**User Sessions:**
```bash
ssh <instance>-<container>.campaign.adobe.com \
  "who && echo '---' && last -20"
```

**psql History (if DB query caused OOM):**
```bash
ssh <instance>-<container>.campaign.adobe.com \
  "sudo cat /root/.psql_history | tail -50"
```

### Key Indicators

| Indicator | Meaning |
|-----------|---------|
| Load: 0.5, 15, 20 | Low 1m, high 5m/15m = recent stress |
| SwapTotal: 0 | No swap = immediate OOM |
| psql multi-GB RSS | Unbounded query |

### Common Causes

1. Large psql queries without LIMIT
2. GDPR exports (\copy)
3. Memory-heavy workflows
4. Web process leak
5. No swap configured

### RCA Template

```
h2. OOM Investigation

h3. Root Cause
[Process] consumed [X GB], exhausting RAM ([Y GB]).

h3. Evidence
||Indicator||Value||
|Server RAM|[X GB]|
|Swap|0B|
|Killed Process|[name, PID, RSS]|

h3. Recommendation
[Preventive measures]
```
