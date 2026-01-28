---
name: campaign-splunk-query
description: Build Splunk SPL queries for Campaign log analysis
---

# Campaign Splunk Query Builder

Build SPL queries for Campaign instance log analysis.

## Arguments

```
/campaign-splunk-query <instance> <query_type> [--timerange=<range>]
```

- `instance`: Campaign instance name (required)
- `query_type`: Type of query - email_delivery, bounces, mta_errors, apache_errors, workflow_errors, slow_queries
- `--timerange`: Time range like -1h, -24h, -7d (default: -24h)

## Instructions

### Host Naming Convention (CRITICAL)

Campaign uses different naming conventions:
- **Application logs** (mta_log, runwf_log): DASHES → `host=<instance>-*`
- **Momentum logs** (eventlog_momentum): UNDERSCORES → `cust.InstanceName="*<instance_underscored>*"`

Convert: `comcastbusiness-mkt-prod1` → `comcastbusiness_mkt_prod1` for Momentum queries.

### Sourcetype Reference

| Sourcetype | Description | Host Filter |
|------------|-------------|-------------|
| eventlog_momentum | Email delivery/bounce | host=momentum_prod* |
| mta_log | Campaign MTA process | host=<instance>-* |
| mtachild_log | MTA child (sends) | host=<instance>-* |
| runwf_log | Workflow execution | host=<instance>-* |
| access_combined | Apache access | host=<instance>-* |
| apache_error | Apache errors | host=<instance>-* |

### Query Templates

**Email Delivery Status:**
```spl
index=campaign_prod sourcetype=eventlog_momentum host=momentum_prod*
cust.InstanceName="*<instance_underscored>*"
| stats count by cust.Status
| sort -count
```

**Bounce Analysis:**
```spl
index=campaign_prod sourcetype=eventlog_momentum host=momentum_prod*
cust.InstanceName="*<instance_underscored>*" cust.Status="bounce*"
| stats count by cust.BounceClass, cust.BounceReason
| sort -count
```

**MTA Errors:**
```spl
index=campaign_prod sourcetype=mta_log host=<instance>-*
("error" OR "warning" OR "WDB-" OR "failed")
| stats count by error_type
| sort -count
```

**Apache HTTP Errors:**
```spl
index=campaign_prod sourcetype=access_combined host=<instance>-*
status>=400
| stats count by status, uri
| sort -count
```

**Workflow Errors:**
```spl
index=campaign_prod sourcetype=runwf_log host=<instance>-*
("error" OR "failed" OR "WKF-")
| stats count by wkf_error
| sort -count
```

### Output Format

Generate the appropriate SPL query with:
1. Correct host pattern based on sourcetype
2. Instance name in correct format (dashes or underscores)
3. Time range applied: `earliest=<timerange>`
4. Helpful field extractions where applicable
