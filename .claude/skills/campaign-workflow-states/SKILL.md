---
name: campaign-workflow-states
description: Quick reference for Campaign workflow states and queries
---

# Campaign Workflow States Reference

Quick reference for workflow states and common queries.

## Arguments

```
/campaign-workflow-states [--query=<type>]
```

- `--query`: running, stuck, errors, recent (optional, shows reference if not provided)

## Instructions

### Workflow State Reference

| istate | Status | Description | Safe to Drop Tables? |
|--------|--------|-------------|---------------------|
| 0 | Being edited | Draft/design mode | ✅ Yes |
| 2 | Running | Currently executing | ❌ NO! |
| 11 | Finished | Completed successfully | ✅ Yes |
| 13 | Error | Failed execution | ❌ NO (may retry) |
| 15 | Paused | Manually paused | ❌ NO (will resume) |
| 20 | Starting | Initializing | ❌ NO! |

### Common Queries

**All Running Workflows:**
```sql
SELECT iworkflowid, slabel, istate, tslaststart
FROM xtkworkflow
WHERE istate = 2
ORDER BY tslaststart DESC;
```

**Stuck Workflows (running > 1 hour):**
```sql
SELECT iworkflowid, slabel, istate,
       now() - tslaststart as runtime
FROM xtkworkflow
WHERE istate = 2
  AND tslaststart < now() - interval '1 hour'
ORDER BY runtime DESC;
```

**Workflows in Error:**
```sql
SELECT iworkflowid, slabel, tslaststart, tslastmodified
FROM xtkworkflow
WHERE istate = 13
ORDER BY tslastmodified DESC
LIMIT 20;
```

**Recent Workflow Activity:**
```sql
SELECT iworkflowid, slabel, istate,
       CASE istate
         WHEN 0 THEN 'editing'
         WHEN 2 THEN 'running'
         WHEN 11 THEN 'finished'
         WHEN 13 THEN 'error'
         WHEN 15 THEN 'paused'
         WHEN 20 THEN 'starting'
       END as state_name,
       tslaststart
FROM xtkworkflow
WHERE tslastmodified > now() - interval '24 hours'
ORDER BY tslastmodified DESC
LIMIT 20;
```

**Workflows by Name Pattern:**
```sql
SELECT iworkflowid, slabel, istate, tslaststart
FROM xtkworkflow
WHERE slabel ILIKE '%<pattern>%'
ORDER BY tslaststart DESC;
```

**Count by State:**
```sql
SELECT istate,
       CASE istate
         WHEN 0 THEN 'editing'
         WHEN 2 THEN 'running'
         WHEN 11 THEN 'finished'
         WHEN 13 THEN 'error'
         WHEN 15 THEN 'paused'
         WHEN 20 THEN 'starting'
         ELSE istate::text
       END as state_name,
       count(*)
FROM xtkworkflow
GROUP BY istate
ORDER BY count(*) DESC;
```

### Temp Table Naming

Workflow temp tables follow pattern: `wkf<workflowid>_<activityid>_<version>`

Example: `wkf123456789_5_1`
- Workflow ID: 123456789
- Activity ID: 5
- Version: 1
