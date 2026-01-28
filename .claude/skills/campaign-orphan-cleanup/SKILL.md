---
name: campaign-orphan-cleanup
description: Identify and clean up orphaned wkf* temp tables from Campaign workflows
---

# Campaign Orphaned Table Cleanup

Identify and clean up orphaned workflow temp tables.

## Arguments

```
/campaign-orphan-cleanup <instance> <action>
```

- `instance`: Campaign instance name (required)
- `action`: analyze, generate_drop, execute_drop

## Instructions

### ⚠️ SAFETY RULES

1. **NEVER drop tables for RUNNING workflows**
2. **Generate CSV for review** before drops
3. **Draft Jira comment** before executing
4. **Exclude states**: 2 (Running), 13 (Error), 15 (Paused), 20 (Starting)

### Workflow States

| istate | Status | Safe to Drop? |
|--------|--------|---------------|
| 0 | Being edited | ✅ Yes |
| 2 | Running | ❌ NO! |
| 11 | Finished | ✅ Yes |
| 13 | Error | ❌ NO |
| 15 | Paused | ❌ NO |
| 20 | Starting | ❌ NO! |

### Analyze Query

```sql
WITH wkf_tables AS (
  SELECT tablename,
         substring(tablename from 4 for position('_' in substring(tablename from 4)) - 1) as wkf_id
  FROM pg_tables
  WHERE schemaname = 'public' AND tablename LIKE 'wkf%'
),
running_wkfs AS (
  SELECT DISTINCT iworkflowid::text as wkf_id
  FROM xtkworkflow
  WHERE istate IN (2, 13, 15, 20)
)
SELECT t.tablename, t.wkf_id,
       pg_size_pretty(pg_total_relation_size(t.tablename::regclass)) as size
FROM wkf_tables t
WHERE NOT EXISTS (SELECT 1 FROM running_wkfs r WHERE r.wkf_id = t.wkf_id)
ORDER BY pg_total_relation_size(t.tablename::regclass) DESC;
```

### Generate CSV

```sql
\COPY (
  -- Same query as above
) TO '/tmp/orphaned_tables.csv' WITH CSV HEADER;
```

### Generate DROP Statements

```bash
tail -n +2 /tmp/orphaned_tables.csv | cut -d',' -f1 | xargs -I{} echo "DROP TABLE IF EXISTS {};" > /tmp/drop_orphaned.sql
```

### Execute (AFTER APPROVAL)

```bash
psql -f /tmp/drop_orphaned.sql
```

### Output

Always include:
- Count of orphaned tables
- Total size recoverable
- Workflow states excluded
- CSV attached to Jira
