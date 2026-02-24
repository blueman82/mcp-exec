---
name: campaign-rca
description: Generate comprehensive Root Cause Analysis documentation
---

# Campaign Root Cause Analysis

Generate comprehensive RCA documentation.

## Arguments

```
/campaign-rca <ticket> <incident_type>
```

- `ticket`: Jira ticket ID (required)
- `incident_type`: oom, crash, slow_queries, stuck_workflows, reboot, outage

## Instructions

### RCA Structure

Every RCA should include:
1. **Summary** - One sentence root cause
2. **Timeline** - Chronological events
3. **Evidence** - Data supporting conclusion
4. **Actions Taken** - What was done
5. **Recommendations** - Prevention measures

### RCA Templates by Type

**OOM Event:**
```
h2. Root Cause Analysis - OOM Event

h3. Summary
[Process] consumed [X GB] memory on [server], exhausting available RAM and triggering OOM killer.

h3. Timeline
||Time (UTC)||Event||
|[HH:MM]|[First indicator]|
|[HH:MM]|OOM killer activated|
|[HH:MM]|Process terminated|
|[HH:MM]|Services recovered|

h3. Evidence
||Indicator||Value||
|Server RAM|[X GB]|
|Swap|[0B/configured]|
|Killed Process|[name, PID, RSS]|
|Trigger Process|[name - triggered, not caused]|

h3. Root Cause Detail
[Detailed explanation]

h3. Actions Taken
# [Action 1]
# [Action 2]

h3. Recommendations
* [Prevention measure 1]
* [Prevention measure 2]
```

**Database Performance:**
```
h2. Root Cause Analysis - Database Performance

h3. Summary
[Issue description - e.g., Missing index on table X caused full table scans]

h3. Evidence
||Check||Finding||
|Running Queries|[details]|
|Wait Events|[DataFileRead, etc.]|
|Index Usage|[seq:idx ratio]|
|Table Stats|[last_analyze, bloat]|

h3. Actions Taken
# [Action with SQL if applicable]

h3. Verification
{code:sql}
[Verification query]
{code}

h3. Results
||Metric||Before||After||
|Query Time|[X min]|[Y sec]|
```

**Storage Exhaustion:**
```
h2. Root Cause Analysis - Storage Exhaustion

h3. Summary
RDS storage reached critically low levels at [TIME UTC], causing workflow failures. Root cause: [workflow design inefficiency / accumulated temp objects / keepResult flags].

h3. Current State
||Metric||Value||
|Allocated Storage|[X GB]|
|Used Storage|[X GB (Y%)]|
|Free Storage|[X GB]|
|Status|[Workflows resumed / Still impacted]|

h3. Storage Timeline (UTC)
||Time||Free Space||Event||
|[HH:MM]|[X MB]|[First workflow failure]|
|[HH:MM]|[X MB]|[Additional failures]|
|[HH:MM]|[X GB]|[Recovery after cleanup]|

h3. Top Storage Consumers

h4. Workflow Temp Tables
||Workflow ID||Label||Status||Total Size||
|WKF[X]|[Label]|[Status]|[X GB]|

h4. Delivery Prep Tables (grp%)
||Table||Size||
|grp[X]|[X GB]|

h3. Configuration Issues Found
||Issue||Count||Impact||
|Workflows with keepResult=1|[X]|Temp tables retained|
|Workflows with keepResult="true" in mdata|[X]|Additional retention|
|Workflows with showSQL="true"|[X]|Debug overhead|
|Data retention period|[X days]|Could reduce to [Y days]|

h3. Root Cause Detail
[Detailed explanation - e.g., non-selective filters matching 97% of table]

h3. Recommendations

h4. Immediate Actions (Customer)
# Reset {{keepResult}} flags on workflows retaining temp tables
# Reset {{showSQL}} flags on debug-enabled workflows
# Review and delete orphaned wkf% and grp% temp objects

h4. Short-term (Customer)
# Review workflow [WKF ID] - [X GB] temp tables indicates design issue
# Optimize query filters to use more selective conditions
# Consider reducing retention from [X] to [Y] days

h4. Long-term (Customer)
# Implement workflow design review before production deployment
# Schedule regular temp table cleanup maintenance

h3. Actions Completed (Adobe)
* Executed ANALYZE on critical tables: [list]
* Identified workflows with keepResult flags
* [Other actions]
```

**Service Crash:**
```
h2. Root Cause Analysis - Service Crash

h3. Summary
[Service] became unresponsive due to [cause].

h3. Timeline
||Time (UTC)||Event||
|[HH:MM]|Health check failed|
|[HH:MM]|Core dump captured|
|[HH:MM]|Services restarted|

h3. Evidence
* Core dump: [S3 path]
* Health check: [port X OK, port Y timeout]
* Logs: [relevant log entries]

h3. Actions Taken
[Auto-remediation or manual steps]

h3. Next Steps
* [Follow-up investigation]
```

### Important Rules

1. **Be specific** - Include exact values, timestamps
2. **No internal details** - Don't mention AWS profiles
3. **Attach evidence** - CSV files, screenshots
4. **Draft first** - Always review before posting
5. **Neutral automation framing** - When automated monitoring raised a false positive or had a minor detection gap, document it as a system behaviour observation — not as a named failure of a specific tool. Use section headers like `OOM Detection — False Positive` rather than `[Tool] reported X — Incorrect`. The goal is improvement, not blame.
