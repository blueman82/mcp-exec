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

## Automated Investigation Script (Recommended First Step)

Run the OOM investigation script to get a full JSON report:

```bash
ssh -o ConnectTimeout=30 <instance>-<container>.campaign.adobe.com "bash -s" \
  < ~/.claude/scripts/campaign-oom-investigate.sh 2>/dev/null | jq .
```

JSON output includes: memory state, top memory processes, nlserver RSS breakdown, OOM kill details (killed process, RSS, VM, invoker), kernel OOM events (last 7 days), user sessions, psql history, and a risk assessment (`low`/`elevated`/`high`/`critical`).

## Instructions

### ⚠️ OOM Terminology

When logs say "X invoked oom-killer":
- Process X **triggered** OOM by requesting memory
- Process X did **NOT necessarily cause** the OOM
- **Actual cause** is whatever consumed the memory

Example: "falcon-sensor invoked oom-killer" = CrowdStrike needed memory, NOT that it caused OOM!

### ⚠️ False Positive — Operator Commands in Syslog

Automated OOM detection can match pattern keywords (`kill`, `oom`, `out of memory`) found in syslog entries that record **operator investigation commands**, not actual OOM events.

Before concluding OOM, check if the detection was triggered by an operator's own grep:

```bash
ssh <instance> "sudo grep -i 'COMMAND.*grep' /var/log/syslog | grep -i 'kill\|oom\|memory' | tail -10"
```

If you see `COMMAND=/bin/grep -i kill|oom` in the output, the pattern matched an operator command — not a real event. Verify kern.log is clean:

```bash
ssh <instance> "sudo grep -i 'Out of memory' /var/log/kern.log && sudo dmesg -T | grep -i 'kill\|oom\|out of memory'"
# Both should return empty if no real OOM occurred
```

**When documenting a false positive, use neutral system-level framing:**
- ❌ Avoid: `Automation "OOM Signature found" — False Positive`
- ✓ Use: `OOM Detection — False Positive (pattern matched operator grep command)`

The goal is to capture the detection gap so it can be improved — not to record that any tool was wrong.

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
