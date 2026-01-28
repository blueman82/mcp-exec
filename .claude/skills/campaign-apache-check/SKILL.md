---
name: campaign-apache-check
description: Check Apache logs and status for Campaign instance
---

# Campaign Apache Log Analysis

Check Apache logs and status.

## Arguments

```
/campaign-apache-check <instance> [--type=<check_type>]
```

- `instance`: Campaign instance name (required)
- `--type`: errors, access, status_codes, ssl, soap_router (default: errors)

## Instructions

### Log Locations

| Log | Path |
|-----|------|
| Access | /var/log/apache2/access.log |
| SSL Access | /var/log/apache2/ssl_access.log |
| Error | /var/log/apache2/error.log |

### Quick Checks

**Recent Errors:**
```bash
ssh <instance>-1.campaign.adobe.com \
  "sudo tail -100 /var/log/apache2/error.log | grep -iE 'error|warn|fail|AH[0-9]'"
```

**HTTP Status Distribution:**
```bash
ssh <instance>-1.campaign.adobe.com \
  "sudo tail -1000 /var/log/apache2/ssl_access.log | awk '{print \$9}' | sort | uniq -c | sort -rn"
```

**4xx/5xx Errors:**
```bash
ssh <instance>-1.campaign.adobe.com \
  "sudo tail -5000 /var/log/apache2/ssl_access.log | awk '\$9 >= 400 {print \$9, \$7}' | sort | uniq -c | sort -rn | head -20"
```

**TLS Versions:**
```bash
ssh <instance>-1.campaign.adobe.com \
  "sudo tail -1000 /var/log/apache2/ssl_access.log | grep -oE 'TLSv[0-9.]+' | sort | uniq -c | sort -rn"
```

**Invalid URI Errors (AH10244):**
```bash
ssh <instance>-1.campaign.adobe.com \
  "sudo grep 'AH10244' /var/log/apache2/error.log | tail -20"
```

### Common Error Codes

| Code | Meaning |
|------|---------|
| AH10244 | Invalid URI |
| AH00126 | Invalid URI in request |
| AH01630 | Client denied |

### Splunk Queries

```spl
index=campaign_prod sourcetype=access_combined host=<instance>-*
status>=400
| stats count by status, uri
```
