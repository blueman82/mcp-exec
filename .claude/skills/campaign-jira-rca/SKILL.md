---
name: campaign-jira-rca
description: Generate properly formatted Jira RCA comments for Campaign incidents
---

# Campaign Jira RCA Comment Generator

Generate properly formatted Jira wiki markup comments.

## Arguments

```
/campaign-jira-rca <ticket> <issue_type>
```

- `ticket`: Jira ticket ID (e.g., CPGNREQ-186263)
- `issue_type`: db_performance, oom, stuck_workflows, reboot, index_fix, cleanup

## Instructions

### Jira Wiki Markup Reference

| Element | Syntax |
|---------|--------|
| Heading 2 | `h2. Title` |
| Heading 3 | `h3. Subtitle` |
| Bold | `*bold*` |
| Code inline | `{{code}}` |
| Code block | `{code}...{code}` |
| Table header | `\|\|Col1\|\|Col2\|\|` |
| Table row | `\|Cell1\|Cell2\|` |
| Bullet | `* item` |

### RCA Templates

**Database Performance:**
```
h2. Investigation Findings - Database Performance

h3. Root Cause
[Describe root cause]

h3. Evidence
||Check||Finding||
|Running Queries|[X queries over Y minutes]|
|Wait Events|[DataFileRead, etc.]|

h3. Actions Taken
# [Action 1]
# [Action 2]

h3. Results
* Before: [metric]
* After: [metric]
```

**OOM Investigation:**
```
h2. OOM Investigation - Root Cause Analysis

h3. Root Cause
[Process] consumed [X GB] causing OOM.

h3. Evidence
||Indicator||Value||
|Server RAM|[X GB]|
|Swap|0B|
|Killed Process|[name, PID, RSS]|

h3. Recommendation
[Preventive measures]
```

### Automation Detection Notes Template

When automated monitoring (e.g. OOM detection, process checks) flags something that turns out to be a false positive or has a minor discrepancy, document it with a neutral system-level section — **do not name the automation system in the header alongside negative labels like "False Positive" or "Incorrect"**.

```
h4. OOM Detection — False Positive

Automated monitoring flagged an OOM signature. Verified no actual OOM events on host.

*Pattern matched:* [e.g., "kill" keyword found in syslog from operator grep command at HH:MM]
*Verified clean:*
{code}
$ sudo grep -i 'Out of memory' /var/log/kern.log
(no results)
$ sudo dmesg -T | grep -i 'kill|oom|out of memory'
(no results)
$ free -h
Mem: 30Gi total, Xgi used, Ygi free
{code}
```

```
h4. Process Start Date — Clarification

Automated report listed watchdog start date as the web start date.
Actual web process start: [date from pdump web@default].
```

### Important Rules

1. **DRAFT FIRST** - Always show comment before posting
2. **NO INTERNAL DETAILS** - Don't mention AWS profiles, internal URLs
3. **INCLUDE COMMANDS** - Show SQL for reproducibility
4. **ATTACH DATA** - Upload CSV for large datasets
5. **NEUTRAL AUTOMATION FRAMING** - When documenting automation false positives or misdetections, use system-level section headers (e.g., `OOM Detection — False Positive`), not `[Tool Name] reported X — Incorrect`. The purpose is to capture the detection gap for improvement, not to record that a tool was wrong.

### API Usage

```javascript
// Add comment
await jira.add_jira_comment({
  issueIdOrKey: '<ticket>',
  comment: { body: 'Wiki markup here' }
});

// Upload attachment
await jira.upload_attachment({
  issueIdOrKey: '<ticket>',
  filePath: '/tmp/data.csv'
});
```
