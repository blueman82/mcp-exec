---
name: campaign-core-dump-analyze
description: Download and analyze core dumps from S3 for crash investigation
---

# Campaign Core Dump Analysis

Download and analyze core dumps from S3 or on-host.

## Arguments

```
/campaign-core-dump-analyze <instance> [--timestamp=<ts>]
```

- `instance`: Campaign instance name (required)
- `--timestamp`: Specific dump timestamp (optional)

## Diagnostic Script (Quick Core Dump Check)

The comprehensive diagnostic script lists all local core dumps with sizes and dates:

```bash
ssh -o ConnectTimeout=30 <instance>-1.campaign.adobe.com "bash -s" \
  < ~/.claude/scripts/campaign-diagnose.sh 2>/dev/null
```

Check the `core_dumps` section of the JSON output. For backtrace analysis, use the manual gdb command in Step 0 below.

## Instructions

### Container Awareness

Campaign instances typically have multiple containers (e.g., `<instance>-1`, `<instance>-2`, `<instance>-3`). Core dumps are local to the container where the crash occurred. Check the watchdog log or the alert to identify which container crashed, then SSH to that specific container. If unsure, check all containers:

```bash
for i in 1 2 3; do
  echo "=== <instance>-$i ==="
  ssh <instance>-$i.campaign.adobe.com \
    "sudo find /home/neolane/nl7/var/ /home/neolane/nl6/var/ \
     -name 'core.*' -newer /tmp -type f 2>/dev/null | head -5" 2>/dev/null
done
```

### Step 0: Check Local Core Dumps FIRST

Before checking S3, core dumps are often still on the host:

```bash
# Primary local paths (check both nl6 and nl7)
ssh <instance>-1.campaign.adobe.com \
  "sudo find /home/neolane/nl7/var/ /home/neolane/nl6/var/ /usr/local/neolane/zerocrash/ \
   -type f -name 'core.*' -exec ls -lh {} \; 2>/dev/null"
```

**On-host GDB backtrace (fastest path to root cause):**
```bash
# Get the backtrace directly from the core dump on the host
ssh <instance>-1.campaign.adobe.com \
  "sudo timeout 30 gdb -batch -ex 'bt' -ex 'quit' \
   /usr/local/neolane/nl7/bin/nlserver /home/neolane/nl7/var/core.<pid> 2>&1 | tail -40"
```

For nl6 instances:
```bash
ssh <instance>-1.campaign.adobe.com \
  "sudo timeout 30 gdb -batch -ex 'bt' -ex 'quit' \
   /usr/local/neolane/nl6/bin/nlserver /home/neolane/nl6/var/core.<pid> 2>&1 | tail -40"
```

**Identify which PID crashed (match to watchdog log):**
```bash
ssh <instance>-1.campaign.adobe.com \
  "sudo grep -i 'crash\|SRV-810' /usr/local/neolane/nl7/log/default/watchdog.log | tail -10"
```

The PID in the watchdog crash entry (e.g., `pid=2480476`) corresponds to the core dump filename (`core.2480476`).

### S3 Path Structure (if not found locally)

```
s3://campaign-capture/core_dumps/<instance>/<timestamp>/
```

Files:
- `core_nlserverweb.<pid>.gz` - Web process crash
- `core_apache.<pid>.gz` - Apache crash
- `core_nlserver.<pid>.gz` - Other nlserver crash

### Step 1: List Available Core Dumps

```bash
aws s3 ls s3://campaign-capture/core_dumps/<instance>/ \
  --profile campaign_prod_v7
```

Or for V8:
```bash
aws s3 ls s3://campaign-capture/core_dumps/<instance>/ \
  --profile campaign_prod_v8
```

### Step 2: List Specific Timestamp

```bash
aws s3 ls s3://campaign-capture/core_dumps/<instance>/<timestamp>/ \
  --profile campaign_prod_v7
```

### Step 3: Download Core Dump

```bash
aws s3 cp s3://campaign-capture/core_dumps/<instance>/<timestamp>/core_nlserverweb.<pid>.gz \
  /tmp/core_dump.gz \
  --profile campaign_prod_v7
```

### Step 4: Extract

```bash
gunzip /tmp/core_dump.gz
```

### Step 5: Analyze (if tools available)

**Basic info:**
```bash
file /tmp/core_dump
```

**With GDB (if available):**
```bash
gdb -c /tmp/core_dump -ex "bt" -ex "quit"
```

### Local Core Dump Paths

Core dumps may be in any of these locations:
```bash
/home/neolane/nl7/var/core.*          # nl7 instances (most common)
/home/neolane/nl6/var/core.*          # nl6/v8 instances
/usr/local/neolane/zerocrash/         # zerocrash directory
```

### Common Core Dump Causes

| File Pattern | Likely Cause |
|--------------|--------------|
| core_nlserverweb | Web process hung/OOM |
| core_apache | Apache crash |
| core_mta | MTA process issue |

### Size Reference

- Small (~2MB): Apache child
- Medium (~30MB): Apache main
- Large (~500MB+): nlserverweb with large heap

### Jira Documentation

```
h2. Core Dump Analysis

h3. S3 Location
s3://campaign-capture/core_dumps/<instance>/<timestamp>/

h3. Files Found
||File||Size||
|core_nlserverweb.123456.gz|528MB|

h3. Analysis
[Findings from dump analysis]
```
