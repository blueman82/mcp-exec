---
name: campaign-index-fix
description: Create indexes to fix slow Campaign queries
---

# Campaign Index Fix

Create indexes to fix slow queries.

## Arguments

```
/campaign-index-fix <instance> [--table=<table>] [--column=<column>]
```

- `instance`: Campaign instance name (required)
- `--table`: Table name (optional, will diagnose if not provided)
- `--column`: Column name (optional)

## Instructions

### Step 1: Identify Missing Indexes

**Check Index Usage Ratio:**
```sql
SELECT relname, seq_scan, idx_scan,
       CASE WHEN idx_scan > 0
            THEN round(seq_scan::numeric/idx_scan, 2)
            ELSE seq_scan END as seq_to_idx_ratio
FROM pg_stat_user_tables
WHERE seq_scan > 1000
ORDER BY seq_to_idx_ratio DESC NULLS FIRST
LIMIT 20;
```

High ratio (1000+:1) = missing indexes

**Check Slow Query Plans:**
```sql
EXPLAIN (COSTS OFF) <slow_query>;
```

Look for "Seq Scan" on large tables.

### Step 2: Verify Index Doesn't Exist

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = '<table>'
  AND indexdef LIKE '%<column>%';
```

### Step 3: Create Index (CONCURRENTLY!)

**ALWAYS use CONCURRENTLY** - doesn't block reads/writes:

```sql
CREATE INDEX CONCURRENTLY idx_<table>_<column>
ON <table> (<column>);
```

For composite indexes:
```sql
CREATE INDEX CONCURRENTLY idx_<table>_<col1>_<col2>
ON <table> (<col1>, <col2>);
```

### Step 4: Verify Index Created

```sql
SELECT indexname, pg_size_pretty(pg_relation_size(indexname::regclass)) as size
FROM pg_indexes
WHERE tablename = '<table>';
```

### Step 5: Verify Query Uses Index

```sql
EXPLAIN ANALYZE <slow_query>;
```

Should show "Index Scan" instead of "Seq Scan".

### Important Notes

1. **CREATE INDEX CONCURRENTLY** - Always use, doesn't lock table
2. **New queries only** - Running queries keep old plans, need restart
3. **ANALYZE after** - Update statistics: `ANALYZE <table>;`
4. **Index naming** - Use `idx_<table>_<column>` convention

### Jira Documentation

```
h2. Index Creation

h3. Problem
[Table] showing Seq Scan on [column], causing slow queries.

h3. Solution
{code:sql}
CREATE INDEX CONCURRENTLY idx_<table>_<column> ON <table> (<column>);
{code}

h3. Results
||Metric||Before||After||
|Scan Type|Seq Scan|Index Scan|
|Query Time|[X min]|[Y sec]|
|Index Size|N/A|[size]|
```
