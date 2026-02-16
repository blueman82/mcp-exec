---
name: campaign-db-diagnose
description: Diagnose Adobe Campaign PostgreSQL database performance issues
---

# Campaign Database Performance Diagnosis

Investigate database performance issues for Campaign instance.

## Arguments

```
/campaign-db-diagnose <instance> [issue]
```

- `instance`: Campaign instance name (e.g., comcastbusiness-mkt-prod1) - required
- `issue`: Optional issue description (e.g., "slow queries", "stuck workflows")

## Diagnostic Script (Quick DB Check)

For a quick overview of DB health including active queries, connections, waits, and xtksessioninfo, run the comprehensive diagnostic script:

```bash
ssh -o ConnectTimeout=30 <instance>-1.campaign.adobe.com "bash -s" \
  < ~/.claude/scripts/campaign-diagnose.sh 2>/dev/null
```

The `database` section of the JSON output covers: connectivity, active queries, total connections, wait events, xtksessioninfo count and top logins. For deeper DB analysis (table stats, index usage, lock contention, storage consumers, workflow temp tables), use the manual queries below.

## Manual Instructions

When user invokes this skill:

### Container Awareness

Campaign instances typically have multiple containers (e.g., `<instance>-1`, `<instance>-2`, `<instance>-3`). All containers share the same RDS database, so DB diagnostic queries can be run from any container. However, the `camp-db-params` output and `pg_stat_activity.client_addr` will show which containers have active DB connections — this helps identify which container is generating problematic queries.

### 1. Connect to Database

**For interactive SSH sessions:**
```bash
ssh <instance>-1.campaign.adobe.com
sudo -i camp-db-params -e
# Copy the PGHOST/PGUSER/PGPASSWORD/PGDATABASE exports, then:
psql
```

**For non-interactive SSH (scripted/remote commands):**

The `source env.sh` approach does NOT work over non-interactive SSH. Use inline env vars instead:

```bash
# Step 1: Get the DB params
ssh <instance>-1.campaign.adobe.com "sudo -i camp-db-params -e"
# Output example:
# export PGHOST='instance-mkt-prod1.chqkifxvjhq8.us-west-2.rds.amazonaws.com'
# export PGUSER='instancemktprod1'
# export PGPASSWORD='...'
# export PGDATABASE='instancemktprod1'

# Step 2: Run queries with inline env vars
ssh <instance>-1.campaign.adobe.com \
  "PGHOST='<host>' PGUSER='<user>' PGPASSWORD='<pass>' PGDATABASE='<db>' \
   psql -c \"<query>\""
```

**CRITICAL**: Always verify `$PGHOST` — it may point to a `-restore` instance!

### 2. Run Diagnostic Queries

**Running Queries:**
```sql
SELECT pid, now()-query_start as runtime, state,
       wait_event_type, wait_event,
       left(query, 150) as query
FROM pg_stat_activity
WHERE state = 'active' AND query NOT LIKE '%pg_stat_activity%'
ORDER BY runtime DESC LIMIT 15;
```

**Lock Contention:**
```sql
SELECT blocked.pid AS blocked_pid, blocked.query AS blocked_query,
       blocking.pid AS blocking_pid, blocking.query AS blocking_query
FROM pg_stat_activity blocked
JOIN pg_locks bl ON blocked.pid = bl.pid
JOIN pg_locks bll ON bl.locktype = bll.locktype AND bl.relation = bll.relation AND bl.pid != bll.pid
JOIN pg_stat_activity blocking ON bll.pid = blocking.pid
WHERE NOT bl.granted;
```

**Table Statistics:**
```sql
SELECT relname, n_dead_tup, n_live_tup,
       round(100.0 * n_dead_tup / NULLIF(n_live_tup, 0), 2) as dead_pct,
       last_vacuum, last_autovacuum, last_analyze
FROM pg_stat_user_tables WHERE n_live_tup > 100000
ORDER BY n_dead_tup DESC LIMIT 20;
```

