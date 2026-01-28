---
name: campaign-newrelic-check
description: Check New Relic metrics for Campaign instance
---

# Campaign New Relic Metrics

Check New Relic metrics for incident analysis.

## Arguments

```
/campaign-newrelic-check <instance> [--timerange=<range>]
```

- `instance`: Campaign instance name (required)
- `--timerange`: Time range (e.g., "1 hour ago", "30 minutes ago")

## Instructions

### NRQL Host Pattern

```
host LIKE '<instance>-%'
```

Example: `host LIKE 'comcastbusiness-mkt-prod1-%'`

### Common NRQL Queries

**CPU Usage:**
```sql
SELECT average(cpuPercent)
FROM SystemSample
WHERE host LIKE '<instance>-%'
TIMESERIES AUTO
SINCE <timerange>
```

**Memory Usage:**
```sql
SELECT average(memoryUsedPercent)
FROM SystemSample
WHERE host LIKE '<instance>-%'
TIMESERIES AUTO
SINCE <timerange>
```

**Disk Usage:**
```sql
SELECT average(diskUsedPercent)
FROM SystemSample
WHERE host LIKE '<instance>-%'
TIMESERIES AUTO
SINCE <timerange>
```

**Process Memory (nlserver):**
```sql
SELECT average(memoryResidentSizeBytes)/1024/1024 as 'MB'
FROM ProcessSample
WHERE host LIKE '<instance>-%'
  AND processDisplayName LIKE 'nlserver%'
TIMESERIES AUTO
SINCE <timerange>
```

### New Relic Links

Jarvis tickets often include direct New Relic links. Look for URLs like:
```
https://one.newrelic.com/...
```

### Using newrelic MCP (if available)

```javascript
await newrelic.nrql_query({
  query: "SELECT average(cpuPercent) FROM SystemSample WHERE host LIKE '<instance>-%' SINCE 1 hour ago",
  accountId: "<account>"
});
```

### Key Metrics for Incidents

| Metric | Normal | Warning | Critical |
|--------|--------|---------|----------|
| CPU | <60% | 60-80% | >80% |
| Memory | <70% | 70-85% | >85% |
| Disk | <80% | 80-90% | >90% |

### Correlating with Incidents

1. Check CPU/Memory spike times
2. Compare with OOM/crash timestamps
3. Look for gradual memory growth (leaks)
4. Check disk I/O patterns
