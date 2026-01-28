---
name: campaign-core-dump-analyze
description: Download and analyze core dumps from S3 for crash investigation
---

# Campaign Core Dump Analysis

Download and analyze core dumps from S3.

## Arguments

```
/campaign-core-dump-analyze <instance> [--timestamp=<ts>]
```

- `instance`: Campaign instance name (required)
- `--timestamp`: Specific dump timestamp (optional)

## Instructions

### S3 Path Structure

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

### Local Zerocrash Directory

Core dumps may also be in:
```bash
ssh <instance>-1.campaign.adobe.com \
  "ls -la /usr/local/neolane/zerocrash/"
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
