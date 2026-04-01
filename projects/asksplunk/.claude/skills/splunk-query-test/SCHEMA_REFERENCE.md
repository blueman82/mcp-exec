# Schema Reference

## Common Adobe Campaign SPL Patterns

### Delivery/Broadlog Queries
```spl
index=campaign sourcetype=broadlog
| stats count by status
| where status IN ("sent", "failed", "bounced")
```

### Workflow Queries
```spl
index=campaign sourcetype=workflow
| search state="failed" OR state="error"
| stats count by workflow_name, state
```

### Tracking Log Queries
```spl
index=campaign sourcetype=trackinglog
| stats dc(recipient_id) as unique_opens by delivery_id
```

## Field Name Conventions

When reviewing generated SPL, verify field names against the authoritative definitions in `docs/schema/`. Common fields include:

- **broadlog**: delivery_id, recipient_id, status, event_date, failure_reason, failure_type
- **workflow**: workflow_id, workflow_name, state, start_date, end_date, error_message
- **trackinglog**: tracking_id, delivery_id, recipient_id, event_type, event_date, url

## Validation Rules

1. **Index**: Must be `campaign` (or environment-specific variant)
2. **Sourcetype**: Must match one of the defined log types
3. **Time ranges**: Always include `earliest=` and `latest=` for bounded queries
4. **Field references**: Must exist in the schema — no invented field names
5. **Stats commands**: Use `dc()` for distinct counts, `count` for totals
6. **Filters**: Use `where` for post-search filtering, `search` for initial filtering