**Index Usage:**
```sql
SELECT relname, seq_scan, idx_scan,
       CASE WHEN idx_scan > 0 THEN round(seq_scan::numeric/idx_scan, 2)
            ELSE seq_scan END as seq_to_idx_ratio
FROM pg_stat_user_tables WHERE seq_scan > 1000
ORDER BY seq_to_idx_ratio DESC NULLS FIRST LIMIT 20;
```

**Wait Events (I/O pressure):**
```sql
SELECT wait_event_type, wait_event, count(*)
FROM pg_stat_activity WHERE wait_event IS NOT NULL
GROUP BY 1,2 ORDER BY 3 DESC LIMIT 10;
```

**Storage Consumers (wkf% and grp% tables):**
```sql
SELECT pg_size_pretty(pg_relation_size(pg_class.oid)) as size,
       pg_class.relname,
       pg_stat_all_tables.last_vacuum,
       pg_stat_all_tables.last_analyze
FROM pg_class
LEFT OUTER JOIN pg_stat_all_tables ON (pg_stat_all_tables.relname = pg_class.relname)
WHERE pg_class.relname ~ '^(wkf|grp)'
ORDER BY pg_relation_size(pg_class.oid) DESC LIMIT 20;
```

**Workflow Temp Tables by Workflow:**
```sql
SELECT
    w.iworkflowid,
    w.slabel,
    CASE w.istatus
        WHEN 0 THEN 'EDITING' WHEN 1 THEN 'RUNNING' WHEN 2 THEN 'STARTED'
        WHEN 3 THEN 'PAUSED' WHEN 5 THEN 'FINISHED' WHEN 13 THEN 'ERROR'
    END AS status,
    COUNT(c.relname) AS temp_tables,
    pg_size_pretty(SUM(pg_total_relation_size(c.oid))) AS total_size
FROM xtkworkflow w
JOIN pg_class c ON c.relname ~ ('^wkf' || w.iworkflowid || '_')
WHERE c.relkind = 'r'
GROUP BY w.iworkflowid, w.slabel, w.istatus
HAVING SUM(pg_total_relation_size(c.oid)) > 500000000
ORDER BY SUM(pg_total_relation_size(c.oid)) DESC;
```

**keepResult Flags (cause temp table retention):**
```sql
-- Workflows retaining intermediate results
SELECT count(*) as workflows_with_keepresult FROM xtkworkflowevent WHERE ikeepresult=1;

-- Workflows with keepResult in mdata
SELECT count(*) as workflows_with_keepresult_mdata FROM xtkworkflow WHERE mdata LIKE '%keepResult="true%';

-- Workflows with showSQL debug flag (should be disabled in prod)
SELECT iworkflowid, slabel FROM xtkworkflow WHERE mdata LIKE '%showSQL="true%';
```

**Disk Space (from PostgreSQL):**
```sql
SELECT
    pg_size_pretty(pg_database_size(current_database())) as db_size,
    pg_size_pretty(sum(pg_total_relation_size(oid))) as total_relations
FROM pg_class WHERE relkind = 'r';
```

### 3. Diagnose Common Issues

| Issue | Indicator | Solution |
|-------|-----------|----------|
| Missing indexes | High seq_to_idx_ratio | CREATE INDEX CONCURRENTLY |
| Stale statistics | last_analyze > 1 week | ANALYZE <table> |
| Table bloat | dead_pct > 20% | VACUUM ANALYZE <table> |
| I/O contention | Many DataFileRead waits | Increase gp3 IOPS/throughput |
| Lock contention | Blocked queries exist | Identify and cancel blocking query |
| Storage exhaustion | Large wkf%/grp% tables | Customer: reset keepResult flags, delete orphaned tables |
| Temp table accumulation | keepResult=1 count > 50 | Customer: disable keepResult on workflows |
| Debug flags in prod | showSQL="true" found | Customer: disable showSQL flags |

### 4. Output Format

Present findings in a clear summary:
- Currently running queries with runtime
- Wait event distribution
- Tables needing ANALYZE
- Index recommendations
- Resource bottleneck indicators
